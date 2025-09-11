import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Simple in-memory metrics collector."""

    def __init__(self):
        self.metrics = {
            "query_latency": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_tokens": [],
            "errors": {},
            "query_types": {},
        }

    def record_latency(
        self, operation: str, duration: float, metadata: Optional[Dict] = None
    ):
        """Record operation latency."""
        self.metrics["query_latency"].append(
            {
                "operation": operation,
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }
        )

        # Keep only last 1000 entries to prevent memory issues
        if len(self.metrics["query_latency"]) > 1000:
            self.metrics["query_latency"] = self.metrics["query_latency"][-1000:]

    def increment_cache_hit(self):
        """Increment cache hit counter."""
        self.metrics["cache_hits"] += 1

    def increment_cache_miss(self):
        """Increment cache miss counter."""
        self.metrics["cache_misses"] += 1

    def record_llm_usage(self, tokens: int, model: str):
        """Record LLM token usage."""
        self.metrics["llm_tokens"].append(
            {
                "tokens": tokens,
                "model": model,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Keep only last 1000 entries
        if len(self.metrics["llm_tokens"]) > 1000:
            self.metrics["llm_tokens"] = self.metrics["llm_tokens"][-1000:]

    def record_error(self, error_type: str, details: Optional[str] = None):
        """Record error occurrence."""
        if error_type not in self.metrics["errors"]:
            self.metrics["errors"][error_type] = 0
        self.metrics["errors"][error_type] += 1

        logger.error(
            "Error recorded",
            extra_fields={"error_type": error_type, "details": details},
        )

    def record_query_type(self, query_type: str):
        """Record query type occurrence."""
        if query_type not in self.metrics["query_types"]:
            self.metrics["query_types"][query_type] = 0
        self.metrics["query_types"][query_type] += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        latencies = self.metrics["query_latency"]

        # Calculate latency statistics
        if latencies:
            durations = [latency["duration"] for latency in latencies]
            p50 = sorted(durations)[len(durations) // 2] if durations else 0
            p95 = sorted(durations)[int(len(durations) * 0.95)] if durations else 0
            avg = sum(durations) / len(durations) if durations else 0
        else:
            p50 = p95 = avg = 0

        # Calculate cache hit rate
        total_cache = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = (
            self.metrics["cache_hits"] / total_cache if total_cache > 0 else 0
        )

        return {
            "latency": {"p50": p50, "p95": p95, "avg": avg, "count": len(latencies)},
            "cache": {
                "hits": self.metrics["cache_hits"],
                "misses": self.metrics["cache_misses"],
                "hit_rate": cache_hit_rate,
            },
            "llm": {
                "total_tokens": sum(t["tokens"] for t in self.metrics["llm_tokens"]),
                "request_count": len(self.metrics["llm_tokens"]),
            },
            "errors": self.metrics["errors"],
            "query_types": self.metrics["query_types"],
        }


# Global metrics collector
metrics = MetricsCollector()


@contextmanager
def track_latency(operation: str, metadata: Optional[Dict] = None):
    """Context manager to track operation latency."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.record_latency(operation, duration, metadata)
        logger.info(
            "Operation completed",
            extra_fields={
                "operation": operation,
                "duration_ms": duration * 1000,
                "metadata": metadata or {},
            },
        )


def track_metric(metric_name: str, value: Any, metadata: Optional[Dict] = None):
    """Track a custom metric."""
    logger.info(
        "Metric tracked",
        extra_fields={
            "metric": metric_name,
            "value": value,
            "metadata": metadata or {},
        },
    )


def track_event(event_name: str, metadata: Optional[Dict] = None):
    """Track a custom event."""
    logger.info(
        "Event tracked", extra_fields={"event": event_name, "metadata": metadata or {}}
    )


def measure_performance(operation_name: Optional[str] = None):
    """Decorator to measure function performance."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with track_latency(name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with track_latency(name):
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
