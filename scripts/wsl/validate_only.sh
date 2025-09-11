#!/usr/bin/env bash
set -euo pipefail

# Validation-only pass for seeded documents (WSL)

DOCS=${1:-/mnt/d/Dev/EDbotv8/docs}

export PYTHONPATH=/mnt/d/Dev/EDbotv8
export DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/edbot}

python3 scripts/seed_real_documents.py --docs-path "$DOCS" --validate-only
