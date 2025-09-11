"""Test source attribution in responses."""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.orm import Session

from src.models.entities import Document, DocumentRegistry
from src.pipeline.rag_retriever import RAGRetriever
from src.pipeline.response_formatter import ResponseFormatter
from src.pipeline.router import QueryRouter


class TestSourceAttribution:
    """Test that source citations properly display document names."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return Mock()
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.generate = AsyncMock(return_value="Test response with citation")
        return client
    
    def test_response_formatter_extracts_display_names(self):
        """Test that response formatter properly extracts display names from sources."""
        formatter = ResponseFormatter()
        
        # Test with new format (dict sources)
        retrieved_data = [
            {
                "content": "Test content",
                "source": {
                    "filename": "test_protocol.pdf",
                    "display_name": "Test Protocol Document"
                }
            },
            {
                "content": "Another content",
                "sources": [
                    {
                        "filename": "criteria_doc.pdf",
                        "display_name": "Clinical Criteria Guidelines"
                    }
                ]
            }
        ]
        
        sources = formatter._extract_sources(retrieved_data)
        
        assert len(sources) == 2
        assert sources[0]["display_name"] == "Test Protocol Document"
        assert sources[0]["filename"] == "test_protocol.pdf"
        assert sources[1]["display_name"] == "Clinical Criteria Guidelines"
        assert sources[1]["filename"] == "criteria_doc.pdf"
    
    def test_response_formatter_handles_legacy_format(self):
        """Test that response formatter handles legacy string sources."""
        formatter = ResponseFormatter()
        
        # Test with old format (string sources)
        retrieved_data = [
            {
                "content": "Test content",
                "source": "legacy_file.pdf"
            }
        ]
        
        sources = formatter._extract_sources(retrieved_data)
        
        assert len(sources) == 1
        assert sources[0]["display_name"] == "Legacy File"  # Auto-generated from filename
        assert sources[0]["filename"] == "legacy_file.pdf"
    
    @pytest.mark.asyncio
    async def test_router_preserves_display_names(self, mock_db, mock_redis, mock_llm_client):
        """Test that router preserves display names throughout pipeline."""
        router = QueryRouter(mock_db, mock_redis, mock_llm_client)
        
        # Mock document and registry
        mock_doc = Mock(spec=Document)
        mock_doc.id = "doc123"
        mock_doc.filename = "blood_transfusion_consent.pdf"
        mock_doc.content_type = "form"
        
        mock_registry = Mock(spec=DocumentRegistry)
        mock_registry.display_name = "Blood Transfusion Consent Form"
        mock_registry.document_id = "doc123"
        
        # Setup database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_doc,  # First call returns document
            mock_registry  # Second call returns registry
        ]
        
        # Call the form handler
        result = await router._handle_form_query(
            "show me the blood transfusion form",
            None,
            None
        )
        
        # Verify sources contain display name
        assert "sources" in result
        assert len(result["sources"]) > 0
        source = result["sources"][0]
        assert isinstance(source, dict)
        assert source["display_name"] == "Blood Transfusion Consent Form"
        assert source["filename"] == "blood_transfusion_consent.pdf"
    
    def test_rag_retriever_includes_display_names(self, mock_db):
        """Test that RAG retriever includes display names in search results."""
        retriever = RAGRetriever(mock_db)
        
        # Mock the semantic search result
        mock_result = Mock()
        mock_result.id = "chunk1"
        mock_result.document_id = "doc123"
        mock_result.chunk_text = "Test content"
        mock_result.chunk_index = 0
        mock_result.similarity = 0.95
        mock_result.metadata = {}
        mock_result.filename = "test_doc.pdf"
        mock_result.display_name = "Test Document Display Name"
        mock_result.content_type = "protocol"
        mock_result.file_type = "pdf"
        mock_result.category = "clinical"
        mock_result.description = "Test description"
        
        mock_db.execute.return_value.fetchall.return_value = [mock_result]
        
        # Perform search
        results = retriever.semantic_search("test query", k=1)
        
        # Verify display name is included
        assert len(results) == 1
        assert results[0]["source"]["display_name"] == "Test Document Display Name"
        assert results[0]["source"]["filename"] == "test_doc.pdf"
    
    @pytest.mark.asyncio
    async def test_llm_response_includes_proper_citations(self, mock_db, mock_redis, mock_llm_client):
        """Test that LLM responses include proper source citations."""
        router = QueryRouter(mock_db, mock_redis, mock_llm_client)
        
        # Configure LLM to return response with citation
        mock_llm_client.generate.return_value = "According to the STEMI Protocol [Source: STEMI Activation Guidelines], the door-to-balloon time should be under 90 minutes."
        
        sources = [
            {"display_name": "STEMI Activation Guidelines", "filename": "stemi_activation.pdf"},
            {"display_name": "Cardiac Protocol Manual", "filename": "cardiac_protocol.pdf"}
        ]
        
        result = await router._generate_llm_response(
            "What is the STEMI protocol?",
            "protocol",
            "Context about STEMI",
            sources=sources
        )
        
        # Verify response includes sources
        assert "sources" in result
        assert len(result["sources"]) == 2
        assert result["sources"][0]["display_name"] == "STEMI Activation Guidelines"
        
        # Verify LLM was called with proper prompt including source names
        call_args = mock_llm_client.generate.call_args
        prompt = call_args[1]["prompt"]
        assert "STEMI Activation Guidelines" in prompt
        assert "Cardiac Protocol Manual" in prompt
    
    def test_source_resolution_with_display_names(self, mock_db):
        """Test document source resolution includes display names."""
        router = QueryRouter(mock_db, Mock(), Mock())
        
        # Mock documents and registries
        doc1 = Mock(spec=Document)
        doc1.id = "doc1"
        doc1.filename = "protocol1.pdf"
        
        doc2 = Mock(spec=Document)
        doc2.id = "doc2"
        doc2.filename = "protocol2.pdf"
        
        reg1 = Mock(spec=DocumentRegistry)
        reg1.display_name = "Protocol One Guidelines"
        
        reg2 = Mock(spec=DocumentRegistry)
        reg2.display_name = "Protocol Two Standards"
        
        # Setup query responses with proper mock chaining
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            doc1, reg1, doc2, reg2
        ]
        
        # Resolve sources
        sources = router._resolve_document_sources_with_display_names(["doc1", "doc2"])
        
        assert len(sources) == 2
        assert sources[0]["display_name"] == "Protocol One Guidelines"
        assert sources[0]["filename"] == "protocol1.pdf"
        assert sources[1]["display_name"] == "Protocol Two Standards"
        assert sources[1]["filename"] == "protocol2.pdf"