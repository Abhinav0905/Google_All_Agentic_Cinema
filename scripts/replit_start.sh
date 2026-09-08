#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -e .
if [ ! -d web/node_modules ]; then
  (cd web && npm install)
fi
if [ ! -d web/dist ]; then
  (cd web && npm run build)
fi
PORT="${PORT:-8000}"
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
