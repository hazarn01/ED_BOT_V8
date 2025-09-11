#!/usr/bin/env bash
set -euo pipefail

# Full corpus seeding wrapper (WSL)
# Optional args: docs path, batch size

DOCS=${1:-/mnt/d/Dev/EDbotv8/docs}
BATCH=${2:-10}

export PYTHONPATH=/mnt/d/Dev/EDbotv8
export DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/edbot}

python3 scripts/seed_real_documents.py --docs-path "$DOCS" --batch-size "$BATCH"
