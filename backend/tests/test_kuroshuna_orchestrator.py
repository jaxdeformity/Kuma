"""Unit tests for the Kuroshuna autonomous orchestrator (scoped auto-loop)."""
from kuma_core.authz import Gate
from detectors.kuroshuna import KuroshunaOrchestrator


def _gate(tmp_path, armed=True, **extra):
    cfg = {"lab_mode": armed, "kuroshuna_armed": armed,
           "approved_targets": [], "response_cooldown": 30}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


class _Clock:
    def __init__(self, step=0.0):
        self.t = 0.0
        self.step = step
    def __call__(self):
        v = self.t
        self.t += self.step
        return v
    def advance(self, secs):
        self.t += secs


# ---------------------------------------------------------------------------
# Task 1: disarmed tick
# ---------------------------------------------------------------------------

def test_tick_disarmed_does_nothing(tmp_path):
    g = _gate(tmp_path, armed=False)
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    out = orch.tick()
    assert out["armed"] is False
    assert out["actions"] == []


# ---------------------------------------------------------------------------
# Task 2: authorized-target enumeration
# ---------------------------------------------------------------------------

def test_authorized_targets_merges_approved_and_hostiles(tmp_path):
    g = _gate(tmp_path, approved_targets=["192.168.50.0/24", "AA:BB:CC:DD:EE:FF"])
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    g.auto_hostile_add("ca:fe:ca:fe:ca:fe", evidence="deauth")
    targets = orch._authorized_targets()
    assert "192.168.50.0/24" in targets
    assert "AA:BB:CC:DD:EE:FF" in targets
    assert "CA:FE:CA:FE:CA:FE" in [t.upper() for t in targets]


def test_authorized_targets_dedupes(tmp_path):
    g = _gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    g.auto_hostile_add("AA:BB:CC:DD:EE:FF")     # same MAC, different case
    targets = orch._authorized_targets()
    uppers = [t.upper() for t in targets]
    assert uppers.count("AA:BB:CC:DD:EE:FF") == 1


# ---------------------------------------------------------------------------
# Task 3: engage
# ---------------------------------------------------------------------------

class _FakeRF:
    def __init__(self): self.deauthed = []
    def deauth(self, bssid, **kw): self.deauthed.append(bssid); return ("rf", bssid)


class _FakeScan:
    def __init__(self, ok, open_ports): self.ok = ok; self.open_ports = open_ports


class _FakeNet:
    def __init__(self, open_ports): self._open = open_ports; self.scanned = []; self.bruted = []
    def scan(self, host, **kw): self.scanned.append(host); return _FakeScan(True, self._open)
    def bruteforce(self, host, proto, **kw): self.bruted.append((host, proto)); return ("brute", host, proto)


def test_engage_mac_deauths(tmp_path):
    g = _gate(tmp_path, approved_targets=["AA:BB:CC:DD:EE:FF"])
    rf = _FakeRF()
    orch = KuroshunaOrchestrator(gate=g, rf=rf, clock=_Clock())
    acts = orch.engage("AA:BB:CC:DD:EE:FF")
    assert rf.deauthed == ["AA:BB:CC:DD:EE:FF"]
    assert acts[0][0] == "deauth"


def test_engage_ip_scans_then_brutes_open_services(tmp_path):
    g = _gate(tmp_path, approved_targets=["192.168.50.0/24"])
    net = _FakeNet(open_ports=[22, 445, 9999])     # 9999 has no proto mapping
    orch = KuroshunaOrchestrator(gate=g, net=net, clock=_Clock())
    acts = orch.engage("192.168.50.162")
    assert net.scanned == ["192.168.50.162"]
    assert ("192.168.50.162", "ssh") in net.bruted
    assert ("192.168.50.162", "smb") in net.bruted
    assert all(p != 9999 for (_h, p) in [])        # unmapped port -> no brute
    assert len(net.bruted) == 2                      # only ssh + smb, not 9999


def test_engage_ip_no_open_ports_no_brute(tmp_path):
    g = _gate(tmp_path, approved_targets=["192.168.50.0/24"])
    net = _FakeNet(open_ports=[])
    orch = KuroshunaOrchestrator(gate=g, net=net, clock=_Clock())
    orch.engage("192.168.50.5")
    assert net.bruted == []


# ---------------------------------------------------------------------------
# Task 4: tick with cooldown
# ---------------------------------------------------------------------------

