#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d "evidence_api/.venv" ]; then
  python3 -m venv evidence_api/.venv
fi
source evidence_api/.venv/bin/activate
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
  python -m pip install --upgrade pip
  if [ -d "wheels" ]; then
    python -m pip install --no-index --find-links=wheels -r evidence_api/requirements.txt
  else
    python -m pip install -r evidence_api/requirements.txt
  fi
fi
exec python -m uvicorn evidence_api.main:app --host 127.0.0.1 --port 8000 --reload
