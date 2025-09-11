# PRP 23: Tests for New Components

## Problem Statement
The new hybrid search, source highlighting, table extraction, and caching components need comprehensive test coverage to ensure reliability and prevent regressions. Tests must be fast, isolated, and skip optional services when unavailable.

## Success Criteria
- Unit tests for all new components with >90% coverage
- Integration tests for end-to-end workflows
- Tests skip gracefully when optional services unavailable
- Performance benchmarks for new features
- CI pipeline remains fast and stable

## Implementation Approach

### 1. Test Organization Structure
```
tests/
├── unit/
│   ├── test_hybrid_retriever.py
│   ├── test_source_highlighter.py
│   ├── test_table_extractor.py
│   ├── test_semantic_cache.py
│   ├── test_elasticsearch_client.py
│   └── test_feature_flags.py
├── integration/
│   ├── test_hybrid_search_flow.py
│   ├── test_dual_indexing.py
│   ├── test_pdf_viewer_endpoints.py
│   └── test_streamlit_integration.py
├── performance/
│   ├── test_hybrid_latency.py
│   ├── test_cache_performance.py
│   └── test_table_extraction_speed.py
└── fixtures/
    ├── sample_pdfs/
    ├── mock_responses/
    └── test_data/
```

### 2. Unit Tests for Core Components

