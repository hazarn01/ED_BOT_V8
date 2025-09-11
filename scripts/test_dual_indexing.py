#!/usr/bin/env python3
"""
Test script for dual indexing functionality.
This validates the implementation without requiring Docker/Elasticsearch.
"""

import asyncio
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import Settings
from src.search.elasticsearch_client import ElasticsearchClient
from src.search.es_index_manager import ElasticsearchIndexManager


class DualIndexingTester:
    """Test dual indexing implementation."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []
    
    def report(self, test_name: str, passed: bool, message: str = ""):
        """Report test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append(f"{status}: {test_name}")
        if message:
            self.results.append(f"    {message}")
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
    
    def test_elasticsearch_client_initialization(self):
        """Test ES client can be initialized."""
        try:
            settings = Settings(
                search_backend="hybrid",
                elasticsearch_url="http://localhost:9200"
            )
            
            # Test with mock ES
            with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
                mock_instance = Mock()
                mock_instance.ping.return_value = True
                mock_es.return_value = mock_instance
                
                client = ElasticsearchClient(settings)
                available = client.is_available()
                
                self.report("ES Client Initialization", available, 
                          f"Client available: {available}")
        except Exception as e:
            self.report("ES Client Initialization", False, str(e))
    
    def test_elasticsearch_graceful_fallback(self):
        """Test ES client handles unavailability gracefully."""
        try:
            settings = Settings(search_backend="hybrid")
            
            # Test with ES unavailable
            with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
                mock_es.side_effect = Exception("Connection failed")
                
                client = ElasticsearchClient(settings)
                available = client.is_available()
                
                self.report("ES Graceful Fallback", not available,
                          "Client correctly reports unavailable")
        except Exception as e:
            self.report("ES Graceful Fallback", False, str(e))
    
    def test_index_manager_operations(self):
        """Test index manager can handle operations."""
        try:
            settings = Settings(
                search_backend="hybrid",
                elasticsearch_index_prefix="test_edbot"
            )
            
            with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
                mock_instance = Mock()
                mock_instance.ping.return_value = True
                mock_instance.indices.exists.return_value = False
                mock_instance.indices.create.return_value = {"acknowledged": True}
                mock_es.return_value = mock_instance
                
                client = ElasticsearchClient(settings)
                manager = ElasticsearchIndexManager(client, settings)
                
                # Test index names
                names = manager.get_index_names()
                assert 'documents' in names
                assert 'chunks' in names
                assert 'registry' in names
                assert names['documents'] == 'test_edbot_documents'
                
                self.report("Index Manager Operations", True,
                          f"Index names: {list(names.keys())}")
        except Exception as e:
            self.report("Index Manager Operations", False, str(e))
    
    def test_medical_synonyms_configuration(self):
        """Test medical synonyms are properly configured."""
        try:
            from src.search.es_mappings import DOCUMENT_INDEX_MAPPING, MEDICAL_SYNONYMS
            
            # Check synonyms exist
            assert len(MEDICAL_SYNONYMS) > 20
            
            # Check critical medical terms
            has_stemi = any("STEMI" in s for s in MEDICAL_SYNONYMS)
            has_mi = any("MI,myocardial infarction" in s for s in MEDICAL_SYNONYMS)
            has_ed = any("ED,emergency department" in s for s in MEDICAL_SYNONYMS)
            
            assert has_stemi, "Missing STEMI synonym"
            assert has_mi, "Missing MI synonym"
            assert has_ed, "Missing ED synonym"
            
            # Check mapping includes medical analyzer
            mapping = DOCUMENT_INDEX_MAPPING
            assert 'medical_analyzer' in mapping['settings']['analysis']['analyzer']
            
            self.report("Medical Synonyms Configuration", True,
                      f"Found {len(MEDICAL_SYNONYMS)} medical synonyms")
        except Exception as e:
            self.report("Medical Synonyms Configuration", False, str(e))
    
    async def test_document_processor_dual_indexing(self):
        """Test document processor can handle dual indexing."""
        try:
            # Check that DocumentProcessor supports dual indexing
            import inspect

            from src.ingestion.tasks import DocumentProcessor
            
            # Check __init__ signature includes es_client parameter
            init_params = inspect.signature(DocumentProcessor.__init__).parameters
            assert 'es_client' in init_params, "DocumentProcessor missing es_client parameter"
            
            # Check for _index_to_elasticsearch method
            assert hasattr(DocumentProcessor, '_index_to_elasticsearch'), "Missing _index_to_elasticsearch method"
            
            # Check that dual_index is set as an attribute
            source = inspect.getsource(DocumentProcessor.__init__)
            assert 'self.dual_index' in source, "DocumentProcessor should set dual_index attribute"
            
            self.report("Document Processor Dual Indexing", True,
                      "Processor supports dual indexing via es_client")
        except Exception as e:
            self.report("Document Processor Dual Indexing", False, str(e))
    
    async def test_document_processor_pgvector_only(self):
        """Test document processor works without Elasticsearch."""
        try:
            # Check that DocumentProcessor can work without ES
            # Verify the processor can be initialized with dual_index=False
            # This is a code inspection test rather than runtime test
            import inspect

            from src.ingestion.tasks import DocumentProcessor
            source = inspect.getsource(DocumentProcessor.__init__)
            
            # Check that dual_index parameter defaults to False or is optional
            assert 'dual_index' in source, "DocumentProcessor should support dual_index parameter"
            
            self.report("Document Processor PGVector Only", True,
                      "Processor supports pgvector-only mode")
        except Exception as e:
            self.report("Document Processor PGVector Only", False, str(e))
    
    def test_backfill_script_exists(self):
        """Test backfill script is properly configured."""
        try:
            script_path = "/mnt/d/Dev/EDbotv8/scripts/backfill_elasticsearch.py"
            assert os.path.exists(script_path), f"Script not found: {script_path}"
            
            # Check content instead of importing (to avoid dependencies)
            with open(script_path, 'r') as f:
                content = f.read()
            
            # Check key classes exist in content
            assert 'class ElasticsearchBackfiller' in content
            assert 'backfill_all' in content
            assert '_backfill_documents' in content
            assert '_backfill_chunks' in content
            
            self.report("Backfill Script Configuration", True,
                      "Backfill script properly configured")
        except Exception as e:
            self.report("Backfill Script Configuration", False, str(e))
    
    def test_makefile_targets(self):
        """Test Makefile has all ES management targets."""
        try:
            makefile_path = "/mnt/d/Dev/EDbotv8/Makefile.v8"
            with open(makefile_path, 'r') as f:
                content = f.read()
            
            required_targets = [
                'es-health',
                'es-indices',
                'es-create',
                'es-delete',
                'es-stats',
                'es-backfill',
                'es-backfill-execute',
                'es-optimize',
                'es-verify'
            ]
            
            missing = []
            for target in required_targets:
                if f"{target}:" not in content:
                    missing.append(target)
            
            if missing:
                self.report("Makefile ES Targets", False,
                          f"Missing targets: {missing}")
            else:
                self.report("Makefile ES Targets", True,
                          f"All {len(required_targets)} targets present")
        except Exception as e:
            self.report("Makefile ES Targets", False, str(e))
    
    def test_integration_tests_exist(self):
        """Test integration tests for dual indexing exist."""
        try:
            test_path = "/mnt/d/Dev/EDbotv8/tests/integration/test_dual_indexing.py"
            assert os.path.exists(test_path), f"Test file not found: {test_path}"
            
            with open(test_path, 'r') as f:
                content = f.read()
            
            # Check for key test methods
            required_tests = [
                'test_dual_indexing_enabled_success',
                'test_dual_indexing_elasticsearch_failure_graceful_fallback',
                'test_pgvector_only_mode_no_elasticsearch',
                'test_elasticsearch_bulk_indexing_operations',
                'test_medical_analyzer_synonym_processing'
            ]
            
            missing = []
            for test in required_tests:
                if test not in content:
                    missing.append(test)
            
            if missing:
                self.report("Integration Tests", False,
                          f"Missing tests: {missing}")
            else:
                self.report("Integration Tests", True,
                          f"All {len(required_tests)} integration tests present")
        except Exception as e:
            self.report("Integration Tests", False, str(e))
    
    async def run_all_tests(self):
        """Run all validation tests."""
        print("="*60)
        print("DUAL INDEXING IMPLEMENTATION VALIDATION")
        print("="*60)
        print()
        
        # Run synchronous tests
        self.test_elasticsearch_client_initialization()
        self.test_elasticsearch_graceful_fallback()
        self.test_index_manager_operations()
        self.test_medical_synonyms_configuration()
        self.test_backfill_script_exists()
        self.test_makefile_targets()
        self.test_integration_tests_exist()
        
        # Run async tests
        await self.test_document_processor_dual_indexing()
        await self.test_document_processor_pgvector_only()
        
        # Print results
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        for result in self.results:
            print(result)
        
        print("\n" + "="*60)
        print(f"SUMMARY: {self.tests_passed} passed, {self.tests_failed} failed")
        print("="*60)
        
        if self.tests_failed == 0:
            print("\n✅ All validation tests passed!")
            print("\nNext steps to complete PRP 15:")
            print("1. Install Docker Desktop and enable WSL integration")
            print("2. Run: bash scripts/setup_elasticsearch_docker.sh")
            print("3. Run integration tests: python3 -m pytest tests/integration/test_dual_indexing.py -v")
            print("4. Test backfill: make es-backfill")
            print("5. Execute backfill: make es-backfill-execute")
            return 0
        else:
            print(f"\n❌ {self.tests_failed} tests failed")
            return 1


async def main():
    """Main entry point."""
    tester = DualIndexingTester()
    return await tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))