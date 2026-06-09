# Kuroshuna Phase 6 — Backend Kuroshuna API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the HTTP control surface the T-Deck uses to (a) see Kuroshuna arm state, (b) arm/disarm Kuroshuna and the broadcast tier from the device with safety gating, and (c) get a yes/no from the authoritative Pi gate before the T-Deck's own ESP32 radio transmits.

**Architecture:** Extend the existing FastAPI router (`backend/kuma_api/routes.py`). `/api/status` gains `kuroshuna_armed` + `broadcast_armed` (read fresh from `lab_targets.json`). New `POST /api/kuroshuna/arm`, `POST /api/kuroshuna/broadcast-arm`, and `POST /api/kuroshuna/authorize`. Arming is safety-gated: **arming Kuroshuna requires `lab_mode`; arming broadcast additionally requires `allow_broadcast`; disarming is ALWAYS allowed** (you can always stand down). Arm state persists by writing `lab_targets.json` via a new `authz.save_lab` helper; the gate re-reads it. `/authorize` runs the Phase-1 `Gate` (which audits) and returns allow/deny.

**Tech Stack:** FastAPI, Pydantic, the Phase-1 `kuma_core.authz.Gate`. Tests use `TestClient` (see `tests/test_api.py`) with `lab_targets.json` redirected to `tmp_path`.

**How to run tests:** from `backend/`: `python -m pytest tests/test_kuroshuna_api.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Kuroshuna mode skin" — /api/status flags + arm). Depends on Phase 1 (`Gate`).

---

## File Structure

- Modify: `backend/kuma_core/authz.py` — add `save_lab(cfg)` (write `lab_targets.json`).
- Modify: `backend/kuma_api/schemas.py` — add `kuroshuna_armed`/`broadcast_armed` to `StatusResponse`; add request/response models.
- Modify: `backend/kuma_api/routes.py` — populate status flags; add the 3 endpoints.
- Create: `backend/tests/test_kuroshuna_api.py` — TestClient tests with a redirected lab file.

Shared contract:
- `ArmRequest{armed: bool}`; `ArmResponse{lab_mode, kuroshuna_armed, broadcast_armed}`.
- `AuthorizeRequest{target: str, action: str}`; `AuthorizeResponse{allowed: bool, reason: str}`.
- Arm rules: `kuroshuna_armed=True` requires `lab_mode` (else 409); `broadcast_armed=True` requires `lab_mode` AND `allow_broadcast` (else 409); any `armed=False` always succeeds.

---

### Task 1: `authz.save_lab` writer

**Files:**
- Modify: `backend/kuma_core/authz.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kuroshuna_api.py
"""API tests for the Kuroshuna control surface (lab file redirected to tmp)."""
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def lab_file(tmp_path, monkeypatch):
    """Redirect lab_targets.json to a temp file with a known starting state."""
    from kuma_core import authz
    p = tmp_path / "lab_targets.json"
    p.write_text(json.dumps({
        "lab_mode": False, "kuroshuna_armed": False, "allow_broadcast": False,
        "broadcast_armed": False, "approved_targets": [], "protect_bssids": [],
    }), encoding="utf-8")
    monkeypatch.setattr(authz, "LAB_TARGETS_FILE", p)
    return p