def test_tick_engages_each_authorized_target(tmp_path):
    g = _gate(tmp_path, approved_targets=["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
    rf = _FakeRF()
    orch = KuroshunaOrchestrator(gate=g, rf=rf, clock=_Clock())
    out = orch.tick()
    assert out["armed"] is True
    assert set(rf.deauthed) == {"AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"}


def test_tick_respects_cooldown(tmp_path):
    g = _gate(tmp_path, approved_targets=["AA:BB:CC:DD:EE:FF"], response_cooldown=30)
    rf = _FakeRF()
    clk = _Clock()
    orch = KuroshunaOrchestrator(gate=g, rf=rf, clock=clk)
    orch.tick()                       # engages once
    orch.tick()                       # within cooldown -> skipped
    assert rf.deauthed == ["AA:BB:CC:DD:EE:FF"]
    clk.advance(31)                   # past cooldown
    orch.tick()
    assert rf.deauthed == ["AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"]


# ---------------------------------------------------------------------------
# Task 5: on_event
# ---------------------------------------------------------------------------

def test_on_event_promotes_confirmed_attacker(tmp_path):
    g = _gate(tmp_path)                       # nothing approved
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    ev = {"event_type": "deauth_burst", "severity": "high",
          "bssid": "ca:fe:ca:fe:ca:fe"}
    assert orch.on_event(ev) is True
    # now that attacker is an authorized target
    assert "CA:FE:CA:FE:CA:FE" in [t.upper() for t in orch._authorized_targets()]


def test_on_event_ignores_low_severity_and_benign(tmp_path):
    g = _gate(tmp_path)
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    assert orch.on_event({"event_type": "deauth_burst", "severity": "low",
                          "bssid": "ca:fe:ca:fe:ca:fe"}) is False
    assert orch.on_event({"event_type": "network_seen", "severity": "high",
                          "bssid": "ca:fe:ca:fe:ca:fe"}) is False
    assert orch._authorized_targets() == []


def test_on_event_falls_back_to_source_ip(tmp_path):
    g = _gate(tmp_path)
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    ev = {"event_type": "ssh_bruteforce", "severity": "high",
          "source": "192.168.50.162"}
    assert orch.on_event(ev) is True
    assert "192.168.50.162" in orch._authorized_targets()


def test_on_event_will_not_promote_protected(tmp_path):
    g = _gate(tmp_path, protect_bssids=["aa:bb:cc:dd:ee:ff"])
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    ev = {"event_type": "deauth_burst", "severity": "high",
          "bssid": "AA:BB:CC:DD:EE:FF"}
    assert orch.on_event(ev) is False         # gate refuses own gear
    assert orch._authorized_targets() == []


# ---------------------------------------------------------------------------
# Task 6: simulate + broadcast guard + CLI
# ---------------------------------------------------------------------------

def test_simulate_delegates_to_broadcast(tmp_path):
    g = _gate(tmp_path)
    class _FakeB:
        def __init__(self): self.calls = []
        def deauth_flood(self, **kw): self.calls.append(("deauth_flood", kw)); return "bcast"
    b = _FakeB()
    orch = KuroshunaOrchestrator(gate=g, bcast=b, clock=_Clock())
    res = orch.simulate("deauth_flood", duration=3)
    assert res == "bcast"
    assert b.calls == [("deauth_flood", {"duration": 3})]


def test_simulate_unknown_action(tmp_path):
    g = _gate(tmp_path)
    orch = KuroshunaOrchestrator(gate=g, bcast=object(), clock=_Clock())
    import pytest
    with pytest.raises(ValueError):
        orch.simulate("nuke")


def test_tick_is_not_auto_firing_broadcast(tmp_path):
    # tick() must never call a broadcast method on its own.
    g = _gate(tmp_path, approved_targets=["AA:BB:CC:DD:EE:FF"])
    class _FakeB:
        def __init__(self): self.calls = []
        def deauth_flood(self, **kw): self.calls.append("x"); return None
        def beacon_spam(self, **kw): self.calls.append("x"); return None
        def assoc_flood(self, *a, **kw): self.calls.append("x"); return None
        def ble_spam(self, **kw): self.calls.append("x"); return None
    b = _FakeB()
    orch = KuroshunaOrchestrator(gate=g, rf=_FakeRF(), bcast=b, clock=_Clock())
    orch.tick()
    assert b.calls == []          # broadcast NEVER auto-fired


def test_cli_tick_runs_once(tmp_path, capsys):
    g = _gate(tmp_path, approved_targets=["AA:BB:CC:DD:EE:FF"])
    orch = KuroshunaOrchestrator(gate=g, rf=_FakeRF(), clock=_Clock())
    from detectors.kuroshuna import build_args, run_cli
    rc = run_cli(build_args(["--tick"]), orch=orch)
    assert rc == 0
    assert "armed" in capsys.readouterr().out.lower()
