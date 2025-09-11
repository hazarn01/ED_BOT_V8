# PRP 16: Implement HybridRetriever

## Problem Statement
Need to implement a retrieval system that combines keyword search (Elasticsearch) with semantic search (pgvector) and intelligently fuses results based on query type. Different medical query types benefit from different search strategies - exact matches for forms/protocols vs semantic similarity for summaries.

## Success Criteria
- Keyword and semantic searches execute in parallel
- Results fused with per-QueryType configurable weights
- FORM queries prioritize exact keyword hits
- SUMMARY queries include semantically similar content
- Graceful fallback to pgvector-only when ES unavailable
- No regression in existing retrieval quality

## Implementation Approach

### 1. HybridRetriever Core
```python
# src/pipeline/hybrid_retriever.py
from typing import List, Dict, Tuple
from dataclasses import dataclass
import asyncio
from src.pipeline.retriever import RAGRetriever
from src.search.elasticsearch_client import ElasticsearchClient

@dataclass
class RetrievalResult:
    """Unified result from retrieval"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    source: str  # "keyword" or "semantic"
    metadata: Dict

class HybridRetriever:
    """Combines keyword and semantic search with query-aware fusion"""
    
    # Query-type specific weights (keyword_weight, semantic_weight)
    FUSION_WEIGHTS = {
        QueryType.FORM_RETRIEVAL: (0.8, 0.2),      # Heavy keyword bias
        QueryType.PROTOCOL_STEPS: (0.7, 0.3),      # Prefer exact protocol names
        QueryType.CONTACT_LOOKUP: (0.9, 0.1),      # Almost pure keyword
        QueryType.CRITERIA_CHECK: (0.4, 0.6),      # Balance both
        QueryType.DOSAGE_LOOKUP: (0.6, 0.4),       # Slight keyword preference
        QueryType.SUMMARY_REQUEST: (0.3, 0.7),     # Heavy semantic bias
    }
    
    def __init__(
        self,
        rag_retriever: RAGRetriever,
        es_client: Optional[ElasticsearchClient],
        settings: Settings
    ):
        self.rag_retriever = rag_retriever
        self.es_client = es_client
        self.settings = settings
        self.hybrid_enabled = es_client and es_client.enabled
        
    async def retrieve(
        self,
        query: str,
        query_type: QueryType,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """Main retrieval method with hybrid search"""
        
        # Fallback to semantic-only if hybrid disabled
        if not self.hybrid_enabled:
            return await self._semantic_only(query, top_k, filters)
            
        # Run both searches in parallel
        keyword_task = asyncio.create_task(
            self._keyword_search(query, query_type, top_k * 2, filters)
        )
        semantic_task = asyncio.create_task(
            self._semantic_search(query, top_k * 2, filters)
        )
        
        # Wait for both with timeout
        try:
            keyword_results, semantic_results = await asyncio.gather(
                keyword_task,
                semantic_task,
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return await self._semantic_only(query, top_k, filters)
            
        # Handle partial failures
        if isinstance(keyword_results, Exception):
            logger.warning(f"Keyword search failed: {keyword_results}")
            keyword_results = []
        if isinstance(semantic_results, Exception):
            logger.warning(f"Semantic search failed: {semantic_results}")
            semantic_results = []
            
        # Fuse results
        return self._fuse_results(
            keyword_results,
            semantic_results,
            query_type,
            top_k
        )
        
    async def _keyword_search(
        self,
        query: str,
        query_type: QueryType,
        top_k: int,
        filters: Optional[Dict]
    ) -> List[RetrievalResult]:
        """Elasticsearch keyword search"""
        es = self.es_client.get_client()
        if not es:
            return []
            
        # Build ES query based on query type
        es_query = self._build_es_query(query, query_type, filters)
        
        try:
            response = await asyncio.to_thread(
                es.search,
                index=f"{self.settings.elasticsearch_index_prefix}_chunks",
                body=es_query,
                size=top_k
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                results.append(RetrievalResult(
                    chunk_id=hit["_source"]["id"],
                    document_id=hit["_source"]["document_id"],
                    content=hit["_source"]["content"],
                    score=hit["_score"],
                    source="keyword",
                    metadata=hit["_source"].get("metadata", {})
                ))
            return results
            
        except Exception as e:
            logger.error(f"ES search failed: {e}")
            return []
            
    async def _semantic_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict]
    ) -> List[RetrievalResult]:
        """Pgvector semantic search"""
        chunks = await self.rag_retriever.retrieve_chunks(query, top_k, filters)
        
        results = []
        for chunk, score in chunks:
            results.append(RetrievalResult(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                content=chunk.content,
                score=score,
                source="semantic",
                metadata=chunk.meta or {}
            ))
        return results
        
    def _build_es_query(
        self,
        query: str,
        query_type: QueryType,
        filters: Optional[Dict]
    ) -> Dict:
        """Build Elasticsearch query based on query type"""
        
        # Base query structure
        es_query = {
            "query": {
                "bool": {
                    "should": [],
                    "filter": []
                }
            }
        }
        
        # Query-type specific search fields
        if query_type == QueryType.FORM_RETRIEVAL:
            # Exact match on form names
            es_query["query"]["bool"]["should"] = [
                {"match": {"form_name": {"query": query, "boost": 3}}},
                {"match": {"filename.keyword": {"query": query, "boost": 2}}},
                {"match": {"content": query}}
            ]
        elif query_type == QueryType.PROTOCOL_STEPS:
            # Protocol name matching
            es_query["query"]["bool"]["should"] = [
                {"match": {"protocol_name": {"query": query, "boost": 3}}},
                {"match": {"title.keyword": {"query": query, "boost": 2}}},
                {"match": {"content": query}}
            ]
        else:
            # General text search
            es_query["query"]["bool"]["should"] = [
                {"match": {"content": {"query": query, "analyzer": "medical_analyzer"}}},
                {"match": {"content.exact": {"query": query, "boost": 0.5}}}
            ]
            
        # Add filters
        if filters:
            if "content_type" in filters:
                es_query["query"]["bool"]["filter"].append(
                    {"term": {"content_type": filters["content_type"]}}
                )
                
        return es_query
        
    def _fuse_results(
        self,
        keyword_results: List[RetrievalResult],
        semantic_results: List[RetrievalResult],
        query_type: QueryType,
        top_k: int
    ) -> List[RetrievalResult]:
        """Fuse keyword and semantic results with query-aware weights"""
        
        # Get fusion weights for this query type
        kw_weight, sem_weight = self.FUSION_WEIGHTS.get(
            query_type,
            (0.5, 0.5)  # Default balanced
        )
        
        # Normalize scores within each result set
        keyword_results = self._normalize_scores(keyword_results)
        semantic_results = self._normalize_scores(semantic_results)
        
        # Create unified score map
        chunk_scores = {}
        
        # Add keyword results
        for result in keyword_results:
            chunk_scores[result.chunk_id] = {
                "result": result,
                "fused_score": result.score * kw_weight,
                "sources": ["keyword"]
            }
            
        # Add/merge semantic results
        for result in semantic_results:
            if result.chunk_id in chunk_scores:
                # Combine scores for chunks found by both methods
                chunk_scores[result.chunk_id]["fused_score"] += result.score * sem_weight
                chunk_scores[result.chunk_id]["sources"].append("semantic")
            else:
                chunk_scores[result.chunk_id] = {
                    "result": result,
                    "fused_score": result.score * sem_weight,
                    "sources": ["semantic"]
                }
                
        # Sort by fused score and return top k
        sorted_chunks = sorted(
            chunk_scores.values(),
            key=lambda x: x["fused_score"],
            reverse=True
        )[:top_k]
        
        # Add fusion metadata
        results = []
        for chunk_data in sorted_chunks:
            result = chunk_data["result"]
            result.score = chunk_data["fused_score"]
            result.metadata["retrieval_sources"] = chunk_data["sources"]
            results.append(result)
            
        return results
        
    def _normalize_scores(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Normalize scores to 0-1 range"""
        if not results:
            return results
            
        max_score = max(r.score for r in results)
        min_score = min(r.score for r in results)
        
        if max_score == min_score:
            # All scores are the same
            for r in results:
                r.score = 1.0
        else:
            # Min-max normalization
            for r in results:
                r.score = (r.score - min_score) / (max_score - min_score)
                
        return results
```

