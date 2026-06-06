"""Confidence -> severity / threat-level scoring.

KUMA never claims certainty. Detectors emit a 0-100 confidence score and this
module maps that onto human-facing severity buckets using the thresholds in
kuma_settings.json. Keeping this in one place means tuning is a config change,
not a code change.
"""
from __future__ import annotations

from .config import settings

# Ordered worst-to-best so we can pick the highest bucket a score clears.
_ORDER = ["critical", "high", "medium", "low"]


def severity_for(confidence: float) -> str:
    """Return the severity bucket for a 0-100 confidence score."""
    thresholds = settings.thresholds
    for level in _ORDER:
        if confidence >= thresholds.get(level, 999):
            return level
    return "low"


def threat_level_for(events: list[dict]) -> str:
    """Roll up recent events into a single device threat level.

    The device is only as calm as its worst recent event. Empty -> low.
    """
    if not events:
        return "low"
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    worst = max(events, key=lambda e: rank.get(e.get("severity", "low"), 0))
    return worst.get("severity", "low")


def clamp_confidence(value: float) -> int:
    """Confidence is always an int in [0, 100]."""
    return max(0, min(100, int(round(value))))
