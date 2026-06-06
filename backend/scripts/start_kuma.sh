#!/usr/bin/env bash
# KUMA Guard — start the backend API.
#   ./start_kuma.sh            # mock mode (default, Sprint 1)
#   KUMA_MOCK=0 ./start_kuma.sh  # disable the synthetic event loop
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # backend/
cd "$HERE"

# Activate venv if present.
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

HOST="${KUMA_HOST:-0.0.0.0}"
PORT="${KUMA_PORT:-8080}"

echo "[KUMA] Starting backend on ${HOST}:${PORT} (mock=${KUMA_MOCK:-1})"
exec uvicorn kuma_api.app:app --host "$HOST" --port "$PORT"
