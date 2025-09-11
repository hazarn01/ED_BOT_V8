"""API endpoints module."""

from fastapi import APIRouter

from .admin import router as admin_router
from .cache import router as cache_router
from .health import router as health_router
from .query import router as query_router
from .viewer import router as viewer_router

# Main API router that includes all endpoint routers
router = APIRouter()
router.include_router(query_router, tags=["queries"])  # Main query endpoints  
router.include_router(health_router, tags=["health"])
router.include_router(viewer_router, prefix="/viewer", tags=["viewer"])
router.include_router(cache_router, prefix="/cache", tags=["cache"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])

__all__ = ["router", "query_router", "viewer_router", "health_router", "cache_router", "admin_router"]