# Kuroshuna Phase 5 — Autonomous Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the scoped autonomous loop that ties Tier A RF + network offense together — iterating ONLY the authorized target set (approved_targets + confirmed auto-hostiles), chaining recon→attack with cooldowns, and wiring detector-confirmed attackers into the gate's auto-hostile set. This is the "runs automatically like pwnagotchi/Bjorn" behavior — bounded to scope.

**Architecture:** New module `backend/detectors/kuroshuna.py`. `KuroshunaOrchestrator` holds the `Gate` plus the offense engines (`TargetedRF`, `NetworkOffense`, `BroadcastRF` — all injected). `tick()` does ONE scoped pass: enumerate authorized targets, skip those in cooldown, `engage()` each (MAC→deauth; IP→scan then brute by discovered port), record the time. Every offense call still passes through the gate (defence in depth). `on_event()` feeds confirmed attackers from the live detectors into `gate.auto_hostile_add`. **Tier B broadcast is NOT auto-fired by the loop** — indiscriminate DoS stays a deliberate, explicit call (`simulate()`), never automatic. `run()` is a thin sleep-loop over `tick()`.

**Tech Stack:** Python 3, Phase 1 `kuma_core.authz.Gate`, Phase 2 `offense.rf_targeted.TargetedRF`, Phase 3 `offense.net_offense.NetworkOffense`, Phase 4 `offense.rf_broadcast.BroadcastRF`.

**How to run tests:** from `backend/`: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Autonomous orchestrator"). Depends on Phases 1–4.

---

## File Structure

- Create: `backend/detectors/kuroshuna.py` — `KuroshunaOrchestrator` + `PORT_PROTO` + CLI.
- Create: `backend/tests/test_kuroshuna_orchestrator.py` — unit tests (real `Gate`, injected mock offense engines + clock, `tmp_path`).

`KuroshunaOrchestrator.__init__(gate, *, rf=None, net=None, bcast=None, cooldown=None, clock=None, sleep=None)` — offense engines + clock injected so the loop is testable with no hardware and no real time.

Shared contract:
- `PORT_PROTO = {22:"ssh", 21:"ftp", 445:"smb", 3389:"rdp", 23:"telnet", 3306:"sql"}`
- `tick()` returns `{"armed": bool, "actions": list[tuple[str, result]]}`.
- The mock RF/net/bcast in tests are simple objects exposing the same method names as the real engines (`deauth`, `scan`, `bruteforce`, etc.).

---

### Task 1: orchestrator skeleton + disarmed tick

**Files:**
- Create: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kuroshuna_orchestrator.py
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


