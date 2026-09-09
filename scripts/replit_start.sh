#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d web/dist ]; then
  echo "Build is missing. Run bash scripts/replit_build.sh first." >&2
  exit 1
fi
PORT="${PORT:-8000}"
# One process owns the background jobs and event streams. Use a Reserved VM
# deployment, or an Autoscale deployment constrained to one instance.
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
