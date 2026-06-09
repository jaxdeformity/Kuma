"""Unit tests for the Kuroshuna authorization gate (pure decision logic)."""
from kuma_core.authz import Gate


def test_empty_config_is_disarmed(tmp_path):
    g = Gate(config={}, audit_file=tmp_path / "audit.jsonl")
    assert g.armed() is False
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is False
    assert "disarmed" in reason
