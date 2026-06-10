# Kuroshuna Phase 8 — Mirrored Red Dashboard + Combat Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Kuroshuna is armed, the T-Deck home screen becomes the blood-red, mirrored "evil twin" of the normal dashboard (クロシュナ wordmark) with a combat stat bar: **TX** (live inject light + session frame count) · **PWNED** (count of any successful offense) · **UPTIME**. Backend supplies the new data.

**Architecture:** A small backend `kuroshuna_stats` module owns a JSON stats file (`backend/data/kuroshuna_stats.json`): a cumulative `pwned` count, a cumulative `tx_frames` count, and a `tx_last_ts` heartbeat. The offense modules/orchestrator call `record_pwn()` / `record_tx(n)` on success; the API reads it and exposes `pwned_count`, `tx_frames`, `tx_active` (true iff the heartbeat is fresh) on `/api/status`. The firmware `drawHome` Kuroshuna branch mirrors the top bar (status left, wordmark+level right), recolors everything blood-red, and draws the reversed `TX / PWNED / UPTIME` strip.

**Tech Stack:** Python/FastAPI (TDD via TestClient), C++/LovyanGFX firmware (compile-verified). Builds on Phases 1–7+2b.

**How to run tests:** backend from `backend/`: `python -m pytest tests/test_kuroshuna_stats.py tests/test_kuroshuna_api.py -v`. Firmware: `pio run -e t-deck`.

**Spec:** the Kuroshuna spec + Jax's dashboard direction (2026-06-09): mirrored layout, blood-red, クロシュナ, stat bar = TX (light+count) / PWNED (any successful offense) / UPTIME.

---

## File Structure

- Create: `backend/kuma_core/kuroshuna_stats.py` — stats file read/write + `tx_active` freshness logic.
- Create: `backend/tests/test_kuroshuna_stats.py` — unit tests (tmp stats file).
- Modify: `backend/kuma_api/schemas.py` — `StatusResponse` += `pwned_count`, `tx_frames`, `tx_active`.
- Modify: `backend/kuma_api/routes.py` — populate the three fields in `get_status`.
- Modify: offense call sites to record: `backend/offense/rf_targeted.py` (deauth frames → `record_tx`; capture success → `record_pwn`), `backend/offense/net_offense.py` (brute creds found → `record_pwn`), `backend/offense/rf_broadcast.py` (bursts → `record_tx`), `backend/detectors/kuroshuna.py` (deauth in engage → `record_pwn`).
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h`/`.cpp` — KumaStatus fields + parse.
- Modify: `firmware/tdeck-ui/src/kuma_ui.cpp` — mirrored red Kuroshuna dashboard + reversed stat bar.

Contract:
- `kuroshuna_stats.record_pwn(target: str) -> None` (dedupes by target so re-pwning the same network doesn't inflate the count).
- `kuroshuna_stats.record_tx(frames: int) -> None` (adds to `tx_frames`, bumps `tx_last_ts`).
- `kuroshuna_stats.read() -> {"pwned": int, "tx_frames": int, "tx_active": bool}` (`tx_active` = now − `tx_last_ts` < `TX_FRESH_SECONDS`, default 3).
- Injectable `stats_file` path + `now`/clock for tests.

---

### Task 1: kuroshuna_stats module

**Files:**
- Create: `backend/kuma_core/kuroshuna_stats.py`
- Test: `backend/tests/test_kuroshuna_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kuroshuna_stats.py
"""Unit tests for the Kuroshuna combat-stats tracker."""
from kuma_core import kuroshuna_stats as KS


def _s(tmp_path):
    return tmp_path / "kuroshuna_stats.json"


def test_empty_defaults(tmp_path):
    out = KS.read(stats_file=_s(tmp_path))
    assert out == {"pwned": 0, "tx_frames": 0, "tx_active": False}


def test_record_pwn_dedupes(tmp_path):
    f = _s(tmp_path)
    KS.record_pwn("AA:BB:CC:DD:EE:FF", stats_file=f)
    KS.record_pwn("aa:bb:cc:dd:ee:ff", stats_file=f)   # same target, different case
    KS.record_pwn("11:22:33:44:55:66", stats_file=f)
    assert KS.read(stats_file=f)["pwned"] == 2


