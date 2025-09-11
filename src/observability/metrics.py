"""
Metrics collection framework for EDBotv8.

Provides comprehensive monitoring with Prometheus metrics for all system components.
"""

try:
    from prometheus_client import Counter, Enum, Gauge, Histogram, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, amount=1): pass
        def labels(self, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, amount): pass
        def time(self): return self
        def labels(self, **kwargs): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, value): pass
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def labels(self, **kwargs): return self
    
    class Enum:
        def __init__(self, *args, **kwargs): pass
        def state(self, value): pass
        def labels(self, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, value): pass
        def labels(self, **kwargs): return self
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Dict

logger = logging.getLogger(__name__)

# Core Query Metrics
query_total = Counter(
    'edbot_queries_total',
    'Total number of queries processed',
    ['query_type', 'status', 'cache_hit']
)

query_duration = Histogram(
    'edbot_query_duration_seconds',
    'Query processing duration',
    ['query_type', 'backend'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

query_confidence = Histogram(
    'edbot_query_confidence',
    'Query response confidence scores',
    ['query_type'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Hybrid Search Metrics
hybrid_retrieval_duration = Histogram(
    'edbot_hybrid_retrieval_seconds',
    'Hybrid retrieval component duration',
    ['component'],  # 'keyword', 'semantic', 'fusion'
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

hybrid_result_sources = Counter(
    'edbot_hybrid_results_total',
    'Sources of hybrid search results after fusion',
    ['query_type', 'source']  # source: 'keyword', 'semantic', 'both'
)

search_backend_status = Enum(
    'edbot_search_backend_status',
    'Current search backend status',
    ['backend'],  # 'pgvector', 'hybrid'
    states=['healthy', 'degraded', 'failed']
)

# Elasticsearch Metrics
elasticsearch_operations = Counter(
    'edbot_elasticsearch_operations_total',
    'Elasticsearch operations',
    ['operation', 'status']  # operation: 'search', 'index', 'bulk'
)

elasticsearch_duration = Histogram(
    'edbot_elasticsearch_duration_seconds',
    'Elasticsearch operation duration',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# Cache Metrics
cache_operations = Counter(
    'edbot_cache_operations_total',
    'Cache operations',
    ['operation', 'query_type', 'result']  # operation: 'get', 'set'
)

cache_hit_rate = Gauge(
    'edbot_cache_hit_rate',
    'Cache hit rate by query type',
    ['query_type']
)

cache_similarity_scores = Histogram(
    'edbot_cache_similarity_scores',
    'Similarity scores for cache hits',
    ['query_type'],
    buckets=[0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0]
)

# Table Extraction Metrics
table_extraction_duration = Histogram(
    'edbot_table_extraction_seconds',
    'Table extraction processing time',
    ['extraction_method'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

tables_extracted = Counter(
    'edbot_tables_extracted_total',
    'Number of tables extracted',
    ['table_type', 'confidence_bucket']  # confidence_bucket: 'high', 'medium', 'low'
)

# Source Highlighting Metrics
highlighting_duration = Histogram(
    'edbot_highlighting_duration_seconds',
    'Source highlighting processing time',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5]
)

highlights_generated = Counter(
    'edbot_highlights_generated_total',
    'Number of highlights generated per response',
    ['query_type']
)

# Medical Safety Metrics
safety_alerts = Counter(
    'edbot_safety_alerts_total',
    'Medical safety alerts triggered',
    ['alert_type', 'severity']  # alert_type: 'low_confidence', 'phi_detected', 'dosage_warning'
)

phi_scrubbing_events = Counter(
    'edbot_phi_scrubbing_total',
    'PHI scrubbing events',
    ['component']  # component: 'query', 'response', 'cache'
)

# Feature Flag Metrics
feature_flag_changes = Counter(
    'edbot_feature_flag_changes_total',
    'Feature flag changes',
    ['flag_name', 'new_value']
)

feature_usage = Counter(
    'edbot_feature_usage_total',
    'Feature usage by request',
    ['feature_name', 'enabled']
)

# LLM Backend Metrics
llm_backend_requests = Counter(
    'edbot_llm_requests_total',
    'LLM backend requests',
    ['backend', 'status']  # backend: 'gpt-oss', 'ollama', 'azure'
)

llm_backend_duration = Histogram(
    'edbot_llm_duration_seconds',
    'LLM request duration',
    ['backend'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

llm_tokens = Counter(
    'edbot_llm_tokens_total',
    'LLM tokens consumed',
    ['backend', 'type']  # type: 'input', 'output'
)

# System Health Metrics
system_health = Gauge(
    'edbot_system_health',
    'Overall system health score (0-1)',
)

component_health = Gauge(
    'edbot_component_health',
    'Individual component health status',
    ['component']  # component: 'database', 'redis', 'elasticsearch', 'llm'
)

# Performance Metrics
response_time_percentiles = Histogram(
    'edbot_response_time_percentiles',
    'Response time percentiles',
    ['endpoint'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

concurrent_requests = Gauge(
    'edbot_concurrent_requests',
    'Number of concurrent requests being processed'
)


class MetricsCollector:
    """Central metrics collection and instrumentation"""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_metrics', True) if settings else True
        
    @contextmanager
    def time_operation(self, metric: Histogram, labels: Dict[str, str]):
        """Context manager for timing operations"""
        if not self.enabled:
            yield
            return
            
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            metric.labels(**labels).observe(duration)
            
    def track_query(self, query_type: str, duration: float, confidence: float, 
                   cache_hit: bool = False, backend: str = "hybrid"):
        """Track query metrics"""
        if not self.enabled:
            return
            
        status = "success"  # Could be enhanced with error tracking
        cache_status = "hit" if cache_hit else "miss"
        
        query_total.labels(
            query_type=query_type,
            status=status,
            cache_hit=cache_status
        ).inc()
        
        query_duration.labels(
            query_type=query_type,
            backend=backend
        ).observe(duration)
        
        query_confidence.labels(
            query_type=query_type
        ).observe(confidence)
        
    def track_hybrid_search(self, query_type: str, keyword_time: float, 
                          semantic_time: float, fusion_time: float,
                          result_sources: Dict[str, int]):
        """Track hybrid search component performance"""
        if not self.enabled:
            return
            
        # Component timings
        hybrid_retrieval_duration.labels(component="keyword").observe(keyword_time)
        hybrid_retrieval_duration.labels(component="semantic").observe(semantic_time)
        hybrid_retrieval_duration.labels(component="fusion").observe(fusion_time)
        
        # Result source distribution
        for source, count in result_sources.items():
            hybrid_result_sources.labels(
                query_type=query_type,
                source=source
            ).inc(count)
            
    def track_cache_operation(self, operation: str, query_type: str, 
                            hit: bool = None, similarity: float = None):
        """Track cache operations"""
        if not self.enabled:
            return
            
        result = "hit" if hit else "miss" if hit is not None else "set"
        
        cache_operations.labels(
            operation=operation,
            query_type=query_type,
            result=result
        ).inc()
        
        if similarity is not None:
            cache_similarity_scores.labels(
                query_type=query_type
            ).observe(similarity)
            
    def track_table_extraction(self, method: str, duration: float, 
                             table_count: int, table_type: str = "unknown",
                             confidence: float = 0.0):
        """Track table extraction metrics"""
        if not self.enabled:
            return
            
        table_extraction_duration.labels(
            extraction_method=method
        ).observe(duration)
        
        # Determine confidence bucket
        if confidence >= 0.8:
            confidence_bucket = "high"
        elif confidence >= 0.6:
            confidence_bucket = "medium"
        else:
            confidence_bucket = "low"
            
        tables_extracted.labels(
            table_type=table_type,
            confidence_bucket=confidence_bucket
        ).inc(table_count)
        
    def track_highlighting(self, query_type: str, duration: float, 
                         highlight_count: int):
        """Track source highlighting metrics"""
        if not self.enabled:
            return
            
        highlighting_duration.observe(duration)
        highlights_generated.labels(query_type=query_type).inc(highlight_count)
        
    def track_safety_alert(self, alert_type: str, severity: str = "medium"):
        """Track medical safety alerts"""
        if not self.enabled:
            return
            
        safety_alerts.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
        
        # Log safety alerts for immediate attention
        logger.warning(f"Medical safety alert: {alert_type} (severity: {severity})")
        
    def track_phi_scrubbing(self, component: str, event_count: int = 1):
        """Track PHI scrubbing events"""
        if not self.enabled:
            return
            
        phi_scrubbing_events.labels(component=component).inc(event_count)
        
    def track_feature_usage(self, feature_name: str, enabled: bool):
        """Track feature flag usage"""
        if not self.enabled:
            return
            
        feature_usage.labels(
            feature_name=feature_name,
            enabled=str(enabled).lower()
        ).inc()
        
    def track_llm_request(self, backend: str, duration: float, 
                         input_tokens: int = 0, output_tokens: int = 0,
                         status: str = "success"):
        """Track LLM backend requests"""
        if not self.enabled:
            return
            
        llm_backend_requests.labels(
            backend=backend,
            status=status
        ).inc()
        
        llm_backend_duration.labels(backend=backend).observe(duration)
        
        if input_tokens > 0:
            llm_tokens.labels(backend=backend, type="input").inc(input_tokens)
        if output_tokens > 0:
            llm_tokens.labels(backend=backend, type="output").inc(output_tokens)
            
    def update_system_health(self, health_score: float):
        """Update overall system health score"""
        if not self.enabled:
            return
            
        system_health.set(health_score)
        
    def update_component_health(self, component: str, is_healthy: bool):
        """Update individual component health"""
        if not self.enabled:
            return
            
        component_health.labels(component=component).set(1.0 if is_healthy else 0.0)
        
    def track_elasticsearch_operation(self, operation: str, duration: float, 
                                    status: str = "success"):
        """Track Elasticsearch operations"""
        if not self.enabled:
            return
            
        elasticsearch_operations.labels(
            operation=operation,
            status=status
        ).inc()
        
        elasticsearch_duration.labels(operation=operation).observe(duration)
        
    def update_concurrent_requests(self, count: int):
        """Update concurrent request count"""
        if not self.enabled:
            return
            
        concurrent_requests.set(count)


# Global metrics collector instance
metrics = MetricsCollector()


def init_metrics(settings):
    """Initialize metrics collector with settings"""
    global metrics
    metrics.settings = settings
    metrics.enabled = getattr(settings, 'enable_metrics', True)
    
    # Initialize component health metrics
    components = ['database', 'redis', 'elasticsearch', 'llm']
    for component in components:
        metrics.update_component_health(component, True)  # Start optimistic


# Decorators for automatic instrumentation
def track_query_metrics(func):
    """Decorator to automatically track query metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Extract metrics from result
            if hasattr(result, 'query_type'):
                metrics.track_query(
                    query_type=getattr(result, 'query_type', 'unknown'),
                    duration=duration,
                    confidence=getattr(result, 'confidence', 0.0),
                    cache_hit=getattr(result, 'cache_hit', False)
                )
            return result
        except Exception:
            # Track error metrics
            duration = time.time() - start_time
            query_total.labels(
                query_type="unknown",
                status="error",
                cache_hit="miss"
            ).inc()
            raise
    return wrapper


def track_elasticsearch_metrics(operation: str):
    """Decorator for Elasticsearch operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                metrics.track_elasticsearch_operation(operation, duration, "success")
                return result
            except Exception:
                duration = time.time() - start_time
                metrics.track_elasticsearch_operation(operation, duration, "error")
                raise
        return wrapper
    return decorator


def track_llm_metrics(backend: str):
    """Decorator for LLM operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Extract token counts if available
                input_tokens = getattr(result, 'input_tokens', 0)
                output_tokens = getattr(result, 'output_tokens', 0)
                
                metrics.track_llm_request(
                    backend=backend,
                    duration=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    status="success"
                )
                return result
            except Exception:
                duration = time.time() - start_time
                metrics.track_llm_request(backend, duration, status="error")
                raise
        return wrapper
    return decorator


# Context manager for concurrent request tracking
@contextmanager
def track_concurrent_request():
    """Context manager to track concurrent requests"""
    concurrent_requests.inc()
    try:
        yield
    finally:
        concurrent_requests.dec()