def test_tick_disarmed_does_nothing(tmp_path):
    g = _gate(tmp_path, armed=False)
    orch = KuroshunaOrchestrator(gate=g, clock=_Clock())
    out = orch.tick()
    assert out["armed"] is False
    assert out["actions"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'detectors.kuroshuna'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/detectors/kuroshuna.py
"""Kuroshuna autonomous orchestrator: the scoped 'runs automatically like
pwnagotchi/Bjorn' loop. Each tick() enumerates ONLY the authorized target set
(approved_targets + confirmed auto-hostiles), skips those in cooldown, and
chains recon->attack per target. Every offense call still passes through the
gate. Tier B broadcast is NEVER auto-fired here -- indiscriminate DoS stays an
explicit, deliberate call. on_event() promotes detector-confirmed attackers into
the gate's session auto-hostile set.
"""
from __future__ import annotations

import time

from kuma_core.authz import _is_mac

PORT_PROTO = {22: "ssh", 21: "ftp", 445: "smb", 3389: "rdp",
              23: "telnet", 3306: "sql"}


class KuroshunaOrchestrator:
    def __init__(self, gate, *, rf=None, net=None, bcast=None, cooldown=None,
                 clock=None, sleep=None) -> None:
        self.gate = gate
        self.rf = rf
        self.net = net
        self.bcast = bcast
        self.cooldown = (cooldown if cooldown is not None
                         else gate.cfg.get("response_cooldown", 30))
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._last: dict[str, float] = {}

    def tick(self, *, channel: int = 6) -> dict:
        if not self.gate.armed():
            return {"armed": False, "actions": []}
        return {"armed": True, "actions": []}   # enumeration added in Task 4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): orchestrator skeleton + disarmed tick"
```

---

### Task 2: authorized-target enumeration (approved + auto-hostiles, deduped)

**Files:**
- Modify: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -k authorized_targets -v`
Expected: FAIL — no `_authorized_targets`

- [ ] **Step 3: Write minimal implementation**

```python
    def _authorized_targets(self) -> list:
        approved = list(self.gate.cfg.get("approved_targets", []))
        hostiles = sorted(self.gate._auto_hostile)   # session-scoped set
        seen, out = set(), []
        for t in approved + hostiles:
            key = (t or "").strip().upper()
            if key and key not in seen:
                seen.add(key)
                out.append(t)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): authorized-target enumeration (approved + auto-hostiles)"
```

---

### Task 3: engage — MAC→deauth, IP→scan then brute by port

**Files:**
- Modify: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -k engage -v`
Expected: FAIL — no `engage`

- [ ] **Step 3: Write minimal implementation**

```python
    def engage(self, target: str, *, channel: int = 6) -> list:
        actions = []
        if _is_mac(target):
            if self.rf is not None:
                actions.append(("deauth", self.rf.deauth(target)))
        else:
            if self.net is not None:
                scan = self.net.scan(target)
                actions.append(("scan", scan))
                if getattr(scan, "ok", False) and getattr(scan, "open_ports", None):
                    for port in scan.open_ports:
                        proto = PORT_PROTO.get(port)
                        if proto:
                            actions.append(
                                (f"brute_{proto}", self.net.bruteforce(target, proto)))
        return actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): engage - MAC deauth / IP scan+brute by discovered port"
```

---

### Task 4: tick — iterate authorized set with cooldown

**Files:**
- Modify: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -k tick -v`
Expected: FAIL — tick returns empty actions (Task 1 stub)

- [ ] **Step 3: Write minimal implementation**

Add cooldown helpers and complete `tick`:

```python
    def _cooldown_ok(self, target: str) -> bool:
        last = self._last.get(target.upper())
        return last is None or (self._clock() - last) >= self.cooldown

    def _mark(self, target: str) -> None:
        self._last[target.upper()] = self._clock()
```

Replace the `tick` body's armed branch:

```python
    def tick(self, *, channel: int = 6) -> dict:
        if not self.gate.armed():
            return {"armed": False, "actions": []}
        actions = []
        for t in self._authorized_targets():
            if not self._cooldown_ok(t):
                continue
            actions.extend(self.engage(t, channel=channel))
            self._mark(t)
        return {"armed": True, "actions": actions}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): tick iterates authorized set with per-target cooldown"
```

---

### Task 5: on_event — promote detector-confirmed attackers to auto-hostile

**Files:**
- Modify: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -k on_event -v`
Expected: FAIL — no `on_event`

- [ ] **Step 3: Write minimal implementation**

Add the hostile-event set as a class attribute and the method:

```python
    # detector event_types that confirm an active attacker worth counter-targeting
    HOSTILE_EVENTS = {
        "deauth_burst", "disassoc_burst", "pwnagotchi_detected",
        "ssh_bruteforce", "evil_twin", "rogue_ap", "karma_probe",
    }

    def on_event(self, event: dict) -> bool:
        """Promote a detector-confirmed attacker into the gate's auto-hostile set.
        Returns True if a new hostile was armed. The gate still refuses protected/
        own gear, so this can never auto-target our own equipment."""
        if event.get("severity") not in ("high", "critical"):
            return False
        if event.get("event_type") not in self.HOSTILE_EVENTS:
            return False
        ident = (event.get("bssid") or event.get("source") or "").strip()
        if not ident:
            return False
        return self.gate.auto_hostile_add(ident, evidence=event.get("event_type", ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): on_event promotes confirmed attackers to auto-hostile"
```

---

### Task 6: explicit Tier B passthrough + run() loop + CLI

**Files:**
- Modify: `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -k "simulate or auto_firing or cli" -v`
Expected: FAIL — no `simulate` / `build_args` / `run_cli`

- [ ] **Step 3: Write minimal implementation**

```python
    # explicit Tier B passthrough -- NEVER called from tick(); broadcast DoS is
    # always a deliberate operator action. The BroadcastRF method itself enforces
    # broadcast_allowed() + time-box + footprint limits.
    _SIM = {"deauth_flood", "beacon_spam", "assoc_flood", "ble_spam"}

    def simulate(self, action: str, **kwargs):
        if action not in self._SIM:
            raise ValueError(f"unknown broadcast action: {action}")
        if self.bcast is None:
            raise RuntimeError("no BroadcastRF engine wired")
        return getattr(self.bcast, action)(**kwargs)

    def run(self, *, interval: float = 10.0, channel: int = 6) -> None:  # pragma: no cover
        """Thin continuous loop over tick(); for on-device autonomous operation."""
        while True:
            self.tick(channel=channel)
            self._sleep(interval)
```

```python
def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="detectors.kuroshuna",
        description="Kuroshuna orchestrator: scoped autonomous Tier A loop.")
    p.add_argument("--tick", action="store_true", help="run one scoped pass and exit")
    p.add_argument("--run", action="store_true", help="continuous loop (Ctrl-C to stop)")
    p.add_argument("--interval", type=float, default=10.0)
    p.add_argument("--channel", type=int, default=6)
    return p.parse_args(argv)


