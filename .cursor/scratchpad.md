# Background and Motivation

The dev stack fails on Windows hosts without a compatible NVIDIA setup because the `llm` service (vLLM) requires CUDA ≥ 12.8. When `llm` crashes, `api` and `worker` also fail to start due to `depends_on: llm`. We need a GPU-optional path that brings up `api` and `worker` reliably, plus an opt‑in GPU path. The code already has `LLM_BACKEND` settings but always wires `GPTOSSClient`; there’s no CPU client or mock yet.

Additionally, we want the default CPU path (Ollama) to use Mistral 7B Instruct for better quality than Gemma 2B, but the current defaults still point to `gemma2:2b` and the Ollama client pulls its model name from `langextract_local_model`, causing confusion and failures if `mistral:7b` is not pulled.

## New Incident: API Availability and Web Audit Issues (Windows/Dev)

- API is not reachable: `HTTPConnectionPool(host='localhost', port=8001) ... Connection refused` when calling `/api/v1/query`.
- Web audit surfaced issues: missing/incorrect headers (`content-type` charset not `utf-8`, `x-content-type-options`), cookie flags (`secure`/`httponly`), protocol‑relative URLs, cache‑busting for static assets, and accessibility issues (autocomplete misuse, missing `id`/`name`, missing labels).
- We need to restore API availability first, then harden headers/cookies, fix static asset caching and URL schemes, and address accessibility.

# Additional Motivation: Document ingestion and seeding on Windows/WSL

- Ensure the ingestion pipeline works locally on Windows via WSL2 for both single-document processing and full corpus seeding (≈338 PDFs), with clear dependency steps and validation.
- Provide reproducible commands/scripts for:
  - Installing OS-level dependencies in WSL: `poppler-utils`, `tesseract-ocr`, `libmagic1`.
  - Running a single-document test using `DocumentProcessor`.
  - Executing the full seeding script and a validation-only pass.
  - Documenting Windows/WSL path conventions (e.g., `/mnt/d/Dev/EDbotv8`).
# Additional Motivation: Hybrid Search and Source Highlighting (denser-chat learnings)

- Improve retrieval precision and recall by combining exact keyword search with semantic search via a hybrid approach (Elasticsearch + pgvector). This helps with clinical terminology, protocol names, and form identifiers where exact matches matter.
- Provide interactive source highlighting for PDFs so users can see exactly where answers come from; capture page numbers and spans during ingestion to power a simple viewer.
- Enhance table extraction (medical dosage tables, protocol steps) and persist structured tables for targeted retrieval.
- Add a semantic cache for similar queries to reduce latency without sacrificing freshness, gated by safety checks and query type.
- Provide an optional Streamlit demo UI for faster validation by non-engineers while keeping the production API unchanged.

# Additional Motivation: Ground Truth QA Quality Alignment (PRP-36)

- Current bot answers are low-quality and often generic (e.g., just "Clinical Criteria") despite rich `ground_truth_qa/` data and ingested PDFs.
- Queries like "what is the STEMI protocol" should return concrete steps, timing, contacts from STEMI docs; dosage questions should extract precise values from dosing references.
- We need a deterministic, benchmark-aligned path that reliably surfaces specific facts with correct citations, while preserving the flexible RAG pipeline for open queries.

## PRP‑36 Gaps (Why quality is still poor)

- No direct wiring to `ground_truth_qa/` JSON: the live router only uses DB/RAG; curated Q/A is never consulted, so deterministic facts (e.g., STEMI steps, Ottawa ankle rules) are missed.
- Classifier/Router mapping drift: “what is the STEMI protocol” sometimes routes to generic SUMMARY/CRITERIA and produces template text.
- Retrieval weak signals: embeddings may be missing or `_generate_embedding` is stubbed; text fallback is shallow, causing empty or irrelevant chunks and “insufficient information”.
- Prompting too generic: generation templates don’t enforce fact extraction + citation per QueryType; temperature/length settings lead to boilerplate.
- Citation mapping: responses often lack precise source/page; registry mapping is inconsistent.
- Dosage coverage: many dose queries (e.g., epi in cardiac arrest) aren’t answered from docs or QA; needs deterministic mapping when present, and clear fallback when not.

# Key Challenges and Analysis

- vLLM GPU requirement
  - `nvidia-container-cli` enforces CUDA ≥ 12.8; `vllm/vllm-openai:latest` expects newest CUDA.
  - On Windows: GPU passthrough needs WSL2 + modern NVIDIA driver + Docker GPU enabled. Many dev machines won’t meet this by default.
- Compose coupling
  - `api` and `worker` have `depends_on: llm`, so they don’t start when `llm` fails. This blocks all dev work.
  - Solution: remove hard dependency on `llm` and use profiles so `llm` only runs with `--profile gpu`.
- Backend abstraction gap
  - `src/config/settings.py` exposes `llm_backend` (gpt-oss|ollama|azure), but DI in `src/api/dependencies.py` always instantiates `GPTOSSClient`.
  - No `OllamaClient` or `MockLLMClient` exists. Classifier already falls back to rules but assumes a primary client is injected.
