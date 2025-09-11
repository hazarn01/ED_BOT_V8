#!/usr/bin/env bash
set -euo pipefail

# Single-document ingestion example for WSL
# Usage: ./single_ingest_example.sh "/mnt/d/Dev/EDbotv8/docs/STEMI Activation.pdf" protocol

FILE_PATH=${1:-/mnt/d/Dev/EDbotv8/docs/STEMI\ Activation.pdf}
CONTENT_TYPE=${2:-protocol}

export PYTHONPATH=/mnt/d/Dev/EDbotv8
export DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/edbot}

python3 - <<PY
import asyncio
import os
from src.ingestion.tasks import process_document

file_path = r"${FILE_PATH}"
content_type = r"${CONTENT_TYPE}"

async def main():
    ok = await process_document(file_path, content_type)
    print({"Success": bool(ok)})

asyncio.run(main())
PY
