"""
Runtime feature flag management for EDBotv8.

Provides runtime configuration updates with Redis overrides, in-memory caching,
and production safety constraints. This implementation matches the unit test
interface and behaviors (keys, TTLs, and error handling).
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .enhanced_settings import EnhancedSettings

logger = logging.getLogger(__name__)


# Allow tests to patch this factory
def get_redis_client():  # pragma: no cover (patched in tests)
    import redis.asyncio as redis
    return redis.Redis()


class FeatureManager:
    """Runtime feature flag management with Redis overrides and local cache"""

    def __init__(self, settings: EnhancedSettings):
        self.settings = settings
        self.redis_client = None
        self.cache_ttl = 300  # seconds; can be tuned in tests
        # Simple in-memory cache: {flag_name: (value, expires_at)}
        self._flag_cache: Dict[str, Any] = {}

    async def __aenter__(self):
        await self._ensure_redis_connection()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # No persistent connection to close in mocked context
        return False

    async def _ensure_redis_connection(self) -> None:
        try:
            if self.redis_client is None:
                self.redis_client = get_redis_client()
            # Ping to verify
            await self.redis_client.ping()
        except Exception:
            # Gracefully degrade if Redis unavailable
            self.redis_client = None

    def _cache_get(self, name: str) -> Optional[bool]:
        item = self._flag_cache.get(name)
        if not item:
            return None
        value, expires_at = item
        if time.time() <= expires_at:
            return value
        # Expired
        self._flag_cache.pop(name, None)
        return None

    def _cache_set(self, name: str, value: bool) -> None:
        self._flag_cache[name] = (value, time.time() + self.cache_ttl)

    def _redis_key(self, flag_name: str) -> str:
        return f"flag:{flag_name}"

    def _is_valid_flag_name(self, flag_name: str) -> bool:
        if not flag_name or not hasattr(self.settings, "features"):
            return False
        return hasattr(self.settings.features, flag_name)

    def _is_flag_update_allowed(self, flag_name: str, value: bool) -> bool:
        if getattr(self.settings, "is_production", False):
            if flag_name in ("enable_phi_scrubbing", "enable_response_validation") and not value:
                return False
        return True

    def _check_flag_dependencies(self) -> List[str]:
        warnings: List[str] = []
        features = getattr(self.settings, "features", object())

        # Hybrid backend consistency
        if getattr(features, "search_backend", "") == "hybrid" and not getattr(features, "enable_hybrid_search", False):
            warnings.append("Hybrid backend selected but enable_hybrid_search is False")

        # Hybrid requires Elasticsearch for best results
        if getattr(features, "enable_hybrid_search", False) and not getattr(features, "enable_elasticsearch", False):
            warnings.append("Hybrid search enabled but Elasticsearch disabled")

        return warnings

    async def get_flag(self, flag_name: str) -> bool:
        # In-memory cache
        cached = self._cache_get(flag_name)
        if cached is not None:
            return cached

        # Attempt Redis override
        value: Optional[bool] = None
        try:
            await self._ensure_redis_connection()
            if self.redis_client is not None:
                raw = await self.redis_client.get(self._redis_key(flag_name))
                if raw is not None:
                    s = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
                    if isinstance(s, str):
                        s_lower = s.strip().lower()
                        if s_lower in ("true", "false"):
                            value = (s_lower == "true")
                        else:
                            # JSON bool or other format
                            try:
                                value = bool(json.loads(s))
                            except Exception:
                                value = None
        except Exception:
            # Fall back to settings on Redis errors
            value = None

        if value is None:
            # Default to settings.features
            value = bool(getattr(getattr(self.settings, "features", object()), flag_name, False))

        # Cache locally
        self._cache_set(flag_name, value)
        return value

    async def set_flag(self, flag_name: str, value: bool, ttl_minutes: int = 60) -> bool:
        if not self._is_valid_flag_name(flag_name):
            return False
        if not self._is_flag_update_allowed(flag_name, value):
            return False

        try:
            await self._ensure_redis_connection()
            if self.redis_client is None:
                return False
            # Set override with TTL (seconds)
            await self.redis_client.set(self._redis_key(flag_name), str(value).lower(), ex=ttl_minutes * 60)

            # Clear local cache entry
            self._flag_cache.pop(flag_name, None)

            # Metrics (best-effort)
            try:
                from ..observability.metrics import feature_flag_changes
                feature_flag_changes.labels(flag_name=flag_name, new_value=str(value).lower()).inc()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to set flag {flag_name}: {e}")
            return False

    async def clear_overrides(self) -> int:
        try:
            await self._ensure_redis_connection()
            if self.redis_client is None:
                return 0
            keys = await self.redis_client.keys("flag:*")
            # Filter only our flag keys
            flag_keys = [k for k in keys if (k.decode() if isinstance(k, (bytes, bytearray)) else k).startswith("flag:")]
            if not flag_keys:
                return 0
            # Delete
            await self.redis_client.delete(*flag_keys)
            # Clear local cache
            self._flag_cache.clear()
            return len(flag_keys)
        except Exception as e:
            logger.error(f"Failed to clear flag overrides: {e}")
            return 0

    async def get_all_flags(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        # Candidate flag names from settings + overrides present in Redis
        names: set = set()
        # From settings (attributes starting with enable_)
        features = getattr(self.settings, "features", object())
        for name in dir(features):
            if name.startswith("enable_"):
                names.add(name)
        # From Redis keys
        try:
            await self._ensure_redis_connection()
            if self.redis_client is not None:
                keys = await self.redis_client.keys("flag:*")
                for k in keys:
                    n = (k.decode() if isinstance(k, (bytes, bytearray)) else k)[5:]
                    if n:
                        names.add(n)
        except Exception:
            pass

        for name in sorted(names):
            current_value = await self.get_flag(name)
            default_value = bool(getattr(features, name, False))
            has_override = False
            ttl_seconds: Optional[int] = None
            try:
                if self.redis_client is not None:
                    ttl_seconds = await self.redis_client.ttl(self._redis_key(name))
                    has_override = ttl_seconds is not None and ttl_seconds > 0
            except Exception:
                pass

            entry = {
                "current_value": current_value,
                "default_value": default_value,
                "has_override": has_override,
            }
            if has_override:
                entry["ttl_seconds"] = ttl_seconds
            result[name] = entry

        return result

    async def validate_flag_dependencies(self) -> List[str]:
        warnings: List[str] = []
        try:
            if await self.get_flag("enable_hybrid_search") and not await self.get_flag("enable_elasticsearch"):
                warnings.append("Hybrid search enabled but Elasticsearch disabled")
            if await self.get_flag("enable_source_highlighting") and not await self.get_flag("enable_pdf_viewer"):
                warnings.append("Source highlighting enabled without PDF viewer - highlights won't be visible")
            if await self.get_flag("enable_table_extraction") and not await self.get_flag("enable_hybrid_search"):
                warnings.append("Table extraction more effective with hybrid search enabled")
        except Exception as e:
            logger.error(f"Flag dependency validation failed: {e}")
            warnings.append(f"Validation error: {e}")
        return warnings

    async def get_feature_usage_stats(self) -> Dict[str, Any]:
        all_flags = await self.get_all_flags()
        enabled_count = sum(1 for f in all_flags.values() if f.get("current_value"))
        overrides_count = sum(1 for f in all_flags.values() if f.get("has_override"))
        total_count = len(all_flags)
        return {
            "total_flags": total_count,
            "enabled_flags": enabled_count,
            "overrides_count": overrides_count,
            "feature_adoption_rate": (enabled_count / total_count) if total_count else 0,
        }