- Developer UX
  - `Makefile.v8 dev-setup` always runs full stack; no GPU detection or profile selection.
  - Tests should not require a live LLM.
- Ollama model selection (current blocker)
  - `OllamaClient` uses `settings.langextract_local_model` as its model, defaulting to `gemma2:2b`, not a chat model choice.
  - `docker-compose.v8.yml` pulls `${OLLAMA_DEFAULT_MODEL:-gemma2:2b}` via `ollama-pull`, so Mistral is never pre-pulled unless overridden.
  - There is no dedicated `OLLAMA_MODEL`/`ollama_model` setting; env and code defaults are misaligned.
  - Result: switching to Mistral 7B Instruct stalls unless we manually pull and override in multiple places.

- API crash on startup (new blocker)
  - FastAPI container exits with `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.`
  - Root cause: multiple ORM models define an attribute named `metadata` (e.g., in `src/models/entities.py` for `Document`, `DocumentChunk`, `DocumentRegistry`, `ChatSession`, `ChatMessage`). In SQLAlchemy Declarative, `metadata` is reserved on the Base.
  - Fix: rename Python attribute to a non-reserved name (e.g., `meta` or `metadata_json`) while mapping to DB column `metadata` via `Column('metadata', JSON, ...)` to preserve schema. Update all usages.

- Ollama pre-pull command (fixed)
  - Previous compose used `sh -lc` inside `ollama/ollama`, which fails because the image entrypoint is `ollama` (interpreted `sh` as subcommand).
  - Fixed compose to use `command: ["pull", "${OLLAMA_DEFAULT_MODEL:-mistral:7b-instruct}"]` so the entrypoint runs `ollama pull` directly.
  - Impact: model is now pulling successfully; `/api/tags` is empty until pull completes.

- Query pipeline error (current blocker)
  - Error: `'QueryClassifier' object has no attribute 'classify'` in `QueryProcessor.process_query`.
  - Root cause: `QueryClassifier` exposes `classify_query(...)` but `QueryProcessor` is calling `classify(...)`.
  - Fix: change call to `self.classifier.classify_query(query)` or add a small alias method.

- Schema/endpoint mismatch (risk after unblock)
  - Endpoints and router reference fields like `Document.doc_type`, `Document.title`, `Document.file_path` which are not present in `src/models/entities.py` (`Document` has `content_type`, `filename`, `file_type`, `meta`).
  - This may cause filters/response serialization issues for FORM/PROTOCOL routes.
  - Options: (A) align models (add columns and migrations) or (B) adjust queries to use existing fields and `meta` payload.

- Windows validation friction
  - `make` not present by default; `curl` quoting causes JSON errors in PowerShell.
  - Provide PowerShell `Invoke-RestMethod` snippets and/or a small `scripts/validate.ps1` helper.

- Hybrid search without regressions
  - Introduce Elasticsearch as an optional service (compose profile) and add dual indexing in ingestion. Keep the default search path as pgvector-only. Use a feature flag `SEARCH_BACKEND` (pgvector|hybrid) to enable fusion.
  - Ensure index mappings, analyzers (medical tokenization/keyword fields), and backfill scripts are idempotent.

- Result fusion and query-type awareness
  - Build a `HybridRetriever` that performs keyword and semantic search, then fuses results with weights tuned per `QueryType` (e.g., heavier keyword weight for FORM/PROTOCOL, heavier semantic for SUMMARY/CRITERIA).
  - Maintain strict fallbacks to existing `RAGRetriever` if the hybrid path is disabled or ES is unavailable.

- Source highlighting pipeline
  - During ingestion, persist page numbers and character spans per chunk. For PDFs, store a mapping from chunk → (pdf_path, page_no, span_start, span_end).
  - Extend response schema to include `highlighted_sources` while keeping existing fields for backward compatibility.

- Table extraction reliability
  - Choose an extraction path that works headless in containers (e.g., Unstructured table elements first; optionally Camelot/Tabula behind a feature flag due to Java/Ghostscript dependencies).
  - Store tables as structured JSON with headers, units, and row provenance.

- Semantic cache safety
  - Cache by semantic similarity only for safe query types; include PHI scrubbing on cache keys and values. Add metrics to monitor hit rate and stale responses. Always bypass cache for CONTACT/FORM queries where freshness/precision dominate.

- Streamlit as dev-only
  - Run Streamlit in a separate optional service. Do not couple to the API process. Gate it behind a compose profile and feature flag so production is unaffected.
 
 - Ingestion/seeding on Windows/WSL
   - OS packages are Linux-side; they must be installed in WSL, not Windows (PowerShell).
   - Paths must use WSL mounts (e.g., `/mnt/d/Dev/EDbotv8/docs/...`) when invoking Python inside WSL.
   - Ensure `DATABASE_URL` points to a reachable Postgres (Docker or host) from WSL.
   - Automate environment export for `PYTHONPATH` and per-invocation overrides to avoid IDE path confusion.
   - Validate dependency presence at runtime (graceful error if `pdftotext`/Tesseract missing with actionable message).

