# PRP 20: Semantic Cache

## Problem Statement
Many queries are semantically similar (e.g., "STEMI protocol" vs "ST-elevation MI protocol"). A semantic cache can reduce latency and LLM costs by serving cached responses for similar queries while ensuring medical accuracy and freshness requirements are met.

## Success Criteria
- Similar queries served from cache with <100ms latency
- Cache hit rate >30% for common query patterns
- Never cache CONTACT or FORM queries (freshness critical)
- PHI scrubbed from cache keys and values
- Stale responses prevented via TTL and invalidation
- Medical safety maintained (no inappropriate caching)

## Implementation Approach

### 1. Semantic Cache Model
```python
# src/cache/semantic_cache.py
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import numpy as np
from redis import Redis
import pickle

@dataclass
class CachedResponse:
    """Cached query response with metadata"""
    query: str
    query_embedding: np.ndarray
    response: Dict
    sources: List[str]
    query_type: str
    confidence: float
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    
class SemanticCache:
    """Semantic similarity-based cache for queries"""
    
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
        self.redis = redis_client
        self.settings = settings
        self.embedding_service = embedding_service
        self.enabled = settings.enable_semantic_cache
        self.namespace = "semantic_cache"
        
    async def get(
        self,
        query: str,
        query_type: QueryType,
        similarity_threshold: Optional[float] = None
    ) -> Optional[CachedResponse]:
        """Retrieve cached response for similar query"""
        
        # Check if caching enabled and allowed for this type
        if not self.enabled or query_type in self.NEVER_CACHE:
            return None
            
        # Scrub PHI from query
        scrubbed_query = self._scrub_phi(query)
        
        # Generate embedding for query
        query_embedding = await self.embedding_service.embed(scrubbed_query)
        
        # Get similarity threshold
        threshold = similarity_threshold or self.SIMILARITY_THRESHOLDS.get(
            query_type, 0.9
        )
        
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
                
        return None
        
    async def set(
        self,
        query: str,
        response: Dict,
        query_type: QueryType,
        sources: List[str],
        confidence: float
    ) -> bool:
        """Cache a query response"""
        
        # Check if caching allowed
        if not self.enabled or query_type in self.NEVER_CACHE:
            return False
            
        # Don't cache low confidence responses
        if confidence < 0.7:
            logger.info(f"Skipping cache for low confidence response: {confidence}")
            return False
            
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
        
        logger.info(f"Cached response for {query_type.value}, TTL: {ttl_seconds}s")
        return True
        
    async def _find_similar(
        self,
        query_embedding: np.ndarray,
        query_type: QueryType,
        threshold: float
    ) -> Optional[CachedResponse]:
        """Find most similar cached query"""
        
        # Get all cached entries for this query type
        pattern = f"{self.namespace}:{query_type.value}:*"
        keys = self.redis.scan_iter(match=pattern)
        
        best_match = None
        best_similarity = 0
        
        for key in keys:
            try:
                # Deserialize cached entry
                data = self.redis.get(key)
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
        """Store entry in Redis"""
        # Generate key
        key_hash = hashlib.md5(
            f"{cached.query_type}:{cached.query}".encode()
        ).hexdigest()
        key = f"{self.namespace}:{cached.query_type}:{key_hash}"
        
        # Serialize and store
        data = pickle.dumps(cached)
        ttl = int((cached.expires_at - datetime.utcnow()).total_seconds())
        
        self.redis.setex(key, ttl, data)
        
    async def _remove(self, cached: CachedResponse):
        """Remove expired entry"""
        key_hash = hashlib.md5(
            f"{cached.query_type}:{cached.query}".encode()
        ).hexdigest()
        key = f"{self.namespace}:{cached.query_type}:{key_hash}"
        
        self.redis.delete(key)
        
    async def _update_hit_count(self, cached: CachedResponse):
        """Update hit count for metrics"""
        # Store updated entry
        await self._store(cached)
        
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0
            
        return dot_product / (norm_a * norm_b)
        
    def _scrub_phi(self, text: str) -> str:
        """Remove potential PHI from text"""
        if not self.settings.log_scrub_phi:
            return text
            
        # Patterns to scrub
        import re
        
        # MRN pattern
        text = re.sub(r'\b\d{6,}\b', '[MRN]', text)
        
        # Date of birth
        text = re.sub(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            '[DATE]',
            text
        )
        
        # SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        
        # Phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        
        return text
        
    def _scrub_phi_from_response(self, response: Dict) -> Dict:
        """Scrub PHI from response object"""
        scrubbed = response.copy()
        
        if "answer" in scrubbed:
            scrubbed["answer"] = self._scrub_phi(scrubbed["answer"])
            
        if "sources" in scrubbed:
            scrubbed["sources"] = [
                self._scrub_phi(s) for s in scrubbed["sources"]
            ]
            
        return scrubbed
        
    async def invalidate_by_type(self, query_type: QueryType):
        """Invalidate all cache entries for a query type"""
        pattern = f"{self.namespace}:{query_type.value}:*"
        keys = list(self.redis.scan_iter(match=pattern))
        
        if keys:
            self.redis.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache entries for {query_type.value}")
            
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        stats = {}
        
        for query_type in QueryType:
            if query_type in self.NEVER_CACHE:
                continue
                
            pattern = f"{self.namespace}:{query_type.value}:*"
            keys = list(self.redis.scan_iter(match=pattern))
            
            total_hits = 0
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if data:
                        cached = pickle.loads(data)
                        total_hits += cached.hit_count
                except:
                    pass
                    
            stats[query_type.value] = {
                "entries": len(keys),
                "total_hits": total_hits
            }
            
        return stats
```

