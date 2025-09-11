# Fix: Feature Manager, Semantic Cache, Medical Metrics, and Test Failures

## Summary
Address failing unit tests and runtime edge cases across:
- Feature flags (FeatureManager + Redis overrides/caching)
- Semantic cache (async Redis interface, TTLs, NEVER_CACHE, PHI scrubbing)
- Medical metrics (helpers + tracking robustness)
- Related unit test fixes where expectations mismatch stable behavior

## Scope
- src/config/feature_manager.py
- src/cache/semantic_cache.py (+ metrics integration)
- src/observability/medical_metrics.py
- Targeted test fixes (no broad rewrites)

## Plan
1. Normalize remaining imports for consistent test import paths.
2. FeatureManager:
   - Mockable Redis client surface (get/set/delete/scan), time-based expiry.
   - Override precedence (Redis > settings), name validation, dependency checks.
   - Error handling with metrics and graceful fallback.
3. SemanticCache:
   - Align async Redis usage with tests; ensure NEVER_CACHE + TTL per type.
   - PHI scrubbing; coverage of get/set/invalidate/stats.
   - Robust embedding-service interaction (awaitable).
4. MedicalMetrics:
   - Fix helper functions (classification, route parsing, safety event logging).
   - Fill missing imports/types; guard exceptions in tracking paths.
5. Tests:
   - Adjust/minor fixes where assumptions are brittle; keep behavior intact.
6. Validation:
   - Run unit tests for targeted modules; iterate until green.

## Non-Goals
- Production deployment changes;
- Database schema updates; 
- Broad refactors outside failing paths.

## Risks & Mitigations
- Behavior regressions: use unit tests as guardrails, keep changes minimal.
- Redis/ES availability: design for graceful fallback during tests.

---

Co-authored-by: AI Assistant