```python
# tests/unit/test_hybrid_retriever.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import numpy as np

from src.pipeline.hybrid_retriever import HybridRetriever, RetrievalResult
from src.models.entities import QueryType

@pytest.fixture
def mock_rag_retriever():
    """Mock RAG retriever"""
    retriever = Mock()
    retriever.retrieve_chunks = AsyncMock(return_value=[
        (Mock(id="1", content="semantic result", meta={}), 0.9),
        (Mock(id="2", content="another result", meta={}), 0.8)
    ])
    return retriever

@pytest.fixture  
def mock_es_client():
    """Mock Elasticsearch client"""
    client = Mock()
    client.enabled = True
    client.get_client = Mock(return_value=Mock())
    return client

@pytest.fixture
def hybrid_retriever(mock_rag_retriever, mock_es_client, settings):
    """Create hybrid retriever with mocks"""
    return HybridRetriever(mock_rag_retriever, mock_es_client, settings)

class TestHybridRetriever:
    
    async def test_semantic_only_fallback(self, hybrid_retriever, mock_rag_retriever):
        """Test fallback to semantic-only when ES unavailable"""
        hybrid_retriever.hybrid_enabled = False
        
        results = await hybrid_retriever.retrieve(
            "test query", 
            QueryType.PROTOCOL_STEPS
        )
        
        assert len(results) == 2
        assert all(r.source == "semantic" for r in results)
        mock_rag_retriever.retrieve_chunks.assert_called_once()
        
    @patch('src.pipeline.hybrid_retriever.asyncio.to_thread')
    async def test_keyword_search_execution(self, mock_to_thread, hybrid_retriever):
        """Test keyword search execution"""
        # Mock ES response
        mock_to_thread.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "id": "1",
                            "document_id": "doc1", 
                            "content": "exact keyword match",
                            "metadata": {}
                        },
                        "_score": 1.5
                    }
                ]
            }
        }
        
        results = await hybrid_retriever._keyword_search(
            "test query",
            QueryType.FORM_RETRIEVAL,
            10,
            None
        )
        
        assert len(results) == 1
        assert results[0].source == "keyword"
        assert results[0].score == 1.5
        
    def test_fusion_weights_by_query_type(self, hybrid_retriever):
        """Test that different query types use appropriate fusion weights"""
        keyword_results = [
            RetrievalResult("1", "d1", "exact match", 1.0, "keyword", {})
        ]
        semantic_results = [
            RetrievalResult("2", "d2", "similar content", 0.8, "semantic", {})
        ]
        
        # Test FORM (keyword-heavy: 0.8, 0.2)
        form_fused = hybrid_retriever._fuse_results(
            keyword_results, semantic_results,
            QueryType.FORM_RETRIEVAL, 10
        )
        # After normalization: keyword=1.0*0.8=0.8, semantic=1.0*0.2=0.2
        assert form_fused[0].chunk_id == "1"  # Keyword should win
        
        # Test SUMMARY (semantic-heavy: 0.3, 0.7)  
        summary_fused = hybrid_retriever._fuse_results(
            keyword_results, semantic_results,
            QueryType.SUMMARY_REQUEST, 10
        )
        # After normalization: keyword=1.0*0.3=0.3, semantic=1.0*0.7=0.7
        assert summary_fused[0].chunk_id == "2"  # Semantic should win
        
    def test_score_normalization(self, hybrid_retriever):
        """Test score normalization"""
        results = [
            RetrievalResult("1", "d1", "text", 10.0, "test", {}),
            RetrievalResult("2", "d2", "text", 5.0, "test", {}),
            RetrievalResult("3", "d3", "text", 0.0, "test", {})
        ]
        
        normalized = hybrid_retriever._normalize_scores(results)
        
        assert normalized[0].score == 1.0  # Max normalized to 1
        assert normalized[1].score == 0.5  # Middle value
        assert normalized[2].score == 0.0  # Min normalized to 0

# tests/unit/test_source_highlighter.py  
class TestSourceHighlighter:
    
    def test_highlight_generation(self, sample_chunk):
        """Test basic highlight generation"""
        chunk = sample_chunk(
            content="The STEMI protocol requires door-to-balloon time under 90 minutes.",
            page_number=5
        )
        
        response_text = "door-to-balloon time under 90 minutes is critical"
        
        highlighter = SourceHighlighter(settings)
        highlights = highlighter.generate_highlights([chunk], "", response_text)
        
        assert len(highlights) == 1
        assert highlights[0].page_number == 5
        assert "door-to-balloon" in highlights[0].text_snippet
        assert len(highlights[0].highlight_spans) > 0
        
    def test_span_merging(self):
        """Test overlapping span merger"""
        highlighter = SourceHighlighter(settings)
        spans = [(10, 20), (15, 25), (30, 40)]
        merged = highlighter._merge_overlapping_spans(spans)
        assert merged == [(10, 25), (30, 40)]
        
    def test_confidence_calculation(self):
        """Test highlight confidence scoring"""
        highlighter = SourceHighlighter(settings)
        
        # High coverage should give high confidence
        matches = [(0, 50), (60, 100)]  # 90 chars matched
        confidence = highlighter._calculate_confidence(matches, "x" * 200)
        assert confidence > 0.8
        
        # Low coverage should give low confidence  
        matches = [(0, 10)]  # 10 chars matched
        confidence = highlighter._calculate_confidence(matches, "x" * 200)
        assert confidence < 0.2
```

### 3. Integration Tests

