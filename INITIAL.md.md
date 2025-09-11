## FEATURE:
ED Bot v8: On‑prem medical assistant with local GPT‑OSS 20B backend, Unstructured+LangExtract ingestion, and an intent‑aware 3‑step pipeline. Must:
- Classify into CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY
- Return actual PDFs for FORM queries with reliable download/preview
- Preserve citations for all responses
- Enforce HIPAA by default (no external inference, scrub logs)
- Provide Docker Compose + Makefile + Alembic for reproducible setup

## EXAMPLES:
Use existing examples in `examples/` as inspiration for content/flow checks (do not copy). For v8, add:
- `examples/forms_query.md` – Expected output with `[PDF:/api/v1/documents/pdf/{filename}|{display_name}]`
- `examples/protocol_query.md` – Stepwise protocol with contacts/timing and citations
- `examples/contact_query.md` – On‑call contact examples (Amion driven) with fallback language
Each example should include: query text, expected classification, response outline, and source list.

## DOCUMENTATION:
- GPT‑OSS 20B: https://huggingface.co/openai/gpt-oss-20b
- LangExtract: https://github.com/google/langextract#installation
- Unstructured: https://docs.unstructured.io/
- FastAPI: https://fastapi.tiangolo.com/
- Alembic: https://alembic.sqlalchemy.org/

## OTHER CONSIDERATIONS:
- Always bypass cache for FORM queries; inject PDF refs on cached responses as a safety net
- Deterministic decoding for clinical responses: temperature=0.0, top_p≤0.1, explicit stop tokens
- Add `.env.example`; never commit real secrets
- Pin dependency and model versions; weekly upgrade window with regression tests
- Provide health endpoints for API/DB/Redis/LLM; add basic metrics (latency, cache hit, tokens/sec) 