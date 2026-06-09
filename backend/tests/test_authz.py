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


def test_protect_bssid_hard_denied_even_if_approved(tmp_path):
    # An own AP mistakenly also listed in approved_targets must STILL be denied.
    g = Gate(config=_armed_cfg(
        approved_targets=["aa:bb:cc:dd:ee:ff"],
        protect_bssids=["aa:bb:cc:dd:ee:ff"]),
        audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is False
    assert "hard deny" in reason


def test_own_infra_hard_denied(tmp_path):
    g = Gate(config=_armed_cfg(
        approved_targets=["192.168.50.0/24"],
        own_infra=["192.168.50.225"]),       # the Lily
        audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("192.168.50.225", "ssh_brute")
    assert allowed is False
    assert "hard deny" in reason


def test_ip_inside_approved_cidr_allowed(tmp_path):
    g = Gate(config=_armed_cfg(approved_targets=["192.168.50.0/24"]),
             audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("192.168.50.162", "ssh_brute")  # Bjorn rig
    assert allowed is True
    assert "approved" in reason


def test_ip_outside_cidr_denied(tmp_path):
    g = Gate(config=_armed_cfg(approved_targets=["192.168.50.0/24"]),
             audit_file=tmp_path / "a.jsonl")
    allowed, _ = g.is_authorized("10.0.0.5", "ssh_brute")
    assert allowed is False


def test_mac_match_is_case_insensitive(tmp_path):
    g = Gate(config=_armed_cfg(approved_targets=["DE:AD:BE:EF:DE:AD"]),
             audit_file=tmp_path / "a.jsonl")
    allowed, _ = g.is_authorized("de:ad:be:ef:de:ad", "deauth")  # pwnagotchi rig
    assert allowed is True
