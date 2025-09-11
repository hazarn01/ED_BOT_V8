# PRP 24: Observability

## Problem Statement
The new hybrid search and enhancement features need comprehensive monitoring to track performance, identify issues, and measure business impact. Observability must cover feature adoption, performance metrics, error rates, and medical safety indicators.

## Success Criteria
- Key metrics tracked for all new features
- Performance regressions detected quickly
- Feature adoption and effectiveness measured
- Medical safety alerts for anomalies
- Dashboards available for operators and stakeholders

## Implementation Approach

### 1. Metrics Collection Framework

```python
# src/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Enum, Info
from typing import Dict, Optional
import time
from functools import wraps
from contextlib import contextmanager

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

class MetricsCollector:
    """Central metrics collection and instrumentation"""
    
    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.enable_metrics
        
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
            
    def track_safety_alert(self, alert_type: str, severity: str = "medium"):
        """Track medical safety alerts"""
        if not self.enabled:
            return
            
        safety_alerts.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
        
    def track_feature_usage(self, feature_name: str, enabled: bool):
        """Track feature flag usage"""
        if not self.enabled:
            return
            
        feature_usage.labels(
            feature_name=feature_name,
            enabled=str(enabled).lower()
        ).inc()

# Global metrics collector instance
metrics = MetricsCollector(None)  # Will be initialized with settings

def init_metrics(settings):
    """Initialize metrics collector with settings"""
    global metrics
    metrics.settings = settings
    metrics.enabled = getattr(settings, 'enable_metrics', True)

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
                    query_type=result.query_type,
                    duration=duration,
                    confidence=getattr(result, 'confidence', 0.0),
                    cache_hit=getattr(result, 'cache_hit', False)
                )
            return result
        except Exception as e:
            # Track error metrics
            duration = time.time() - start_time
            # Could track error details here
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
                
                elasticsearch_operations.labels(
                    operation=operation,
                    status="success"
                ).inc()
                
                elasticsearch_duration.labels(
                    operation=operation
                ).observe(duration)
                
                return result
            except Exception as e:
                elasticsearch_operations.labels(
                    operation=operation,
                    status="error"
                ).inc()
                raise
        return wrapper
    return decorator
```

### 2. Custom Metrics for Medical Domain

```python
# src/observability/medical_metrics.py
from prometheus_client import Counter, Histogram, Gauge
from typing import Dict, List
import re

# Medical-specific metrics
medical_queries_by_specialty = Counter(
    'edbot_medical_queries_by_specialty',
    'Queries categorized by medical specialty',
    ['specialty', 'query_type']
)

protocol_adherence = Gauge(
    'edbot_protocol_adherence_score',
    'Protocol adherence score for responses',
    ['protocol_name']
)

medication_dosage_queries = Counter(
    'edbot_medication_queries_total',
    'Medication dosage queries',
    ['medication', 'route']
)

time_sensitive_protocols = Histogram(
    'edbot_time_sensitive_response_seconds',
    'Response time for time-sensitive protocols',
    ['protocol_type'],  # 'STEMI', 'stroke', 'sepsis'
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
)

clinical_confidence_distribution = Histogram(
    'edbot_clinical_confidence',
    'Distribution of clinical response confidence',
    ['clinical_area'],  # 'cardiology', 'emergency', 'pharmacy'
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]
)

class MedicalMetricsCollector:
    """Medical domain-specific metrics"""
    
    # Medical specialty keywords
    SPECIALTY_KEYWORDS = {
        'cardiology': ['heart', 'cardiac', 'MI', 'STEMI', 'angina', 'EKG', 'troponin'],
        'emergency': ['trauma', 'shock', 'CPR', 'code', 'arrest', 'emergency'],
        'pharmacy': ['dosage', 'medication', 'drug', 'mg', 'mcg', 'units'],
        'pulmonology': ['respiratory', 'lung', 'pneumonia', 'asthma', 'COPD'],
        'neurology': ['stroke', 'seizure', 'neurologic', 'brain', 'TPA']
    }
    
    # Time-sensitive protocols
    TIME_SENSITIVE = ['STEMI', 'stroke', 'sepsis', 'trauma']
    
    def __init__(self, settings):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_medical_metrics', True)
        
    def classify_medical_specialty(self, query: str) -> str:
        """Classify query by medical specialty"""
        query_lower = query.lower()
        
        for specialty, keywords in self.SPECIALTY_KEYWORDS.items():
            if any(keyword.lower() in query_lower for keyword in keywords):
                return specialty
                
        return 'general'
        
    def extract_medication(self, query: str) -> str:
        """Extract medication name from query"""
        # Simple regex for common medication patterns
        patterns = [
            r'\b([a-z]+(?:ol|pril|pine|zide|mycin|cillin))\b',  # Common suffixes
            r'\b(aspirin|heparin|insulin|morphine|ativan|versed)\b'  # Common names
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)
                
        return 'unknown'
        
    def is_time_sensitive(self, query: str) -> bool:
        """Check if query relates to time-sensitive protocol"""
        query_lower = query.lower()
        return any(protocol.lower() in query_lower for protocol in self.TIME_SENSITIVE)
        
    def track_medical_query(self, query: str, query_type: str, confidence: float, 
                          response_time: float):
        """Track medical-specific metrics"""
        if not self.enabled:
            return
            
        # Classify by specialty
        specialty = self.classify_medical_specialty(query)
        medical_queries_by_specialty.labels(
            specialty=specialty,
            query_type=query_type
        ).inc()
        
        # Track clinical confidence by area
        clinical_confidence_distribution.labels(
            clinical_area=specialty
        ).observe(confidence)
        
        # Track time-sensitive protocols
        if self.is_time_sensitive(query):
            protocol_type = next(
                (p for p in self.TIME_SENSITIVE if p.lower() in query.lower()),
                'other'
            )
            time_sensitive_protocols.labels(
                protocol_type=protocol_type
            ).observe(response_time)
            
        # Track medication queries
        if query_type == 'DOSAGE_LOOKUP':
            medication = self.extract_medication(query)
            # Extract route if present
            route = 'unknown'
            if 'IV' in query.upper():
                route = 'IV'
            elif 'PO' in query.upper():
                route = 'PO'
            elif 'SubQ' in query:
                route = 'SubQ'
                
            medication_dosage_queries.labels(
                medication=medication,
                route=route
            ).inc()
```