def test_record_tx_accumulates_and_marks_active(tmp_path):
    f = _s(tmp_path)
    KS.record_tx(64, stats_file=f, now=lambda: 1000.0)
    KS.record_tx(64, stats_file=f, now=lambda: 1001.0)
    out = KS.read(stats_file=f, now=lambda: 1001.5)   # 0.5s after last tx
    assert out["tx_frames"] == 128
    assert out["tx_active"] is True


def test_tx_goes_inactive_when_stale(tmp_path):
    f = _s(tmp_path)
    KS.record_tx(10, stats_file=f, now=lambda: 1000.0)
    out = KS.read(stats_file=f, now=lambda: 1010.0)    # 10s later > TX_FRESH
    assert out["tx_active"] is False
    assert out["tx_frames"] == 10                       # count persists
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_stats.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Write minimal implementation**

```python
# backend/kuma_core/kuroshuna_stats.py
"""Kuroshuna combat stats: cumulative PWNED count (deduped by target) + TX frame
count + a TX heartbeat. Written by the offense modules, read by /api/status. Plain
JSON file so the API process and the offense/orchestrator processes share it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from kuma_core.config import DATA_DIR

STATS_FILE = DATA_DIR / "kuroshuna_stats.json"
TX_FRESH_SECONDS = 3.0   # tx_active true only if a frame went out within this window


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pwned_targets": [], "tx_frames": 0, "tx_last_ts": 0.0}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def record_pwn(target: str, *, stats_file: Path | None = None) -> None:
    p = stats_file or STATS_FILE
    d = _load(p)
    t = (target or "").strip().upper()
    if t and t not in d.get("pwned_targets", []):
        d.setdefault("pwned_targets", []).append(t)
        _save(p, d)


def record_tx(frames: int, *, stats_file: Path | None = None, now=time.time) -> None:
    p = stats_file or STATS_FILE
    d = _load(p)
    d["tx_frames"] = int(d.get("tx_frames", 0)) + int(frames)
    d["tx_last_ts"] = now()
    _save(p, d)


def read(*, stats_file: Path | None = None, now=time.time) -> dict:
    d = _load(stats_file or STATS_FILE)
    fresh = (now() - float(d.get("tx_last_ts", 0.0))) < TX_FRESH_SECONDS
    return {
        "pwned": len(d.get("pwned_targets", [])),
        "tx_frames": int(d.get("tx_frames", 0)),
        "tx_active": bool(fresh and d.get("tx_last_ts")),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_stats.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/kuroshuna_stats.py backend/tests/test_kuroshuna_stats.py
git commit -m "feat(kuroshuna): combat-stats tracker (pwned dedup + tx heartbeat)"
```

---

### Task 2: expose stats on /api/status

**Files:**
- Modify: `backend/kuma_api/schemas.py`
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test** (append to the existing kuroshuna_api test file)

```python
def test_status_has_combat_stats(client):
    body = client.get("/api/status").json()
    assert body["pwned_count"] == 0
    assert body["tx_frames"] == 0
    assert body["tx_active"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py -k combat_stats -v`
Expected: FAIL — keys absent

- [ ] **Step 3: Write minimal implementation**

In `schemas.py` `StatusResponse`, after `broadcast_armed`:

```python
    pwned_count: int = 0      # networks/hosts with any successful offense
    tx_frames: int = 0        # attack frames transmitted this session
    tx_active: bool = False   # adapter is injecting right now
```

In `routes.py` `get_status`, add `from kuma_core import kuroshuna_stats` at top and:

```python
    ks = kuroshuna_stats.read()
```
then in the `StatusResponse(...)` kwargs:
```python
        pwned_count=ks["pwned"],
        tx_frames=ks["tx_frames"],
        tx_active=ks["tx_active"],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_api/schemas.py backend/kuma_api/routes.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(api): expose pwned_count/tx_frames/tx_active in /api/status"
```

---

### Task 3: wire offense modules to record stats

**Files:**
- Modify: `backend/offense/rf_targeted.py`, `backend/offense/net_offense.py`, `backend/offense/rf_broadcast.py`, `backend/detectors/kuroshuna.py`
- Test: `backend/tests/test_kuroshuna_stats_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kuroshuna_stats_wiring.py
"""The offense engines must record TX frames + PWNs as they act."""
from kuma_core import kuroshuna_stats as KS
from kuma_core.authz import Gate
from offense.rf_targeted import TargetedRF


def _armed(tmp_path):
    return Gate(config={"lab_mode": True, "kuroshuna_armed": True,
                        "approved_targets": ["aa:bb:cc:dd:ee:ff"]},
               audit_file=tmp_path / "a.jsonl")


def test_deauth_records_tx(tmp_path, monkeypatch):
    sf = tmp_path / "ks.json"
    monkeypatch.setattr(KS, "STATS_FILE", sf)
    rf = TargetedRF(gate=_armed(tmp_path), sender=lambda *a: None)
    rf.deauth("AA:BB:CC:DD:EE:FF", count=8)   # 2 frames * 8 = 16
    assert KS.read(stats_file=sf, now=lambda: 0)["tx_frames"] == 16
```

