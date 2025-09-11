"""Metrics collection for semantic cache.

Extends the existing observability system with semantic cache specific metrics.
"""

from typing import Any, Dict

from src.utils.logging import get_logger
from src.utils.observability import metrics as global_metrics

logger = get_logger(__name__)


class SemanticCacheMetrics:
    """Metrics collector for semantic cache operations."""
    
    def __init__(self):
        """Initialize semantic cache metrics."""
        self.metrics = {
            "semantic_cache_hits": 0,
            "semantic_cache_misses": 0,
            "semantic_cache_sets": 0,
            "semantic_cache_evictions": 0,
            "similarity_scores": [],
            "cache_sizes": {},  # Per query type
            "hit_rates_by_type": {},  # Per query type
        }
    
    def record_cache_hit(self, query_type: str, similarity: float):
        """Record a semantic cache hit.
        
        Args:
            query_type: Type of query that hit cache
            similarity: Similarity score for the hit
        """
        self.metrics["semantic_cache_hits"] += 1
        self.metrics["similarity_scores"].append({
            "score": similarity,
            "query_type": query_type,
            "hit": True
        })
        
        # Keep only last 1000 similarity scores
        if len(self.metrics["similarity_scores"]) > 1000:
            self.metrics["similarity_scores"] = self.metrics["similarity_scores"][-1000:]
        
        # Update per-type metrics
        if query_type not in self.metrics["hit_rates_by_type"]:
            self.metrics["hit_rates_by_type"][query_type] = {"hits": 0, "misses": 0}
        self.metrics["hit_rates_by_type"][query_type]["hits"] += 1
        
        logger.info(
            "Semantic cache hit",
            extra_fields={
                "query_type": query_type,
                "similarity": similarity,
                "cache_hits": self.metrics["semantic_cache_hits"]
            }
        )
    
    def record_cache_miss(self, query_type: str):
        """Record a semantic cache miss.
        
        Args:
            query_type: Type of query that missed cache
        """
        self.metrics["semantic_cache_misses"] += 1
        
        # Update per-type metrics
        if query_type not in self.metrics["hit_rates_by_type"]:
            self.metrics["hit_rates_by_type"][query_type] = {"hits": 0, "misses": 0}
        self.metrics["hit_rates_by_type"][query_type]["misses"] += 1
        
        logger.debug(
            "Semantic cache miss",
            extra_fields={
                "query_type": query_type,
                "cache_misses": self.metrics["semantic_cache_misses"]
            }
        )
    
    def record_cache_set(self, query_type: str, confidence: float):
        """Record a semantic cache set operation.
        
        Args:
            query_type: Type of query being cached
            confidence: Confidence score of cached response
        """
        self.metrics["semantic_cache_sets"] += 1
        
        logger.debug(
            "Semantic cache set",
            extra_fields={
                "query_type": query_type,
                "confidence": confidence,
                "cache_sets": self.metrics["semantic_cache_sets"]
            }
        )
    
    def record_cache_eviction(self, query_type: str, reason: str = "expired"):
        """Record a cache eviction.
        
        Args:
            query_type: Type of query evicted
            reason: Reason for eviction (expired, manual, etc.)
        """
        self.metrics["semantic_cache_evictions"] += 1
        
        logger.debug(
            "Semantic cache eviction",
            extra_fields={
                "query_type": query_type,
                "reason": reason,
                "total_evictions": self.metrics["semantic_cache_evictions"]
            }
        )
    
    def update_cache_size(self, query_type: str, size: int):
        """Update cache size for a query type.
        
        Args:
            query_type: Query type
            size: Current number of cached entries for this type
        """
        self.metrics["cache_sizes"][query_type] = size
    
    def get_cache_hit_rate(self, query_type: str = None) -> float:
        """Get cache hit rate.
        
        Args:
            query_type: Optional specific query type, None for overall
            
        Returns:
            Hit rate as percentage (0-100)
        """
        if query_type:
            type_metrics = self.metrics["hit_rates_by_type"].get(query_type, {"hits": 0, "misses": 0})
            total = type_metrics["hits"] + type_metrics["misses"]
            return (type_metrics["hits"] / total * 100) if total > 0 else 0
        else:
            total = self.metrics["semantic_cache_hits"] + self.metrics["semantic_cache_misses"]
            return (self.metrics["semantic_cache_hits"] / total * 100) if total > 0 else 0
    
    def get_average_similarity(self, query_type: str = None) -> float:
        """Get average similarity score for cache hits.
        
        Args:
            query_type: Optional specific query type, None for overall
            
        Returns:
            Average similarity score
        """
        scores = self.metrics["similarity_scores"]
        
        if query_type:
            scores = [s for s in scores if s["query_type"] == query_type and s["hit"]]
        else:
            scores = [s for s in scores if s["hit"]]
        
        if scores:
            return sum(s["score"] for s in scores) / len(scores)
        return 0.0
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of semantic cache metrics.
        
        Returns:
            Dictionary with metrics summary
        """
        total_requests = self.metrics["semantic_cache_hits"] + self.metrics["semantic_cache_misses"]
        hit_rate = self.get_cache_hit_rate()
        avg_similarity = self.get_average_similarity()
        
        # Per-type hit rates
        type_hit_rates = {}
        for query_type, type_metrics in self.metrics["hit_rates_by_type"].items():
            total_type = type_metrics["hits"] + type_metrics["misses"]
            type_hit_rates[query_type] = {
                "hit_rate": (type_metrics["hits"] / total_type * 100) if total_type > 0 else 0,
                "hits": type_metrics["hits"],
                "misses": type_metrics["misses"],
                "avg_similarity": self.get_average_similarity(query_type)
            }
        
        return {
            "semantic_cache": {
                "total_requests": total_requests,
                "hits": self.metrics["semantic_cache_hits"],
                "misses": self.metrics["semantic_cache_misses"],
                "hit_rate_percent": hit_rate,
                "sets": self.metrics["semantic_cache_sets"],
                "evictions": self.metrics["semantic_cache_evictions"],
                "avg_similarity": avg_similarity,
                "cache_sizes": self.metrics["cache_sizes"],
                "by_type": type_hit_rates
            }
        }


# Global semantic cache metrics instance
semantic_cache_metrics = SemanticCacheMetrics()


def extend_global_metrics():
    """Extend the global metrics collector with semantic cache metrics."""
    
    # Add method to get semantic cache metrics to global metrics
    original_get_summary = global_metrics.get_metrics_summary
    
    def extended_get_summary():
        """Extended metrics summary including semantic cache."""
        summary = original_get_summary()
        summary.update(semantic_cache_metrics.get_metrics_summary())
        return summary
    
    global_metrics.get_metrics_summary = extended_get_summary
    
    # Add convenience methods to global metrics
    global_metrics.record_semantic_cache_hit = semantic_cache_metrics.record_cache_hit
    global_metrics.record_semantic_cache_miss = semantic_cache_metrics.record_cache_miss
    global_metrics.record_semantic_cache_set = semantic_cache_metrics.record_cache_set
    global_metrics.record_semantic_cache_eviction = semantic_cache_metrics.record_cache_eviction
    global_metrics.update_semantic_cache_size = semantic_cache_metrics.update_cache_size


# Initialize extended metrics on import
extend_global_metrics()