```python
# tests/integration/test_hybrid_search_flow.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
@pytest.mark.skipif(not pytest.elasticsearch_available, reason="Elasticsearch not available")
class TestHybridSearchFlow:
    
    async def test_end_to_end_hybrid_search(self, client: AsyncClient):
        """Test complete hybrid search workflow"""
        # Enable hybrid search
        await client.post("/api/v1/config/flags/enable_hybrid_search", json={"enabled": True})
        
        # Submit query
        response = await client.post(
            "/api/v1/query",
            json={"query": "STEMI protocol door to balloon"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have both keyword and semantic results
        assert "STEMI" in data["answer"]
        assert len(data["sources"]) > 0
        
        # Check for hybrid metadata
        highlighted = data.get("highlighted_sources", [])
        if highlighted:
            assert any("STEMI" in h["text_snippet"] for h in highlighted)
            
    async def test_fallback_when_es_down(self, client: AsyncClient):
        """Test graceful fallback when Elasticsearch is unavailable"""
        # Enable hybrid but ES is down
        with patch('src.search.elasticsearch_client.Elasticsearch') as mock_es:
            mock_es.return_value.ping.return_value = False
            
            response = await client.post(
                "/api/v1/query", 
                json={"query": "test protocol"}
            )
            
            assert response.status_code == 200
            # Should still work with pgvector only

# tests/integration/test_dual_indexing.py
@pytest.mark.asyncio
@pytest.mark.skipif(not pytest.elasticsearch_available, reason="Elasticsearch not available")
class TestDualIndexing:
    
    async def test_document_indexed_in_both_stores(self, db_session):
        """Test that ingested documents appear in both PostgreSQL and Elasticsearch"""
        from src.ingestion.tasks import DocumentIngestionTask
        
        # Enable dual indexing
        settings.features.enable_elasticsearch = True
        
        # Ingest test document
        task = DocumentIngestionTask(db_session, settings, es_client)
        doc = await task.ingest_document("test.pdf", "protocol")
        
        # Check PostgreSQL
        assert doc.id is not None
        chunks = db_session.query(DocumentChunk).filter_by(document_id=doc.id).all()
        assert len(chunks) > 0
        
        # Check Elasticsearch
        es = es_client.get_client()
        doc_exists = es.exists(
            index=f"{settings.elasticsearch_index_prefix}_documents",
            id=hashlib.md5(f"{doc.id}".encode()).hexdigest()
        )
        assert doc_exists
        
    async def test_indexing_continues_on_es_failure(self, db_session):
        """Test that PostgreSQL indexing continues if ES fails"""
        with patch('src.search.elasticsearch_client.ElasticsearchClient.get_client') as mock_client:
            mock_client.return_value = None  # Simulate ES failure
            
            task = DocumentIngestionTask(db_session, settings, es_client)
            doc = await task.ingest_document("test.pdf", "protocol")
            
            # Should still succeed in PostgreSQL
            assert doc.id is not None
```

### 4. Performance Tests

```python
# tests/performance/test_hybrid_latency.py
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.performance
class TestHybridPerformance:
    
    async def test_hybrid_search_latency(self, hybrid_retriever):
        """Benchmark hybrid search latency"""
        queries = [
            "STEMI protocol", 
            "blood transfusion form",
            "sepsis criteria",
            "metoprolol dosage"
        ] * 10  # 40 queries total
        
        latencies = []
        
        for query in queries:
            start = time.time()
            results = await hybrid_retriever.retrieve(query, QueryType.PROTOCOL_STEPS)
            end = time.time()
            
            latencies.append(end - start)
            assert len(results) > 0  # Should return results
            
        # Performance assertions
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        
        assert avg_latency < 1.0, f"Average latency too high: {avg_latency:.3f}s"
        assert p95_latency < 2.0, f"P95 latency too high: {p95_latency:.3f}s"
        
    async def test_concurrent_hybrid_search(self, hybrid_retriever):
        """Test performance under concurrent load"""
        async def search_task():
            return await hybrid_retriever.retrieve("test query", QueryType.PROTOCOL_STEPS)
            
        # Run 10 concurrent searches
        start = time.time()
        tasks = [search_task() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        end = time.time()
        
        # All should succeed
        assert all(len(r) > 0 for r in results)
        
        # Total time should be reasonable (not 10x single query)
        total_time = end - start
        assert total_time < 5.0, f"Concurrent search too slow: {total_time:.3f}s"

# tests/performance/test_cache_performance.py
@pytest.mark.performance  
class TestCachePerformance:
    
    async def test_cache_hit_latency(self, semantic_cache):
        """Test cache hit response time"""
        # Populate cache
        await semantic_cache.set(
            "test query",
            {"answer": "cached response"},
            QueryType.PROTOCOL_STEPS,
            ["source1"],
            0.9
        )
        
        # Measure cache hit latency
        latencies = []
        for _ in range(100):
            start = time.time()
            result = await semantic_cache.get("test query", QueryType.PROTOCOL_STEPS)
            end = time.time()
            
            assert result is not None
            latencies.append(end - start)
            
        avg_latency = statistics.mean(latencies)
        assert avg_latency < 0.01, f"Cache too slow: {avg_latency:.3f}s"  # <10ms
```

