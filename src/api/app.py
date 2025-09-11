import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from ..config.enhanced_settings import get_settings
from ..models.async_database import init_async_database
from ..observability.health import init_health_monitoring
from ..observability.metrics import init_metrics
from ..validation.hipaa import setup_hipaa_logging
from .endpoints import router
from .endpoints.admin import router as admin_router
from .endpoints.cache import router as cache_router
from .endpoints.health import router as health_router
from .endpoints.simple_query import router as simple_router
from .endpoints.viewer import router as viewer_router
from .security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize HIPAA compliance logging
    setup_hipaa_logging()
    
    # Get settings for initialization
    settings = get_settings()
    
    # Initialize async database
    init_async_database()
    logger.info("Async database connections initialized")
    
    # Initialize observability systems
    init_metrics(settings)
    init_health_monitoring(settings)
    
    logger.info("Starting ED Bot v8 API with observability enabled")
    yield
    logger.info("Shutting down ED Bot v8 API")


app = FastAPI(
    title="ED Bot v8 API",
    description="HIPAA-compliant Emergency Department Medical AI Assistant",
    version="8.0.0",
    lifespan=lifespan,
)


class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Allow unsafe-eval for Swagger UI to work
        if request.url.path in ["/docs", "/redoc"] or request.url.path.startswith("/docs"):
            response.headers["Content-Security-Policy"] = "script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; object-src 'none';"
        return response


# Add security headers and CSP middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSPMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(simple_router)  # Simple query endpoint - no prefix as it's already in router
app.include_router(viewer_router, prefix="/api/v1")  # PDF viewer endpoints (PRP 18)
app.include_router(cache_router, prefix="/api/v1")  # Semantic cache endpoints (PRP 20)
app.include_router(admin_router, prefix="/api/v1")  # Admin endpoints (PRP 22)
app.include_router(health_router, prefix="/api/v1")  # Health endpoints (PRP 24)

# Mount static files
static_path = Path(__file__).parent.parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def serve_index():
    """Serve the frontend application."""
    static_index = static_path / "index.html"
    if static_index.exists():
        return FileResponse(str(static_index))
    return {"message": "ED Bot v8 API - Frontend not available", "docs": "/docs"}


@app.get("/health")
async def basic_health_check():
    """Basic health endpoint for backwards compatibility"""
    from ..observability.health import health_monitor
    
    try:
        # Quick database check for basic health
        db_check = await health_monitor.check_database_health()
        
        if db_check.status.value in ["healthy", "degraded"]:
            return {"status": "healthy", "service": "ed-bot-v8"}
        else:
            return {"status": "unhealthy", "service": "ed-bot-v8"}
    except Exception:
        return {"status": "unknown", "service": "ed-bot-v8"}


@app.get("/health-simple")
async def health_simple():
    """Very fast health endpoint for simple checks"""
    return {"status": "ok"}


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    from fastapi import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    
    try:
        metrics_data = generate_latest()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return Response(
            content=f"# Error generating metrics: {e}",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