# High-level Task Breakdown
- [x] Task 1: Decouple services via Compose profiles (success: `api`/`worker` start without `llm`)
  - Add `profiles: [gpu]` to `llm` service in `docker-compose.v8.yml`.
  - Remove `depends_on: llm` from `api` and `worker`.
  - Validate: `docker compose up -d` runs `db`, `redis`, `api`, `worker`; `curl :8001/health` → 200 on Windows without GPU.

- [x] Task 2: LLM backend factory + Ollama CPU path (success: API works when LLM unavailable)
  - Added `src/ai/ollama_client.py`.
  - Implemented backend selection in `src/api/dependencies.py` using `LLM_BACKEND`.
  - Updated `settings.py` default to `ollama`; wired env into compose for `api`/`worker`.

- [x] Task 3: Switch Ollama default to Mistral 7B Instruct (success: CPU path uses `mistral:7b` end-to-end)
  - Add `ollama_model` setting to `src/config/settings.py` with default `mistral:7b`.
  - Update `src/ai/ollama_client.py` to use `settings.ollama_model` (not `langextract_local_model`).
  - Add `OLLAMA_DEFAULT_MODEL=mistral:7b` to `EDBOTv8.env.example`; propagate via compose to `ollama-pull`.
  - Ensure `docker-compose.v8.yml` keeps `ollama` and `ollama-pull` in CPU profile; pre-pull uses `${OLLAMA_DEFAULT_MODEL}`.
  - Validate: `make up-cpu` → `curl :11434/api/tags` lists `mistral:7b`, and `make query-test` returns responses.

- [ ] Task 4: GPU path fix for vLLM (success: `llm` healthy)
  - Option A: Document driver upgrade to meet CUDA ≥ 12.8.
  - Option B: Pin `VLLM_IMAGE` to a tag matching installed CUDA (e.g., `vllm/vllm-openai:0.x.y-cuda12.1`).
  - Validate: `docker compose --profile gpu up -d`; `GET http://localhost:8000/health` and `/v1/models` return OK.

- [x] Task 5: Makefile UX (success: `make dev-setup` chooses sane default)
  - Added `make up-cpu` / `make up-gpu` shortcuts and defaulted `dev-setup` to CPU.

- [ ] Task 6: Tests resilient to no‑LLM (success: CI green without LLM)
  - Mark tests requiring an LLM and gate them behind env or skip by default.
  - Set `MOCK_LLM=true` in test env; ensure unit/integration tests don’t call live endpoints.

- [ ] Task 7: Docs and troubleshooting (success: Windows devs can start reliably)
  - Update `README_V8.md` with CPU/mock modes, profiles, Make targets, and the new `OLLAMA_DEFAULT_MODEL`/`ollama_model` guidance.
  - Add troubleshooting: WSL2, Docker GPU, driver checks, image pinning, and env examples for `LLM_BACKEND` and model selection.

- [ ] Task 8: Environment diagnostics helper (optional but useful)
  - Script/Make target to print: `nvidia-smi` (if present), `docker info` runtimes, compose logs for `llm`, and Ollama tags.

- [x] Task 9: Fix SQLAlchemy reserved `metadata` attributes (success: API boots and serves /health)
  - Rename Python attributes from `metadata` → `meta` (or `metadata_json`) in all affected models.
  - Map to DB column name `metadata` using `Column('metadata', JSON, default=...)` to avoid schema change.
  - Update references across code to the new attribute names.
  - Validate: `docker compose up -d api` → `GET :8001/health` returns 200; basic endpoints respond.

- [ ] Task 10 (optional): Faster CPU default model (success: first run <2 min)
  - Temporarily set `OLLAMA_DEFAULT_MODEL=phi3:mini` for quicker initial dev startup.
  - Keep `mistral:7b-instruct` as the documented recommended model and allow switching via env.
  - Validate: `/api/tags` lists the chosen model and a simple generation works.

- [ ] Task 11: Fix classifier API mismatch (success: queries no longer 500)
  - Update `src/pipeline/query_processor.py` to call `self.classifier.classify_query(query)`.
  - Alternatively, add `def classify(self, query): return asyncio.run(self.classify_query(query))` if needed (prefer direct await in async flow).
  - Validate: contact/form/protocol queries return non-error responses.

- [ ] Task 12: Align router/endpoints with models (success: form/protocol routes work)
  - Option A (model-forward): add `title`, `file_path`, and `doc_type` (or map to existing: `content_type`) to `Document` with migration.
  - Option B (code-forward, faster): adjust `router.py` and response models to use `Document.content_type`, `Document.filename`, and `Document.meta` fields; compute display names and links from `meta` and known docs path.
  - Validate: `/api/v1/documents` and `.../download` work; protocol/form queries route correctly or fall back to LLM gracefully.

