#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH=src
exec uvicorn aviation_ai.server:app --host 127.0.0.1 --port 8000 "$@"
