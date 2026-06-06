"""Scoring: confidence -> severity, threat roll-up, clamping."""
from kuma_core import scoring


def test_severity_buckets():
    # defaults: low>=25, medium>=50, high>=75, critical>=90
    assert scoring.severity_for(10) == "low"
    assert scoring.severity_for(25) == "low"
    assert scoring.severity_for(60) == "medium"
    assert scoring.severity_for(80) == "high"
    assert scoring.severity_for(95) == "critical"


def test_clamp():
    assert scoring.clamp_confidence(-5) == 0
    assert scoring.clamp_confidence(140) == 100
    assert scoring.clamp_confidence(73.6) == 74


def test_threat_rollup_takes_worst():
    events = [
        {"severity": "low"},
        {"severity": "high"},
        {"severity": "medium"},
    ]
    assert scoring.threat_level_for(events) == "high"


def test_threat_empty_is_low():
    assert scoring.threat_level_for([]) == "low"
