"""Hybrid retriever combining keyword and semantic search with query-aware fusion."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.config.settings import Settings
from src.models.query_types import QueryType
from src.pipeline.rag_retriever import RAGRetriever
from src.search.elasticsearch_client import ElasticsearchClient

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Unified result from retrieval."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    source: str  # "keyword" or "semantic"
    metadata: Dict[str, Any]


@dataclass
class RetrievalMetrics:
    """Performance metrics for retrieval operations."""
    total_requests: int = 0
    hybrid_requests: int = 0
    semantic_only_requests: int = 0
    keyword_failures: int = 0
    semantic_failures: int = 0
    total_latency_seconds: float = 0.0
    keyword_latency_seconds: float = 0.0
    semantic_latency_seconds: float = 0.0
    fusion_latency_seconds: float = 0.0
    
    # Per-query-type stats
    query_type_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def record_request(self, query_type: QueryType, is_hybrid: bool, total_time: float, 
                      keyword_time: float = 0, semantic_time: float = 0, fusion_time: float = 0):
        """Record a retrieval request with timing."""
        self.total_requests += 1
        self.total_latency_seconds += total_time
        
        if is_hybrid:
            self.hybrid_requests += 1
            self.keyword_latency_seconds += keyword_time
            self.semantic_latency_seconds += semantic_time
            self.fusion_latency_seconds += fusion_time
        else:
            self.semantic_only_requests += 1
            self.semantic_latency_seconds += semantic_time
            
        # Track per-query-type stats
        qt_key = query_type.value
        if qt_key not in self.query_type_stats:
            self.query_type_stats[qt_key] = {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0
            }
            
        self.query_type_stats[qt_key]["count"] += 1
        self.query_type_stats[qt_key]["total_time"] += total_time
        self.query_type_stats[qt_key]["avg_time"] = (
            self.query_type_stats[qt_key]["total_time"] / 
            self.query_type_stats[qt_key]["count"]
        )
    
    def record_failure(self, failure_type: str):
        """Record a search failure."""
        if failure_type == "keyword":
            self.keyword_failures += 1
        elif failure_type == "semantic":
            self.semantic_failures += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if self.total_requests == 0:
            return {"message": "No requests recorded"}
            
        return {
            "total_requests": self.total_requests,
            "hybrid_requests": self.hybrid_requests,
            "semantic_only_requests": self.semantic_only_requests,
            "keyword_failures": self.keyword_failures,
            "semantic_failures": self.semantic_failures,
            "avg_total_latency_ms": (self.total_latency_seconds / self.total_requests) * 1000,
            "avg_keyword_latency_ms": (self.keyword_latency_seconds / max(1, self.hybrid_requests)) * 1000,
            "avg_semantic_latency_ms": (self.semantic_latency_seconds / self.total_requests) * 1000,
            "avg_fusion_latency_ms": (self.fusion_latency_seconds / max(1, self.hybrid_requests)) * 1000,
            "hybrid_success_rate": (
                (self.hybrid_requests - self.keyword_failures) / max(1, self.hybrid_requests) * 100
            ),
            "query_type_performance": self.query_type_stats
        }


class HybridRetriever:
    """Combines keyword and semantic search with query-aware fusion."""
    
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
        """Initialize hybrid retriever.
        
        Args:
            rag_retriever: The existing RAG retriever for semantic search
            es_client: Elasticsearch client for keyword search
            settings: Application settings
        """
        self.rag_retriever = rag_retriever
        self.es_client = es_client
        self.settings = settings
        self.hybrid_enabled = es_client and es_client.is_available()
        self.metrics = RetrievalMetrics()
        
        # Load custom fusion weights if provided
        if hasattr(settings, 'fusion_weights_json') and settings.fusion_weights_json:
            try:
                custom_weights = json.loads(settings.fusion_weights_json)
                self.FUSION_WEIGHTS.update(custom_weights)
                logger.info(f"Loaded custom fusion weights: {custom_weights}")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid fusion weights JSON: {e}")
        
        logger.info(f"HybridRetriever initialized, hybrid_enabled: {self.hybrid_enabled}")
        
    async def retrieve(
        self,
        query: str,
        query_type: QueryType,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """Main retrieval method with hybrid search.
        
        Args:
            query: Search query
            query_type: Type of query for fusion weight selection
            top_k: Number of results to return
            filters: Optional filters for search
            
        Returns:
            List of unified retrieval results
        """
        start_time = time.time()
        keyword_time = 0.0
        semantic_time = 0.0
        fusion_time = 0.0
        
        try:
            # Fallback to semantic-only if hybrid disabled
            if not self.hybrid_enabled:
                logger.info("Hybrid search disabled, falling back to semantic-only")
                semantic_start = time.time()
                results = await self._semantic_only(query, top_k, filters)
                semantic_time = time.time() - semantic_start
                
                # Record metrics for semantic-only
                total_time = time.time() - start_time
                self.metrics.record_request(query_type, False, total_time, 
                                          semantic_time=semantic_time)
                return results
                
            # Run both searches in parallel
            logger.info(f"Running hybrid search for query_type: {query_type.value}")
            
            # Time the parallel searches
            time.time()
            keyword_task = asyncio.create_task(
                self._timed_keyword_search(query, query_type, top_k * 2, filters)
            )
            semantic_task = asyncio.create_task(
                self._timed_semantic_search(query, top_k * 2, filters)
            )
            
            # Wait for both with timeout
            try:
                (keyword_results, kw_time), (semantic_results, sem_time) = await asyncio.gather(
                    keyword_task,
                    semantic_task,
                    return_exceptions=True
                )
                keyword_time = kw_time if not isinstance(keyword_results, Exception) else 0
                semantic_time = sem_time if not isinstance(semantic_results, Exception) else 0
            except Exception as e:
                logger.error(f"Hybrid search failed: {e}")
                semantic_start = time.time()
                results = await self._semantic_only(query, top_k, filters)
                semantic_time = time.time() - semantic_start
                
                total_time = time.time() - start_time
                self.metrics.record_request(query_type, False, total_time, 
                                          semantic_time=semantic_time)
                return results
                
            # Handle partial failures
            if isinstance(keyword_results, Exception):
                logger.warning(f"Keyword search failed: {keyword_results}")
                self.metrics.record_failure("keyword")
                keyword_results = []
                keyword_time = 0
            if isinstance(semantic_results, Exception):
                logger.warning(f"Semantic search failed: {semantic_results}")
                self.metrics.record_failure("semantic")
                semantic_results = []
                semantic_time = 0
                
            # If both failed, try semantic fallback
            if not keyword_results and not semantic_results:
                logger.warning("Both search methods failed, trying semantic fallback")
                semantic_start = time.time()
                results = await self._semantic_only(query, top_k, filters)
                semantic_time = time.time() - semantic_start
                
                total_time = time.time() - start_time
                self.metrics.record_request(query_type, False, total_time, 
                                          semantic_time=semantic_time)
                return results
                
            # Fuse results
            fusion_start = time.time()
            fused_results = self._fuse_results(
                keyword_results,
                semantic_results,
                query_type,
                top_k
            )
            fusion_time = time.time() - fusion_start
            
            logger.info(f"Hybrid search returned {len(fused_results)} results")
            
            # Record successful hybrid request metrics
            total_time = time.time() - start_time
            self.metrics.record_request(query_type, True, total_time, 
                                      keyword_time, semantic_time, fusion_time)
            
            return fused_results
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed unexpectedly: {e}")
            # Try semantic fallback as last resort
            semantic_start = time.time()
            results = await self._semantic_only(query, top_k, filters)
            semantic_time = time.time() - semantic_start
            
            total_time = time.time() - start_time
            self.metrics.record_request(query_type, False, total_time, 
                                      semantic_time=semantic_time)
            return results
        
    async def _keyword_search(
        self,
        query: str,
        query_type: QueryType,
        top_k: int,
        filters: Optional[Dict]
    ) -> List[RetrievalResult]:
        """Elasticsearch keyword search."""
        if not self.es_client or not self.es_client.is_available():
            return []
            
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
                source_data = hit["_source"]
                results.append(RetrievalResult(
                    chunk_id=source_data["id"],
                    document_id=source_data["document_id"],
                    content=source_data["content"],
                    score=hit["_score"],
                    source="keyword",
                    metadata=source_data.get("metadata", {})
                ))
                
            logger.info(f"Keyword search returned {len(results)} results")
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
        """Pgvector semantic search using existing RAG retriever."""
        try:
            # Determine content type filter from filters
            content_type = filters.get("content_type") if filters else None
            
            # Use the existing semantic search method (synchronous)
            search_results = self.rag_retriever.semantic_search(
                query=query,
                k=top_k,
                content_type=content_type,
                threshold=0.6  # Use lower threshold for broader results
            )
            
            results = []
            for result in search_results:
                results.append(RetrievalResult(
                    chunk_id=str(result["chunk_id"]),
                    document_id=str(result["document_id"]),
                    content=result["content"],
                    score=result["similarity"],
                    source="semantic",
                    metadata=result.get("metadata", {})
                ))
                
            logger.info(f"Semantic search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    async def _timed_keyword_search(
        self,
        query: str,
        query_type: QueryType,
        top_k: int,
        filters: Optional[Dict]
    ) -> Tuple[List[RetrievalResult], float]:
        """Keyword search with timing."""
        start_time = time.time()
        try:
            results = await self._keyword_search(query, query_type, top_k, filters)
            elapsed = time.time() - start_time
            return results, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            return e, elapsed
    
    async def _timed_semantic_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict]
    ) -> Tuple[List[RetrievalResult], float]:
        """Semantic search with timing."""
        start_time = time.time()
        try:
            results = await self._semantic_search(query, top_k, filters)
            elapsed = time.time() - start_time
            return results, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            return e, elapsed
        
    async def _semantic_only(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict]
    ) -> List[RetrievalResult]:
        """Fallback to semantic-only search."""
        logger.info("Using semantic-only fallback")
        return await self._semantic_search(query, top_k, filters)
        
    def _build_es_query(
        self,
        query: str,
        query_type: QueryType,
        filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """Build Elasticsearch query based on query type."""
        
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
            # Exact match on form names and filenames
            es_query["query"]["bool"]["should"] = [
                {"match": {"form_name": {"query": query, "boost": 3}}},
                {"match": {"filename.keyword": {"query": query, "boost": 2}}},
                {"match": {"content": query}}
            ]
        elif query_type == QueryType.PROTOCOL_STEPS:
            # Protocol name matching with emphasis on titles
            es_query["query"]["bool"]["should"] = [
                {"match": {"protocol_name": {"query": query, "boost": 3}}},
                {"match": {"title.keyword": {"query": query, "boost": 2}}},
                {"match": {"content": query}}
            ]
        elif query_type == QueryType.CONTACT_LOOKUP:
            # Contact and specialty matching
            es_query["query"]["bool"]["should"] = [
                {"match": {"specialty": {"query": query, "boost": 3}}},
                {"match": {"contact_info": {"query": query, "boost": 2}}},
                {"match": {"content": query}}
            ]
        else:
            # General text search with medical analyzer if available
            es_query["query"]["bool"]["should"] = [
                {"match": {"content": {"query": query, "analyzer": "standard"}}},
                {"match": {"content.exact": {"query": query, "boost": 0.5}}}
            ]
            
        # Add filters
        if filters:
            if "content_type" in filters:
                es_query["query"]["bool"]["filter"].append(
                    {"term": {"content_type": filters["content_type"]}}
                )
            if "document_id" in filters:
                es_query["query"]["bool"]["filter"].append(
                    {"term": {"document_id": filters["document_id"]}}
                )
                
        return es_query
        
    def _fuse_results(
        self,
        keyword_results: List[RetrievalResult],
        semantic_results: List[RetrievalResult],
        query_type: QueryType,
        top_k: int
    ) -> List[RetrievalResult]:
        """Fuse keyword and semantic results with query-aware weights."""
        
        # Get fusion weights for this query type
        kw_weight, sem_weight = self.FUSION_WEIGHTS.get(
            query_type,
            (0.5, 0.5)  # Default balanced
        )
        
        logger.info(f"Using fusion weights for {query_type.value}: keyword={kw_weight}, semantic={sem_weight}")
        
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
                # Use the result with better individual score for metadata
                if result.score > chunk_scores[result.chunk_id]["result"].score:
                    chunk_scores[result.chunk_id]["result"] = result
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
        """Normalize scores to 0-1 range using min-max normalization."""
        if not results:
            return results
            
        scores = [r.score for r in results]
        max_score = max(scores)
        min_score = min(scores)
        
        if max_score == min_score:
            # All scores are the same, set to 1.0
            for r in results:
                r.score = 1.0
        else:
            # Min-max normalization
            for r in results:
                r.score = (r.score - min_score) / (max_score - min_score)
                
        return results

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics and health information."""
        stats = {
            "hybrid_enabled": self.hybrid_enabled,
            "elasticsearch_available": self.es_client.is_available() if self.es_client else False,
            "fusion_weights": {
                qt.value if hasattr(qt, 'value') else str(qt): weights 
                for qt, weights in self.FUSION_WEIGHTS.items()
            },
            "performance_metrics": self.metrics.get_summary()
        }
        
        if self.es_client:
            health = self.es_client.get_cluster_health()
            if health:
                stats["elasticsearch_health"] = health
                
        return stats
        
    def reset_metrics(self):
        """Reset performance metrics."""
        self.metrics = RetrievalMetrics()
        logger.info("Hybrid retrieval metrics reset")
