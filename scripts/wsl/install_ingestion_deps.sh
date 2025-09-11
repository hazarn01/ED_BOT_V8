#!/usr/bin/env bash
set -euo pipefail

# WSL Ubuntu 22.04 ingestion dependencies installer
# Installs poppler-utils (pdftotext), tesseract-ocr, and libmagic1

if ! command -v lsb_release >/dev/null 2>&1; then
  echo "This script must run inside WSL Ubuntu." >&2
  exit 1
fi

. /etc/os-release
if [ "${ID}" != "ubuntu" ]; then
  echo "This script supports Ubuntu only (detected ${PRETTY_NAME})." >&2
  exit 1
fi

echo "Updating apt index..."
sudo apt-get update -y

echo "Installing packages..."
sudo apt-get install -y poppler-utils tesseract-ocr libtesseract-dev libmagic1 python3-magic

# Optional: common OCR languages
if [ -n "${INSTALL_OCR_LANGS:-}" ]; then
  echo "Installing extra OCR languages: ${INSTALL_OCR_LANGS}"
  sudo apt-get install -y ${INSTALL_OCR_LANGS}
fi

echo "\nVersions:"
if command -v pdftotext >/dev/null 2>&1; then pdftotext -v | head -n 2; else echo "pdftotext missing"; fi
if command -v tesseract >/dev/null 2>&1; then tesseract --version | head -n 2; else echo "tesseract missing"; fi

python3 - <<'PY'
try:
    import magic
    print("python-magic OK")
except Exception as e:
    print(f"python-magic import failed: {e}")
PY

echo "\nDone."