- [ ] Task 13: Windows-friendly validation (success: easy local validation)
  - Add `scripts/validate.ps1` using `Invoke-RestMethod` with `ConvertTo-Json`.
  - Document usage in `README_V8.md`; keep `make validate` for Linux/WSL.
  - Validate: script returns 200 health and JSON for sample queries.

- [ ] Task 14: Add Elasticsearch as optional service (success: ES healthy, default remains pgvector)
  - Extend `docker-compose.v8.yml` with `elasticsearch` service (single-node, security disabled for dev) under a new profile `search`.
  - Add `SEARCH_BACKEND` setting with default `pgvector`; when `hybrid`, API attempts ES connection but falls back gracefully.
  - Validate: `docker compose --profile search up -d elasticsearch`; `GET :9200/_cluster/health` is green.

- [ ] Task 15: Dual indexing during ingestion (success: ES index populated alongside DB)
  - Define ES index templates/mappings (keyword fields for protocol/form names; text with analyzers; metadata fields).
  - Update `src/ingestion/tasks.py` to push documents/chunks to ES when `SEARCH_BACKEND=hybrid`.
  - Provide a one-shot backfill script: `python -m scripts.index_real_documents --target es`.
  - Validate: Counts in ES match DB doc/chunk counts within tolerance; sample queries return results in both backends.

- [ ] Task 16: Implement `HybridRetriever` and wire into router (success: intent-aware fusion)
  - New `src/pipeline/hybrid_retriever.py` with keyword (ES) + semantic (pgvector) search; fuse with per-`QueryType` weights.
  - Add feature-flag path in `QueryRouter` to use hybrid when enabled; otherwise use existing retriever.
  - Validate: FORM queries prioritize exact keyword hits; SUMMARY queries include semantically similar paragraphs.

- [ ] Task 17: Source highlighting pipeline (success: PDF page/span highlights available)
  - Extend ingestion to store `(pdf_path, page_no, span_start, span_end)` on chunks; update ORM models as needed via Alembic migration (additive only).
  - Add `highlighted_sources` to `QueryResponse` without removing current fields.
  - Build a `SourceHighlighter` to compute spans for returned chunks and include them in responses.
  - Validate: Response includes highlights; existing consumers remain unaffected.

- [ ] Task 18: Minimal PDF viewer endpoint (success: open PDF with highlights)
  - Add a static viewer page and a small endpoint that serves PDFs plus a JSON of highlights for a given response.
  - Keep this as a dev-only feature (flagged) to avoid coupling to production frontend.
  - Validate: Developer can click a link from API response to open a viewer with highlighted regions/pages.

- [ ] Task 19: Table extraction module (success: structured tables retrievable)
  - Implement table extraction in ingestion (prefer Unstructured’s table elements; optionally gate Camelot/Tabula under a flag).
  - Persist tables as JSON with schema (headers, units, rows, row_source → doc/page/span) in a new table `extracted_tables` (Alembic migration).
  - Update retrieval to optionally include table rows in answers; ensure citations point to table page.
  - Validate: Dosage/protocol tables are extractable and queryable; no regressions when disabled.

- [ ] Task 20: Semantic cache (success: lower latency for repeat/similar queries)
  - Implement vectorized cache keys in Redis or DB; store `(query_embedding, response, sources, timestamp)`.
  - Apply for safe types (SUMMARY/CRITERIA/PROTOCOL) with TTLs; always bypass for CONTACT/FORM.
  - Add metrics for hit rate and stale hit prevention; PHI scrubbing on keys/values.
  - Validate: Measurable cache hit rate in dev; no stale answers on updated docs.

- [ ] Task 21: Optional Streamlit demo app (success: dev-only UI works; API untouched)
  - Add a `streamlit` service behind a `ui` compose profile. The app calls existing API endpoints and displays highlights.
  - Validate: `docker compose --profile ui up -d streamlit` → demo available at `:8501`.

- [ ] Task 22: Configuration and flags (success: safe rollout, defaults unchanged)
  - Add `SEARCH_BACKEND`, `ENABLE_HIGHLIGHTS`, `ENABLE_TABLES`, `ENABLE_SEMANTIC_CACHE`, `ENABLE_STREAMLIT` to settings with conservative defaults.
  - Update `README_V8.md` with feature flag documentation and Windows notes.

- [ ] Task 23: Tests for new components (success: CI green)
  - Unit tests: `HybridRetriever` fusion logic, `SourceHighlighter`, table extraction parser, semantic cache policy.
  - Integration: dual indexing, hybrid search path, highlights in responses.
  - Ensure tests skip when optional services are not running.

- [ ] Task 24: Observability (success: metrics visible)
  - Add metrics: ES availability, hybrid latency breakdown, cache hit rate, highlight generation time.
  - Expose via existing observability module; add basic dashboards.

- [ ] Task 25: Backfill and rollout plan (success: no downtime, reversible)
  - Write idempotent backfill for ES and new tables; provide `--dry-run` mode.
  - Rollout stages: enable indexing first; enable hybrid read path on canary env; toggle highlights after validation.
  - Provide rollback: disable flags; delete ES indices if needed.

