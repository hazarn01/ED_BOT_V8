"""
Unit tests for semantic cache functionality.

Tests the semantic similarity-based caching system for ED Bot v8.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.cache.embedding_service import EmbeddingService
from src.cache.semantic_cache import CachedResponse, SemanticCache
from src.models.query_types import QueryType


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    def test_embedding_service_initialization(self):
        """Test embedding service can be initialized."""
        service = EmbeddingService()
        assert service.embedding_model is None
        
        mock_model = Mock()
        service_with_model = EmbeddingService(mock_model)
        assert service_with_model.embedding_model == mock_model
    
    @pytest.mark.asyncio
    async def test_embedding_with_sentence_transformer(self):
        """Test embedding generation with sentence transformer style model."""
        mock_model = Mock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        
        service = EmbeddingService(mock_model)
        embedding = await service.embed("test text")
        
        mock_model.encode.assert_called_once_with("test text")
        assert np.array_equal(embedding, np.array([0.1, 0.2, 0.3]))
    
    @pytest.mark.asyncio
    async def test_embedding_with_openai_style(self):
        """Test embedding generation with OpenAI style client."""
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        
        mock_model = Mock()
        # Remove encode method so it will use OpenAI style
        if hasattr(mock_model, 'encode'):
            delattr(mock_model, 'encode')
        mock_model.embeddings.create.return_value = mock_response
        
        service = EmbeddingService(mock_model)
        embedding = await service.embed("test text")
        
        mock_model.embeddings.create.assert_called_once_with(
            input="test text",
            model="text-embedding-ada-002"
        )
        assert np.array_equal(embedding, np.array([0.1, 0.2, 0.3]))
    
    @pytest.mark.asyncio
    async def test_embedding_fallback(self):
        """Test fallback to hash-based embedding when no model available."""
        service = EmbeddingService()
        embedding = await service.embed("test text")
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 768  # Default dimension
        assert np.linalg.norm(embedding) == pytest.approx(1.0, rel=1e-5)  # Normalized
    
    @pytest.mark.asyncio
    async def test_embedding_error_handling(self):
        """Test error handling in embedding generation."""
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Model error")
        
        service = EmbeddingService(mock_model)
        embedding = await service.embed("test text")
        
        # Should fallback to hash-based embedding
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 768


class TestSemanticCache:
    """Test semantic cache functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis.scan.return_value = (0, [])
        redis.get.return_value = None
        redis.setex.return_value = True
        redis.delete.return_value = True
        redis.ping.return_value = True
        return redis
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service."""
        service = Mock()
        service.embed = AsyncMock(return_value=np.array([0.1, 0.2, 0.3]))
        return service
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        settings = Mock()
        settings.enable_semantic_cache = True
        settings.log_scrub_phi = True
        settings.semantic_cache_similarity_threshold = 0.9
        settings.semantic_cache_min_confidence = 0.7
        return settings
    
    @pytest.fixture
    def semantic_cache(self, mock_redis, mock_embedding_service, mock_settings):
        """Create semantic cache instance."""
        return SemanticCache(mock_redis, mock_settings, mock_embedding_service)
    
    def test_cache_initialization(self, semantic_cache, mock_settings):
        """Test cache initialization."""
        assert semantic_cache.enabled == mock_settings.enable_semantic_cache
        assert semantic_cache.namespace == "semantic_cache"
        assert QueryType.CONTACT_LOOKUP in semantic_cache.NEVER_CACHE
        assert QueryType.FORM_RETRIEVAL in semantic_cache.NEVER_CACHE
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self, mock_redis, mock_embedding_service):
        """Test cache behavior when disabled."""
        settings = Mock()
        settings.enable_semantic_cache = False
        
        cache = SemanticCache(mock_redis, settings, mock_embedding_service)
        
        # Should return None for get
        result = await cache.get("test query", QueryType.PROTOCOL_STEPS)
        assert result is None
        
        # Should return False for set
        success = await cache.set(
            "test query", 
            {"answer": "test"}, 
            QueryType.PROTOCOL_STEPS, 
            ["source1"], 
            0.9
        )
        assert success is False
    
    @pytest.mark.asyncio
    async def test_never_cache_types(self, semantic_cache):
        """Test that certain query types are never cached."""
        # CONTACT_LOOKUP should never be cached
        result = await semantic_cache.get("who is on call", QueryType.CONTACT_LOOKUP)
        assert result is None
        
        success = await semantic_cache.set(
            "who is on call",
            {"answer": "Dr. Smith"},
            QueryType.CONTACT_LOOKUP,
            ["contacts"],
            1.0
        )
        assert success is False
        
        # FORM_RETRIEVAL should never be cached
        result = await semantic_cache.get("show form", QueryType.FORM_RETRIEVAL)
        assert result is None
        
        success = await semantic_cache.set(
            "show form",
            {"answer": "form content"},
            QueryType.FORM_RETRIEVAL,
            ["form.pdf"],
            1.0
        )
        assert success is False
    
    @pytest.mark.asyncio
    async def test_low_confidence_not_cached(self, semantic_cache):
        """Test that low confidence responses are not cached."""
        success = await semantic_cache.set(
            "test query",
            {"answer": "low confidence answer"},
            QueryType.PROTOCOL_STEPS,
            ["source1"],
            0.5  # Below threshold
        )
        assert success is False
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, semantic_cache, mock_redis, mock_embedding_service):
        """Test basic cache set and get functionality."""
        # Test setting cache
        success = await semantic_cache.set(
            "What is the STEMI protocol?",
            {"answer": "STEMI protocol details...", "confidence": 0.95},
            QueryType.PROTOCOL_STEPS,
            ["stemi_protocol.pdf"],
            0.95
        )
        assert success is True
        
        # Verify Redis was called to store
        mock_redis.setex.assert_called()
        
        # Mock Redis to return a cached entry
        mock_cached_data = CachedResponse(
            query="What is the STEMI protocol?",
            query_embedding=np.array([0.1, 0.2, 0.3]),
            response={"answer": "STEMI protocol details...", "confidence": 0.95},
            sources=["stemi_protocol.pdf"],
            query_type=QueryType.PROTOCOL_STEPS.value,
            confidence=0.95,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            hit_count=0
        )
        
        import pickle
        mock_redis.get.return_value = pickle.dumps(mock_cached_data)
        mock_redis.scan.return_value = (0, ["semantic_cache:protocol:test_key"])
        
        # Test getting from cache
        cached = await semantic_cache.get(
            "Show me the ST-elevation MI protocol",  # Similar query
            QueryType.PROTOCOL_STEPS
        )
        
        assert cached is not None
        assert cached.response["answer"] == "STEMI protocol details..."
        assert cached.similarity > 0.9  # Should have high similarity
    
    @pytest.mark.asyncio
    async def test_similarity_matching(self, semantic_cache):
        """Test semantic similarity matching."""
        # Mock high similarity
        semantic_cache._cosine_similarity = Mock(return_value=0.95)
        
        mock_cached_data = CachedResponse(
            query="STEMI protocol",
            query_embedding=np.array([0.1, 0.2, 0.3]),
            response={"answer": "Protocol details"},
            sources=["protocol.pdf"],
            query_type=QueryType.PROTOCOL_STEPS.value,
            confidence=0.95,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            hit_count=0
        )
        
        import pickle
        semantic_cache.redis.get.return_value = pickle.dumps(mock_cached_data)
        semantic_cache.redis.scan.return_value = (0, ["semantic_cache:protocol:test_key"])
        
        cached = await semantic_cache.get("ST elevation MI protocol", QueryType.PROTOCOL_STEPS)
        assert cached is not None
        assert cached.similarity == 0.95
    
    @pytest.mark.asyncio
    async def test_similarity_threshold(self, semantic_cache):
        """Test similarity threshold filtering."""
        # Mock low similarity
        semantic_cache._cosine_similarity = Mock(return_value=0.7)
        
        mock_cached_data = CachedResponse(
            query="different protocol",
            query_embedding=np.array([0.1, 0.2, 0.3]),
            response={"answer": "Different protocol"},
            sources=["other.pdf"],
            query_type=QueryType.PROTOCOL_STEPS.value,
            confidence=0.95,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            hit_count=0
        )
        
        import pickle
        semantic_cache.redis.get.return_value = pickle.dumps(mock_cached_data)
        semantic_cache.redis.scan.return_value = (0, ["semantic_cache:protocol:test_key"])
        
        # Should not return cache hit due to low similarity
        cached = await semantic_cache.get("STEMI protocol", QueryType.PROTOCOL_STEPS)
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, semantic_cache):
        """Test cache expiration handling."""
        # Mock expired cache entry
        mock_cached_data = CachedResponse(
            query="expired query",
            query_embedding=np.array([0.1, 0.2, 0.3]),
            response={"answer": "Expired answer"},
            sources=["source.pdf"],
            query_type=QueryType.PROTOCOL_STEPS.value,
            confidence=0.95,
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            hit_count=0
        )
        
        import pickle
        semantic_cache.redis.get.return_value = pickle.dumps(mock_cached_data)
        semantic_cache.redis.scan.return_value = (0, ["semantic_cache:protocol:test_key"])
        
        cached = await semantic_cache.get("expired query", QueryType.PROTOCOL_STEPS)
        assert cached is None
        
        # Should have called delete to remove expired entry
        semantic_cache.redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_phi_scrubbing(self, semantic_cache):
        """Test PHI scrubbing functionality."""
        # Test PHI scrubbing in query
        scrubbed = semantic_cache._scrub_phi("Patient MRN 123456789 needs protocol")
        assert "123456789" not in scrubbed
        assert "[MRN]" in scrubbed
        
        # Test PHI scrubbing in response
        response = {
            "answer": "Patient DOB 01/01/1990 should follow protocol",
            "sources": ["Contact 555-123-4567 for details"]
        }
        scrubbed_response = semantic_cache._scrub_phi_from_response(response)
        assert "01/01/1990" not in scrubbed_response["answer"]
        assert "555-123-4567" not in scrubbed_response["sources"][0]
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_by_type(self, semantic_cache):
        """Test cache invalidation by query type."""
        semantic_cache.redis.scan.return_value = (0, [
            "semantic_cache:protocol:key1",
            "semantic_cache:protocol:key2"
        ])
        
        await semantic_cache.invalidate_by_type(QueryType.PROTOCOL_STEPS)
        
        # Should have scanned for the pattern
        semantic_cache.redis.scan.assert_called()
        
        # Should have deleted the keys
        semantic_cache.redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, semantic_cache):
        """Test cache statistics generation."""
        # Mock cache entries
        mock_cached_data = CachedResponse(
            query="test query",
            query_embedding=np.array([0.1, 0.2, 0.3]),
            response={"answer": "Test answer"},
            sources=["source.pdf"],
            query_type=QueryType.PROTOCOL_STEPS.value,
            confidence=0.95,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            hit_count=5
        )
        
        import pickle
        semantic_cache.redis.get.return_value = pickle.dumps(mock_cached_data)
        semantic_cache.redis.scan.return_value = (0, ["semantic_cache:protocol:key1"])
        
        stats = await semantic_cache.get_stats()
        
        assert "protocol" in stats
        assert stats["protocol"]["entries"] == 1
        assert stats["protocol"]["total_hits"] == 5
    
    def test_cosine_similarity(self, semantic_cache):
        """Test cosine similarity calculation."""
        a = np.array([1, 0, 0])
        b = np.array([1, 0, 0])
        similarity = semantic_cache._cosine_similarity(a, b)
        assert similarity == pytest.approx(1.0)
        
        a = np.array([1, 0, 0])
        b = np.array([0, 1, 0])
        similarity = semantic_cache._cosine_similarity(a, b)
        assert similarity == pytest.approx(0.0)
        
        # Test zero vectors
        a = np.array([0, 0, 0])
        b = np.array([1, 0, 0])
        similarity = semantic_cache._cosine_similarity(a, b)
        assert similarity == 0.0


class TestSemanticCacheIntegration:
    """Test semantic cache integration with other components."""
    
    @pytest.mark.asyncio
    async def test_cache_with_query_router(self):
        """Test semantic cache integration with query router."""
        # This would test the full integration with QueryRouter
        # For now, we'll test the interface
        pass
    
    @pytest.mark.asyncio
    async def test_cache_metrics_integration(self):
        """Test integration with cache metrics."""
        from src.cache.metrics import semantic_cache_metrics
        
        # Test recording cache hit
        semantic_cache_metrics.record_cache_hit("protocol", 0.95)
        assert semantic_cache_metrics.metrics["semantic_cache_hits"] == 1
        
        # Test recording cache miss
        semantic_cache_metrics.record_cache_miss("protocol")
        assert semantic_cache_metrics.metrics["semantic_cache_misses"] == 1
        
        # Test getting hit rate
        hit_rate = semantic_cache_metrics.get_cache_hit_rate("protocol")
        assert hit_rate == 50.0  # 1 hit out of 2 total


if __name__ == "__main__":
    pytest.main([__file__, "-v"])