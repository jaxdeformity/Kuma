"""Passive deauth / disassociation burst detection.

SKELETON for Sprint 1. Real implementation (Sprint 2+) is PASSIVE ONLY — it
listens on a monitor-mode interface and counts management frames; it never
transmits. The offensive mirror of this is exactly what Bjorn/Bruce *send*; we
only ever count and score them.

Severity ladder (see docs/detection-logic.md):
    low      small burst, little/no target repetition
    medium   repeated frames within a window, repeated channel/BSSID
    high     repeated frames at a known client/AP, or burst -> EAPOL
    critical reserved

Attribution honesty: MACs can be spoofed. Events say "suspected"; confidence
reflects repetition strength, never source identity.
"""
from __future__ import annotations

from kuma_core import events


class DeauthDetector:
    def __init__(self, window_seconds: int = 30, burst_threshold: int = 20) -> None:
        self.window_seconds = window_seconds
        self.burst_threshold = burst_threshold

    def evaluate(self, frame_count: int, *, channel: int | None = None,
                 ssid: str | None = None, bssid: str | None = None,
                 reason_codes: list[int] | None = None) -> dict | None:
        """Score a window's worth of observed deauth/disassoc frames.

        Returns an event dict or None if below threshold. Wired in Sprint 2 to
        a scapy/tshark sniffer feeding window counts.
        """
        if frame_count < self.burst_threshold:
            return None
        # Confidence scales with how far past threshold we are.
        conf = min(90, 40 + (frame_count - self.burst_threshold))
        return events.make_event(
            mode="sentinel",
            event_type="deauth_burst",
            confidence=conf,
            message=f"Suspected deauth/disassoc burst on channel {channel}",
            ssid=ssid, bssid=bssid, channel=channel,
            raw_json={"window_seconds": self.window_seconds,
                      "frame_count": frame_count,
                      "reason_codes": reason_codes or []},
        )
