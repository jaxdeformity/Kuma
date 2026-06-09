#!/bin/bash
# KUMA monitor-mode setup. Waits for the Alfa (wlan1) to enumerate after boot
# (USB + out-of-tree 8821au driver can appear several seconds late), frees it
# from any network manager, and puts it in monitor mode for the detector.
#
# Installed to /usr/local/sbin/kuma-monitor.sh, run by kuma-monitor.service.
set -u
IF=wlan1

# 1. wait up to ~30s for the interface to exist
for _ in $(seq 1 30); do
  ip link show "$IF" >/dev/null 2>&1 && break
  sleep 1
done
if ! ip link show "$IF" >/dev/null 2>&1; then
  echo "kuma-monitor: $IF never appeared" >&2
  exit 1
fi

# 2. stop anything that would fight monitor mode (best effort)
if command -v nmcli >/dev/null 2>&1; then
  nmcli device set "$IF" managed no >/dev/null 2>&1 || true
fi
if command -v rfkill >/dev/null 2>&1; then
  rfkill unblock wifi >/dev/null 2>&1 || true
fi

# 3. monitor mode
ip link set "$IF" down
iw dev "$IF" set type monitor
ip link set "$IF" up
iw dev "$IF" set channel 6    # detector channel-hops; this is just a sane default

echo "kuma-monitor: $IF is $(iw dev "$IF" info | awk '/type/{print $2}')"