- [x] Task 26: WSL dependency installation for ingestion (success: tools available in WSL)
  - Document and script install of `poppler-utils`, `tesseract-ocr`, and `libmagic1` in Ubuntu 22.04 (WSL).
  - Validate: `pdftotext -v`, `tesseract --version`, and Python `import magic` succeed.

- [x] Task 27: Single-document ingestion test (success: returns Success: True)
  - Provide a copy-paste WSL command using `PYTHONPATH=/mnt/d/Dev/EDbotv8` to run `DocumentProcessor` on `docs/STEMI Activation.pdf`.
  - Ensure `DATABASE_URL` is set and reachable; confirm record creation in DB.

- [x] Task 28: Full corpus seeding script run (success: all 338 docs processed)
  - Run `scripts/seed_real_documents.py` with appropriate env in WSL; add a Make/PowerShell wrapper for convenience.
  - Capture progress logs and error handling for problematic PDFs without aborting the whole run.

- [x] Task 29: Validation-only pass (success: no missing/invalid documents)
  - Run `scripts/seed_real_documents.py --validate-only` to verify counts and integrity.
  - Emit a concise summary with totals, failures, and suggested retries.

- [x] Task 30: Windows-friendly helpers and docs (success: one-command local validation)
  - Add `scripts/validate.ps1` and WSL bash snippets for common tasks (install, single test, seed, validate).
  - Update `README_V8.md` with exact Windows/WSL commands and path examples.

- [x] Task 31: Basic ingestion observability and retries (success: robust seeding)
  - Add metrics/logging for extraction steps (OCR vs text, table detection) and per-doc timings.
  - Implement retry-once policy for transient failures; produce a CSV report of failures for follow-up.

- [x] Task 32: Ground-truth QA fallback for PROTOCOL (success: correct STEMI answers)
  - Load curated `ground_truth_qa/` into a lightweight index.
  - Route PROTOCOL_STEPS queries to deterministic answers first; fall back to RAG/LLM if no match.
  - Validate: "what is the STEMI protocol" returns concrete steps/timing from STEMI docs with citations.
  - Step-by-step plan:
    - Implement `src/pipeline/qa_index.py` loader:
      - Walk `ground_truth_qa/` recursively; parse both list- and object-shaped JSON; support nested `qa_pairs`.
      - Normalize: lowercase, whitespace collapse, hyphen/slash splitting; store `question`, `answer`, `query_type`, `source_file`, `document`, `source_section`.
      - Token-overlap scorer with conservative threshold (≥0.35) plus domain anchors (e.g., stemi, ottawa) for weak matches.
      - Confidence mapping: `confidence = 0.6 + score*0.4` capped at 1.0; include `qa_fallback` metadata.
    - Integrate into `QueryRouter` for PROTOCOL:
      - Order of operations: QA → tables (`TableRetriever`) → unified retrieval (Hybrid/RAG) → LLM generation.
      - Add `_qa_fallback(query, QueryType.PROTOCOL_STEPS)` and preserve `sources` with `display_name` + `filename` + optional section.
      - Record observability counters: `qa_fallback_hits_total{type="protocol"}`, `qa_fallback_score_bucket`.
    - Guardrails:
      - Only accept QA when score ≥ threshold OR anchors intersect; otherwise bypass.
      - Preserve RAG/LLM paths for recall and non-curated queries.
    - Validation:
      - Manual: STEMI protocol returns timing, pager/contact, pack contents if present; cites correct doc.
      - Unit: match existence + non-empty answer; assert citation filename.

- [x] Task 33: Extend QA fallback to DOSAGE and CRITERIA (success: precise dosing/criteria)
  - Add QueryType-aware fallback for DOSAGE_LOOKUP and CRITERIA_CHECK with conservative threshold.
  - Validate: "epinephrine dose cardiac arrest" and "ottawa ankle criteria" are answered from curated data.
  - Step-by-step plan:
    - DOSAGE:
      - Integrate QA fallback before table retrieval; reuse same threshold/anchors.
      - Improve medication term extraction (simple: keep alphanumerics >3 chars; future: add NER hook).
      - Normalize synonyms (e.g., "epi" → "epinephrine") in a small alias map.
    - CRITERIA:
      - Integrate QA fallback before RAG; on acceptance, return bulletized criteria as-is from curated answer; no reformat.
      - Accept variants like "rules"/"criteria"/"guideline" via tokens.
    - Validation:
      - Epinephrine dosing includes either 0.5 mg IM or 0.01 mg/kg IM; Ottawa outputs criteria sentences; both cite doc.
    - Telemetry:
      - Add dimensioned counters by query_type; emit score histogram for tuning.

