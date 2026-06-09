import kuma_core.mitigation as mit
from kuma_core.mitigation import MitigationEngine


class _Proc:
    def __init__(self, stdout=""):
        self.stdout = stdout


class _FakeGate:
    def __init__(self):
        self.marked = []

    def auto_hostile_add(self, target, evidence=""):
        self.marked.append(target)
        return True


def _fake_nmcli(monkeypatch, active_conn="HomeWiFi",
                active_bssid="AA\\:BB\\:CC\\:DD\\:EE\\:FF", record=None):
    """Patch subprocess.run so auto-discovery returns a fake active Wi-Fi + BSSID."""
    def run(cmd, *a, **k):
        if record is not None:
            record.append(cmd)
        if "show" in cmd and "--active" in cmd:
            return _Proc(f"{active_conn}:802-11-wireless\nlo:loopback\n")
        if "device" in cmd and "wifi" in cmd:
            return _Proc(f"yes:{active_bssid}\nno:11\\:22\\:33\\:44\\:55\\:66\n")
        return _Proc("")
    monkeypatch.setattr(mit.subprocess, "run", run)


def test_canonical_for_zeroconfig_primary():
    e = MitigationEngine(cfg={})
    assert e.canonical_for("deauth_burst") == "harden"
    assert e.canonical_for("handshake_harvest") == "harden"
    assert e.canonical_for("rogue_ap") == "avoid"
    assert e.canonical_for("evil_twin") == "avoid"
    assert e.canonical_for("beacon_flood") == "mark"
    assert e.canonical_for("sniffer_detected") == "mark"
    assert e.canonical_for("") == "mark"


def test_harden_auto_detects_active_connection(monkeypatch):
    rec = []
    _fake_nmcli(monkeypatch, active_conn="HomeWiFi", record=rec)
    e = MitigationEngine(cfg={})   # NO protected_connection configured
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert res["action"] == "harden"
    assert "HomeWiFi" in res["message"] and "PMF" in res["message"]
    assert any("802-11-wireless-security.pmf" in " ".join(c) for c in rec)


def test_avoid_pins_to_legit_bssid_and_marks(monkeypatch):
    rec = []
    _fake_nmcli(monkeypatch, active_conn="HomeWiFi",
                active_bssid="AA\\:BB\\:CC\\:DD\\:EE\\:FF", record=rec)
    gate = _FakeGate()
    e = MitigationEngine(cfg={}, gate=gate)
    res = e.apply("99:88:77:66:55:44", "evil_twin")
    assert res["action"] == "avoid+mark"
    assert "AA:BB:CC:DD:EE:FF" in res["message"]   # pinned to the legit BSSID
    assert gate.marked == ["99:88:77:66:55:44"]
    assert any("802-11-wireless.bssid" in " ".join(c) for c in rec)


def test_mark_only_for_flood(monkeypatch):
    _fake_nmcli(monkeypatch)
    gate = _FakeGate()
    e = MitigationEngine(cfg={}, gate=gate)
    res = e.apply("12:34:56:78:9a:bc", "beacon_flood")
    assert res["action"] == "mark"
    assert gate.marked == ["12:34:56:78:9a:bc"]


def test_harden_skips_gracefully_without_active_wifi(monkeypatch):
    monkeypatch.setattr(mit.subprocess, "run", lambda *a, **k: _Proc(""))
    e = MitigationEngine(cfg={})
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert res["action"] == "harden"
    assert "skipped" in res["message"]


def test_optional_redirect_when_backup_configured(monkeypatch):
    _fake_nmcli(monkeypatch)
    e = MitigationEngine(cfg={"backup_connection": "lte"})
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert res["action"] == "harden+redirect"
    assert "redirected protected link to 'lte'" in res["message"]


def test_optional_contain_when_controller_configured(monkeypatch):
    _fake_nmcli(monkeypatch)
    monkeypatch.setattr(mit.urllib.request, "urlopen", lambda *a, **k: True)
    e = MitigationEngine(cfg={"containment": {"blacklist_url": "http://ctrl"}},
                         gate=_FakeGate())
    res = e.apply("99:88:77:66:55:44", "rogue_ap")
    assert "contain" in res["action"]           # avoid+mark+contain
    assert "blacklisted 99:88:77:66:55:44" in res["message"]
