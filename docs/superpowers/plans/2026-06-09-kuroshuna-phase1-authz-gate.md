# Kuroshuna Phase 1 — Authorization Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `backend/kuma_core/authz.py` — the single authorization chokepoint every Kuroshuna offensive action routes through — fully unit-tested, before any offensive module exists.

**Architecture:** A `Gate` class loads the extended `lab_targets.json` config. Tier A actions call `is_authorized(target, action)` which hard-denies protected/own infra, then allows only `approved_targets` (incl. CIDR membership) or session-scoped auto-hostiles. Tier B calls `broadcast_allowed()` (arm-gated, no target). Every decision appends to a JSONL audit log. No transmission happens here — this is pure gating logic.

**Tech Stack:** Python 3 (stdlib `ipaddress`, `re`, `json`, `pathlib`), pytest. Follows the existing `responder.py` / `config.py` patterns.

**How to run tests:** from `backend/`: `python -m pytest tests/test_authz.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "The authorization gate")

---

## File Structure

- Create: `backend/kuma_core/authz.py` — the `Gate` class + helpers (one responsibility: authorization decisions + audit).
- Create: `backend/tests/test_authz.py` — unit tests for the allow/deny matrix.
- Modify: `backend/config/lab_targets.json` — add Kuroshuna schema keys, all defaulting to safe-off.
- Modify: `.gitignore` (repo root) — add `reference/` (cloned source repos, read-only).

The `Gate` takes an injectable `config` dict and `audit_file` path so tests run fully in-memory / in `tmp_path` with no real config or data writes.

---

### Task 1: Gate skeleton + safe-default load

**Files:**
- Create: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_authz.py
"""Unit tests for the Kuroshuna authorization gate (pure decision logic)."""
from kuma_core.authz import Gate


def test_empty_config_is_disarmed(tmp_path):
    g = Gate(config={}, audit_file=tmp_path / "audit.jsonl")
    assert g.armed() is False
    allowed, reason = g.is_authorized("AA:BB:CC:DD:EE:FF", "deauth")
    assert allowed is False
    assert "disarmed" in reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py::test_empty_config_is_disarmed -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kuma_core.authz'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/kuma_core/authz.py
"""Kuroshuna authorization gate.

Single chokepoint between every offensive capability and every action. Default
posture is passive blue-team: nothing is authorized unless lab_mode + the
relevant arm are set, and even then only against Jax's authorized target set.
Protected BSSIDs and Kuma's own infrastructure are hard-denied, always.

  Tier A (targeted)  -> is_authorized(target, action)
  Tier B (broadcast) -> broadcast_allowed()   (no target; arm + footprint gated)

Every decision is written to an append-only JSONL audit log.
"""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path

from kuma_core.config import DATA_DIR, LAB_TARGETS_FILE
from kuma_core.events import utcnow_iso

AUDIT_FILE = DATA_DIR / "kuroshuna_audit.jsonl"
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _is_mac(t: str) -> bool:
    return bool(_MAC_RE.match(t.lower()))


def _norm(target: str) -> str:
    """Trim a target; upper-case MACs, leave IPs/CIDRs as-is."""
    t = (target or "").strip()
    return t.upper() if _is_mac(t) else t


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class Gate:
    def __init__(self, config: dict | None = None,
                 audit_file: Path | None = None) -> None:
        self.cfg = config if config is not None else _load_lab()
        self.audit_file = audit_file or AUDIT_FILE
        self._auto_hostile: set[str] = set()

    def reload(self) -> None:
        self.cfg = _load_lab()

    def armed(self) -> bool:
        return bool(self.cfg.get("lab_mode")) and bool(
            self.cfg.get("kuroshuna_armed"))

    def is_authorized(self, target: str, action: str) -> tuple[bool, str]:
        if not self.armed():
            return False, "disarmed (need lab_mode + kuroshuna_armed)"
        return False, "not in authorized set"

    def audit(self, event: dict) -> None:  # filled in Task 7
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py::test_empty_config_is_disarmed -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): Gate skeleton + safe-default disarmed state"
```

---

### Task 2: Allow an approved target when armed

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
def _armed_cfg(**extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return cfg


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k approved_mac -v`
Expected: FAIL — returns `(False, "not in authorized set")` for the approved MAC

- [ ] **Step 3: Write minimal implementation**

Replace `is_authorized` and add `_decide` + `_matches`:

```python
    def is_authorized(self, target: str, action: str) -> tuple[bool, str]:
        return self._decide(target, action)

    def _decide(self, target: str, action: str) -> tuple[bool, str]:
        if not self.armed():
            return False, "disarmed (need lab_mode + kuroshuna_armed)"
        t = _norm(target)
        if not t:
            return False, "empty target"
        approved = {_norm(a) for a in self.cfg.get("approved_targets", [])}
        if self._matches(t, approved):
            return True, "approved_targets allowlist"
        return False, "not in authorized set"

    def _matches(self, target: str, allow: set[str]) -> bool:
        if target in allow:
            return True
        if not _is_mac(target):
            try:
                ip = ipaddress.ip_address(target)
            except ValueError:
                return False
            for entry in allow:
                if "/" in entry:
                    try:
                        if ip in ipaddress.ip_network(entry, strict=False):
                            return True
                    except ValueError:
                        continue
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS (all 4 tests so far)

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): allow approved targets when armed, deny unlisted"
```

---

### Task 3: Hard-deny protected BSSIDs and own infra

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k "hard_denied or own_infra" -v`
Expected: FAIL — both currently return allowed=True (approved/CIDR match wins)