### 2. Integration with Router
```python
# src/pipeline/router.py (modifications)
class QueryRouter:
    def __init__(self, ...):
        # ...
        self.semantic_cache = SemanticCache(
            redis_client,
            settings,
            embedding_service
        )
        
    async def route_query(self, query: str) -> QueryResponse:
        # Classify query
        classification = await self.classifier.classify_query(query)
        
        # Check cache first
        cached = await self.semantic_cache.get(
            query,
            classification.query_type
        )
        
        if cached:
            # Return cached response
            return QueryResponse(
                answer=cached.response["answer"],
                sources=cached.sources,
                confidence=cached.confidence,
                query_type=cached.query_type,
                metadata={"cache_hit": True, "similarity": cached.similarity}
            )
            
        # Generate new response
        response = await self._generate_response(query, classification)
        
        # Cache the response
        await self.semantic_cache.set(
            query=query,
            response=response.dict(),
            query_type=classification.query_type,
            sources=response.sources,
            confidence=response.confidence
        )
        
        return response
```

### 3. Cache Management Endpoints
```python
# src/api/endpoints/cache.py
@router.get("/cache/stats")
async def get_cache_stats(
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
):
    """Get cache statistics"""
    if not settings.enable_semantic_cache:
        return {"enabled": False}
        
    stats = await cache.get_stats()
    return {
        "enabled": True,
        "stats": stats
    }
    
@router.delete("/cache/{query_type}")
async def invalidate_cache(
    query_type: str,
    settings: Settings = Depends(get_settings),
    cache: SemanticCache = Depends(get_semantic_cache)
):
    """Invalidate cache for query type"""
    if not settings.enable_semantic_cache:
        raise HTTPException(400, "Cache not enabled")
        
    try:
        qtype = QueryType(query_type)
        await cache.invalidate_by_type(qtype)
        return {"status": "invalidated", "query_type": query_type}
    except ValueError:
        raise HTTPException(400, f"Invalid query type: {query_type}")
```

### 4. Metrics
```python
# src/cache/metrics.py
from prometheus_client import Counter, Histogram, Gauge

cache_hits = Counter(
    "semantic_cache_hits_total",
    "Total cache hits",
    ["query_type"]
)

cache_misses = Counter(
    "semantic_cache_misses_total",
    "Total cache misses",
    ["query_type"]
)

cache_similarity = Histogram(
    "semantic_cache_similarity",
    "Similarity scores for cache hits",
    ["query_type"],
    buckets=[0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0]
)

cache_entries = Gauge(
    "semantic_cache_entries",
    "Number of cached entries",
    ["query_type"]
)
```

## Testing Strategy
```python
# tests/unit/test_semantic_cache.py
async def test_cache_similarity_matching():
    """Test semantic similarity matching"""
    cache = SemanticCache(redis, settings, embedder)
    
    # Cache a response
    await cache.set(
        query="What is the STEMI protocol?",
        response={"answer": "STEMI protocol details..."},
        query_type=QueryType.PROTOCOL_STEPS,
        sources=["protocol.pdf"],
        confidence=0.95
    )
    
    # Similar query should hit cache
    cached = await cache.get(
        "Show me the ST-elevation MI protocol",
        QueryType.PROTOCOL_STEPS
    )
    assert cached is not None
    assert cached.similarity > 0.9
    
async def test_never_cache_types():
    """Test that certain types are never cached"""
    cache = SemanticCache(redis, settings, embedder)
    
    # Try to cache CONTACT query
    result = await cache.set(
        query="Who is on call?",
        response={"answer": "Dr. Smith"},
        query_type=QueryType.CONTACT_LOOKUP,
        sources=["contacts"],
        confidence=1.0
    )
    assert result is False  # Should not cache
    
async def test_phi_scrubbing():
    """Test PHI removal from cache"""
    cache = SemanticCache(redis, settings, embedder)
    
    query = "Patient MRN 123456789 needs protocol"
    scrubbed = cache._scrub_phi(query)
    assert "123456789" not in scrubbed
    assert "[MRN]" in scrubbed
```

## Performance Impact
- Cache hits: <10ms response time
- Cache misses: No overhead (async check)
- Memory: ~1KB per cached entry
- Redis memory limit enforced via maxmemory-policy

## Rollback Plan
1. Set `ENABLE_SEMANTIC_CACHE=false`
2. All queries bypass cache immediately
3. Existing cache entries expire naturally
4. Can flush Redis if needed: `redis-cli FLUSHDB`