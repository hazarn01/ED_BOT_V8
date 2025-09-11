FEATURE:
ED Bot v8 starter pack: local GPT‑OSS 20B LLM service, ingestion worker (Unstructured+LangExtract), and FastAPI API with 3‑step intent‑aware pipeline. Includes command‑line tools to seed registry and verify PDF endpoints. Amion contact lookup integrated with fallback.

EXAMPLES:
In the `examples/` folder, provide:
- README.md – How to validate v8 features and structure your own examples for new specialties and forms
- examples/cli_seed.py – minimal CLI to trigger ingestion on a directory and view registry stats
- examples/queries/ – example queries and expected shapes
  - forms.md – form queries, expected `[PDF:/api/v1/documents/pdf/{filename}|{display_name}]` entries, and links
  - protocol.md – STEMI/sepsis protocol examples with step/timing/contacts
  - contact.md – cardiology/EP on‑call examples (Amion driven)
Use these as inspiration and best practices; do not copy into production code.

DOCUMENTATION:
- GPT‑OSS 20B (on‑prem LLM): https://huggingface.co/openai/gpt-oss-20b
- LangExtract: https://github.com/google/langextract#installation
- Unstructured PDF parsing: https://docs.unstructured.io/
- FastAPI: https://fastapi.tiangolo.com/
- Redis: https://redis.io/docs/
- PostgreSQL + pgvector: https://github.com/pgvector/pgvector

OTHER CONSIDERATIONS:
- Include `.env.example`, `README.md` with setup steps (Compose/Makefile/Alembic), and a project structure tree
- Use `python-dotenv` and load `.env` on startup for local dev
- Pin versions for LangExtract, Unstructured, and serving stack; document the weekly upgrade routine
- Provide health checks for API/DB/Redis/LLM and basic metrics endpoints; add a lightweight terminal validator script to test the PDF endpoint and query flow 