### 3. Dashboards and Alerting

```python
# src/observability/dashboards.py
from typing import Dict, List
import json

# Grafana dashboard definitions
HYBRID_SEARCH_DASHBOARD = {
    "dashboard": {
        "title": "EDBotv8 - Hybrid Search Performance",
        "panels": [
            {
                "title": "Query Volume by Type",
                "type": "stat",
                "targets": [
                    {
                        "expr": "rate(edbot_queries_total[5m])",
                        "legendFormat": "{{query_type}}"
                    }
                ]
            },
            {
                "title": "Query Response Time",
                "type": "graph",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(edbot_query_duration_seconds_bucket[5m]))",
                        "legendFormat": "95th percentile"
                    },
                    {
                        "expr": "histogram_quantile(0.50, rate(edbot_query_duration_seconds_bucket[5m]))",
                        "legendFormat": "50th percentile"
                    }
                ]
            },
            {
                "title": "Hybrid Search Component Performance",
                "type": "graph",
                "targets": [
                    {
                        "expr": "rate(edbot_hybrid_retrieval_seconds_sum[5m]) / rate(edbot_hybrid_retrieval_seconds_count[5m])",
                        "legendFormat": "{{component}} avg time"
                    }
                ]
            },
            {
                "title": "Cache Hit Rate",
                "type": "stat",
                "targets": [
                    {
                        "expr": "rate(edbot_cache_operations_total{result=\"hit\"}[5m]) / rate(edbot_cache_operations_total[5m]) * 100",
                        "legendFormat": "{{query_type}}"
                    }
                ]
            },
            {
                "title": "Search Result Sources",
                "type": "piechart",
                "targets": [
                    {
                        "expr": "rate(edbot_hybrid_results_total[5m])",
                        "legendFormat": "{{source}}"
                    }
                ]
            }
        ]
    }
}

MEDICAL_SAFETY_DASHBOARD = {
    "dashboard": {
        "title": "EDBotv8 - Medical Safety Monitoring",
        "panels": [
            {
                "title": "Response Confidence Distribution",
                "type": "heatmap",
                "targets": [
                    {
                        "expr": "rate(edbot_query_confidence_bucket[5m])",
                        "legendFormat": "{{le}}"
                    }
                ]
            },
            {
                "title": "Safety Alerts",
                "type": "stat",
                "targets": [
                    {
                        "expr": "rate(edbot_safety_alerts_total[1h])",
                        "legendFormat": "{{alert_type}}"
                    }
                ]
            },
            {
                "title": "Time-Sensitive Protocol Response Times",
                "type": "graph",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(edbot_time_sensitive_response_seconds_bucket[5m]))",
                        "legendFormat": "{{protocol_type}} p95"
                    }
                ]
            }
        ]
    }
}

# Alerting rules
ALERTING_RULES = """
groups:
  - name: edbot_alerts
    rules:
    - alert: HighQueryLatency
      expr: histogram_quantile(0.95, rate(edbot_query_duration_seconds_bucket[5m])) > 5.0
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "High query latency detected"
        description: "95th percentile query latency is {{ $value }}s"
        
    - alert: LowResponseConfidence
      expr: rate(edbot_query_confidence_bucket{le="0.7"}[10m]) / rate(edbot_query_confidence_count[10m]) > 0.3
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High rate of low-confidence responses"
        
    - alert: ElasticsearchDown
      expr: up{job="elasticsearch"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Elasticsearch is down"
        
    - alert: SafetyAlertsSpike
      expr: rate(edbot_safety_alerts_total[5m]) > 0.1
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "Spike in medical safety alerts"
        
    - alert: CacheHitRateLow
      expr: rate(edbot_cache_operations_total{result="hit"}[10m]) / rate(edbot_cache_operations_total[10m]) < 0.1
      for: 5m
      labels:
        severity: info
      annotations:
        summary: "Cache hit rate below 10%"
"""
```