- [ ] Task 34: Tighten QueryClassifier/Router mapping (success: correct routing)
  - Ensure STEMI/criteria/dosage/forms map reliably to PROTOCOL_STEPS/CRITERIA_CHECK/DOSAGE_LOOKUP/FORM_RETRIEVAL.
  - Add keyword/anchor-assisted normalization and tests.
  - Step-by-step plan:
    - Add a deterministic pre-classifier overlay:
      - Keyword → QueryType map (protocol: stemi, stroke code, evd, sepsis; criteria: ottawa, wells, perc, nexus, centor; dosage: dose, dosing, mg/kg, mcg; form: consent, form, request).
      - Apply before/if LLM classifier times out or returns low confidence (<0.55).
    - Normalize protocol phrasing: strip leading "what is/are", trailing "protocol", map remaining tokens to anchors.
    - Router safety checks: if QA fallback would match with high score to a different type, re-route (e.g., criteria-matched QA overrides summary).
    - Tests:
      - Parametrized cases for STEMI, Ottawa, Hypoglycemia criteria, Anaphylaxis dosing, CT consent form → expected QueryType.

- [ ] Task 35: Improve citation mapping (success: correct source names/sections)
  - Map answers to correct file plus section/page where available; harmonize registry display names.
  - Validate: citations show `[Source: Document Name]` with section when present.
  - Step-by-step plan:
    - For QA fallback:
      - Include `document` (preferred) else `source_file` as `display_name`.
      - Include `source_section` when present; keep minimal (no hallucinated page numbers).
    - For DB/RAG paths:
      - Use `DocumentRegistry.display_name` if present else filename→title.
      - If we extract table rows with page context later, add `page` field (future PRP 17 alignment).
    - Response schema:
      - Ensure sources are list of dicts: `{display_name, filename, section?}`.
      - Add light validator to prevent empty or duplicated sources.
    - Tests:
      - STEMI and Ottawa: assert source includes correct `display_name` and `filename` from curated set.

- [ ] Task 36: Prompt and LLM parameter tuning (success: specific, doc-only answers)
  - Enforce strict document-only prompting; set temperature/top_p low; add per-QueryType instruction blocks.
  - Validate: no generic boilerplate; include specific numbers and steps.
  - Step-by-step plan:
    - Parameters:
      - `temperature=0.0`, `top_p=0.1`, `max_tokens=800` for protocol/criteria/dosage; shorter for contact/form.
    - Prompts:
      - Per-QueryType templates emphasizing: use ONLY provided context; include numbers/timings; must cite `[Source: ...]`; say "insufficient information" if not present.
      - Prevent boilerplate by including explicit negative instruction: do not add general medical knowledge.
    - Fallback logic:
      - Only call LLM when QA and RAG paths fail or when synthesis is explicitly required (SUMMARY).
    - Tests:
      - Snapshot or assertion-based tests ensuring prompt contains doc-only guardrails and correct source list.

- [ ] Task 37: Regression tests for curated QA (success: baseline green)
  - Add tests for STEMI protocol, epinephrine dose, Ottawa ankle rules; iterate threshold if needed.
  - Automate check to guard against regressions in CI.
  - Step-by-step plan:
    - Unit tests:
      - `tests/unit/test_qa_fallback.py`: STEMI presence; epi dosing keywords; Ottawa criteria existence with skip if missing.
    - Integration smoke (optional):
      - Spin up minimal app context; call router with queries; verify QA fallback sets `metadata.qa_fallback=True` and sources populated.
    - CI:
      - Ensure tests run as part of `make test`; add badge/summary.
    - Tuning loop:
      - If false positives: raise threshold to 0.4; if false negatives on known anchors: add synonyms to anchor set.

- [ ] Task 38: Expand coverage & monitoring (success: broad QA alignment)
  - Gradually extend curated fallback across remaining `ground_truth_qa` categories.
  - Add metrics for QA-fallback hit rate and confidence; dashboard for quality monitoring.
  - Step-by-step plan:
    - Coverage plan (phased):
      - Phase 1 (done): STEMI, epinephrine dosing, Ottawa ankle.
      - Phase 2: Hypoglycemia, Anaphylaxis, Stroke BP/tPA, EVD steps.
      - Phase 3: Pediatric pathways (CAP, UTI, SSTI, Nephrolithiasis), RETU pathways.
    - Monitoring:
      - Add counters: `qa_fallback_hits_total{type}`, `qa_fallback_misses_total{type}`; histogram `qa_score`.
      - Dashboard tiles: hit rate by type; score distribution; top queries; proportion QA vs RAG vs LLM.
    - Quality gates:
      - Alert if hit rate drops >20% week-over-week or average score <0.4.
      - Sample and manually review 10 QA answers/week.

- [ ] Task 39: Restore API availability on :8001 (success: health and query OK)
  - Verify Docker compose `api` service is running and `ports: ["8001:8001"]` present; rebuild if needed.
  - Ensure Uvicorn binds `0.0.0.0:8001`; add explicit flags in entrypoint/compose.
  - Add/verify `/health-simple` and `/health` endpoints return 200.
  - Validate: `curl :8001/health-simple` returns 200; POST `/api/v1/query` works.
  - Step-by-step plan:
    - Inspect `docker-compose.v8.yml` → `services.api.ports` contains `"8001:8001"` and `command`/`entrypoint` runs `uvicorn src.api.app:app --host 0.0.0.0 --port 8001`.
    - `docker compose logs -f api | cat` to confirm startup and no crash loops.
    - If local run: ensure env `PORT=8001` or CLI flag binds 8001 and host `0.0.0.0`.
    - Confirm routes: `GET /health-simple` and/or `GET /health` implemented and wired under `/api/v1` if applicable.
    - If port collision on Windows, suggest alternate port mapping `8002:8001` and update frontend `.env`/Base URL.
    - Add healthcheck block in compose for faster diagnostics.

