import kuma_core.mitigation as mit
from kuma_core.mitigation import MitigationEngine


def _eng():
    return MitigationEngine(cfg={})


def test_canonical_for_deauth_family():
    e = _eng()
    for et in ("deauth_burst", "disassoc_flood", "handshake_harvest", "eapol_burst"):
        assert e.canonical_for(et) == "harden+redirect"


def test_canonical_for_rogue_family():
    e = _eng()
    for et in ("rogue_ap", "new_bssid_for_known_ssid", "evil_twin", "pineapple_karma", "karma_probe"):
        assert e.canonical_for(et) == "contain"


def test_canonical_for_flood_family():
    e = _eng()
    for et in ("beacon_flood", "ssid_flood", "botnet_beacon", "worm_spread"):
        assert e.canonical_for(et) == "mark+contain"


def test_canonical_for_passive_fallback():
    e = _eng()
    assert e.canonical_for("sniffer_detected") == "mark"
    assert e.canonical_for("rf_jam") == "mark"
    assert e.canonical_for("") == "mark"


def test_actions_noop_without_config():
    e = MitigationEngine(cfg={})
    assert "skipped" in e.harden_pmf()
    assert "skipped" in e.redirect()
    assert "stub" in e.contain("AA:BB:CC:DD:EE:FF")


def test_apply_deauth_runs_harden_and_redirect(monkeypatch):
    calls = []
    monkeypatch.setattr(mit.subprocess, "run", lambda *a, **k: calls.append(a))
    e = MitigationEngine(cfg={"protected_connection": "home", "backup_connection": "lte"})
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert res["action"] == "harden+redirect"
    assert res["target"] == "AA:BB:CC:DD:EE:FF"
    assert "hardened PMF" in res["message"] and "redirected" in res["message"]
    assert calls  # nmcli was invoked


def test_apply_rogue_contains(monkeypatch):
    sent = {}
    monkeypatch.setattr(mit.urllib.request, "urlopen", lambda *a, **k: sent.setdefault("hit", True))
    e = MitigationEngine(cfg={"containment": {"blacklist_url": "http://ctrl/api"}})
    res = e.apply("11:22:33:44:55:66", "rogue_ap")
    assert res["action"] == "contain"
    assert "blacklisted 11:22:33:44:55:66" in res["message"]


def test_apply_passive_marks(monkeypatch):
    marked = {}

    class FakeGate:
        def auto_hostile_add(self, t, evidence=""):
            marked["t"] = t
            return True

    e = MitigationEngine(cfg={}, gate=FakeGate())
    res = e.apply("99:88:77:66:55:44", "sniffer_detected")
    assert res["action"] == "mark"
    assert marked["t"] == "99:88:77:66:55:44"
    assert "marked" in res["message"]
