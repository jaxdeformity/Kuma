"""Evil-twin detection - rogue AP that also looks like a security/RF anomaly.

SKELETON for Sprint 1. Builds on RogueApDetector: a new BSSID for a known SSID
is *suspicious*; if it also shows a security downgrade or a suspicious RSSI jump
it escalates toward *evil twin*. Security downgrade pins severity to >= high
regardless of raw confidence, because that's the high-impact case.
"""
from __future__ import annotations

from kuma_core import events

# Loose ranking so "WPA3 -> WPA2 -> WPA -> OPEN" reads as a downgrade.
_SEC_RANK = {"OPEN": 0, "WEP": 1, "WPA": 2, "WPA2": 3, "WPA2/WPA3": 4, "WPA3": 5}


def _is_downgrade(expected: str | None, seen: str | None) -> bool:
    if not expected or not seen:
        return False
    return _SEC_RANK.get(seen, 99) < _SEC_RANK.get(expected, -1)


class EvilTwinDetector:
    def __init__(self, trusted_networks: list[dict]) -> None:
        self.expected_security = {
            n["ssid"]: n.get("expected_security") for n in trusted_networks
        }
        self.trusted_bssids = {
            n["ssid"]: {b.upper() for b in n.get("bssids", [])}
            for n in trusted_networks
        }

    def evaluate(self, observation: dict) -> dict | None:
        ssid = observation.get("ssid")
        bssid = (observation.get("bssid") or "").upper()
        if ssid not in self.trusted_bssids:
            return None
        if bssid in self.trusted_bssids[ssid]:
            return None
        seen_sec = observation.get("security")
        downgrade = _is_downgrade(self.expected_security.get(ssid), seen_sec)
        confidence = 82 if downgrade else 60
        severity = "high" if downgrade else None  # else derive from confidence
        return events.make_event(
            mode="sentinel",
            event_type="evil_twin_suspected",
            confidence=confidence,
            severity=severity,
            message="Known SSID from unknown BSSID with possible security drift",
            ssid=ssid, bssid=bssid,
            channel=observation.get("channel"),
            rssi=observation.get("rssi"),
            raw_json={"security_seen": seen_sec,
                      "security_expected": self.expected_security.get(ssid),
                      "downgrade": downgrade},
        )