- [ ] Task 40: Fix response schema usage and error path (success: no generic unknown)
  - Ensure `QueryResponse.sources` uses dicts `{display_name, filename}` end-to-end.
  - Audit endpoints/routers for schema mismatches and update formatting.
  - Validate: STEMI, consent form, epi dosing, Ottawa queries return 200 with sources.
  - Step-by-step plan:
    - Grep for `.get("sources")` producers in `src/pipeline/router.py`, `src/api/endpoints*.py`, any services; standardize to dict form.
    - In `QueryProcessor`, keep `List[Dict[str,str]]` and remove leftover string-based code paths; add minimal validator to drop empty/dup sources.
    - Update tests or add unit tests asserting structured sources and successful pydantic serialization.
    - Ensure error handler returns meaningful `query_type` from enum where known; avoid hardcoded `"unknown"` if classification succeeded.

- [ ] Task 41: Add standard security headers (success: headers present)
  - Add FastAPI middleware to set `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (minimal), and basic `Content-Security-Policy` for dev.
  - Validate: audit passes for these headers.
  - Step-by-step plan:
    - Create `src/api/security.py` with a Starlette `BaseHTTPMiddleware` that injects headers on all responses.
    - Defaults (dev-safe):
      - `X-Content-Type-Options: nosniff`
      - `X-Frame-Options: SAMEORIGIN`
      - `Referrer-Policy: no-referrer`
      - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
      - `Content-Security-Policy: default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'` (relax inline only if needed for existing CSS)
    - Register middleware in `src/api/app.py` after app creation.
    - Add setting/flag to disable CSP locally if it blocks dev features.

- [ ] Task 42: Enforce UTF-8 charset in responses (success: charset=utf-8)
  - Set default response class/content-type with `charset=utf-8` for HTML/text routes and static.
  - Validate: audit states charset is `utf-8`.
  - Step-by-step plan:
    - Ensure Uvicorn/Starlette serves `text/html; charset=utf-8` for `HTMLResponse` and templates (add `<meta charset="utf-8">`).
    - For any `PlainTextResponse` or manual headers, include `charset=utf-8`.
    - Configure `StaticFiles` mount with `headers={"Cache-Control": ..., "Accept-Charset": "utf-8"}` if needed; verify actual `Content-Type` includes charset for text assets.

- [ ] Task 43: Harden cookies (success: secure, httponly, samesite)
  - If app sets cookies, ensure `HttpOnly`, `Secure` (when HTTPS), and `SameSite=Lax/Strict`.
  - If not used, remove unintended `Set-Cookie` headers.
  - Validate: audit shows compliant cookies.
  - Step-by-step plan:
    - Search for `set_cookie`/`Response.set_cookie` usage; centralize in a helper `set_secure_cookie(response, ...)` that applies `httponly=True`, `samesite="Lax"`, `secure=ENV_IS_HTTPS`.
    - Ensure no framework session cookie is emitted inadvertently (disable sessions if unused).
    - Add test that inspects response headers for absent/included flags appropriately.

- [ ] Task 44: Cache busting for static assets (success: assets versioned)
  - Add version hash or `?v=` query param for CSS/JS; set `Cache-Control` for static.
  - Validate: audit no longer flags missing cache busting.
  - Step-by-step plan:
    - Introduce `STATIC_VERSION` (env or git short sha) in settings.
    - Update `static/index.html` references to `/static/app.css?v={{STATIC_VERSION}}` and `/static/app.js?v={{STATIC_VERSION}}` (if templated) or prebuild inject.
    - Configure `StaticFiles` to set `Cache-Control: public, max-age=31536000, immutable` for versioned assets; `no-store` for HTML.

- [ ] Task 45: Remove protocol-relative URLs (success: explicit schemes)
  - Replace `//` URLs with `https://` or relative paths in HTML/JS.
  - Validate: audit passes this check.
  - Step-by-step plan:
    - Grep repo for `src=\"//` and `href=\"//`; replace with explicit `https://` where external, or relative `/...` for internal.
    - Re-run audit to confirm no protocol-relative references remain.

