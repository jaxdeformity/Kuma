"""Rogue AP detection - observations vs the trusted baseline.

SKELETON for Sprint 1. Compares live observations against trusted_networks.json
and the known_aps table. Signals (see docs/detection-logic.md):

    same SSID + unknown BSSID        -> suspicious      (medium)
    same SSID + changed channel      -> low/medium
    unknown BSSID repeatedly seen    -> confidence climbs
    known BSSID missing a long time  -> informational
"""
from __future__ import annotations

from kuma_core import events


class RogueApDetector:
    def __init__(self, trusted_networks: list[dict]) -> None:
        # index trusted BSSIDs per SSID for quick lookup
        self.trusted: dict[str, set[str]] = {}
        for net in trusted_networks:
            self.trusted[net["ssid"]] = {b.upper() for b in net.get("bssids", [])}

    def evaluate(self, observation: dict) -> dict | None:
        ssid = observation.get("ssid")
        bssid = (observation.get("bssid") or "").upper()
        if ssid not in self.trusted:
            return None  # unknown SSID handled by the foraging/new-AP path
        if bssid in self.trusted[ssid]:
            return None  # known-good
        return events.make_event(
            mode="sentinel",
            event_type="new_bssid_for_known_ssid",
            confidence=48,
            message="New BSSID advertising a known SSID",
            ssid=ssid, bssid=bssid,
            channel=observation.get("channel"),
            rssi=observation.get("rssi"),
            raw_json={"trusted_bssids": sorted(self.trusted[ssid])},
        )