- [ ] **Step 3: Write minimal implementation**

Add `_protected` and insert the hard-deny check **before** the allow check in `_decide`:

```python
    def _protected(self) -> set[str]:
        prot = {_norm(b) for b in self.cfg.get("protect_bssids", [])}
        prot |= {_norm(b) for b in self.cfg.get("own_infra", [])}
        return prot
```

In `_decide`, after the empty-target check and before the approved check, add:

```python
        if self._matches(t, self._protected()):
            return False, "protected/own-infra (hard deny)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): hard-deny protect_bssids + own_infra before any allow"
```

---

### Task 4: CIDR + MAC-case matching

**Files:**
- Test: `backend/tests/test_authz.py` (logic already implemented in `_matches`; this task proves it and guards regressions)

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `python -m pytest tests/test_authz.py -k "cidr or case_insensitive" -v`
Expected: PASS (the `_matches` logic from Task 2 already covers this). If any FAIL, fix `_matches` until green — these are the canonical matching contract.

- [ ] **Step 3: (no new code unless a test failed)**

If green, skip. If red, correct `_matches` per the failing case.

- [ ] **Step 4: Re-run**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_authz.py
git commit -m "test(authz): lock CIDR membership + MAC case-insensitive matching"
```

---

### Task 5: Auto-hostile session allowlist

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k auto_hostile -v`
Expected: FAIL — `Gate` has no `auto_hostile_add`

- [ ] **Step 3: Write minimal implementation**

Add the auto-hostile check in `_decide` (after hard-deny, before/after approved is fine — put it before approved):

```python
        if t in self._auto_hostile:
            return True, "auto-hostile (confirmed attacker)"
```

Add the method:

```python
    def auto_hostile_add(self, mac: str, evidence: str = "") -> bool:
        t = _norm(mac)
        if not t or self._matches(t, self._protected()):
            return False
        self._auto_hostile.add(t)
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): session-scoped auto-hostile allowlist (never own gear)"
```

---

### Task 6: Broadcast (Tier B) arm gate + limits

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
def test_broadcast_requires_all_three_arms(tmp_path):
    g = Gate(config={"lab_mode": True, "allow_broadcast": True,
                     "broadcast_armed": True}, audit_file=tmp_path / "a.jsonl")
    assert g.broadcast_allowed() == (True, "broadcast armed")


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k broadcast -v`
Expected: FAIL — no `broadcast_allowed` / `broadcast_limits`

- [ ] **Step 3: Write minimal implementation**

```python
    def broadcast_allowed(self) -> tuple[bool, str]:
        if not self.cfg.get("lab_mode"):
            return False, "lab_mode off"
        if not self.cfg.get("allow_broadcast"):
            return False, "allow_broadcast off"
        if not self.cfg.get("broadcast_armed"):
            return False, "broadcast_armed off"
        return True, "broadcast armed"

    def broadcast_limits(self) -> dict:
        b = self.cfg.get("broadcast", {})
        return {
            "channel": b.get("channel", 6),
            "max_tx_power_dbm": b.get("max_tx_power_dbm", 5),
            "max_burst_seconds": b.get("max_burst_seconds", 30),
            "honor_protect_bssids": b.get("honor_protect_bssids", True),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): broadcast arm gate + footprint limits with safe defaults"
```

---

### Task 7: Append-only audit log on every decision

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
import json as _json


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k audit -v`
Expected: FAIL — `audit()` is a no-op (pass), file never written

- [ ] **Step 3: Write minimal implementation**

Implement `audit`:

```python
    def audit(self, event: dict) -> None:
        rec = {"ts": utcnow_iso(), **event}
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
```

Wire it into `is_authorized` (wrap `_decide`) and `auto_hostile_add`:

```python
    def is_authorized(self, target: str, action: str) -> tuple[bool, str]:
        allowed, reason = self._decide(target, action)
        self.audit({"tier": "A", "action": action, "target": _norm(target),
                    "allowed": allowed, "reason": reason})
        return allowed, reason

    def auto_hostile_add(self, mac: str, evidence: str = "") -> bool:
        t = _norm(mac)
        if not t or self._matches(t, self._protected()):
            self.audit({"tier": "A", "action": "auto_hostile_add", "target": t,
                        "allowed": False, "reason": "refused: protected/own-infra"})
            return False
        self._auto_hostile.add(t)
        self.audit({"tier": "A", "action": "auto_hostile_add", "target": t,
                    "allowed": True, "reason": evidence or "confirmed attacker"})
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS (full suite, ~13 tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_authz.py
git commit -m "feat(authz): append-only JSONL audit on every gate decision"
```