(Use `monkeypatch.setattr(KS, "STATS_FILE", sf)` so the module's default path points at tmp during the test, since the engines call `record_tx` with no explicit path.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_stats_wiring.py -v`
Expected: FAIL — `tx_frames` is 0 (no wiring yet)

- [ ] **Step 3: Write minimal implementation**

Add `from kuma_core import kuroshuna_stats` to each module, and at the SUCCESS points (after the gate-approved, non-dry-run action completes):

- `rf_targeted.py` `deauth`, on success before returning: `kuroshuna_stats.record_tx(len(frames) * count)`.
- `rf_targeted.py` `capture_handshake`, when `pkts` captured (frames_captured > 0): `kuroshuna_stats.record_pwn(bssid)`.
- `net_offense.py` `bruteforce`, when a cred is found (in the `found` accumulation, right before/with the audit on success): `kuroshuna_stats.record_pwn(host)`.
- `rf_broadcast.py` each method, after `_run_burst` returns `bursts` (>0, non-dry-run): `kuroshuna_stats.record_tx(bursts)`.
- `detectors/kuroshuna.py` `engage`, after a successful `rf.deauth` (result `.ok`): `kuroshuna_stats.record_pwn(target)` (the orchestrator counts an engaged MAC as pwned).

Keep each call guarded so a stats-write failure never breaks the offense (wrap in try/except Exception: pass — stats are best-effort telemetry, not safety).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_stats_wiring.py tests/test_rf_targeted.py tests/test_net_offense.py tests/test_rf_broadcast.py -v`
Expected: PASS (and no regression in the existing offense tests — the stats calls are additive + guarded)

- [ ] **Step 5: Commit**

```bash
git add backend/offense backend/detectors/kuroshuna.py backend/tests/test_kuroshuna_stats_wiring.py
git commit -m "feat(kuroshuna): offense engines record tx frames + pwns (best-effort)"
```

---

### Task 4: firmware — KumaStatus combat fields + parse

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h` / `.cpp`

- [ ] **Step 1: Add fields** — in `KumaStatus` (in `kuma_api_client.h`), after `broadcastArmed`:

```cpp
  uint32_t pwnedCount = 0;   // networks/hosts with any successful offense
  uint32_t txFrames = 0;     // attack frames transmitted this session
  bool     txActive = false; // adapter injecting right now
```

- [ ] **Step 2: Parse** — in `kuma_api_client.cpp` status parse, alongside the kuroshuna flags:

```cpp
  out.pwnedCount = doc["pwned_count"] | 0;
  out.txFrames   = doc["tx_frames"] | 0;
  out.txActive   = doc["tx_active"] | false;
```

- [ ] **Step 3: Verify compile** — `pio run -e t-deck` → SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_api_client.h firmware/tdeck-ui/src/kuma_api_client.cpp
git commit -m "feat(fw): parse pwned_count/tx_frames/tx_active from /api/status"
```

---

### Task 5: firmware — mirrored blood-red Kuroshuna dashboard + stat bar

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_ui.cpp`

READ the current `drawHome` first — it already has a `kuro` branch (Phase 7) for the wordmark/sprite/accent. This task EXTENDS it to (a) mirror the top bar, (b) go full blood-red, (c) replace the stat strip with the reversed combat strip when `kuro`.

- [ ] **Step 1: Mirror the top bar when `kuro`.** In the top-bar block, when `kuro`: draw the status dot + a red "ARMED" on the LEFT (where ONLINE normally is), and the クロシュナ wordmark + `Lv` on the RIGHT (mirror of the normal left-aligned wordmark). Compute right-aligned x from `KUROSHUNA_LOGO_W` + the `Lv NN` text width. Keep the existing non-kuro top bar unchanged. Concretely, branch the existing wordmark/level/online-dot drawing:

```cpp
  const uint16_t KURO_RED = 0xF800, KURO_HOT = 0xF904, KURO_WORD = 0xFE19;
  if (kuro) {
    // status dot + ARMED, LEFT (mirror of the normal right-side ONLINE)
    g->fillCircle(16, 12, 4, KURO_HOT);
    g->setTextColor(KURO_RED); g->setCursor(26, 9); g->print("ARMED");
    // wordmark + level, RIGHT
    int wx = 320 - 8 - KUROSHUNA_LOGO_W;
    g->drawPng(KUROSHUNA_LOGO, sizeof KUROSHUNA_LOGO, wx, 3);
    char lv[12]; snprintf(lv, sizeof lv, "Lv %u", s.level);
    int lw = (int)strlen(lv) * 6;
    g->setTextColor(KURO_RED); g->setCursor(wx - 8 - lw, 11); g->print(lv);
    g->drawFastHLine(0, 26, 320, KURO_RED);
  } else {
    // ... existing (non-kuro) top bar unchanged ...
  }
```

- [ ] **Step 2: Blood-red HUD bands + accent.** Where the Phase-7 `accent` was set, use `KURO_RED` for the HUD hairlines/bands when `kuro` (top line y26, bottom line y206). The center sprite already draws KUROSHUNA_APEX per Phase 7 — leave it.

- [ ] **Step 3: Reversed combat stat bar when `kuro`.** Replace the normal 4-cell stat bar block with a `kuro` branch drawing 3 cells in MIRRORED order — left→right: **TX**, **PWNED**, **UPTIME** (uptime rightmost). Cell centers e.g. `{60, 160, 270}`. All red. TX shows a lit dot (KURO_HOT when `s.txActive`, dim `0x5800` when idle) + the `txFrames` count; PWNED shows `pwnedCount`; UPTIME shows the hms string:

```cpp
  if (kuro) {
    g->drawFastHLine(0, 206, 320, KURO_RED);
    char up[16]; hms(s.uptimeSeconds, up);
    char tx[8]; snprintf(tx, sizeof tx, "%u", s.txFrames);
    char pw[8]; snprintf(pw, sizeof pw, "%u", s.pwnedCount);
    const int cxs[3] = {60, 160, 270};
    const char* labels[3] = {"TX", "PWNED", "UPTIME"};
    const char* vals[3]   = {tx, pw, up};
    g->setTextSize(1);
    for (int i = 0; i < 3; ++i) {
      g->setTextColor(0x9925);  // dim red label
      g->setCursor(cxs[i] - (int)strlen(labels[i]) * 3, 212); g->print(labels[i]);
      g->setTextColor(KURO_RED);
      g->setCursor(cxs[i] - (int)strlen(vals[i]) * 3, 226); g->print(vals[i]);
    }
    // TX live light, just left of the TX value
    uint16_t lit = s.txActive ? KURO_HOT : 0x5800;
    g->fillCircle(cxs[0] - (int)strlen(tx) * 3 - 7, 229, 3, lit);
  } else {
    // ... existing 4-cell UPTIME/EVENTS/NETWORKS/SENSOR bar unchanged ...
  }
```

- [ ] **Step 4: Verify compile** — `pio run -e t-deck` → SUCCESS + flash %.

- [ ] **Step 5: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_ui.cpp
git commit -m "feat(fw): mirrored blood-red Kuroshuna dashboard + TX/PWNED/UPTIME stat bar"
```

---

## Phase exit criteria

- Backend: `python -m pytest -q` all green; `/api/status` returns `pwned_count`/`tx_frames`/`tx_active`; offense engines record into the stats file (best-effort, never breaking offense).
- Firmware: `pio run -e t-deck` compiles clean; when `kuroshunaArmed`, the home is the mirrored blood-red クロシュナ dashboard with the `TX(light+count) / PWNED / UPTIME` strip; the normal/Shuna home is unchanged.
- `tx_active` reflects a live heartbeat (true only within ~3s of a real inject).

## On-device validation (Jax, COM8 + Pi)

1. Flash; arm via terminal (`kuroshuna arm` → confirm). Confirm home flips to the mirrored blood-red クロシュナ dashboard.
2. Run a `kuroshuna deauth` / Pi-side offense; confirm TX light goes hot + frame count climbs, PWNED increments on a successful capture/crack/deauth, and TX returns to dim a few seconds after activity stops.
3. Disarm → home returns to the normal/Shuna skin + the standard stat bar.

## Next

- On-device validation of all Kuroshuna phases. Then the deferred backlog (events case-mgmt + real mitigation, networks redesign + GPS, Shuna battle audio).
