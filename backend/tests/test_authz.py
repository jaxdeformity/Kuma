"""Unit tests for the Kuroshuna authorization gate (pure decision logic)."""
import json as _json

from kuma_core.authz import Gate
from kuma_core.config import LAB_TARGETS_FILE


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


def test_auto_hostile_add_then_authorized(tmp_path):
    g = Gate(config=_armed_cfg(), audit_file=tmp_path / "a.jsonl")
    assert g.is_authorized("CA:FE:CA:FE:CA:FE", "counter_deauth")[0] is False
    added = g.auto_hostile_add("ca:fe:ca:fe:ca:fe", evidence="deauth flood vs AP")
    assert added is True
    allowed, reason = g.is_authorized("CA:FE:CA:FE:CA:FE", "counter_deauth")
    assert allowed is True
    assert "auto-hostile" in reason


def test_auto_hostile_refuses_protected(tmp_path):
    g = Gate(config=_armed_cfg(protect_bssids=["aa:bb:cc:dd:ee:ff"]),
             audit_file=tmp_path / "a.jsonl")
    added = g.auto_hostile_add("AA:BB:CC:DD:EE:FF", evidence="x")
    assert added is False  # never auto-target our own gear
    assert g.is_authorized("AA:BB:CC:DD:EE:FF", "counter_deauth")[0] is False


def test_broadcast_requires_all_three_arms(tmp_path):
    g = Gate(config={"lab_mode": True, "allow_broadcast": True,
                     "broadcast_armed": True}, audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.broadcast_allowed()
    assert allowed is True
    assert reason == "broadcast armed"


def test_broadcast_denied_when_any_arm_off(tmp_path):
    for missing in ("lab_mode", "allow_broadcast", "broadcast_armed"):
        cfg = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True}
        cfg[missing] = False
        g = Gate(config=cfg, audit_file=tmp_path / "a.jsonl")
        allowed, reason = g.broadcast_allowed()
        assert allowed is False
        assert missing in reason


def test_broadcast_limits_have_safe_defaults(tmp_path):
    g = Gate(config={}, audit_file=tmp_path / "a.jsonl")
    lim = g.broadcast_limits()
    assert lim["max_burst_seconds"] == 30
    assert lim["honor_protect_bssids"] is True
    assert lim["channel"] == 6
    assert lim["max_tx_power_dbm"] == 5


def test_decisions_are_audited(tmp_path):
    af = tmp_path / "audit.jsonl"
    g = Gate(config=_armed_cfg(approved_targets=["aa:bb:cc:dd:ee:ff"]),
             audit_file=af)
    g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")      # allow
    g.is_authorized("11:22:33:44:55:66", "deauth")      # deny
    lines = af.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec0 = _json.loads(lines[0])
    assert rec0["tier"] == "A"
    assert rec0["action"] == "deauth"
    assert rec0["target"] == "AA:BB:CC:DD:EE:FF"
    assert rec0["allowed"] is True
    assert "ts" in rec0 and "reason" in rec0
    rec1 = _json.loads(lines[1])
    assert rec1["allowed"] is False


def test_auto_hostile_add_is_audited(tmp_path):
    af = tmp_path / "audit.jsonl"
    g = Gate(config=_armed_cfg(), audit_file=af)
    g.auto_hostile_add("ca:fe:ca:fe:ca:fe", evidence="deauth flood")
    rec = _json.loads(af.read_text(encoding="utf-8").strip().splitlines()[0])
    assert rec["action"] == "auto_hostile_add"
    assert rec["allowed"] is True
    assert rec["target"] == "CA:FE:CA:FE:CA:FE"


def test_real_lab_targets_has_kuroshuna_schema_safe_off():
    cfg = _json.loads(LAB_TARGETS_FILE.read_text(encoding="utf-8"))
    # New Kuroshuna keys must exist and default to OFF/empty.
    assert cfg.get("kuroshuna_armed") is False
    assert cfg.get("allow_broadcast") is False
    assert cfg.get("broadcast_armed") is False
    assert cfg.get("lab_mode") is False
    assert isinstance(cfg.get("own_infra"), list)
    b = cfg.get("broadcast", {})
    assert b.get("max_burst_seconds") == 30
    assert b.get("honor_protect_bssids") is True


# FIX 1 — MAC normalization: dash-format in protect_bssids must still hard-deny
def test_protect_bssid_dash_format_still_denies(tmp_path):
    g = Gate(config=_armed_cfg(
        approved_targets=["aa:bb:cc:dd:ee:ff"],
        protect_bssids=["aa-bb-cc-dd-ee-ff"]),
        audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is False
    assert "hard deny" in reason


# FIX 2 — IPv6 normalization: expanded form matches compressed form in own_infra
def test_own_infra_ipv6_expanded_form_still_denies(tmp_path):
    g = Gate(config=_armed_cfg(
        own_infra=["::1"]),
        audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("0:0:0:0:0:0:0:1", "ssh_brute")
    assert allowed is False
    assert "hard deny" in reason


# FIX 3 — Garbage approved entries must not authorize
def test_garbage_approved_entry_does_not_authorize(tmp_path):
    g = Gate(config=_armed_cfg(approved_targets=["not-a-real-target"]),
             audit_file=tmp_path / "a.jsonl")
    allowed, _ = g.is_authorized("not-a-real-target", "ssh_brute")
    assert allowed is False


# FIX 5 — auto_hostile_add rejects garbage, accepts valid IP
def test_auto_hostile_rejects_garbage(tmp_path):
    g = Gate(config=_armed_cfg(), audit_file=tmp_path / "a.jsonl")
    assert g.auto_hostile_add("garbage") is False


def test_auto_hostile_accepts_ip(tmp_path):
    g = Gate(config=_armed_cfg(), audit_file=tmp_path / "a.jsonl")
    assert g.auto_hostile_add("192.168.50.162") is True
    allowed, reason = g.is_authorized("192.168.50.162", "ssh_brute")
    assert allowed is True
    assert "auto-hostile" in reason


# FIX 6 — broadcast decisions are audited
def test_broadcast_decision_is_audited(tmp_path):
    af = tmp_path / "audit.jsonl"
    g = Gate(config={"lab_mode": True, "allow_broadcast": True,
                     "broadcast_armed": True}, audit_file=af)
    g.broadcast_allowed()
    lines = af.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = _json.loads(lines[0])
    assert rec["tier"] == "B"
    assert rec["action"] == "broadcast"


# FIX 8 — own_infra IP inside approved CIDR is still hard-denied
def test_own_infra_ip_inside_approved_cidr_denied(tmp_path):
    g = Gate(config=_armed_cfg(
        approved_targets=["192.168.50.0/24"],
        own_infra=["192.168.50.225"]),
        audit_file=tmp_path / "a.jsonl")
    allowed, reason = g.is_authorized("192.168.50.225", "ssh_brute")
    assert allowed is False
    assert "hard deny" in reason
