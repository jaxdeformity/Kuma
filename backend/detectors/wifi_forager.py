"""Wi-Fi Foraging - AP discovery and baseline building.

SKELETON for Sprint 1. The real implementation (Sprint 2) wraps simple Linux
tooling first (``iw dev <iface> scan``, ``nmcli -f ... dev wifi``) before any
scapy/tshark packet parsing. Prefer reliable command wrappers over clever
frame parsing - get the pipeline working, then deepen.

Honesty rule: foraging NEVER auto-trusts a network. Observations land in the
``observations`` table; promotion to ``trusted_networks.json`` is an explicit,
human-confirmed action.
"""
from __future__ import annotations

import subprocess  # noqa: F401  (used by the real implementation)

from kuma_core import database, events


class WifiForager:
    def __init__(self, interface: str) -> None:
        self.interface = interface

    def scan(self) -> list[dict]:
        """Return a list of observed APs.

        Sprint 1: returns []. Sprint 2: parse ``iw dev <iface> scan`` output
        into observation dicts {ssid, bssid, channel, rssi, security}.
        """
        # TODO(sprint2): shell out to `iw` / `nmcli`, parse, return obs dicts.
        return []

    def record(self, observation: dict) -> None:
        """Persist a raw observation. Does not touch the trusted baseline."""
        database.insert_observation(
            {**observation, "timestamp": events.utcnow_iso(),
             "source": "forager"}
        )
