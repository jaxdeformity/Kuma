#!/bin/bash
# Install/refresh KUMA's always-on systemd services on the Pi.
# Run on the Pi from the repo root:  sudo bash deploy/install-services.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[*] installing monitor-setup script"
install -m 0755 "$HERE/kuma-monitor.sh" /usr/local/sbin/kuma-monitor.sh

echo "[*] installing unit files"
install -m 0644 "$HERE/systemd/kuma-monitor.service"   /etc/systemd/system/
install -m 0644 "$HERE/systemd/kuma-capture.service"   /etc/systemd/system/
install -m 0644 "$HERE/systemd/kuma-authwatch.service" /etc/systemd/system/

echo "[*] reloading systemd"
systemctl daemon-reload

echo "[*] enabling + (re)starting services"
systemctl enable kuma-monitor.service kuma-capture.service kuma-authwatch.service
systemctl restart kuma-monitor.service
systemctl restart kuma-capture.service
systemctl restart kuma-authwatch.service

echo "[*] status"
for s in kuma-backend kuma-monitor kuma-capture kuma-authwatch; do
  printf "  %-18s %s / %s\n" "$s" \
    "$(systemctl is-enabled "$s".service 2>/dev/null)" \
    "$(systemctl is-active "$s".service 2>/dev/null)"
done
echo "[done] KUMA is always-on. Detectors auto-start on boot."
