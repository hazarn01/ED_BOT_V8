import asyncio
import json
from typing import Any, Dict, Optional

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or settings.redis_url
        self._client: Optional[aioredis.Redis] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to Redis."""
        async with self._lock:
            if self._client is None:
                try:
                    self._client = await aioredis.from_url(
                        self.url,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=30,
                    )
                    # Test connection
                    await self._client.ping()
                    logger.info("Connected to Redis", extra_fields={"url": self.url})
                except RedisError as e:
                    logger.error(f"Failed to connect to Redis: {e}")
                    raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        async with self._lock:
            if self._client:
                await self._client.close()
                self._client = None
                logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[str]:
        """Get value from src.cache."""
        if not self._client:
            await self.connect()

        try:
            value = await self._client.get(key)
            if value:
                logger.debug("Cache hit", extra_fields={"key": key})
            else:
                logger.debug("Cache miss", extra_fields={"key": key})
            return value
        except RedisError as e:
            logger.error(f"Redis get error: {e}", extra_fields={"key": key})
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self._client:
            await self.connect()

        try:
            if ttl and ttl > 0:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)

            logger.debug("Cache set", extra_fields={"key": key, "ttl": ttl})
            return True
        except RedisError as e:
            logger.error(f"Redis set error: {e}", extra_fields={"key": key})
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from src.cache."""
        if not self._client:
            await self.connect()

        try:
            result = await self._client.delete(key)
            logger.debug(
                "Cache delete", extra_fields={"key": key, "deleted": bool(result)}
            )
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis delete error: {e}", extra_fields={"key": key})
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            await self.connect()

        try:
            result = await self._client.exists(key)
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis exists error: {e}", extra_fields={"key": key})
            return False

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON value from src.cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON from cache: {e}", extra_fields={"key": key}
                )
                return None
        return None

    async def set_json(
        self, key: str, value: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """Set JSON value in cache."""
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
        except (json.JSONEncodeError, TypeError) as e:
            logger.error(
                f"Failed to encode JSON for cache: {e}", extra_fields={"key": key}
            )
            return False

    async def ping(self) -> bool:
        """Check Redis connection."""
        if not self._client:
            await self.connect()

        try:
            await self._client.ping()
            return True
        except (RedisError, AttributeError):
            return False

    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._client:
            await self.connect()

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(
                    "Flushed cache keys",
                    extra_fields={"pattern": pattern, "count": deleted},
                )
                return deleted
            return 0
        except RedisError as e:
            logger.error(
                f"Redis flush pattern error: {e}", extra_fields={"pattern": pattern}
            )
            return 0


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get or create global Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client
