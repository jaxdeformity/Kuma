"""Unit tests for the Kuroshuna authorization gate (pure decision logic)."""
from kuma_core.authz import Gate


def _armed_cfg(**extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return cfg


def test_empty_config_is_disarmed(tmp_path):
    g = Gate(config={}, audit_file=tmp_path / "audit.jsonl")
    assert g.armed() is False
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is False
    assert "disarmed" in reason


def test_approved_mac_allowed_when_armed(tmp_path):
    g = Gate(config=_armed_cfg(approved_targets=["aa:bb:cc:dd:ee:ff"]),
             audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is True
    assert "approved" in reason


def test_unlisted_target_denied_when_armed(tmp_path):
    g = Gate(config=_armed_cfg(), audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("11:22:33:44:55:66", "deauth")
    assert allowed is False
    assert "not in authorized set" in reason
