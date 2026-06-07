"""Mock detector - the engine that proves the pipeline before real capture.

This is intentionally the FIRST detector to exist. It manufactures plausible
events so the whole chain (event -> scoring -> SQLite -> API -> M5Core face)
can be demonstrated on a desk with zero Wi-Fi hardware. Sprint 1 ships on this.

Every event it emits is clearly synthetic (``raw_json.mock = True``) so nothing
mock can ever be mistaken for a real observation downstream.
"""
from __future__ import annotations

import random

from kuma_core import events

# A small library of believable events keyed by the detector they imitate.
_TEMPLATES = [
    {
        "event_type": "deauth_burst", "base_conf": 70,
        "ssid": "HomeLab", "bssid": "AA:BB:CC:11:22:33", "channel": 6,
        "rssi": -52,
        "message": "Suspected deauth/disassoc burst observed on channel 6",
        "raw": {"window_seconds": 30, "frame_count": 44, "reason_codes": [7]},
    },
    {
        "event_type": "evil_twin_suspected", "base_conf": 82,
        "ssid": "HomeLab", "bssid": "DE:AD:BE:EF:00:01", "channel": 6,
        "rssi": -41,
        "message": "Known SSID seen from unknown BSSID with possible "
                   "security drift",
        "raw": {"baseline_bssid": "AA:BB:CC:11:22:33", "security_seen": "WPA"},
    },
    {
        "event_type": "new_bssid_for_known_ssid", "base_conf": 48,
        "ssid": "HomeLab", "bssid": "12:34:56:78:9A:BC", "channel": 36,
        "rssi": -67,
        "message": "New BSSID advertising a known SSID",
        "raw": {"baseline_bssids": ["AA:BB:CC:11:22:33"]},
    },
    {
        "event_type": "new_unknown_ap", "base_conf": 20,
        "ssid": "xfinitywifi", "bssid": "99:88:77:66:55:44", "channel": 1,
        "rssi": -78,
        "message": "Previously unseen access point entered the area",
        "raw": {},
    },
    {
        "event_type": "ssid_drift", "base_conf": 38,
        "ssid": "HomeLab", "bssid": "AA:BB:CC:11:22:33", "channel": 11,
        "rssi": -55,
        "message": "Known SSID observed on an unexpected channel",
        "raw": {"expected_channels": [6, 36], "seen_channel": 11},
    },
]


def generate_event(mode: str = "sentinel", rng: random.Random | None = None) -> dict:
    """Produce one synthetic event. Deterministic if you pass a seeded rng."""
    r = rng or random
    t = r.choice(_TEMPLATES)
    # Jitter the confidence a little so the demo feels alive.
    conf = max(5, min(95, t["base_conf"] + r.randint(-8, 8)))
    return events.make_event(
        mode=mode,
        event_type=t["event_type"],
        confidence=conf,
        message=t["message"],
        ssid=t["ssid"],
        bssid=t["bssid"],
        channel=t["channel"],
        rssi=t["rssi"],
        source="mock",
        raw_json={**t["raw"], "mock": True},
    )
