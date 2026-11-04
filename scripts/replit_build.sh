#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Replit's .pythonlibs is a user-package prefix, not a virtual environment.
# Explicitly target .venv and install the checked-in dependency lock.
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to build FrameKind from uv.lock." >&2
  exit 1
fi
UV_PROJECT_ENVIRONMENT=.venv uv sync --frozen --no-dev
(cd web && npm ci && npm run build)
