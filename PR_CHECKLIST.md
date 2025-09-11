# PR Verification Checklist

Use this list to validate your changes locally before opening a PR.

## Environment Setup
- [ ] Python deps: `make bootstrap` (creates `.venv` and installs `requirements.v8.txt`)
- [ ] JS deps (UI tests): `npm ci`
- [ ] Playwright browsers (UI tests): `npx playwright install --with-deps`
- [ ] Optional dev tools (if missing): `pip install pytest pytest-asyncio pytest-cov ruff mypy pre-commit`

## Static Checks
- [ ] Lint: `make lint` (Ruff + format checks)
- [ ] Types: `make typecheck` (MyPy)
- [ ] Pre-commit (optional but recommended): `pre-commit run -a`

## Tests
- [ ] Unit tests: `make test-unit`
- [ ] Integration tests: `make test-integration`
- [ ] Coverage (target meaningful coverage on critical paths): `make test-coverage`
- [ ] UI smoke (headless): `npm test -- tests/ui/api-health.spec.js`
- [ ] UI debug (headed): `npm run test:headed` (as needed)

## Runtime Sanity (API + Stack)
- [ ] Start (CPU profile): `make up-cpu`
- [ ] API health: `make health` (expect HTTP 200)
- [ ] Sample queries: `make query-test` (responses JSON with plausible data)
- [ ] Logs (no errors): `make logs`
- [ ] Stop: `make down` (or `make clean` to prune)

## PR Hygiene
- [ ] Commit message is concise and imperative (e.g., "Fix sepsis protocol responses")
- [ ] PR includes description, linked issues/PRPs, and before/after evidence (screenshots or logs)
- [ ] No secrets in diffs; configs via `.env.*`

If any step fails, capture the command output in the PR for context.
