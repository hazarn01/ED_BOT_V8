import hashlib
from typing import Any, Callable, Dict, Optional

from src.cache.redis_client import get_redis_client
from src.config import settings
from src.utils.logging import get_logger
from src.utils.observability import metrics

logger = get_logger(__name__)


class CacheManager:
    """Manage caching with query-type-specific policies."""

    def __init__(self):
        self.redis_client = None

    async def initialize(self):
        """Initialize cache manager."""
        self.redis_client = await get_redis_client()

    def _generate_cache_key(self, query: str, query_type: str) -> str:
        """Generate cache key from query and type."""
        # Normalize query for consistent caching
        normalized = query.lower().strip()
        query_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"query:{query_type}:{query_hash}"

    async def get(self, query: str, query_type: str) -> Optional[Dict[str, Any]]:
        """Get cached response for query."""
        # Never cache form queries
        if query_type == "form":
            logger.debug("Skipping cache for form query")
            return None

        if not self.redis_client:
            await self.initialize()

        cache_key = self._generate_cache_key(query, query_type)
        cached = await self.redis_client.get_json(cache_key)

        if cached:
            metrics.increment_cache_hit()
            logger.info(
                "Cache hit",
                extra_fields={"query_type": query_type, "cache_key": cache_key},
            )
        else:
            metrics.increment_cache_miss()
            logger.debug(
                "Cache miss",
                extra_fields={"query_type": query_type, "cache_key": cache_key},
            )

        return cached

    async def set(self, query: str, query_type: str, response: Dict[str, Any]) -> bool:
        """Cache response for query."""
        # Never cache form queries
        if query_type == "form":
            logger.debug("Skipping cache set for form query")
            return False

        if not self.redis_client:
            await self.initialize()

        cache_key = self._generate_cache_key(query, query_type)
        ttl = settings.get_cache_ttl(query_type)

        # Don't cache if TTL is 0
        if ttl <= 0:
            logger.debug(
                "Cache disabled for query type", extra_fields={"query_type": query_type}
            )
            return False

        success = await self.redis_client.set_json(cache_key, response, ttl)

        if success:
            logger.info(
                "Response cached",
                extra_fields={
                    "query_type": query_type,
                    "cache_key": cache_key,
                    "ttl": ttl,
                },
            )

        return success

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching pattern."""
        if not self.redis_client:
            await self.initialize()

        count = await self.redis_client.flush_pattern(f"query:{pattern}:*")
        logger.info(
            "Cache invalidated", extra_fields={"pattern": pattern, "count": count}
        )
        return count

    async def invalidate_query_type(self, query_type: str) -> int:
        """Invalidate all cache entries for a query type."""
        return await self.invalidate_pattern(query_type)

    async def warm_cache(
        self, queries: list[tuple[str, str]], generator: Callable
    ) -> int:
        """Warm cache with pre-computed responses."""
        if not self.redis_client:
            await self.initialize()

        warmed = 0
        for query, query_type in queries:
            # Skip form queries
            if query_type == "form":
                continue

            # Check if already cached
            existing = await self.get(query, query_type)
            if existing:
                continue

            # Generate and cache response
            try:
                response = await generator(query, query_type)
                if response:
                    success = await self.set(query, query_type, response)
                    if success:
                        warmed += 1
            except Exception as e:
                logger.error(
                    f"Failed to warm cache for query: {e}",
                    extra_fields={"query": query, "query_type": query_type},
                )

        logger.info("Cache warmed", extra_fields={"count": warmed})
        return warmed

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.redis_client:
            await self.initialize()

        # Get Redis info
        info = {}
        try:
            if self.redis_client._client:
                redis_info = await self.redis_client._client.info()
                info = {
                    "used_memory": redis_info.get("used_memory_human", "N/A"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "total_commands": redis_info.get("total_commands_processed", 0),
                }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")

        # Get metrics from observability
        metrics_summary = metrics.get_metrics_summary()

        return {
            "redis": info,
            "cache_metrics": metrics_summary.get("cache", {}),
            "ttl_settings": {
                "contact": settings.cache_ttl_contact,
                "protocol": settings.cache_ttl_protocol,
                "criteria": settings.cache_ttl_criteria,
                "dosage": settings.cache_ttl_dosage,
                "summary": settings.cache_ttl_summary,
                "form": "disabled",
            },
        }
