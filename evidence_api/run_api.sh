#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install deps
pip install -U pip
pip install -r requirements.txt

# Run API
uvicorn main:app --reload --port 8000