---

### Task 8: Wire the schema into the real config + gitignore reference/

**Files:**
- Modify: `backend/config/lab_targets.json`
- Modify: `.gitignore` (repo root)
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Write the failing test**

```python
from kuma_core.config import LAB_TARGETS_FILE
import json as _json2


def test_real_lab_targets_has_kuroshuna_schema_safe_off():
    cfg = _json2.loads(LAB_TARGETS_FILE.read_text(encoding="utf-8"))
    # New Kuroshuna keys must exist and default to OFF/empty.
    assert cfg.get("kuroshuna_armed") is False
    assert cfg.get("allow_broadcast") is False
    assert cfg.get("broadcast_armed") is False
    assert cfg.get("lab_mode") is False
    assert isinstance(cfg.get("own_infra"), list)
    b = cfg.get("broadcast", {})
    assert b.get("max_burst_seconds") == 30
    assert b.get("honor_protect_bssids") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_authz.py -k real_lab_targets -v`
Expected: FAIL — keys absent in current `lab_targets.json`

- [ ] **Step 3: Edit `backend/config/lab_targets.json`**

Add the Kuroshuna keys (keep existing apex keys intact). Resulting file:

```json
{
  "lab_mode": false,
  "apex_active_response": false,
  "kuroshuna_armed": false,
  "allow_broadcast": false,
  "broadcast_armed": false,
  "response_cooldown": 30,

  "protect_bssids": [],
  "own_infra": [],

  "approved_targets": [],

  "protected_connection": "",
  "backup_connection": "",

  "responses": {
    "harden_pmf": false,
    "redirect": false,
    "contain": false
  },

  "containment": {
    "blacklist_url": "",
    "method": "POST",
    "headers": { "Content-Type": "application/json" },
    "payload": {}
  },

  "broadcast": {
    "channel": 6,
    "max_tx_power_dbm": 5,
    "max_burst_seconds": 30,
    "honor_protect_bssids": true
  },

  "notes": "Apex = passive active-DEFENSE (never transmits attack frames). KUROSHUNA = the offensive tier: Tier A (targeted, gated by lab_mode+kuroshuna_armed against approved_targets/auto-hostiles; protect_bssids + own_infra are hard-denied always) and Tier B broadcast (deauth-flood/beacon/BLE spam, gated by lab_mode+allow_broadcast+broadcast_armed, time-boxed by broadcast.max_burst_seconds, pinned to broadcast.channel, capped to broadcast.max_tx_power_dbm). RF rails shrink but cannot contain the broadcast footprint -- only physical isolation (low power + distance, or a shielded/attenuated setup) keeps broadcast attacks off non-lab gear. Running Tier B is the lab owner's responsibility. own_infra = Pi/Lily/uplink MACs+IPs that must never be targeted."
}
```

- [ ] **Step 4: Edit `.gitignore`** — add the read-only reference repos dir:

```gitignore
# Cloned source repos (pwnagotchi / Bjorn / Bruce), read-only reference only
reference/
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_authz.py -v`
Expected: PASS (full suite green)

- [ ] **Step 6: Commit**

```bash
git add backend/config/lab_targets.json .gitignore backend/tests/test_authz.py
git commit -m "feat(authz): add Kuroshuna schema to lab_targets (safe-off) + ignore reference/"
```

---

## Phase exit criteria

- `python -m pytest tests/test_authz.py -v` → all green.
- `backend/kuma_core/authz.py` exists; `Gate` exposes `armed()`, `is_authorized()`,
  `auto_hostile_add()`, `broadcast_allowed()`, `broadcast_limits()`, `audit()`, `reload()`.
- `lab_targets.json` carries the full Kuroshuna schema, everything OFF.
- No transmission code exists yet — this phase is gating + audit only.

## Next phases (separate plans, written when reached)

- **Phase 2** — Tier A RF offense (T-Deck targeted deauth + Pi/Alfa capture), every action through `Gate.is_authorized`.
- **Phase 3** — Tier A network offense (Bjorn-style scan/brute-force/steal), gate-checked.
- **Phase 4** — Tier B broadcast dispatchers (deauth-flood/beacon/BLE-spam/assoc-flood) behind `broadcast_allowed` + time-box + footprint limits.
- **Phase 5** — Autonomous orchestrator (`detectors/kuroshuna.py`) iterating the authorized set.
- **Phase 0/UI (deferred)** — Kuroshuna sprite skin, 黒シュナ wordmark, on-device arm/disarm + broadcast confirm, `/api/status` flags.