- [ ] Task 46: Accessibility fixes (success: a11y checks green)
  - Add `id`/`name` to inputs, link `<label>` via `for`, correct `autocomplete` values.
  - Validate: basic axe/core rules pass locally.
  - Step-by-step plan:
    - In `static/index.html`, ensure the main input and any forms have `id`, `name`, and a `<label for>` or `aria-label`.
    - Replace nonstandard `autocomplete` values with valid tokens (e.g., `off`, `one-time-code`, or domain-specific ones aren't allowed).
    - Add landmarks/roles (`role="main"`, `aria-live` for streaming output if applicable) and verify keyboard focus order.
    - Run a quick `axe-core` or Lighthouse a11y check and address remaining high-severity items.

# Project Status Board - M4 OPTIMIZATION PLAN

## CURRENT STATUS (Apple Silicon M4 Pro - 24GB RAM)
- ✅ **Infrastructure**: Ollama (Llama 3.1:8b), PostgreSQL (port 5433), Redis (port 6380) all running
- ❌ **API**: Failing to start due to Settings class conflicts and missing attributes
- ❌ **Dependencies**: ml_dtypes version conflict blocking table extraction
- ✅ **LLM Backend**: Ollama responding in ~22 seconds (good M4 performance)

## BULLETPROOF EXECUTION PLAN

### PHASE 1: CONFIGURATION CLEANUP (CRITICAL - BLOCKING API STARTUP)
**Target**: API starts successfully and responds to health checks
- [x] Task 1.1: Fix Settings import conflicts (EnhancedSettings vs Settings)
- [ ] Task 1.2: Add ALL missing attributes to EnhancedSettings class
- [ ] Task 1.3: Audit and fix ALL remaining Settings references in codebase
- [ ] Task 1.4: Validate configuration loads without AttributeError

### PHASE 2: DEPENDENCY RESOLUTION (HIGH PRIORITY)
**Target**: Clean Python environment without version conflicts
- [ ] Task 2.1: Disable table extraction temporarily (comment out imports)
- [ ] Task 2.2: Fix ml_dtypes version conflict or disable unstructured
- [ ] Task 2.3: Create M4-optimized feature flags (disable heavy features)
- [ ] Task 2.4: Test API import without dependency errors

### PHASE 3: CORE API FUNCTIONALITY (HIGH PRIORITY)
**Target**: Working query pipeline end-to-end
- [ ] Task 3.1: Fix QueryClassifier method name (classify vs classify_query)
- [ ] Task 3.2: Complete database schema setup and migrations
- [ ] Task 3.3: Test basic API endpoints (/health, /query)
- [ ] Task 3.4: Verify Ollama integration works with API

### PHASE 4: DOCUMENT PROCESSING (MEDIUM PRIORITY)
**Target**: Basic document ingestion without advanced features
- [ ] Task 4.1: Implement simple PDF processing (no table extraction)
- [ ] Task 4.2: Ingest 5-10 sample medical documents
- [ ] Task 4.3: Test query responses with actual document content
- [ ] Task 4.4: Validate citation and source mapping

### PHASE 5: M4 PERFORMANCE OPTIMIZATION (LOW PRIORITY)
**Target**: Optimal resource utilization on M4 Pro
- [ ] Task 5.1: Monitor memory usage (keep under 20GB of 24GB)
- [ ] Task 5.2: Optimize Ollama model parameters for M4
- [ ] Task 5.3: Enable performance metrics and monitoring
- [ ] Task 5.4: Fine-tune response times (target <30 seconds)

## IMMEDIATE BLOCKERS TO RESOLVE
1. **Settings Class Hell**: Multiple references to old Settings class throughout codebase
2. **Missing Attributes**: EnhancedSettings missing expected attributes (async_database_url, etc.)
3. **Import Conflicts**: Table extraction imports causing ml_dtypes version conflicts
4. **Method Name Mismatch**: QueryClassifier.classify vs classify_query

## SUCCESS CRITERIA
- ✅ API starts without errors and responds to /health
- ✅ Query endpoint returns responses from Ollama
- ✅ At least 5 medical documents successfully indexed
- ✅ Memory usage stays under 20GB
- ✅ Query response time under 30 seconds

# Executor's Feedback or Assistance Requests
- CPU path implemented. Do you want me to auto-pull a small Ollama model (e.g., `gemma2:2b`) on startup, or keep it manual for now?
- When ready, confirm CUDA version to pin `VLLM_IMAGE`.
- For Mistral: prefer tag `mistral:7b` (≈4.1GB) or a specific instruct variant/tag (e.g., `mistral:latest` vs `mistral:7b-instruct-v0.2`)? I will align both settings and compose accordingly.
 - To unblock API now, I propose implementing Task 9 next (rename reserved `metadata` attrs). If you want a faster first boot, I can also switch the default CPU model to `phi3:mini` (Task 10) and leave Mistral as opt‑in.
 - Immediate unblock proposal: implement Task 11 (1-line fix in `QueryProcessor`) so queries stop 500-ing; then do Task 12 (code-forward adjustment) to get form/protocol flows working without DB schema changes.

# Lessons
- Treat GPU inference as optional for dev; do not block core services on LLM.
- Use Compose profiles to scope optional services; never hard‑wire them in `depends_on`.
- Implement a backend factory early so new providers (Ollama, Azure) are drop‑in. 
- Keep a single source of truth for the Ollama model (env + settings); avoid reusing unrelated defaults like `langextract_local_model`. 