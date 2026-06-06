#!/usr/bin/env bash
# KUMA Guard — put a USB Wi-Fi interface into monitor mode.
# Usage: sudo ./set_monitor_mode.sh wlan1
# Conservative: brings the interface down, sets monitor type, brings it up,
# and prints the result. Not used by Sprint 1 (mock mode needs no hardware).
set -euo pipefail

IFACE="${1:-wlan1}"

if [ "$(id -u)" -ne 0 ]; then
  echo "[KUMA] Run as root: sudo $0 $IFACE"
  exit 1
fi

if ! command -v iw >/dev/null 2>&1; then
  echo "[KUMA] 'iw' not found. Install: sudo apt install -y iw"
  exit 1
fi

echo "[KUMA] Setting $IFACE to monitor mode..."
ip link set "$IFACE" down
iw dev "$IFACE" set type monitor
ip link set "$IFACE" up

echo "[KUMA] Done. Current state:"
iw dev "$IFACE" info || true
