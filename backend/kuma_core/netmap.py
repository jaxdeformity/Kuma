"""Host Wi-Fi connection logging (KUMA's own uplink).

Best-effort: reads the currently connected SSID via nmcli (or iwgetid), records
new connections, and awards 'connect' XP the first time KUMA joins a network.
No-op on platforms without those tools (e.g. dev laptops / CI).
"""
from __future__ import annotations

import shutil
import subprocess

from kuma_core import database, progress


def current_ssid() -> str | None:
    try:
        if shutil.which("nmcli"):
            out = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            for line in out.splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1].strip() or None
        if shutil.which("iwgetid"):
            out = subprocess.run(
                ["iwgetid", "-r"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
            return out or None
    except Exception:  # noqa: BLE001 - best effort, never crash the poller
        return None
    return None


def poll_once() -> dict | None:
    """Log the current connection; award connect XP if it's a new network."""
    ssid = current_ssid()
    if not ssid:
        return None
    try:
        if database.record_connection(ssid):
            return progress.award("connect")
    except Exception:  # noqa: BLE001
        return None
    return None