### 2. Integration with QueryRouter
```python
# src/pipeline/router.py (modifications)
class QueryRouter:
    def __init__(self, classifier, retriever, llm_client, settings):
        self.classifier = classifier
        
        # Use hybrid retriever if available
        if settings.search_backend == "hybrid":
            es_client = ElasticsearchClient(settings)
            self.retriever = HybridRetriever(retriever, es_client, settings)
        else:
            self.retriever = retriever
            
    async def route_query(self, query: str) -> QueryResponse:
        """Route with hybrid retrieval"""
        classification = await self.classifier.classify_query(query)
        
        # Retrieve with query-aware fusion
        results = await self.retriever.retrieve(
            query=query,
            query_type=classification.query_type,
            top_k=10,
            filters=self._get_filters(classification)
        )
        
        # Continue with existing response generation...
```

### 3. Configuration
```python
# src/config/settings.py (additions)
class Settings(BaseSettings):
    # Fusion weight overrides (optional)
    fusion_weights_json: Optional[str] = Field(
        default=None,
        description="JSON string of custom fusion weights per query type"
    )
    
    @property
    def fusion_weights(self) -> Dict:
        """Parse custom fusion weights if provided"""
        if self.fusion_weights_json:
            return json.loads(self.fusion_weights_json)
        return {}
```

