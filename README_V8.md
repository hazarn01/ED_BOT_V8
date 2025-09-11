# Background

# ED Bot v8 - README (Scaffold)

## Overview
On‑prem medical assistant using GPT‑OSS 20B, Unstructured+LangExtract ingestion, and an intent‑aware 3‑step pipeline. Built for HIPAA compliance, reproducibility, and performance.

## Quickstart
```
cp EDBOTv8.env.example .env
make up-cpu   # CPU-friendly default with Ollama
make upgrade
python -m scripts.seed_registry --path docs/
```

Smoke tests
```
curl http://localhost:8001/health | jq
curl -I http://localhost:8001/documents/pdf/24hrPharmacies.pdf
curl -s -X POST http://localhost:8001/api/v1/query -H 'Content-Type: application/json' -d '{"query":"show me the blood transfusion form"}' | jq
```

## Compose Topology
- db: Postgres + pgvector
- redis: caching
- llm: vLLM (GPT‑OSS 20B) [gpu profile]; `ollama` as CPU alternative [cpu profile]
- api: FastAPI service
- worker: ingestion (Unstructured + LangExtract)

## Makefile Targets
- `make up` – start stack (no profiles)
- `make up-cpu` – start stack with CPU Ollama profile (also pre-pulls model via `ollama-pull`)
- `make up-gpu` – start stack with GPU vLLM profile
- `make down` – stop stack
- `make upgrade` – apply DB migrations
- `make migrate` – create migration (autogenerate)
- `make ingest` – run ingestion on docs/
- `make logs` – tail compose logs
- `make test` – run tests
- `make diag` – environment diagnostics (GPU/Compose info)

## Configuration
Set via `.env`:
- `LLM_BACKEND` (gpt-oss|ollama|azure). Default is `ollama` for CPU path.
- `VLLM_BASE_URL` or `OLLAMA_BASE_URL`
- `OLLAMA_DEFAULT_MODEL` (default `mistral:7b-instruct`) – pre-pulled on `make up-cpu`
- `VLLM_IMAGE` – optional override to pin vLLM image for your CUDA version
- DB/Redis host/ports
- HIPAA flags (LOG_SCRUB_PHI, DISABLE_EXTERNAL_CALLS)

## CPU Mode (Ollama)
- Bring up with: `make up-cpu`
- Model pre-pull: (default `mistral:7b`) is pulled automatically by `ollama-pull` init service
- Change model by setting `OLLAMA_DEFAULT_MODEL` in `.env` (you can also override the runtime via `OLLAMA_MODEL`)

## GPU Mode (vLLM)
- Bring up with: `make up-gpu`
- Health checks: `curl http://localhost:8000/health` and `curl http://localhost:8000/v1/models`
- If vLLM fails due to CUDA mismatch:
  - Update NVIDIA drivers and Docker GPU runtime, or
  - Pin image via `.env` `VLLM_IMAGE`, e.g. `vllm/vllm-openai:0.6.2-cuda12.4`

## Troubleshooting
- LLM cold start: first response is slower; check service health
- PDFs 404: ensure `docs/` volume mounted and file exists
- Windows GPU: Use WSL2 + latest NVIDIA drivers; enable GPU in Docker Desktop
- Diagnostics: `make diag` to print GPU and runtime info

## Windows/WSL Ingestion Setup

Run these inside Ubuntu 22.04 WSL:

1) Install ingestion dependencies (pdftotext, Tesseract, libmagic):
```
bash scripts/wsl/install_ingestion_deps.sh
```

2) Single-document ingestion test (example: STEMI Activation.pdf):
```
bash scripts/wsl/single_ingest_example.sh "/mnt/d/Dev/EDbotv8/docs/STEMI Activation.pdf" protocol
```

3) Full corpus seeding:
```
bash scripts/wsl/seed_corpus.sh /mnt/d/Dev/EDbotv8/docs 10
```

4) Validation-only pass:
```
bash scripts/wsl/validate_only.sh /mnt/d/Dev/EDbotv8/docs
```

Notes:
- Ensure `PYTHONPATH=/mnt/d/Dev/EDbotv8` and `DATABASE_URL` are set for WSL environment.
- Use WSL paths (`/mnt/d/...`) when invoking Python inside WSL.

## References
- GPT‑OSS 20B: https://huggingface.co/openai/gpt-oss-20b
- LangExtract: https://github.com/google/langextract#installation
- Unstructured: https://docs.unstructured.io/ 