#!/usr/bin/env bash
# KUMA Guard — Raspberry Pi setup.
# Conservative: creates a venv, installs Python deps, initializes the DB.
# Re-runnable. Does NOT touch your Wi-Fi config or enable monitor mode.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # backend/
cd "$HERE"

echo "[KUMA] Setting up in: $HERE"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[KUMA] python3 not found. Install it first: sudo apt install -y python3 python3-venv"
  exit 1
fi

# System packages useful for Sprint 2 Wi-Fi work (safe to install now).
if command -v apt-get >/dev/null 2>&1; then
  echo "[KUMA] Installing system packages (iw, tcpdump)..."
  sudo apt-get update -y
  sudo apt-get install -y iw tcpdump || echo "[KUMA] (optional packages skipped)"
fi

echo "[KUMA] Creating virtualenv (.venv)..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[KUMA] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[KUMA] Initializing database..."
python3 -c "from kuma_core import database; database.init_db(); print('  db ready at', database.DB_PATH)"

cat <<'NEXT'

[KUMA] Setup complete.

Next steps:
  source .venv/bin/activate
  ./scripts/start_kuma.sh            # mock mode (no Wi-Fi hardware needed)

Then browse:
  http://<pi-ip>:8080/api/status
  http://<pi-ip>:8080/docs          # interactive API docs

NEXT
