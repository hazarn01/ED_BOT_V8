"""QA Fallback metrics (Task 38).

Provides counters and histograms for QA fallback hits/misses and scores.
Falls back to no-ops if prometheus_client is unavailable.
"""

import logging

try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    class Counter:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self, amount: int = 1):
            pass

    class Histogram:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def observe(self, value: float):
            pass


logger = logging.getLogger(__name__)

_hits = Counter(
    "edbot_qa_fallback_hits_total",
    "Total QA fallback hits",
    ["type"],
)

_misses = Counter(
    "edbot_qa_fallback_misses_total",
    "Total QA fallback misses",
    ["type"],
)

_score_hist = Histogram(
    "edbot_qa_fallback_score",
    "QA fallback match score",
    ["type"],
    buckets=[0.0, 0.2, 0.35, 0.5, 0.7, 0.85, 1.0],
)


def record_hit(qtype: str, score: float) -> None:
    try:
        _hits.labels(type=qtype).inc()
        _score_hist.labels(type=qtype).observe(float(score))
    except Exception:
        logger.debug("QA metrics hit record failed")


def record_miss(qtype: str) -> None:
    try:
        _misses.labels(type=qtype).inc()
    except Exception:
        logger.debug("QA metrics miss record failed")



