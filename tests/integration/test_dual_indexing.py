"""
Integration tests for dual indexing (PostgreSQL + Elasticsearch).
Tests the complete ingestion pipeline with both storage backends.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config.settings import Settings
from ingestion.tasks import DocumentProcessor
from search.elasticsearch_client import ElasticsearchClient
from search.es_index_manager import ElasticsearchIndexManager


@pytest.fixture
def mock_elasticsearch_available():
    """Mock Elasticsearch as available for testing."""
    with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
        # Mock ES client
        mock_es_instance = Mock()
        mock_es_instance.ping.return_value = True
        mock_es_instance.indices.exists.return_value = True
        mock_es_instance.indices.create.return_value = {"acknowledged": True}
        mock_es_instance.count.return_value = {"count": 5}
        mock_es_instance.bulk.return_value = (5, [])
        mock_es.return_value = mock_es_instance
        
        # Mock bulk helper
        with patch('src.search.elasticsearch_client.bulk') as mock_bulk:
            mock_bulk.return_value = (5, [])
            yield mock_es_instance


@pytest.fixture
def mock_elasticsearch_unavailable():
    """Mock Elasticsearch as unavailable for testing graceful fallback."""
    with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
        mock_es.side_effect = Exception("Connection failed")
        yield mock_es


@pytest.fixture
def hybrid_settings():
    """Settings configured for hybrid search mode."""
    settings = Settings(
        search_backend="hybrid",
        elasticsearch_url="http://localhost:9200",
        elasticsearch_timeout=30,
        elasticsearch_index_prefix="test_edbot",
        database_url="postgresql://user:pass@localhost:5432/testdb"
    )
    return settings


@pytest.fixture
def pgvector_settings():
    """Settings configured for pgvector-only mode."""
    settings = Settings(
        search_backend="pgvector",
        database_url="postgresql://user:pass@localhost:5432/testdb"
    )
    return settings


@pytest.fixture
def mock_database():
    """Mock database session and operations."""
    with patch('src.ingestion.tasks.get_session') as mock_get_session:
        mock_session = Mock()
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        mock_session.close = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_embeddings():
    """Mock embedding generation."""
    with patch('src.ingestion.tasks.EmbeddingGenerator') as mock_gen:
        mock_instance = Mock()
        mock_instance.generate_embeddings.return_value = [[0.1] * 384]  # 384-dim embedding
        mock_gen.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return {
        "text": "This is a test medical protocol for STEMI management. Step 1: Obtain ECG within 10 minutes.",
        "chunks": [
            "This is a test medical protocol for STEMI management.",
            "Step 1: Obtain ECG within 10 minutes."
        ],
        "entities": [
            {
                "type": "protocol_step",
                "content": "Obtain ECG within 10 minutes",
                "timing": "10 minutes",
                "critical": True
            }
        ]
    }


class TestDualIndexingIntegration:
    """Integration tests for dual indexing functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dual_indexing_enabled_success(
        self, 
        hybrid_settings, 
        mock_elasticsearch_available,
        mock_database,
        mock_embeddings,
        sample_pdf_content
    ):
        """Test successful dual indexing to both PostgreSQL and Elasticsearch."""
        
        # Setup document processor with dual indexing
        with patch('src.config.settings.get_settings', return_value=hybrid_settings):
            processor = DocumentProcessor(dual_index=True)
            
            # Mock PDF processing
            with patch.object(processor, '_extract_pdf_content', return_value=sample_pdf_content):
                with patch.object(processor, '_process_with_langextract', return_value=sample_pdf_content["entities"]):
                    
                    # Create temporary test file
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(b"Test PDF content")
                        test_file_path = tmp_file.name
                    
                    try:
                        # Process document
                        result = await processor.process_document(test_file_path)
                        
                        # Verify result
                        assert result is not None
                        assert result["status"] == "success"
                        assert "document_id" in result
                        
                        # Verify PostgreSQL operations
                        assert mock_database.add.call_count >= 3  # Document + chunks + registry
                        mock_database.commit.assert_called()
                        
                        # Verify Elasticsearch operations
                        assert mock_elasticsearch_available.bulk.called
                        
                    finally:
                        os.unlink(test_file_path)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dual_indexing_elasticsearch_failure_graceful_fallback(
        self,
        hybrid_settings,
        mock_elasticsearch_unavailable,
        mock_database,
        mock_embeddings,
        sample_pdf_content
    ):
        """Test graceful fallback when Elasticsearch fails during dual indexing."""
        
        with patch('src.config.settings.get_settings', return_value=hybrid_settings):
            processor = DocumentProcessor(dual_index=True)
            
            # Mock PDF processing
            with patch.object(processor, '_extract_pdf_content', return_value=sample_pdf_content):
                with patch.object(processor, '_process_with_langextract', return_value=sample_pdf_content["entities"]):
                    
                    # Create temporary test file
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(b"Test PDF content")
                        test_file_path = tmp_file.name
                    
                    try:
                        # Process document - should succeed despite ES failure
                        result = await processor.process_document(test_file_path)
                        
                        # Verify result - should still succeed
                        assert result is not None
                        assert result["status"] == "success"
                        
                        # Verify PostgreSQL operations still occurred
                        assert mock_database.add.call_count >= 3
                        mock_database.commit.assert_called()
                        
                        # Verify no ES operations occurred due to unavailability
                        mock_elasticsearch_unavailable.assert_called()
                        
                    finally:
                        os.unlink(test_file_path)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pgvector_only_mode_no_elasticsearch(
        self,
        pgvector_settings,
        mock_database,
        mock_embeddings,
        sample_pdf_content
    ):
        """Test processing with pgvector-only mode (no Elasticsearch)."""
        
        with patch('src.config.settings.get_settings', return_value=pgvector_settings):
            processor = DocumentProcessor(dual_index=False)
            
            # Mock PDF processing
            with patch.object(processor, '_extract_pdf_content', return_value=sample_pdf_content):
                with patch.object(processor, '_process_with_langextract', return_value=sample_pdf_content["entities"]):
                    
                    # Create temporary test file
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(b"Test PDF content")
                        test_file_path = tmp_file.name
                    
                    try:
                        # Process document
                        result = await processor.process_document(test_file_path)
                        
                        # Verify result
                        assert result is not None
                        assert result["status"] == "success"
                        
                        # Verify PostgreSQL operations
                        assert mock_database.add.call_count >= 3
                        mock_database.commit.assert_called()
                        
                        # Verify no Elasticsearch client was created
                        assert not hasattr(processor, 'es_client') or processor.es_client is None
                        
                    finally:
                        os.unlink(test_file_path)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_elasticsearch_bulk_indexing_operations(
        self,
        hybrid_settings,
        mock_elasticsearch_available,
        mock_database,
        mock_embeddings,
        sample_pdf_content
    ):
        """Test that Elasticsearch bulk operations include correct document data."""
        
        with patch('src.config.settings.get_settings', return_value=hybrid_settings):
            processor = DocumentProcessor(dual_index=True)
            
            # Capture bulk operations
            bulk_operations = []
            
            def capture_bulk(*args, **kwargs):
                operations = args[1]  # Second argument is the operations list
                bulk_operations.extend(operations)
                return (len(operations), [])
            
            mock_elasticsearch_available.bulk = Mock(side_effect=capture_bulk)
            
            # Mock PDF processing
            with patch.object(processor, '_extract_pdf_content', return_value=sample_pdf_content):
                with patch.object(processor, '_process_with_langextract', return_value=sample_pdf_content["entities"]):
                    
                    # Create temporary test file
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(b"Test PDF content")
                        test_file_path = tmp_file.name
                    
                    try:
                        # Process document
                        await processor.process_document(test_file_path)
                        
                        # Verify bulk operations were captured
                        assert len(bulk_operations) > 0
                        
                        # Check document operation
                        doc_ops = [op for op in bulk_operations if 'documents' in op.get('_index', '')]
                        assert len(doc_ops) >= 1
                        
                        doc_op = doc_ops[0]
                        assert doc_op['_source']['content_type'] is not None
                        assert doc_op['_source']['filename'] is not None
                        
                        # Check chunk operations
                        chunk_ops = [op for op in bulk_operations if 'chunks' in op.get('_index', '')]
                        assert len(chunk_ops) >= 1
                        
                        chunk_op = chunk_ops[0]
                        assert 'content' in chunk_op['_source']
                        assert 'document_id' in chunk_op['_source']
                        
                        # Check registry operations
                        registry_ops = [op for op in bulk_operations if 'registry' in op.get('_index', '')]
                        assert len(registry_ops) >= 1
                        
                        registry_op = registry_ops[0]
                        assert 'display_name' in registry_op['_source']
                        assert 'category' in registry_op['_source']
                        
                    finally:
                        os.unlink(test_file_path)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_elasticsearch_index_creation(self, hybrid_settings, mock_elasticsearch_available):
        """Test that Elasticsearch indices are created properly."""
        
        with patch('src.config.settings.get_settings', return_value=hybrid_settings):
            es_client = ElasticsearchClient(hybrid_settings)
            index_manager = ElasticsearchIndexManager(es_client, hybrid_settings)
            
            # Test index creation
            success = index_manager.create_indices()
            
            assert success
            assert mock_elasticsearch_available.indices.create.called
            
            # Verify index names
            index_names = index_manager.get_index_names()
            assert 'documents' in index_names
            assert 'chunks' in index_names
            assert 'registry' in index_names
            
            assert index_names['documents'] == 'test_edbot_documents'
            assert index_names['chunks'] == 'test_edbot_chunks'
            assert index_names['registry'] == 'test_edbot_registry'
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_medical_analyzer_synonym_processing(self, hybrid_settings, mock_elasticsearch_available):
        """Test that medical synonyms are properly configured in Elasticsearch mappings."""
        
        from search.es_mappings import DOCUMENT_INDEX_MAPPING, MEDICAL_SYNONYMS
        
        # Verify medical synonyms are included
        assert len(MEDICAL_SYNONYMS) > 20  # Should have substantial medical synonyms
        assert any("MI,myocardial infarction" in synonym for synonym in MEDICAL_SYNONYMS)
        assert any("STEMI,ST elevation" in synonym for synonym in MEDICAL_SYNONYMS)
        assert any("ED,emergency department" in synonym for synonym in MEDICAL_SYNONYMS)
        
        # Verify mapping includes medical analyzer
        mapping = DOCUMENT_INDEX_MAPPING
        assert 'medical_analyzer' in mapping['settings']['analysis']['analyzer']
        assert 'medical_synonyms' in mapping['settings']['analysis']['filter']
        
        # Verify synonyms are in the filter
        synonyms = mapping['settings']['analysis']['filter']['medical_synonyms']['synonyms']
        assert len(synonyms) == len(MEDICAL_SYNONYMS)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dual_indexing_error_handling(
        self,
        hybrid_settings,
        mock_database,
        mock_embeddings,
        sample_pdf_content
    ):
        """Test error handling during dual indexing operations."""
        
        # Mock Elasticsearch to fail on bulk operations
        with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
            mock_es_instance = Mock()
            mock_es_instance.ping.return_value = True
            mock_es_instance.indices.exists.return_value = True
            mock_es_instance.bulk.side_effect = Exception("Bulk operation failed")
            mock_es.return_value = mock_es_instance
            
            with patch('src.config.settings.get_settings', return_value=hybrid_settings):
                processor = DocumentProcessor(dual_index=True)
                
                # Mock PDF processing
                with patch.object(processor, '_extract_pdf_content', return_value=sample_pdf_content):
                    with patch.object(processor, '_process_with_langextract', return_value=sample_pdf_content["entities"]):
                        
                        # Create temporary test file
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                            tmp_file.write(b"Test PDF content")
                            test_file_path = tmp_file.name
                        
                        try:
                            # Process document - should handle ES failure gracefully
                            result = await processor.process_document(test_file_path)
                            
                            # Should still succeed despite ES failure
                            assert result is not None
                            assert result["status"] == "success"
                            
                            # PostgreSQL operations should still work
                            assert mock_database.add.call_count >= 3
                            mock_database.commit.assert_called()
                            
                        finally:
                            os.unlink(test_file_path)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_document_type_specific_indexing(
        self,
        hybrid_settings,
        mock_elasticsearch_available,
        mock_database,
        mock_embeddings
    ):
        """Test that different document types are indexed with appropriate metadata."""
        
        protocol_content = {
            "text": "STEMI Protocol: Obtain ECG within 10 minutes",
            "chunks": ["STEMI Protocol: Obtain ECG within 10 minutes"],
            "entities": [{"type": "protocol_step", "content": "Obtain ECG", "timing": "10 minutes"}]
        }
        
        form_content = {
            "text": "Blood Transfusion Consent Form",
            "chunks": ["Blood Transfusion Consent Form"],
            "entities": []
        }
        
        test_cases = [
            ("protocol", protocol_content),
            ("form", form_content)
        ]
        
        for doc_type, content in test_cases:
            with patch('src.config.settings.get_settings', return_value=hybrid_settings):
                processor = DocumentProcessor(dual_index=True)
                
                # Capture bulk operations
                bulk_operations = []
                
                def capture_bulk(*args, **kwargs):
                    operations = args[1]
                    bulk_operations.extend(operations)
                    return (len(operations), [])
                
                mock_elasticsearch_available.bulk = Mock(side_effect=capture_bulk)
                
                # Mock PDF processing to return specific content type
                with patch.object(processor, '_extract_pdf_content', return_value=content):
                    with patch.object(processor, '_process_with_langextract', return_value=content["entities"]):
                        with patch.object(processor, '_determine_content_type', return_value=doc_type):
                            
                            # Create temporary test file
                            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                                tmp_file.write(b"Test PDF content")
                                test_file_path = tmp_file.name
                            
                            try:
                                # Process document
                                result = await processor.process_document(test_file_path)
                                
                                # Verify document was processed
                                assert result["status"] == "success"
                                
                                # Find document operation in bulk operations
                                doc_ops = [op for op in bulk_operations if 'documents' in op.get('_index', '')]
                                assert len(doc_ops) >= 1
                                
                                doc_source = doc_ops[0]['_source']
                                assert doc_source['content_type'] == doc_type
                                
                                # Check type-specific fields
                                if doc_type == "protocol":
                                    assert 'protocol_name' in doc_source
                                elif doc_type == "form":
                                    assert 'form_name' in doc_source
                                
                            finally:
                                os.unlink(test_file_path)
                                bulk_operations.clear()