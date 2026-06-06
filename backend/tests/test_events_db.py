"""Event creation + database insert/retrieve round-trip + mock detector."""
import random

from kuma_core import events
from detectors import mock_detector


def test_make_event_clamps_and_scores():
    ev = events.make_event(
        mode="sentinel", event_type="deauth_burst",
        confidence=82, message="x", ssid="HomeLab",
    )
    assert ev["confidence"] == 82
    assert ev["severity"] == "high"
    assert ev["timestamp"].endswith("Z")
    assert ev["raw_json"] == {}


def test_security_downgrade_can_pin_severity():
    ev = events.make_event(
        mode="sentinel", event_type="evil_twin_suspected",
        confidence=60, message="x", severity="high",
    )
    assert ev["severity"] == "high"  # pinned, not derived from 60


def test_mock_detector_is_deterministic_with_seed():
    a = mock_detector.generate_event(rng=random.Random(42))
    b = mock_detector.generate_event(rng=random.Random(42))
    assert a["event_type"] == b["event_type"]
    assert a["raw_json"]["mock"] is True


def test_db_insert_and_retrieve(temp_db):
    ev = events.make_event(mode="sentinel", event_type="deauth_burst",
                           confidence=74, message="burst", ssid="HomeLab")
    new_id = temp_db.insert_event(ev)
    assert new_id >= 1
    rows = temp_db.get_events(limit=10)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "deauth_burst"
    assert rows[0]["raw_json"] == {}  # round-trips through JSON


def test_db_filter_by_severity(temp_db):
    temp_db.insert_event(events.make_event(
        mode="sentinel", event_type="a", confidence=10, message="low one"))
    temp_db.insert_event(events.make_event(
        mode="sentinel", event_type="b", confidence=95, message="crit one"))
    crit = temp_db.get_events(severity="critical")
    assert len(crit) == 1
    assert crit[0]["event_type"] == "b"
