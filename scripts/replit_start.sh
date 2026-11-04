#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d web/dist ]; then
  echo "Build is missing. Run bash scripts/replit_build.sh first." >&2
  exit 1
fi
if [ -f .venv/pyvenv.cfg ] && [ -x .venv/bin/python ]; then
  FRAMEKIND_PYTHON=.venv/bin/python
elif [ -z "${REPL_ID:-}" ] && [ -n "${VIRTUAL_ENV:-}" ] && [ -f "$VIRTUAL_ENV/pyvenv.cfg" ]; then
  # Keep an explicitly activated local virtual environment usable.
  FRAMEKIND_PYTHON="$VIRTUAL_ENV/bin/python"
else
  echo "Project virtual environment is missing. Run bash scripts/replit_build.sh first." >&2
  exit 1
fi
PORT="${PORT:-8000}"
# One process owns the background jobs and event streams. Use a Reserved VM
# deployment, or an Autoscale deployment constrained to one instance.
exec "$FRAMEKIND_PYTHON" -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
