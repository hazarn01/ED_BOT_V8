# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Python application code (e.g., `pipeline/`, `api/`, `config/`, `services/`, `search/`, `observability/`).
- `tests/`: Pytest suites by type: `unit/`, `integration/`, `performance/`, `e2e/`, and Playwright specs under `ui/`.
- `scripts/`: Developer utilities (test runner, rollout, backfill, validation).
- `docs/`, `examples/`, `static/`, `streamlit_app/`: reference assets and UI demo.
- `alembic/` + `alembic.ini`: database migrations.
- Top-level: `Makefile`, `docker-compose.v8.yml`, `.env.*` for configuration.

## Build, Test, and Development Commands
- Bootstrap: `make bootstrap` — create venv and install Python deps.
- Run stack (CPU): `make up-cpu` (Ollama); GPU: `make up-gpu` (vLLM); UI demo: `make up-ui`.
- Stop/Clean: `make down` / `make clean` (adds prune) / `make reset`.
- Tests (Python): `make test`, `make test-unit`, `make test-integration`, coverage: `make test-coverage`.
- Lint/Types: `make lint` (ruff/format checks), `make typecheck` (mypy).
- Tests (UI): `npm test` or `npx playwright test`; report: `npm run test:report`.
- Migrations: `make migrate` / `make upgrade` / `make downgrade`.

## Coding Style & Naming Conventions
- Python: Black (line length 100), Ruff for linting; MyPy for types. Indent 4 spaces.
- Naming: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. Tests named `test_*.py`.
- Run pre-commit locally: `pre-commit run -a` (Black, Ruff, whitespace fixes).

## Testing Guidelines
- Framework: Pytest with asyncio auto mode; keep fast, isolated unit tests under `tests/unit/`.
- Coverage: target meaningful coverage on critical paths (`src/pipeline/`, `src/config/`, `src/observability/`).
- UI: Playwright specs in `tests/ui/*.spec.js`; prefer data-testid selectors.
- Example: `python scripts/run_tests.py unit -v` or `pytest tests/integration -v`.

## Commit & Pull Request Guidelines
- Commits: concise, imperative subject (e.g., "Fix ultrawide layout spacing"). Scope logically; reference PRP when relevant.
- PRs: use `PULL_REQUEST.md` template; include description, linked issues/PRPs, tests, and before/after evidence (screenshots or logs). Ensure lint, typecheck, and tests pass.

## Security & Configuration Tips
- Never commit secrets; use `.env.development` locally. Validate with `make diag` and `make validate`. API health: `make health`.
