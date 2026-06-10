"""Regression: threat_level() must only consider RECENT events.

Bug: on reboot KUMA went straight to threat='high'/bear='alert' (an instant
encounter) because threat_level() rolled up the last 50 events ALL-TIME, so
stale pre-reboot high-severity events still counted. It also never calmed down
after an attack stopped. Threat must decay with the same recency window the
rest of the system uses (settings.threat_window_minutes, default 10).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kuma_api import state
from kuma_core import events


def _plant(temp_db, *, severity, age_minutes):
    ev = events.make_event(
        mode="sentinel", event_type="deauth_burst", confidence=90,
        severity=severity, message="x", source="aa:bb:cc:dd:ee:ff",
        bssid="aa:bb:cc:dd:ee:ff", channel=6,
    )
    ev["timestamp"] = (
        datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    temp_db.insert_event(ev)


def test_stale_high_event_does_not_keep_device_alert(temp_db):
    """A high-severity event from before the window must NOT elevate threat.

    Fails pre-fix (returns 'high'); passes post-fix (returns 'low')."""
    _plant(temp_db, severity="high", age_minutes=30)
    assert state.threat_level() == "low"
    assert state.bear_state() != "alert"


def test_recent_high_event_still_elevates(temp_db):
    """A fresh high-severity event still raises threat (no false calm)."""
    _plant(temp_db, severity="high", age_minutes=1)
    assert state.threat_level() == "high"
    assert state.bear_state() == "alert"


def test_no_events_is_calm(temp_db):
    assert state.threat_level() == "low"
    assert state.bear_state() != "alert"