## Testing Strategy
```python
# tests/unit/test_hybrid_retriever.py
async def test_fusion_weights_by_query_type():
    """Test that different query types use appropriate weights"""
    retriever = HybridRetriever(rag, es, settings)
    
    # Mock results
    keyword_results = [
        RetrievalResult("1", "d1", "exact match", 1.0, "keyword", {}),
    ]
    semantic_results = [
        RetrievalResult("2", "d2", "similar content", 0.8, "semantic", {}),
    ]
    
    # Test FORM (keyword-heavy)
    form_fused = retriever._fuse_results(
        keyword_results, semantic_results,
        QueryType.FORM_RETRIEVAL, 10
    )
    assert form_fused[0].chunk_id == "1"  # Keyword result wins
    
    # Test SUMMARY (semantic-heavy)
    summary_fused = retriever._fuse_results(
        keyword_results, semantic_results,
        QueryType.SUMMARY_REQUEST, 10
    )
    # Semantic might win despite lower raw score due to weights

async def test_fallback_on_es_failure():
    """Test graceful degradation when ES unavailable"""
    es_client.enabled = False
    retriever = HybridRetriever(rag, es_client, settings)
    
    results = await retriever.retrieve("test query", QueryType.PROTOCOL_STEPS)
    assert all(r.source == "semantic" for r in results)
```

## Performance Metrics
```python
# src/pipeline/hybrid_retriever.py (additions)
from prometheus_client import Histogram, Counter

hybrid_latency = Histogram(
    "hybrid_retrieval_latency_seconds",
    "Latency of hybrid retrieval",
    ["search_type", "query_type"]
)

fusion_source_counter = Counter(
    "retrieval_source_usage",
    "Count of results by source after fusion",
    ["source", "query_type"]
)
```

## Rollback Plan
1. Set `SEARCH_BACKEND=pgvector` to disable hybrid
2. System immediately falls back to semantic-only
3. No code changes needed
4. Monitor retrieval quality metrics for comparison