def test_save_lab_roundtrip(lab_file):
    from kuma_core import authz
    cfg = authz._load_lab()
    cfg["kuroshuna_armed"] = True
    authz.save_lab(cfg)
    assert json.loads(lab_file.read_text(encoding="utf-8"))["kuroshuna_armed"] is True
    assert authz._load_lab()["kuroshuna_armed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py::test_save_lab_roundtrip -v`
Expected: FAIL — `authz` has no `save_lab`

- [ ] **Step 3: Write minimal implementation**

In `backend/kuma_core/authz.py`, add after `_load_lab`:

```python
def save_lab(cfg: dict) -> None:
    """Persist the lab_targets config (atomic-ish: write then replace)."""
    tmp = LAB_TARGETS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(LAB_TARGETS_FILE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py::test_save_lab_roundtrip -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/authz.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(authz): save_lab writer for lab_targets.json"
```

---

### Task 2: `/api/status` exposes arm flags

**Files:**
- Modify: `backend/kuma_api/schemas.py`
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test**

```python
import os
os.environ["KUMA_MOCK"] = "0"
from kuma_api.app import app  # noqa: E402


@pytest.fixture()
def client(temp_db, lab_file):
    with TestClient(app) as c:
        yield c


def test_status_has_kuroshuna_flags(client):
    body = client.get("/api/status").json()
    assert body["kuroshuna_armed"] is False
    assert body["broadcast_armed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py -k status_has -v`
Expected: FAIL — keys absent

- [ ] **Step 3: Write minimal implementation**

In `schemas.py`, add to `StatusResponse` (after `character`):

```python
    kuroshuna_armed: bool = False   # Tier A offensive arm (gloves off)
    broadcast_armed: bool = False   # Tier B broadcast arm
```

In `routes.py`, import authz at top (`from kuma_core import authz`) and in `get_status` build the response with the flags read fresh:

```python
    lab = authz._load_lab()
```
Add to the `StatusResponse(...)` kwargs:
```python
        kuroshuna_armed=bool(lab.get("kuroshuna_armed")),
        broadcast_armed=bool(lab.get("broadcast_armed")),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_api/schemas.py backend/kuma_api/routes.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(api): expose kuroshuna_armed/broadcast_armed in /api/status"
```

---

### Task 3: `POST /api/kuroshuna/arm` (lab_mode-gated)

**Files:**
- Modify: `backend/kuma_api/schemas.py`
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test**

```python
def test_arm_requires_lab_mode(client, lab_file):
    # lab_mode is False -> arming Kuroshuna is refused
    r = client.post("/api/kuroshuna/arm", json={"armed": True})
    assert r.status_code == 409
    assert "lab_mode" in r.json()["detail"]


def test_arm_succeeds_when_lab_mode_on(client, lab_file):
    cfg = json.loads(lab_file.read_text()); cfg["lab_mode"] = True
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")
    r = client.post("/api/kuroshuna/arm", json={"armed": True})
    assert r.status_code == 200
    assert r.json()["kuroshuna_armed"] is True
    assert json.loads(lab_file.read_text())["kuroshuna_armed"] is True


def test_disarm_always_allowed(client, lab_file):
    # even with lab_mode False, disarming must work (stand down)
    cfg = json.loads(lab_file.read_text()); cfg["kuroshuna_armed"] = True
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")
    r = client.post("/api/kuroshuna/arm", json={"armed": False})
    assert r.status_code == 200
    assert r.json()["kuroshuna_armed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py -k arm -v`
Expected: FAIL — no `/api/kuroshuna/arm`

- [ ] **Step 3: Write minimal implementation**

In `schemas.py`:

```python
class KuroshunaArmRequest(BaseModel):
    armed: bool


class KuroshunaArmResponse(BaseModel):
    lab_mode: bool
    kuroshuna_armed: bool
    broadcast_armed: bool
```

In `routes.py` add (near the other POSTs):

```python
def _arm_response(lab: dict) -> schemas.KuroshunaArmResponse:
    return schemas.KuroshunaArmResponse(
        lab_mode=bool(lab.get("lab_mode")),
        kuroshuna_armed=bool(lab.get("kuroshuna_armed")),
        broadcast_armed=bool(lab.get("broadcast_armed")))


@router.post("/kuroshuna/arm", response_model=schemas.KuroshunaArmResponse)
def kuroshuna_arm(req: schemas.KuroshunaArmRequest):
    lab = authz._load_lab()
    if req.armed and not lab.get("lab_mode"):
        raise HTTPException(status_code=409,
                            detail="cannot arm: lab_mode is off")
    lab["kuroshuna_armed"] = bool(req.armed)
    if not req.armed:
        lab["broadcast_armed"] = False   # disarming Kuroshuna drops broadcast too
    authz.save_lab(lab)
    database.insert_action({
        "timestamp": _now(), "mode": "kuroshuna",
        "action": "kuroshuna_arm", "target": "self",
        "confirmed": 1, "result": "ok",
        "message": f"kuroshuna_armed -> {bool(req.armed)}", "raw_json": {}})
    return _arm_response(lab)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_api/schemas.py backend/kuma_api/routes.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(api): POST /api/kuroshuna/arm (lab_mode-gated; disarm always allowed)"
```

---

### Task 4: `POST /api/kuroshuna/broadcast-arm` (lab_mode + allow_broadcast gated)

**Files:**
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test**

```python
def _set_lab(lab_file, **kw):
    cfg = json.loads(lab_file.read_text()); cfg.update(kw)
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")


def test_broadcast_arm_requires_allow_broadcast(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=False)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": True})
    assert r.status_code == 409
    assert "allow_broadcast" in r.json()["detail"]


def test_broadcast_arm_succeeds_when_enabled(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=True)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": True})
    assert r.status_code == 200
    assert r.json()["broadcast_armed"] is True


def test_broadcast_disarm_always_allowed(client, lab_file):
    _set_lab(lab_file, broadcast_armed=True)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": False})
    assert r.status_code == 200
    assert r.json()["broadcast_armed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py -k broadcast_arm -v`
Expected: FAIL — no endpoint

- [ ] **Step 3: Write minimal implementation**

In `routes.py`:

```python
@router.post("/kuroshuna/broadcast-arm", response_model=schemas.KuroshunaArmResponse)
def kuroshuna_broadcast_arm(req: schemas.KuroshunaArmRequest):
    lab = authz._load_lab()
    if req.armed:
        if not lab.get("lab_mode"):
            raise HTTPException(status_code=409, detail="cannot arm broadcast: lab_mode is off")
        if not lab.get("allow_broadcast"):
            raise HTTPException(status_code=409,
                                detail="cannot arm broadcast: allow_broadcast is off")
    lab["broadcast_armed"] = bool(req.armed)
    authz.save_lab(lab)
    database.insert_action({
        "timestamp": _now(), "mode": "kuroshuna",
        "action": "broadcast_arm", "target": "self", "confirmed": 1,
        "result": "ok", "message": f"broadcast_armed -> {bool(req.armed)}",
        "raw_json": {}})
    return _arm_response(lab)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_api/routes.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(api): POST /api/kuroshuna/broadcast-arm (lab_mode + allow_broadcast gated)"
```

---

### Task 5: `POST /api/kuroshuna/authorize` (the gate round-trip)

**Files:**
- Modify: `backend/kuma_api/schemas.py`
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_kuroshuna_api.py`

- [ ] **Step 1: Write the failing test**

```python
def test_authorize_denies_unapproved(client, lab_file):
    _set_lab(lab_file, lab_mode=True, kuroshuna_armed=True, approved_targets=[])
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "AA:BB:CC:DD:EE:FF", "action": "deauth"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert "not in authorized set" in body["reason"]


def test_authorize_allows_approved(client, lab_file):
    _set_lab(lab_file, lab_mode=True, kuroshuna_armed=True,
             approved_targets=["aa:bb:cc:dd:ee:ff"])
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "AA:BB:CC:DD:EE:FF", "action": "deauth"})
    assert r.json()["allowed"] is True


