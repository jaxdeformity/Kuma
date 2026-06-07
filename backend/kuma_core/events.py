"""Event model + factory.

An Event is the atomic unit that flows through KUMA:

    detector -> Event -> scoring -> SQLite + JSONL -> API -> M5Core face

Detectors should build events through :func:`make_event` so the timestamp,
confidence clamping and severity assignment are always consistent. KUMA's
honesty rule lives here: if a detector is unsure, the message should say
"suspected" and confidence should reflect it - we never hard-assert
attribution.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import scoring


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_event(
    *,
    mode: str,
    event_type: str,
    confidence: float,
    message: str,
    source: str = "unknown",
    target: str = "unknown",
    ssid: str | None = None,
    bssid: str | None = None,
    channel: int | None = None,
    rssi: int | None = None,
    severity: str | None = None,
    raw_json: dict | None = None,
) -> dict:
    """Build a normalized event dict.

    Severity is derived from confidence unless explicitly overridden (some
    detectors want to pin a floor, e.g. security downgrade is always >= high).
    """
    conf = scoring.clamp_confidence(confidence)
    return {
        "timestamp": utcnow_iso(),
        "mode": mode,
        "event_type": event_type,
        "severity": severity or scoring.severity_for(conf),
        "confidence": conf,
        "source": source,
        "target": target,
        "ssid": ssid,
        "bssid": bssid,
        "channel": channel,
        "rssi": rssi,
        "message": message,
        "raw_json": raw_json or {},
    }