def run_cli(args, orch=None) -> int:
    if not (args.tick or args.run):
        print("error: specify --tick or --run", flush=True)
        return 2
    if orch is None:
        from kuma_core.authz import Gate
        from offense.net_offense import NetworkOffense
        from offense.rf_broadcast import BroadcastRF
        from offense.rf_targeted import TargetedRF
        gate = Gate()
        orch = KuroshunaOrchestrator(
            gate=gate, rf=TargetedRF(gate=gate), net=NetworkOffense(gate=gate),
            bcast=BroadcastRF(gate=gate))
    if args.run:  # pragma: no cover
        orch.run(interval=args.interval, channel=args.channel)
        return 0
    out = orch.tick(channel=args.channel)
    print(f"[kuroshuna] armed={out['armed']} actions={len(out['actions'])}", flush=True)
    for name, res in out["actions"]:
        print(f"  - {name}: {res}", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_orchestrator.py -v`
Expected: PASS (full file green)

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_orchestrator.py
git commit -m "feat(kuroshuna): explicit Tier B passthrough + run loop + CLI"
```

---

## Phase exit criteria

- `python -m pytest tests/test_kuroshuna_orchestrator.py -v` → all green; full suite still green.
- `KuroshunaOrchestrator` exposes `tick`, `engage`, `on_event`, `simulate`, `run`,
  `_authorized_targets`.
- `tick()` engages ONLY authorized targets (approved + auto-hostiles), respects per-target
  cooldown, and NEVER auto-fires Tier B broadcast.
- `on_event()` promotes only high/critical hostile-type events, falls back bssid→source,
  and cannot promote protected/own gear (gate refuses).
- Tier B is reachable only via the explicit `simulate()` / CLI, each still gated by
  `broadcast_allowed()` inside `BroadcastRF`.

## On-device wiring + validation (Jax, on the Pi)

1. Wire `on_event` into the live detectors: in `live_capture` / `auth_watch`, after a
   high-severity hostile event is emitted, call `orchestrator.on_event(ev)` so confirmed
   attackers auto-arm. (Integration point — do when running it live.)
2. Run a single scoped pass: `sudo ./.venv/bin/python -m detectors.kuroshuna --tick`
   with `lab_targets` armed + your rig in `approved_targets`; confirm it scans/brutes/deauths
   only your rig and logs to the audit trail.
3. `--run` for continuous autonomous operation; confirm cooldown spacing + that it never
   touches anything outside the authorized set.
4. Tier B stays manual: `python -m offense.rf_broadcast ...` (never auto-fired by the loop).

## Capability complete after this phase

Phases 1–5 deliver the full gated offensive capability. Remaining (separate, deferred):
- **Phase 2b / UI** — T-Deck ESP32 RF + `/api/kuroshuna/authorize`; Kuroshuna sprite skin,
  黒シュナ wordmark, on-device arm/disarm + broadcast confirm, `/api/status` flags. (Next conversation.)