def test_authorize_broadcast_action_uses_broadcast_gate(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=True, broadcast_armed=True)
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "*", "action": "broadcast"})
    assert r.json()["allowed"] is True
    _set_lab(lab_file, broadcast_armed=False)
    r2 = client.post("/api/kuroshuna/authorize",
                     json={"target": "*", "action": "broadcast"})
    assert r2.json()["allowed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kuroshuna_api.py -k authorize -v`
Expected: FAIL — no endpoint

- [ ] **Step 3: Write minimal implementation**

In `schemas.py`:

```python
class KuroshunaAuthorizeRequest(BaseModel):
    target: str
    action: str


class KuroshunaAuthorizeResponse(BaseModel):
    allowed: bool
    reason: str
```

In `routes.py` (import the gate: `from kuma_core.authz import Gate`):

```python
@router.post("/kuroshuna/authorize",
             response_model=schemas.KuroshunaAuthorizeResponse)
def kuroshuna_authorize(req: schemas.KuroshunaAuthorizeRequest):
    """The T-Deck calls this BEFORE its own ESP32 radio transmits, so the Pi gate
    stays authoritative. The gate audits every decision."""
    gate = Gate()  # reads current lab_targets.json
    if req.action == "broadcast":
        allowed, reason = gate.broadcast_allowed()
    else:
        allowed, reason = gate.is_authorized(req.target, req.action)
    return schemas.KuroshunaAuthorizeResponse(allowed=allowed, reason=reason)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kuroshuna_api.py -v`
Expected: PASS (full file green)

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_api/schemas.py backend/kuma_api/routes.py backend/tests/test_kuroshuna_api.py
git commit -m "feat(api): POST /api/kuroshuna/authorize - Pi gate round-trip for the T-Deck"
```

---

## Phase exit criteria

- `python -m pytest tests/test_kuroshuna_api.py -v` → all green; full suite still green.
- `/api/status` returns `kuroshuna_armed` + `broadcast_armed`.
- `POST /api/kuroshuna/arm` refuses to arm without `lab_mode` (409), always allows disarm, and disarming Kuroshuna also drops `broadcast_armed`.
- `POST /api/kuroshuna/broadcast-arm` requires `lab_mode` + `allow_broadcast` to arm; always allows disarm.
- `POST /api/kuroshuna/authorize` returns the gate's decision (broadcast action → `broadcast_allowed`; else `is_authorized`), and the gate audits it.
- Arm state persists to `lab_targets.json` via `authz.save_lab`.

## Next phases (firmware — build-verified here, on-device validated by Jax)

- **Phase 7 — Firmware UI:** bake `KUROSHUNA_APEX` at 192px; when `kuroshuna_armed`, draw
  Kuroshuna + 黒シュナ wordmark + red/purple HUD; Kuroshuna menu entry + arm confirm (POST
  /api/kuroshuna/arm); broadcast second confirm (POST /api/kuroshuna/broadcast-arm).
- **Phase 2b — Firmware ESP32 RF:** Bruce-style targeted deauth on the T-Deck radio, each
  TX preceded by a `POST /api/kuroshuna/authorize` allow from the Pi gate.
