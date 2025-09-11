"""
Health monitoring API endpoints.

Provides health check endpoints for system monitoring, load balancers, and operations.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from ...observability.health import ComponentType, HealthStatus, health_monitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def basic_health_check() -> Dict[str, Any]:
    """Basic health check endpoint for load balancers
    
    Returns a simple status without detailed component checks.
    Fast endpoint suitable for load balancer health checks.
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "EDBotv8",
            "version": "8.0"
        }
    except Exception as e:
        logger.error(f"Basic health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe
    
    Checks if the service is ready to accept traffic.
    Returns 200 if ready, 503 if not ready.
    """
    try:
        # Check critical components only
        db_check = await health_monitor.check_database_health()
        llm_check = await health_monitor.check_llm_backend_health()
        
        if (db_check.status == HealthStatus.HEALTHY and 
            llm_check.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]):
            
            return {
                "status": "ready",
                "timestamp": datetime.now().isoformat(),
                "checks": {
                    "database": db_check.status.value,
                    "llm_backend": llm_check.status.value
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "not_ready",
                    "timestamp": datetime.now().isoformat(),
                    "checks": {
                        "database": db_check.status.value,
                        "llm_backend": llm_check.status.value
                    }
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Readiness check failed"
        )


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe
    
    Checks if the service is alive and should not be restarted.
    Returns 200 if alive, 500 if dead.
    """
    try:
        # Very basic check - just that the service is responding
        return {
            "status": "alive",
            "timestamp": datetime.now().isoformat(),
            "uptime": "unknown"  # Could be enhanced with actual uptime tracking
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Liveness check failed"
        )


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Comprehensive health check with all components
    
    Returns detailed health information for all system components.
    Suitable for monitoring dashboards and detailed diagnostics.
    """
    try:
        system_health = await health_monitor.perform_comprehensive_health_check()
        
        # Return appropriate HTTP status based on overall health
        if system_health.overall_status == HealthStatus.UNHEALTHY:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif system_health.overall_status == HealthStatus.DEGRADED:
            status_code = status.HTTP_200_OK  # Still serving but degraded
        else:
            status_code = status.HTTP_200_OK
        
        response_data = system_health.to_dict()
        
        if status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=status_code, detail=response_data)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Health check system failure",
                "error": str(e)[:200]
            }
        )


@router.get("/component/{component}")
async def component_health_check(component: str) -> Dict[str, Any]:
    """Check health of a specific component
    
    Returns health information for a single system component.
    
    - **component**: Component name (database, redis, elasticsearch, llm, etc.)
    """
    try:
        # Validate component name
        component_type = None
        for comp_type in ComponentType:
            if comp_type.value.lower() == component.lower():
                component_type = comp_type
                break
        
        if not component_type:
            valid_components = [comp.value for comp in ComponentType]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid component '{component}'",
                    "valid_components": valid_components
                }
            )
        
        # Perform component-specific health check
        if component_type == ComponentType.DATABASE:
            health_check = await health_monitor.check_database_health()
        elif component_type == ComponentType.REDIS:
            health_check = await health_monitor.check_redis_health()
        elif component_type == ComponentType.ELASTICSEARCH:
            health_check = await health_monitor.check_elasticsearch_health()
        elif component_type == ComponentType.LLM_BACKEND:
            health_check = await health_monitor.check_llm_backend_health()
        elif component_type == ComponentType.FEATURE_FLAGS:
            health_check = await health_monitor.check_feature_flags_health()
        elif component_type == ComponentType.METRICS:
            health_check = await health_monitor.check_metrics_health()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Health check not implemented for component '{component}'"
            )
        
        response_data = health_check.to_dict()
        
        # Return appropriate status code
        if health_check.status == HealthStatus.UNHEALTHY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response_data
            )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "component": component,
                "status": "error",
                "message": f"Failed to check {component} health",
                "error": str(e)[:200]
            }
        )


@router.get("/history")
async def health_history(
    limit: int = Query(default=10, ge=1, le=100, description="Number of historical checks to return")
) -> Dict[str, Any]:
    """Get recent health check history
    
    Returns recent health check results for trend analysis.
    
    - **limit**: Number of historical checks to return (1-100, default: 10)
    """
    try:
        history = health_monitor.get_health_history(limit=limit)
        
        return {
            "count": len(history),
            "limit": limit,
            "history": [check.to_dict() for check in history]
        }
        
    except Exception as e:
        logger.error(f"Failed to get health history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health history"
        )


@router.get("/trends")
async def health_trends() -> Dict[str, Any]:
    """Get health trends and statistics
    
    Returns health trends, component uptime statistics, and performance indicators
    over recent time periods.
    """
    try:
        trends = health_monitor.get_health_trends()
        return trends
        
    except Exception as e:
        logger.error(f"Failed to get health trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate health trends"
        )


@router.get("/summary")
async def health_summary() -> Dict[str, Any]:
    """Get current health summary
    
    Returns a quick summary of system health suitable for dashboards.
    Includes current status, key metrics, and recent trends.
    """
    try:
        # Get last health check or perform new one
        last_check = health_monitor.get_last_health_check()
        if not last_check:
            last_check = await health_monitor.perform_comprehensive_health_check()
        
        # Get trends
        trends = health_monitor.get_health_trends()
        
        # Build summary
        healthy_components = len([
            check for check in last_check.component_checks 
            if check.status == HealthStatus.HEALTHY
        ])
        
        total_components = len(last_check.component_checks)
        
        return {
            "overall_status": last_check.overall_status.value,
            "health_score": round(last_check.health_score, 3),
            "healthy_components": healthy_components,
            "total_components": total_components,
            "uptime_percentage": round((healthy_components / total_components) * 100, 1) if total_components > 0 else 0,
            "last_check": last_check.timestamp.isoformat(),
            "trends": trends.get("trend", "unknown"),
            "critical_issues": [
                check.message for check in last_check.component_checks
                if check.status == HealthStatus.UNHEALTHY and check.component in [ComponentType.DATABASE, ComponentType.LLM_BACKEND]
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health summary"
        )


@router.post("/check")
async def trigger_health_check() -> Dict[str, Any]:
    """Manually trigger a comprehensive health check
    
    Forces an immediate health check of all system components.
    Useful for on-demand diagnostics or after system changes.
    """
    try:
        logger.info("Manual health check triggered")
        system_health = await health_monitor.perform_comprehensive_health_check()
        
        return {
            "message": "Health check completed",
            "triggered_at": datetime.now().isoformat(),
            **system_health.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Manual health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform health check"
        )


@router.get("/status")
async def health_status() -> Dict[str, Any]:
    """Get simple health status for monitoring systems
    
    Returns a simplified status suitable for external monitoring systems.
    Includes basic health information without sensitive details.
    """
    try:
        last_check = health_monitor.get_last_health_check()
        
        if not last_check:
            # Perform minimal health check
            db_check = await health_monitor.check_database_health()
            
            return {
                "status": db_check.status.value,
                "timestamp": datetime.now().isoformat(),
                "service": "EDBotv8",
                "database": db_check.status.value
            }
        
        # Count healthy components
        healthy_count = len([
            check for check in last_check.component_checks
            if check.status == HealthStatus.HEALTHY
        ])
        
        total_count = len(last_check.component_checks)
        
        return {
            "status": last_check.overall_status.value,
            "health_score": round(last_check.health_score, 2),
            "timestamp": last_check.timestamp.isoformat(),
            "service": "EDBotv8",
            "components_healthy": f"{healthy_count}/{total_count}"
        }
        
    except Exception as e:
        logger.error(f"Health status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health status unavailable"
        )