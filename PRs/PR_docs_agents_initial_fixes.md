# Docs: Add AGENTS.md and PR checklist; initial stability improvements

## Summary
- Add AGENTS.md contributor guide tailored to this repo (structure, commands, style, tests, PR expectations).
- Add PR_CHECKLIST.md for local verification (bootstrap, lint, types, tests, stack sanity).
- Improve test runner portability by using the active interpreter (`sys.executable`).
- Normalize imports across key modules to match tests’ pathing and fix collection errors.
- Add `ConfigurationValidator` warning/error API used by tests (ValidationWarning/ValidationError, helpers).

## Rationale
- Contributors requested concise, actionable guidelines and a consistent pre‑PR checklist.
- Test collection previously failed due to path mismatches and missing validator API; changes unblock local runs and reduce friction.

## Changes
- New: `AGENTS.md`, `PR_CHECKLIST.md`.
- Chore: `scripts/run_tests.py` uses `sys.executable`.
- Refactor: Convert relative to absolute imports in `src/pipeline/*`, `src/cache/*`, `src/search/elasticsearch_client.py`, `src/ai/*`, `src/services/contact_service.py`, `src/validation/*` where needed.
- Feat: Implement `src/config/validators.py` with `ValidationWarning`, `ValidationError`, and expected helpers.
- Lint: Remove stray f‑string prefixes; add missing type imports.

## Validation
- Unit tests now collect; many suites pass locally. Remaining failures are unrelated to docs and will be addressed in follow‑ups (feature flags/redis stubs, metrics helpers, hybrid ES query building).
- Lint/type checks depend on local tool availability (ruff/mypy); see PR_CHECKLIST.md.

## Notes
- No production behavior changes intended beyond import normalization and validator API addition.
- No database schema changes.

## Next Steps (optional follow‑ups)
- Align remaining relative imports and complete test parity for feature manager, semantic cache, and medical metrics.
- Address Playwright test harness setup in CI.

---

Co-authored-by: AI Assistant
