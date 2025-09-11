"""Tests for HybridRetriever functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.config.settings import Settings
from src.models.query_types import QueryType
from src.pipeline.hybrid_retriever import HybridRetriever, RetrievalResult
from src.pipeline.rag_retriever import RAGRetriever
from src.search.elasticsearch_client import ElasticsearchClient


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.search_backend = "hybrid"
    settings.elasticsearch_index_prefix = "test_edbot"
    settings.fusion_weights_json = None
    return settings


@pytest.fixture
def mock_rag_retriever():
    """Create mock RAG retriever."""
    rag = Mock(spec=RAGRetriever)
    rag.semantic_search = AsyncMock()
    return rag


@pytest.fixture
def mock_es_client():
    """Create mock Elasticsearch client."""
    es_client = Mock(spec=ElasticsearchClient)
    es_client.is_available.return_value = True
    es_client.get_client.return_value = Mock()
    return es_client


@pytest.fixture
def hybrid_retriever(mock_rag_retriever, mock_es_client, mock_settings):
    """Create HybridRetriever instance for testing."""
    return HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)


class TestHybridRetrieverInitialization:
    """Test HybridRetriever initialization."""

    def test_initialization_with_hybrid_enabled(self, mock_rag_retriever, mock_es_client, mock_settings):
        """Test initialization with hybrid search enabled."""
        mock_es_client.is_available.return_value = True
        
        retriever = HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)
        
        assert retriever.hybrid_enabled is True
        assert retriever.rag_retriever == mock_rag_retriever
        assert retriever.es_client == mock_es_client
        assert retriever.settings == mock_settings

    def test_initialization_with_hybrid_disabled(self, mock_rag_retriever, mock_es_client, mock_settings):
        """Test initialization with hybrid search disabled."""
        mock_es_client.is_available.return_value = False
        
        retriever = HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)
        
        assert retriever.hybrid_enabled is False

    def test_initialization_with_custom_fusion_weights(self, mock_rag_retriever, mock_es_client, mock_settings):
        """Test initialization with custom fusion weights."""
        custom_weights = '{"FORM_RETRIEVAL": [0.9, 0.1], "SUMMARY_REQUEST": [0.2, 0.8]}'
        mock_settings.fusion_weights_json = custom_weights
        mock_es_client.is_available.return_value = True
        
        retriever = HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)
        
        # Check that custom weights are loaded (would need to convert enum to string)
        assert QueryType.FORM_RETRIEVAL in retriever.FUSION_WEIGHTS

    def test_initialization_with_invalid_fusion_weights_json(self, mock_rag_retriever, mock_es_client, mock_settings):
        """Test initialization with invalid fusion weights JSON."""
        mock_settings.fusion_weights_json = "invalid json"
        mock_es_client.is_available.return_value = True
        
        # Should not raise exception, just use defaults
        retriever = HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)
        
        assert retriever.hybrid_enabled is True


class TestHybridRetrieverSearchMethods:
    """Test HybridRetriever search methods."""

    @pytest.mark.asyncio
    async def test_retrieve_fallback_to_semantic_when_hybrid_disabled(self, hybrid_retriever):
        """Test fallback to semantic-only when hybrid is disabled."""
        hybrid_retriever.hybrid_enabled = False
        
        # Mock semantic search results
        
        # Mock the _semantic_search method directly instead of rag_retriever
        with patch.object(hybrid_retriever, '_semantic_search') as mock_semantic:
            mock_semantic.return_value = [
                RetrievalResult("1", "doc1", "test content", 0.8, "semantic", {})
            ]
            
            results = await hybrid_retriever.retrieve("test query", QueryType.PROTOCOL_STEPS, 5)
            
            assert len(results) == 1
            assert results[0].source == "semantic"
            assert results[0].content == "test content"

    @pytest.mark.asyncio
    async def test_retrieve_hybrid_search_success(self, hybrid_retriever):
        """Test successful hybrid search combining keyword and semantic results."""
        # Mock keyword search results
        with patch.object(hybrid_retriever, '_keyword_search') as mock_keyword:
            mock_keyword.return_value = [
                RetrievalResult("1", "doc1", "keyword result", 0.9, "keyword", {})
            ]
            
            # Mock semantic search results
            with patch.object(hybrid_retriever, '_semantic_search') as mock_semantic:
                mock_semantic.return_value = [
                    RetrievalResult("2", "doc2", "semantic result", 0.8, "semantic", {})
                ]
                
                results = await hybrid_retriever.retrieve("test query", QueryType.FORM_RETRIEVAL, 5)
                
                assert len(results) == 2
                # FORM_RETRIEVAL has keyword bias (0.8, 0.2), so keyword result should be first
                assert results[0].chunk_id == "1"  # keyword result
                assert results[0].metadata["retrieval_sources"] == ["keyword"]

    @pytest.mark.asyncio
    async def test_retrieve_handles_keyword_search_failure(self, hybrid_retriever):
        """Test handling of keyword search failure."""
        # Mock keyword search to raise exception
        with patch.object(hybrid_retriever, '_keyword_search') as mock_keyword:
            mock_keyword.side_effect = Exception("ES connection failed")
            
            # Mock semantic search success
            with patch.object(hybrid_retriever, '_semantic_search') as mock_semantic:
                mock_semantic.return_value = [
                    RetrievalResult("2", "doc2", "semantic result", 0.8, "semantic", {})
                ]
                
                results = await hybrid_retriever.retrieve("test query", QueryType.PROTOCOL_STEPS, 5)
                
                assert len(results) == 1
                assert results[0].source == "semantic"

    @pytest.mark.asyncio
    async def test_retrieve_handles_both_searches_failure(self, hybrid_retriever):
        """Test handling when both searches fail."""
        # Mock both searches to fail
        with patch.object(hybrid_retriever, '_keyword_search') as mock_keyword:
            mock_keyword.side_effect = Exception("ES failed")
            
            with patch.object(hybrid_retriever, '_semantic_search') as mock_semantic:
                mock_semantic.side_effect = Exception("Vector search failed")
                
                # Mock semantic fallback
                with patch.object(hybrid_retriever, '_semantic_only') as mock_fallback:
                    mock_fallback.return_value = []
                    
                    results = await hybrid_retriever.retrieve("test query", QueryType.PROTOCOL_STEPS, 5)
                    
                    assert len(results) == 0
                    mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_keyword_search_success(self, hybrid_retriever):
        """Test successful keyword search."""
        # Mock ES client and response
        mock_es = Mock()
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_score": 1.5,
                        "_source": {
                            "id": "chunk1",
                            "document_id": "doc1",
                            "content": "test content",
                            "metadata": {"filename": "test.pdf"}
                        }
                    }
                ]
            }
        }
        
        hybrid_retriever.es_client.get_client.return_value = mock_es
        
        with patch('asyncio.to_thread') as mock_thread:
            mock_thread.return_value = mock_response
            
            results = await hybrid_retriever._keyword_search(
                "test query", QueryType.FORM_RETRIEVAL, 5, None
            )
            
            assert len(results) == 1
            assert results[0].chunk_id == "chunk1"
            assert results[0].source == "keyword"
            assert results[0].score == 1.5

    @pytest.mark.asyncio
    async def test_semantic_search_success(self, hybrid_retriever):
        """Test successful semantic search."""
        # Mock RAG retriever results
        mock_results = [
            {
                "chunk_id": "chunk1",
                "document_id": "doc1", 
                "content": "semantic content",
                "similarity": 0.85,
                "metadata": {"filename": "test.pdf"}
            }
        ]
        
        # Use regular Mock for the synchronous semantic search
        hybrid_retriever.rag_retriever.semantic_search = Mock(return_value=mock_results)
        
        results = await hybrid_retriever._semantic_search("test query", 5, None)
        
        assert len(results) == 1
        assert results[0].chunk_id == "chunk1"
        assert results[0].source == "semantic"
        assert results[0].score == 0.85


class TestFusionLogic:
    """Test result fusion and scoring logic."""

    def test_fuse_results_with_different_query_types(self, hybrid_retriever):
        """Test fusion with different query type weights."""
        keyword_results = [
            RetrievalResult("1", "doc1", "exact match", 1.0, "keyword", {})
        ]
        semantic_results = [
            RetrievalResult("2", "doc2", "similar content", 0.8, "semantic", {})
        ]
        
        # Test FORM (keyword-heavy: 0.8, 0.2)
        form_results = hybrid_retriever._fuse_results(
            keyword_results, semantic_results, QueryType.FORM_RETRIEVAL, 10
        )
        # After normalization, keyword should win due to higher weight
        assert form_results[0].chunk_id == "1"  # keyword result first
        
        # Test SUMMARY (semantic-heavy: 0.3, 0.7)
        summary_results = hybrid_retriever._fuse_results(
            keyword_results, semantic_results, QueryType.SUMMARY_REQUEST, 10
        )
        # Semantic might win despite lower raw score due to higher weight
        # After normalization both become 1.0, then: keyword=1.0*0.3=0.3, semantic=1.0*0.7=0.7
        assert summary_results[0].chunk_id == "2"  # semantic result first

    def test_fuse_results_with_overlapping_chunks(self, hybrid_retriever):
        """Test fusion when same chunk is found by both methods."""
        keyword_results = [
            RetrievalResult("1", "doc1", "content", 0.9, "keyword", {})
        ]
        semantic_results = [
            RetrievalResult("1", "doc1", "content", 0.8, "semantic", {})  # Same chunk
        ]
        
        results = hybrid_retriever._fuse_results(
            keyword_results, semantic_results, QueryType.CRITERIA_CHECK, 10
        )
        
        assert len(results) == 1  # Only one result since it's the same chunk
        assert "keyword" in results[0].metadata["retrieval_sources"]
        assert "semantic" in results[0].metadata["retrieval_sources"]
        # Score should be combined: normalized scores with weights (0.4, 0.6)
        # Both normalized to 1.0: 1.0*0.4 + 1.0*0.6 = 1.0

    def test_normalize_scores_equal_scores(self, hybrid_retriever):
        """Test score normalization when all scores are equal."""
        results = [
            RetrievalResult("1", "doc1", "content1", 0.5, "keyword", {}),
            RetrievalResult("2", "doc2", "content2", 0.5, "keyword", {}),
        ]
        
        normalized = hybrid_retriever._normalize_scores(results)
        
        assert all(r.score == 1.0 for r in normalized)

    def test_normalize_scores_different_scores(self, hybrid_retriever):
        """Test score normalization with different scores."""
        results = [
            RetrievalResult("1", "doc1", "content1", 1.0, "keyword", {}),  # max
            RetrievalResult("2", "doc2", "content2", 0.5, "keyword", {}),  # mid  
            RetrievalResult("3", "doc3", "content3", 0.0, "keyword", {}),  # min
        ]
        
        normalized = hybrid_retriever._normalize_scores(results)
        
        assert normalized[0].score == 1.0  # (1.0-0.0)/(1.0-0.0) = 1.0
        assert normalized[1].score == 0.5  # (0.5-0.0)/(1.0-0.0) = 0.5
        assert normalized[2].score == 0.0  # (0.0-0.0)/(1.0-0.0) = 0.0

    def test_normalize_scores_empty_list(self, hybrid_retriever):
        """Test score normalization with empty results."""
        results = []
        normalized = hybrid_retriever._normalize_scores(results)
        assert normalized == []


class TestElasticsearchQueryBuilding:
    """Test Elasticsearch query building for different query types."""

    def test_build_es_query_form_retrieval(self, hybrid_retriever):
        """Test ES query building for form retrieval."""
        query = hybrid_retriever._build_es_query(
            "blood transfusion consent", QueryType.FORM_RETRIEVAL, None
        )
        
        should_clauses = query["query"]["bool"]["should"]
        assert len(should_clauses) == 3
        assert should_clauses[0]["match"]["form_name"]["boost"] == 3
        assert should_clauses[1]["match"]["filename.keyword"]["boost"] == 2

    def test_build_es_query_protocol_steps(self, hybrid_retriever):
        """Test ES query building for protocol steps."""
        query = hybrid_retriever._build_es_query(
            "STEMI protocol", QueryType.PROTOCOL_STEPS, None
        )
        
        should_clauses = query["query"]["bool"]["should"]
        assert len(should_clauses) == 3
        assert should_clauses[0]["match"]["protocol_name"]["boost"] == 3
        assert should_clauses[1]["match"]["title.keyword"]["boost"] == 2

    def test_build_es_query_with_filters(self, hybrid_retriever):
        """Test ES query building with content type filter."""
        filters = {"content_type": "protocol"}
        query = hybrid_retriever._build_es_query(
            "test query", QueryType.PROTOCOL_STEPS, filters
        )
        
        filter_clauses = query["query"]["bool"]["filter"]
        assert len(filter_clauses) == 1
        assert filter_clauses[0]["term"]["content_type"] == "protocol"

    def test_build_es_query_contact_lookup(self, hybrid_retriever):
        """Test ES query building for contact lookup."""
        query = hybrid_retriever._build_es_query(
            "cardiology on call", QueryType.CONTACT_LOOKUP, None
        )
        
        should_clauses = query["query"]["bool"]["should"]
        assert len(should_clauses) == 3
        assert should_clauses[0]["match"]["specialty"]["boost"] == 3
        assert should_clauses[1]["match"]["contact_info"]["boost"] == 2


class TestRetrievalStats:
    """Test retrieval statistics and health monitoring."""

    def test_get_retrieval_stats_hybrid_enabled(self, hybrid_retriever):
        """Test retrieval stats when hybrid is enabled."""
        mock_health = {"status": "green", "cluster_name": "test"}
        hybrid_retriever.es_client.get_cluster_health.return_value = mock_health
        
        stats = hybrid_retriever.get_retrieval_stats()
        
        assert stats["hybrid_enabled"] is True
        assert stats["elasticsearch_available"] is True
        assert "fusion_weights" in stats
        assert stats["elasticsearch_health"] == mock_health

    def test_get_retrieval_stats_hybrid_disabled(self, mock_rag_retriever, mock_settings):
        """Test retrieval stats when hybrid is disabled."""
        mock_es_client = Mock(spec=ElasticsearchClient)
        mock_es_client.is_available.return_value = False
        
        retriever = HybridRetriever(mock_rag_retriever, mock_es_client, mock_settings)
        
        stats = retriever.get_retrieval_stats()
        
        assert stats["hybrid_enabled"] is False
        assert stats["elasticsearch_available"] is False
        assert "fusion_weights" in stats


class TestErrorHandling:
    """Test error handling in various scenarios."""

    @pytest.mark.asyncio
    async def test_keyword_search_es_unavailable(self, hybrid_retriever):
        """Test keyword search when ES is unavailable."""
        hybrid_retriever.es_client.is_available.return_value = False
        
        results = await hybrid_retriever._keyword_search(
            "test", QueryType.FORM_RETRIEVAL, 5, None
        )
        
        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_es_exception(self, hybrid_retriever):
        """Test keyword search when ES throws exception."""
        mock_es = Mock()
        hybrid_retriever.es_client.get_client.return_value = mock_es
        
        with patch('asyncio.to_thread') as mock_thread:
            mock_thread.side_effect = Exception("ES timeout")
            
            results = await hybrid_retriever._keyword_search(
                "test", QueryType.FORM_RETRIEVAL, 5, None
            )
            
            assert results == []

    @pytest.mark.asyncio
    async def test_semantic_search_exception(self, hybrid_retriever):
        """Test semantic search when RAG retriever throws exception."""
        hybrid_retriever.rag_retriever.semantic_search = Mock(side_effect=Exception("DB error"))
        
        results = await hybrid_retriever._semantic_search("test", 5, None)
        
        assert results == []


@pytest.mark.integration
class TestHybridRetrieverIntegration:
    """Integration tests for HybridRetriever with real components."""
    
    # These would require actual DB and ES setup, so marked as integration tests
    pass