### 5. Test Configuration and Fixtures

```python
# tests/conftest.py
import pytest
import asyncio
import tempfile
import shutil
from unittest.mock import Mock
import redis.asyncio as redis

# Test settings
@pytest.fixture
def test_settings():
    """Test-specific settings"""
    from src.config.settings import Settings, FeatureFlags
    
    return Settings(
        environment="test",
        features=FeatureFlags(
            enable_hybrid_search=True,
            enable_source_highlighting=True,
            enable_table_extraction=True,
            enable_semantic_cache=True
        ),
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/15"  # Test database
    )

# Redis fixture  
@pytest.fixture
async def redis_client():
    """Redis client for testing"""
    client = redis.from_url("redis://localhost:6379/15")
    yield client
    await client.flushdb()  # Clean up
    await client.close()

# Elasticsearch check
def pytest_configure(config):
    """Configure pytest with environment checks"""
    try:
        import requests
        response = requests.get("http://localhost:9200/_cluster/health", timeout=1)
        pytest.elasticsearch_available = response.status_code == 200
    except:
        pytest.elasticsearch_available = False

# Skip markers
pytest.mark.elasticsearch = pytest.mark.skipif(
    not pytest.elasticsearch_available,
    reason="Elasticsearch not available"
)

# Sample data fixtures
@pytest.fixture
def sample_pdf():
    """Create temporary PDF for testing"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Create minimal PDF content
        f.write(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")
        return f.name

@pytest.fixture  
def sample_chunk():
    """Factory for creating test chunks"""
    def _create_chunk(content="test content", page_number=1, **kwargs):
        from src.models.entities import DocumentChunk
        return DocumentChunk(
            id="test-chunk",
            content=content, 
            page_number=page_number,
            **kwargs
        )
    return _create_chunk
```

### 6. CI Pipeline Integration

```yaml
# .github/workflows/test.yml (additions)
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_PASSWORD: password
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
      elasticsearch:
        image: elasticsearch:8.11.1
        env:
          discovery.type: single-node
          xpack.security.enabled: false
        ports:
          - 9200:9200
          
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest tests/integration/ -v
        
  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - name: Run performance benchmarks
        run: pytest tests/performance/ -v --benchmark-json=benchmark.json
      - name: Comment benchmark results
        uses: benchmark-action/github-action-benchmark@v1
```

### 7. Test Utilities

```python
# tests/utils/test_helpers.py
import json
from typing import Dict, Any

class APITestHelper:
    """Helper for API testing"""
    
    @staticmethod
    async def enable_feature(client, feature_name: str, ttl_minutes: int = 5):
        """Enable feature flag for test"""
        return await client.post(
            f"/api/v1/config/flags/{feature_name}",
            json={"enabled": True, "ttl_minutes": ttl_minutes}
        )
        
    @staticmethod
    async def submit_query(client, query: str) -> Dict[Any, Any]:
        """Submit query and return response"""
        response = await client.post("/api/v1/query", json={"query": query})
        assert response.status_code == 200
        return response.json()

class DataTestHelper:
    """Helper for test data management"""
    
    @staticmethod
    def create_test_document(content: str, doc_type: str = "protocol") -> Dict:
        """Create test document data"""
        return {
            "content": content,
            "content_type": doc_type,
            "filename": f"test_{doc_type}.pdf",
            "metadata": {"page_count": 1}
        }
```

## Testing Strategy Summary

### Unit Tests (Fast, Isolated)
- Mock external dependencies
- Test individual component logic
- Aim for >90% code coverage
- Run in <30 seconds

### Integration Tests (End-to-End)
- Test component interactions
- Use real databases (test instances)
- Skip if optional services unavailable
- Run in <5 minutes

### Performance Tests (Benchmarks)
- Measure latency and throughput
- Set performance regression gates
- Run on PR and releases
- Compare against baselines

### CI Strategy
- Unit tests on every commit
- Integration tests on PR
- Performance tests on PR to main
- Nightly full test suite with coverage