"""Cache management API endpoints.

Provides endpoints for managing and monitoring the semantic cache.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from ...cache.metrics import semantic_cache_metrics
from ...cache.semantic_cache import SemanticCache
from ...config.settings import Settings
from ...models.query_types import QueryType
from ..dependencies import get_semantic_cache, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats(
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
) -> Dict[str, Any]:
    """Get cache statistics.
    
    Returns:
        Dictionary with cache statistics including hit rates and entry counts
    """
    if not settings.enable_semantic_cache:
        return {"enabled": False}
    
    try:
        # Get cache statistics
        cache_stats = await cache.get_stats()
        
        # Get metrics statistics
        metrics_stats = semantic_cache_metrics.get_metrics_summary()
        
        return {
            "enabled": True,
            "cache_entries": cache_stats,
            "metrics": metrics_stats,
            "configuration": {
                "similarity_threshold": settings.semantic_cache_similarity_threshold,
                "min_confidence": settings.semantic_cache_min_confidence,
                "max_entries_per_type": settings.semantic_cache_max_entries_per_type,
                "ttl_by_type": {
                    "protocol": cache.TTL_BY_TYPE.get(QueryType.PROTOCOL_STEPS, 300),
                    "criteria": cache.TTL_BY_TYPE.get(QueryType.CRITERIA_CHECK, 300),
                    "dosage": cache.TTL_BY_TYPE.get(QueryType.DOSAGE_LOOKUP, 300),
                    "summary": cache.TTL_BY_TYPE.get(QueryType.SUMMARY_REQUEST, 300),
                },
                "similarity_thresholds": {
                    "protocol": cache.SIMILARITY_THRESHOLDS.get(QueryType.PROTOCOL_STEPS, 0.9),
                    "criteria": cache.SIMILARITY_THRESHOLDS.get(QueryType.CRITERIA_CHECK, 0.9),
                    "dosage": cache.SIMILARITY_THRESHOLDS.get(QueryType.DOSAGE_LOOKUP, 0.9),
                    "summary": cache.SIMILARITY_THRESHOLDS.get(QueryType.SUMMARY_REQUEST, 0.9),
                }
            }
        }
    except Exception as e:
        logger.error(f"Error retrieving cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.delete("/invalidate/{query_type}")
async def invalidate_cache(
    query_type: str,
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
) -> Dict[str, Any]:
    """Invalidate cache for a specific query type.
    
    Args:
        query_type: Query type to invalidate (protocol, criteria, dosage, summary)
        
    Returns:
        Status of invalidation operation
    """
    if not settings.enable_semantic_cache:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Semantic cache is not enabled"
        )
    
    try:
        # Validate query type
        qtype = QueryType(query_type)
        
        # Check if it's a cacheable type
        if qtype in cache.NEVER_CACHE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query type '{query_type}' is never cached"
            )
        
        # Invalidate cache
        await cache.invalidate_by_type(qtype)
        
        # Record eviction metric
        semantic_cache_metrics.record_cache_eviction(query_type, reason="manual")
        
        logger.info(f"Cache invalidated for query type: {query_type}")
        
        return {
            "status": "success",
            "query_type": query_type,
            "message": f"Cache invalidated for {query_type} queries"
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query type: {query_type}. Valid types: protocol, criteria, dosage, summary"
        )
    except Exception as e:
        logger.error(f"Error invalidating cache for {query_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )


@router.delete("/invalidate")
async def invalidate_all_cache(
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
) -> Dict[str, Any]:
    """Invalidate entire semantic cache.
    
    Returns:
        Status of invalidation operation
    """
    if not settings.enable_semantic_cache:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Semantic cache is not enabled"
        )
    
    try:
        total_invalidated = 0
        
        # Invalidate all cacheable query types
        for qtype in QueryType:
            if qtype not in cache.NEVER_CACHE:
                await cache.invalidate_by_type(qtype)
                semantic_cache_metrics.record_cache_eviction(qtype.value, reason="manual_all")
                total_invalidated += 1
        
        logger.info("Entire semantic cache invalidated")
        
        return {
            "status": "success",
            "message": "Entire semantic cache invalidated",
            "types_invalidated": total_invalidated
        }
        
    except Exception as e:
        logger.error(f"Error invalidating entire cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )


@router.get("/health")
async def cache_health(
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
) -> Dict[str, Any]:
    """Check cache system health.
    
    Returns:
        Health status of cache system
    """
    try:
        # Basic health checks
        health_status = {
            "status": "healthy",
            "enabled": settings.enable_semantic_cache,
            "redis_connected": False,
            "embedding_service_available": False
        }
        
        if settings.enable_semantic_cache:
            # Test Redis connection
            try:
                # Try a simple Redis operation
                await cache.redis.ping()
                health_status["redis_connected"] = True
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["redis_error"] = str(e)
            
            # Test embedding service
            try:
                # Try generating a simple embedding
                test_embedding = await cache.embedding_service.embed("test")
                if test_embedding is not None and len(test_embedding) > 0:
                    health_status["embedding_service_available"] = True
                else:
                    health_status["status"] = "degraded"
                    health_status["embedding_error"] = "Embedding service returned invalid result"
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["embedding_error"] = str(e)
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking cache health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/config")
async def get_cache_config(
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """Get current cache configuration.
    
    Returns:
        Current cache configuration settings
    """
    return {
        "enabled": settings.enable_semantic_cache,
        "similarity_threshold": settings.semantic_cache_similarity_threshold,
        "min_confidence": settings.semantic_cache_min_confidence,
        "max_entries_per_type": settings.semantic_cache_max_entries_per_type,
        "never_cache_types": ["contact", "form"],
        "cacheable_types": ["protocol", "criteria", "dosage", "summary"]
    }