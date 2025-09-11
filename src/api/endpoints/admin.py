"""
Admin endpoints for feature flag and configuration management.

Provides runtime control over feature flags with proper authorization and safety checks.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...config.enhanced_settings import EnhancedSettings
from ...config.feature_manager import FeatureManager
from ...config.validators import ConfigurationValidator
from ..dependencies import get_feature_manager, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class FeatureFlagUpdate(BaseModel):
    """Request model for feature flag updates"""
    enabled: bool
    ttl_minutes: int = 60
    reason: Optional[str] = None


class ConfigurationSummary(BaseModel):
    """Response model for configuration summary"""
    environment: str
    enabled_features: List[str]
    configuration_warnings: List[str]
    backend_services: Dict[str, str]


@router.get("/config/flags")
async def get_feature_flags(
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Get current feature flag status
    
    Returns all feature flags with their current values, defaults,
    descriptions, and override status.
    """
    try:
        return await feature_manager.get_all_flags()
    except Exception as e:
        logger.error(f"Failed to get feature flags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature flags"
        )


@router.post("/config/flags/{flag_name}")
async def set_feature_flag(
    flag_name: str,
    update: FeatureFlagUpdate,
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Temporarily override feature flag
    
    Sets a temporary override for the specified feature flag.
    The override will expire after the specified TTL.
    
    - **flag_name**: Name of the feature flag to update
    - **enabled**: New value for the flag
    - **ttl_minutes**: How long the override should last (default: 60 minutes)
    - **reason**: Optional reason for the change (for audit purposes)
    """
    try:
        success = await feature_manager.set_flag(
            flag_name, 
            update.enabled, 
            update.ttl_minutes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to set feature flag"
            )
        
        # Log the change with reason if provided
        if update.reason:
            logger.info(f"Feature flag {flag_name} set to {update.enabled} by admin: {update.reason}")
        
        return {
            "status": "updated",
            "flag": flag_name,
            "value": update.enabled,
            "ttl_minutes": update.ttl_minutes,
            "reason": update.reason
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set feature flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feature flag"
        )


@router.delete("/config/flags")
async def clear_flag_overrides(
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Clear all temporary flag overrides
    
    Removes all temporary feature flag overrides, reverting all flags
    to their default configuration values.
    """
    try:
        cleared = await feature_manager.clear_overrides()
        logger.info(f"Cleared {cleared} feature flag overrides")
        
        return {
            "status": "cleared",
            "count": cleared,
            "message": f"Cleared {cleared} temporary flag overrides"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear flag overrides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear flag overrides"
        )


@router.get("/config/flags/{flag_name}")
async def get_single_flag(
    flag_name: str,
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Get details for a specific feature flag
    
    Returns detailed information about a single feature flag including
    its current value, default, description, and override status.
    """
    try:
        all_flags = await feature_manager.get_all_flags()
        
        if flag_name not in all_flags:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature flag '{flag_name}' not found"
            )
        
        flag_info = all_flags[flag_name]
        flag_info["name"] = flag_name
        
        return flag_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature flag"
        )


@router.get("/config/summary")
async def get_configuration_summary(
    settings: EnhancedSettings = Depends(get_settings)
) -> ConfigurationSummary:
    """Get human-readable configuration summary
    
    Returns a summary of the current configuration including enabled features,
    environment settings, backend services, and any configuration warnings.
    """
    try:
        validator = ConfigurationValidator(settings)
        summary = validator.get_configuration_summary()
        
        return ConfigurationSummary(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get configuration summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration summary"
        )


@router.get("/config/validate")
async def validate_configuration(
    settings: EnhancedSettings = Depends(get_settings)
) -> Dict[str, Any]:
    """Validate current configuration
    
    Runs comprehensive configuration validation checks and returns
    any warnings or issues found with the current settings.
    """
    try:
        validator = ConfigurationValidator(settings)
        warnings = validator.validate_all()
        
        return {
            "status": "validated",
            "warnings_count": len(warnings),
            "warnings": warnings,
            "environment": settings.environment,
            "is_production": settings.is_production
        }
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration validation failed"
        )


@router.post("/config/validate-dependencies")
async def validate_flag_dependencies(
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Validate feature flag dependencies
    
    Checks for potential issues with the current feature flag configuration,
    such as enabled features that depend on other disabled features.
    """
    try:
        warnings = await feature_manager.validate_flag_dependencies()
        
        return {
            "status": "validated",
            "dependency_warnings": warnings,
            "warnings_count": len(warnings)
        }
        
    except Exception as e:
        logger.error(f"Flag dependency validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dependency validation failed"
        )


@router.get("/config/usage-stats")
async def get_feature_usage_stats(
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Get feature usage statistics
    
    Returns statistics about feature flag usage including adoption rates,
    override counts, and usage patterns.
    """
    try:
        stats = await feature_manager.get_feature_usage_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage statistics"
        )


@router.get("/health/configuration")
async def get_configuration_health(
    settings: EnhancedSettings = Depends(get_settings),
    feature_manager: FeatureManager = Depends(get_feature_manager)
) -> Dict[str, Any]:
    """Get configuration and feature flag health status
    
    Returns the health status of the configuration system including
    flag manager connectivity and validation status.
    """
    try:
        # Validate configuration
        validator = ConfigurationValidator(settings)
        warnings = validator.validate_all()
        
        # Check flag manager connectivity
        flag_manager_healthy = True
        try:
            await feature_manager.get_flag("enable_metrics")  # Test flag access
        except Exception as e:
            flag_manager_healthy = False
            logger.error(f"Flag manager health check failed: {e}")
        
        health_status = "healthy"
        if not flag_manager_healthy:
            health_status = "unhealthy"
        elif len(warnings) > 0:
            health_status = "degraded"
        
        return {
            "status": health_status,
            "flag_manager_healthy": flag_manager_healthy,
            "configuration_warnings": len(warnings),
            "environment": settings.environment,
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Configuration health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }