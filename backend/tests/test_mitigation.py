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
                active_bssid="AA\\:BB\\:CC\\:DD\\:EE\\:FF", ap_pmf=False, record=None):
    """Patch subprocess.run so auto-discovery returns a fake active Wi-Fi, BSSID,
    device, and an `iw scan` whose RSN advertises MFP iff ap_pmf is True."""
    bssid_plain = active_bssid.replace("\\:", ":").lower()

    def run(cmd, *a, **k):
        if record is not None:
            record.append(cmd)
        if "show" in cmd and "--active" in cmd:
            if "NAME,TYPE" in cmd:
                return _Proc(f"{active_conn}:802-11-wireless\nlo:loopback\n")
            if "TYPE,DEVICE" in cmd:
                return _Proc("802-11-wireless:wlan0\nloopback:lo\n")
        if "device" in cmd and "wifi" in cmd:
            return _Proc(f"yes:{active_bssid}\nno:11\\:22\\:33\\:44\\:55\\:66\n")
        if cmd and cmd[0] == "iw" and "scan" in cmd:
            cap = "MFP-capable (0x008c)" if ap_pmf else "(0x000c)"
            return _Proc(f"BSS {bssid_plain}(on wlan0)\n\tRSN:\t * Version: 1\n"
                         f"\t\t * Capabilities: 16-PTKSA-RC {cap}\n")
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


def test_harden_auto_detects_and_uses_optional_on_non_pmf_ap(monkeypatch):
    rec = []
    _fake_nmcli(monkeypatch, active_conn="HomeWiFi", ap_pmf=False, record=rec)
    e = MitigationEngine(cfg={})   # NO protected_connection configured
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert res["action"] == "harden"
    assert "HomeWiFi" in res["message"] and "PMF=optional" in res["message"]
    # non-PMF AP -> pmf set to 1 (optional), never disconnects
    assert any(c[-1] == "1" and "pmf" in " ".join(c) for c in rec)


def test_harden_requires_pmf_on_capable_ap(monkeypatch):
    rec = []
    _fake_nmcli(monkeypatch, active_conn="HomeWiFi", ap_pmf=True, record=rec)
    e = MitigationEngine(cfg={})
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert "PMF=required" in res["message"]
    assert any(c[-1] == "2" and "pmf" in " ".join(c) for c in rec)


def test_pmf_strict_forces_required_even_on_non_pmf_ap(monkeypatch):
    rec = []
    _fake_nmcli(monkeypatch, ap_pmf=False, record=rec)
    e = MitigationEngine(cfg={"pmf_strict": True})
    res = e.apply("AA:BB:CC:DD:EE:FF", "deauth_burst")
    assert "PMF=required" in res["message"]


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
