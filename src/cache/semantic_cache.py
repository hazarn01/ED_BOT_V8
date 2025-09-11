"""Semantic cache implementation for ED Bot v8.

Provides semantic similarity-based caching to reduce latency and LLM costs
while maintaining medical safety and HIPAA compliance.
"""

import hashlib
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from redis import Redis

from src.config.enhanced_settings import EnhancedSettings as Settings
from src.models.query_types import QueryType
from src.validation.hipaa import scrub_phi

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """Cached query response with metadata."""

    query: str
    query_embedding: np.ndarray
    response: Dict[str, Any]
    sources: List[str]
    query_type: str
    confidence: float
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    similarity: float = 0.0  # Set when retrieved


class SemanticCache:
    """Semantic similarity-based cache for queries."""

    # Query types that should NEVER be cached
    NEVER_CACHE = {
        QueryType.CONTACT_LOOKUP,  # Always need current on-call
        QueryType.FORM_RETRIEVAL,  # Forms may update
    }

    # TTL by query type (in seconds)
    TTL_BY_TYPE = {
        QueryType.PROTOCOL_STEPS: 3600,      # 1 hour - protocols stable
        QueryType.CRITERIA_CHECK: 1800,      # 30 min - criteria semi-stable
        QueryType.DOSAGE_LOOKUP: 3600,       # 1 hour - dosages stable
        QueryType.SUMMARY_REQUEST: 300,      # 5 min - summaries may change
    }

    # Similarity thresholds by query type
    SIMILARITY_THRESHOLDS = {
        QueryType.PROTOCOL_STEPS: 0.95,      # Very high similarity required
        QueryType.DOSAGE_LOOKUP: 0.93,       # High similarity for dosages
        QueryType.CRITERIA_CHECK: 0.90,      # Moderate similarity
        QueryType.SUMMARY_REQUEST: 0.85,     # Lower threshold for summaries
    }

    def __init__(
        self,
        redis_client: Redis,
        settings: Settings,
        embedding_service
    ):
        """Initialize semantic cache.

        Args:
            redis_client: Redis client instance
            settings: Application settings
            embedding_service: Service for generating embeddings
        """
        self.redis = redis_client
        self.settings = settings
        self.embedding_service = embedding_service
        self.enabled = getattr(settings, 'enable_semantic_cache', False)
        self.namespace = "semantic_cache"

    async def get(
        self,
        query: str,
        query_type: QueryType,
        similarity_threshold: Optional[float] = None
    ) -> Optional[CachedResponse]:
        """Retrieve cached response for similar query.

        Args:
            query: Query string
            query_type: Type of query
            similarity_threshold: Optional custom similarity threshold

        Returns:
            Cached response if found, None otherwise
        """
        # Check if caching enabled and allowed for this type
        if not self.enabled or query_type in self.NEVER_CACHE:
            return None

        try:
            # Scrub PHI from query
            scrubbed_query = self._scrub_phi(query)

            # Generate embedding for query
            query_embedding = await self.embedding_service.embed(scrubbed_query)

            # Get similarity threshold
            # Prefer global threshold from settings if provided
            threshold = similarity_threshold
            if threshold is None:
                threshold = getattr(
                    self.settings, 'semantic_cache_similarity_threshold', None)
            if threshold is None:
                threshold = self.SIMILARITY_THRESHOLDS.get(query_type, 0.9)

            # Search for similar cached queries
            cached = await self._find_similar(
                query_embedding,
                query_type,
                threshold
            )

            if cached:
                # Check if still valid
                if cached.expires_at > datetime.utcnow():
                    # Update hit count
                    cached.hit_count += 1
                    await self._update_hit_count(cached)

                    # Log cache hit
                    logger.info(
                        f"Cache hit for query type {query_type.value}, "
                        f"similarity: {cached.similarity:.3f}"
                    )

                    return cached
                else:
                    # Expired - remove from cache
                    await self._remove(cached)

        except Exception as e:
            logger.error(f"Error retrieving from semantic cache: {e}")

        return None

    async def set(
        self,
        query: str,
        response: Dict[str, Any],
        query_type: QueryType,
        sources: List[str],
        confidence: float
    ) -> bool:
        """Cache a query response.

        Args:
            query: Original query
            response: Response dictionary
            query_type: Type of query
            sources: List of source references
            confidence: Response confidence score

        Returns:
            True if cached successfully, False otherwise
        """
        # Check if caching allowed
        if not self.enabled or query_type in self.NEVER_CACHE:
            return False

        # Don't cache low confidence responses
        min_conf = getattr(self.settings, 'semantic_cache_min_confidence', 0.7)
        if confidence < float(min_conf):
            logger.info(
                f"Skipping cache for low confidence response: {confidence}")
            return False

        try:
            # Scrub PHI
            scrubbed_query = self._scrub_phi(query)
            scrubbed_response = self._scrub_phi_from_response(response)

            # Generate embedding
            query_embedding = await self.embedding_service.embed(scrubbed_query)

            # Determine TTL
            ttl_seconds = self.TTL_BY_TYPE.get(query_type, 300)
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

            # Create cache entry
            cached = CachedResponse(
                query=scrubbed_query,
                query_embedding=query_embedding,
                response=scrubbed_response,
                sources=sources,
                query_type=query_type.value,
                confidence=confidence,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                hit_count=0
            )

            # Store in Redis
            await self._store(cached)

            logger.info(
                f"Cached response for {query_type.value}, TTL: {ttl_seconds}s")
            return True

        except Exception as e:
            logger.error(f"Error storing to semantic cache: {e}")
            return False

    async def _find_similar(
        self,
        query_embedding: np.ndarray,
        query_type: QueryType,
        threshold: float
    ) -> Optional[CachedResponse]:
        """Find most similar cached query.

        Args:
            query_embedding: Query embedding vector
            query_type: Type of query
            threshold: Similarity threshold

        Returns:
            Most similar cached response if above threshold
        """
        # Get all cached entries for this query type
        pattern = f"{self.namespace}:{query_type.value}:*"

        try:
            # Use Redis SCAN to get keys
            keys = []
            cursor = 0
            while True:
                cursor, batch_keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Error scanning Redis keys: {e}")
            return None

        best_match = None
        best_similarity = 0

        for key in keys:
            try:
                # Deserialize cached entry
                data = await self.redis.get(key)
                if not data:
                    continue

                cached = pickle.loads(data)

                # Calculate cosine similarity
                similarity = self._cosine_similarity(
                    query_embedding,
                    cached.query_embedding
                )

                # Check if above threshold and best so far
                if similarity >= threshold and similarity > best_similarity:
                    best_match = cached
                    best_match.similarity = similarity
                    best_similarity = similarity

            except Exception as e:
                logger.error(f"Error reading cache entry {key}: {e}")
                continue

        return best_match

    async def _store(self, cached: CachedResponse):
        """Store entry in Redis.

        Args:
            cached: Cache entry to store
        """
        # Generate key
        key_hash = hashlib.md5(
            f"{cached.query_type}:{cached.query}".encode()
        ).hexdigest()
        key = f"{self.namespace}:{cached.query_type}:{key_hash}"

        # Serialize and store
        data = pickle.dumps(cached)
        ttl = int((cached.expires_at - datetime.utcnow()).total_seconds())

        if ttl > 0:
            await self.redis.setex(key, ttl, data)

    async def _remove(self, cached: CachedResponse):
        """Remove expired entry.

        Args:
            cached: Cache entry to remove
        """
        key_hash = hashlib.md5(
            f"{cached.query_type}:{cached.query}".encode()
        ).hexdigest()
        key = f"{self.namespace}:{cached.query_type}:{key_hash}"

        await self.redis.delete(key)

    async def _update_hit_count(self, cached: CachedResponse):
        """Update hit count for metrics.

        Args:
            cached: Cache entry with updated hit count
        """
        # Store updated entry
        await self._store(cached)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings.

        Args:
            a: First embedding vector
            b: Second embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0

            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0

    def _scrub_phi(self, text: str) -> str:
        """Remove potential PHI from text.

        Args:
            text: Text to scrub

        Returns:
            Text with PHI removed
        """
        if not self.settings.log_scrub_phi:
            return text

        return scrub_phi(text)

    def _scrub_phi_from_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Scrub PHI from response object.

        Args:
            response: Response dictionary

        Returns:
            Response with PHI scrubbed
        """
        scrubbed = response.copy()

        if "answer" in scrubbed:
            scrubbed["answer"] = self._scrub_phi(scrubbed["answer"])

        if "sources" in scrubbed:
            scrubbed["sources"] = [
                self._scrub_phi(s) for s in scrubbed["sources"]
            ]

        return scrubbed

    async def invalidate_by_type(self, query_type: QueryType):
        """Invalidate all cache entries for a query type.

        Args:
            query_type: Query type to invalidate
        """
        pattern = f"{self.namespace}:{query_type.value}:*"

        try:
            # Get all keys matching pattern
            keys = []
            cursor = 0
            while True:
                cursor, batch_keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break

            if keys:
                await self.redis.delete(*keys)
                logger.info(
                    f"Invalidated {len(keys)} cache entries for {query_type.value}")
        except Exception as e:
            logger.error(
                f"Error invalidating cache for {query_type.value}: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = {}

        for query_type in QueryType:
            if query_type in self.NEVER_CACHE:
                continue

            pattern = f"{self.namespace}:{query_type.value}:*"

            try:
                # Count keys
                keys = []
                cursor = 0
                while True:
                    cursor, batch_keys = await self.redis.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100
                    )
                    keys.extend(batch_keys)
                    if cursor == 0:
                        break

                total_hits = 0
                for key in keys:
                    try:
                        data = await self.redis.get(key)
                        if data:
                            cached = pickle.loads(data)
                            total_hits += cached.hit_count
                    except (pickle.PickleError, AttributeError, KeyError) as e:
                        # Skip corrupted or incompatible cache entries
                        logger.debug(f"Failed to load cache entry {key}: {e}")
                        continue

                stats[query_type.value] = {
                    "entries": len(keys),
                    "total_hits": total_hits
                }
            except Exception as e:
                logger.error(
                    f"Error getting stats for {query_type.value}: {e}")
                stats[query_type.value] = {"entries": 0, "total_hits": 0}

        return stats