### 4. Health Checks and Status

```python
# src/observability/health.py
from typing import Dict, Any
from enum import Enum
import asyncio
import time

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"

class HealthChecker:
    """System health monitoring"""
    
    def __init__(self, settings, db_session, redis_client, es_client=None):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.es_client = es_client
        
    async def check_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        checks = {
            "database": await self._check_database(),
            "redis": await self._check_redis(),
            "search_backend": await self._check_search_backend(),
            "features": await self._check_feature_health()
        }
        
        # Overall status
        overall_status = HealthStatus.HEALTHY
        if any(check["status"] == HealthStatus.UNHEALTHY.value for check in checks.values()):
            overall_status = HealthStatus.UNHEALTHY
        elif any(check["status"] == HealthStatus.DEGRADED.value for check in checks.values()):
            overall_status = HealthStatus.DEGRADED
            
        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "checks": checks
        }
        
    async def _check_database(self) -> Dict[str, Any]:
        """Check PostgreSQL health"""
        try:
            # Simple query to test connectivity
            result = await self.db.execute("SELECT 1")
            return {
                "status": HealthStatus.HEALTHY.value,
                "response_time_ms": 10  # Could measure actual time
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e)
            }
            
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            await self.redis.ping()
            return {
                "status": HealthStatus.HEALTHY.value,
                "memory_usage": await self._get_redis_memory()
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e)
            }
            
    async def _check_search_backend(self) -> Dict[str, Any]:
        """Check search backend health"""
        if self.settings.features.enable_elasticsearch and self.es_client:
            try:
                es = self.es_client.get_client()
                if es and es.ping():
                    cluster_health = es.cluster.health()
                    status = cluster_health["status"]
                    
                    health_map = {
                        "green": HealthStatus.HEALTHY,
                        "yellow": HealthStatus.DEGRADED,
                        "red": HealthStatus.UNHEALTHY
                    }
                    
                    return {
                        "status": health_map.get(status, HealthStatus.UNHEALTHY).value,
                        "backend": "hybrid",
                        "elasticsearch_status": status,
                        "nodes": cluster_health["number_of_nodes"]
                    }
            except Exception as e:
                return {
                    "status": HealthStatus.DEGRADED.value,
                    "backend": "pgvector_fallback",
                    "error": str(e)
                }
        
        # pgvector only
        return {
            "status": HealthStatus.HEALTHY.value,
            "backend": "pgvector"
        }
        
    async def _check_feature_health(self) -> Dict[str, Any]:
        """Check feature-specific health"""
        feature_status = {}
        
        # Cache health
        if self.settings.features.enable_semantic_cache:
            try:
                await self.redis.get("health_check")
                feature_status["semantic_cache"] = HealthStatus.HEALTHY.value
            except:
                feature_status["semantic_cache"] = HealthStatus.UNHEALTHY.value
        
        # Table extraction (check if dependencies available)
        if self.settings.features.enable_table_extraction:
            try:
                import unstructured
                feature_status["table_extraction"] = HealthStatus.HEALTHY.value
            except ImportError:
                feature_status["table_extraction"] = HealthStatus.DEGRADED.value
                
        return {
            "status": HealthStatus.HEALTHY.value,
            "features": feature_status
        }
        
    async def _get_redis_memory(self) -> str:
        """Get Redis memory usage"""
        try:
            info = await self.redis.info("memory")
            return info.get("used_memory_human", "unknown")
        except:
            return "unknown"
```

### 5. Integration with API

```python
# src/api/endpoints/observability.py
from fastapi import APIRouter, Depends
from src.observability.health import HealthChecker
from src.observability.metrics import metrics

router = APIRouter(prefix="/observability", tags=["observability"])

@router.get("/health")
async def health_check(
    health_checker: HealthChecker = Depends(get_health_checker)
):
    """System health check endpoint"""
    return await health_checker.check_system_health()

@router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.get("/stats")
async def get_stats():
    """High-level system statistics"""
    # Could aggregate key metrics for dashboard
    return {
        "queries_per_minute": "calculated from metrics",
        "avg_response_time": "calculated from metrics", 
        "cache_hit_rate": "calculated from metrics",
        "active_features": "list of enabled features"
    }
```

## Performance Impact
- Metrics collection: <1ms overhead per request
- Health checks: Run every 30 seconds
- Dashboard queries: Minimal impact on application
- Storage: ~1MB per day for typical workload

## Rollback Plan
1. Disable metrics collection: `ENABLE_METRICS=false`
2. Remove Prometheus scraping config
3. Dashboards show no data but don't break
4. Health checks continue to work