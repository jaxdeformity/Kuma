# KUMA Real Mitigation — Phase 1 (KUMA Real Defense) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make KUMA's battle `HARDEN` move apply one real, attack-appropriate defensive mitigation against the server-attributed attacker, and swap the rest of the battle to cosmetic per-enemy flavor moves.

**Architecture:** Extract the defensive actions currently inside `ApexResponder` into a shared, pure `MitigationEngine`. Add a token-gated `POST /api/mitigate` that attributes the current attacker from the events DB and applies the canonical action. The T-Deck battle calls it on the (sole) turn-1 `HARDEN` move, then shows enemy-specific flavor moves. Pure blue-team — no `lab_mode`, no offense.

**Tech Stack:** Python 3.11 / FastAPI / pytest (backend on the Pi); C++ / PlatformIO / LovyanGFX (T-Deck firmware).

**Spec:** `docs/superpowers/specs/2026-06-09-kuma-real-mitigation-design.md` (Phase 1 = §3.1–3.4 KUMA-only + §4.1).

---

## File Structure

- **Create** `backend/kuma_core/mitigation.py` — `MitigationEngine`: defensive action bodies (`harden_pmf`, `redirect`, `contain`, `mark_hostile`), `canonical_for(event_type)`, `apply(attacker, event_type)`. Pure/HTTP-free; cfg-injectable for tests.
- **Create** `backend/tests/test_mitigation.py` — engine unit tests.
- **Modify** `backend/detectors/responder.py` — `ApexResponder` delegates its action calls to `MitigationEngine` (keeps its own gates/cooldown).
- **Modify** `backend/kuma_api/schemas.py` — add `MitigateResponse`.
- **Modify** `backend/kuma_api/routes.py` — add `_resolve_attacker()` + `POST /api/mitigate`.
- **Modify** `backend/tests/test_api.py` (or new `test_mitigate_api.py`) — endpoint tests.
- **Modify** `firmware/tdeck-ui/src/kuma_api_client.h` / `.cpp` — add `MitigationResult` + `mitigate()`.
- **Modify** `firmware/tdeck-ui/src/kuma_battle.cpp` — HARDEN turn-1 move, per-enemy flavor table, menu transition.

---

## Task 1: MitigationEngine — canonical action map (pure)

**Files:**
- Create: `backend/kuma_core/mitigation.py`
- Test: `backend/tests/test_mitigation.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mitigation.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mitigation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kuma_core.mitigation'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/kuma_core/mitigation.py
"""Shared defensive mitigation engine.

The real, attack-appropriate blue-team actions KUMA can take against an attacker.
Pure and HTTP-free so both the automated ApexResponder and the manual
/api/mitigate endpoint share one implementation. Actions no-op gracefully when the
operator network config (protected_connection / backup_connection /
containment.blacklist_url) is unset, so manual mitigation is safe out of the box.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request

from kuma_core.config import LAB_TARGETS_FILE


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class MitigationEngine:
    def __init__(self, cfg: dict | None = None, gate=None) -> None:
        self.cfg = cfg if cfg is not None else _load_lab()
        self._gate = gate

    def canonical_for(self, event_type: str) -> str:
        """Strongest real defense for an attack type. Player always sees HARDEN;
        the engine picks the action from the triggering event's type."""
        e = (event_type or "").lower()
        if any(k in e for k in ("deauth", "disassoc", "handshake", "eapol")):
            return "harden+redirect"
        if any(k in e for k in ("rogue", "bssid", "twin", "pineapple", "karma")):
            return "contain"
        if any(k in e for k in ("beacon", "ssid", "botnet", "worm")):
            return "mark+contain"
        return "mark"   # sniffer / jammer / unknown -> nothing to block, mark + log
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mitigation.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/mitigation.py backend/tests/test_mitigation.py
git commit -m "feat(mitigation): canonical-action map for defensive engine"
```

---

## Task 2: MitigationEngine — action bodies + apply()

**Files:**
- Modify: `backend/kuma_core/mitigation.py`
- Test: `backend/tests/test_mitigation.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_mitigation.py
import kuma_core.mitigation as mit


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mitigation.py -q`
Expected: FAIL — `AttributeError: 'MitigationEngine' object has no attribute 'harden_pmf'`

- [ ] **Step 3: Write minimal implementation**

Append these methods to the `MitigationEngine` class in `backend/kuma_core/mitigation.py`:

```python
    # --- defensive action bodies (moved from ApexResponder) ----------------
    def harden_pmf(self) -> str:
        conn = self.cfg.get("protected_connection")
        if not conn:
            return "harden_pmf skipped (set protected_connection)"
        subprocess.run(
            ["nmcli", "connection", "modify", conn,
             "802-11-wireless-security.pmf", "2"], check=False)
        subprocess.run(["nmcli", "connection", "up", conn], check=False)
        return f"hardened PMF=required on '{conn}'"

    def redirect(self) -> str:
        backup = self.cfg.get("backup_connection")
        if not backup:
            return "redirect skipped (set backup_connection)"
        subprocess.run(["nmcli", "connection", "up", backup], check=False)
        return f"redirected protected link to '{backup}'"

    def contain(self, attacker: str) -> str:
        c = self.cfg.get("containment", {})
        url = c.get("blacklist_url")
        if not url:
            return f"containment dispatched (stub) for {attacker} - set containment.blacklist_url"
        try:
            payload = {"mac": attacker, **c.get("payload", {})}
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                method=c.get("method", "POST"),
                headers=c.get("headers", {"Content-Type": "application/json"}))
            urllib.request.urlopen(req, timeout=5)
            return f"containment: blacklisted {attacker} via controller"
        except Exception as e:  # noqa: BLE001
            return f"containment failed for {attacker}: {e}"

    def mark_hostile(self, attacker: str, evidence: str = "") -> str:
        gate = self._gate
        if gate is None:
            from kuma_core.authz import Gate
            gate = Gate()
        gate.auto_hostile_add(attacker, evidence or "battle mitigation")
        return f"marked {attacker} hostile"

    # --- orchestration -----------------------------------------------------
    def apply(self, attacker: str, event_type: str) -> dict:
        action = self.canonical_for(event_type)
        parts: list[str] = []
        if action == "harden+redirect":
            parts.append(self.harden_pmf())
            parts.append(self.redirect())
        elif action == "contain":
            parts.append(self.contain(attacker))
        elif action == "mark+contain":
            parts.append(self.mark_hostile(attacker, event_type))
            parts.append(self.contain(attacker))
        else:  # "mark"
            parts.append(self.mark_hostile(attacker, event_type))
        return {"action": action, "target": attacker, "result": "ok",
                "message": "; ".join(p for p in parts if p)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mitigation.py -q`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/kuma_core/mitigation.py backend/tests/test_mitigation.py
git commit -m "feat(mitigation): defensive action bodies + apply()"
```

---

## Task 3: Refactor ApexResponder to delegate to the engine

**Files:**
- Modify: `backend/detectors/responder.py`
- Test: `backend/tests/test_detectors.py` (existing responder tests must stay green)

- [ ] **Step 1: Run the existing responder tests to confirm the baseline**

Run: `cd backend && python -m pytest tests/test_detectors.py -q`
Expected: PASS (record the count — this is the regression bar)

- [ ] **Step 2: Replace the three private action methods with engine delegation**

In `backend/detectors/responder.py`, add an engine to `__init__`:

```python
    def __init__(self) -> None:
        self.cfg = _load_lab()
        self._last = 0.0
        from kuma_core.mitigation import MitigationEngine
        self._engine = MitigationEngine(cfg=self.cfg)
```

In `reload()`, refresh the engine cfg too:

```python
    def reload(self) -> None:
        self.cfg = _load_lab()
        self._engine.cfg = self.cfg
```

Replace the calls in `on_deauth` (they currently call `self._harden_pmf()`,
`self._redirect()`, `self._contain(attacker)`):

```python
        if resp.get("harden_pmf"):
            actions.append(self._engine.harden_pmf())
        if resp.get("redirect"):
            actions.append(self._engine.redirect())
        if resp.get("contain"):
            actions.append(self._engine.contain(attacker))
```

Delete the now-unused `_harden_pmf`, `_redirect`, `_contain` methods (their bodies
moved to the engine in Task 2). Leave the rest of `ApexResponder` untouched.

- [ ] **Step 3: Run the responder tests to verify no regression**

Run: `cd backend && python -m pytest tests/test_detectors.py -q`
Expected: PASS (same count as Step 1)

- [ ] **Step 4: Run the full suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS (210 + 8 new mitigation tests = 218)

- [ ] **Step 5: Commit**

```bash
git add backend/detectors/responder.py
git commit -m "refactor(apex): delegate defensive actions to MitigationEngine"
```

---

## Task 4: POST /api/mitigate — attribution + endpoint

**Files:**
- Modify: `backend/kuma_api/schemas.py`
- Modify: `backend/kuma_api/routes.py`
- Test: `backend/tests/test_mitigate_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mitigate_api.py
import os
import pytest
from fastapi.testclient import TestClient

from kuma_api.app import app
from kuma_core import database, events

CTRL = {"X-KUMA-Shell-Token": "test-token"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("KUMA_SHELL_TOKEN", "test-token")
    db = tmp_path / "k.db"
    monkeypatch.setattr(database, "DB_PATH", db, raising=False)
    database.init_db()
    return TestClient(app)


def _insert_threat(bssid, etype="deauth_burst", severity="high"):
    database.insert_event(events.make_event(
        mode="sentinel", event_type=etype, confidence=90, severity=severity,
        message="x", source=bssid, bssid=bssid, channel=6))


def test_mitigate_requires_token(client):
    r = client.post("/api/mitigate")
    assert r.status_code in (403, 422)  # missing/empty token rejected


def test_mitigate_no_attacker_returns_applied_false(client):
    r = client.post("/api/mitigate", headers=CTRL)
    assert r.status_code == 200
    assert r.json()["applied"] is False


def test_mitigate_attributes_newest_high_sev_bssid(client):
    _insert_threat("AA:BB:CC:DD:EE:FF", "deauth_burst", "high")
    r = client.post("/api/mitigate", headers=CTRL)
    body = r.json()
    assert body["applied"] is True
    assert body["target"] == "AA:BB:CC:DD:EE:FF"
    assert body["action"] == "harden+redirect"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mitigate_api.py -q`
Expected: FAIL — 404 on `/api/mitigate` (route not defined)

- [ ] **Step 3: Add the schema**

Append to `backend/kuma_api/schemas.py`:

```python
class MitigateResponse(BaseModel):
    applied: bool
    action: str
    target: str
    result: str
    message: str
```

- [ ] **Step 4: Add attribution helper + route to `backend/kuma_api/routes.py`**

```python
def _resolve_attacker() -> tuple[str | None, str | None]:
    """Newest high/critical event that carries a BSSID = the encounter's attacker."""
    for ev in database.get_events(limit=50):
        if ev.get("severity") in ("high", "critical") and ev.get("bssid"):
            return ev["bssid"], ev.get("event_type")
    return None, None


@router.post("/mitigate", response_model=schemas.MitigateResponse)
def post_mitigate(x_kuma_shell_token: str = Header(default="")):
    """KUMA real defense: attribute the current attacker and apply the canonical
    defensive mitigation. Token-gated; no lab_mode (active defense is on by default)."""
    _check_ctrl_token(x_kuma_shell_token)
    attacker, etype = _resolve_attacker()
    if not attacker:
        return schemas.MitigateResponse(
            applied=False, action="", target="", result="none",
            message="no attributable attacker")
    from kuma_core.mitigation import MitigationEngine
    res = MitigationEngine().apply(attacker, etype or "")
    database.insert_action({
        "timestamp": _now(), "mode": "kuma", "action": "mitigate",
        "target": attacker, "confirmed": 1, "result": res["result"],
        "message": res["message"],
        "raw_json": {"engine_action": res["action"], "event_type": etype}})
    return schemas.MitigateResponse(
        applied=True, action=res["action"], target=attacker,
        result=res["result"], message=res["message"])
```

(`Header` is already imported in routes.py for the offensive endpoints; reuse it.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mitigate_api.py -q`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS (221)

- [ ] **Step 7: Commit**

```bash
git add backend/kuma_api/schemas.py backend/kuma_api/routes.py backend/tests/test_mitigate_api.py
git commit -m "feat(api): POST /api/mitigate (attribute attacker + apply canonical defense)"
```

---

## Task 5: Firmware — `mitigate()` API client method

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h`
- Modify: `firmware/tdeck-ui/src/kuma_api_client.cpp`

- [ ] **Step 1: Declare the result struct + method in `kuma_api_client.h`**

Add near the other response structs:

```cpp
struct MitigationResult {
  bool   applied = false;
  String action;     // "harden+redirect" | "contain" | "mark+contain" | "mark"
  String target;     // attacker BSSID
  String message;    // human-readable
};
```

Add to the API client class declaration (next to `armKuroshuna` etc.):

```cpp
  MitigationResult mitigate();   // POST /api/mitigate (token-gated, KUMA defense)
```

- [ ] **Step 2: Implement in `kuma_api_client.cpp`**

Follow the exact pattern of an existing token-gated POST (e.g. `armKuroshuna`):
same base URL, add header `http.addHeader("X-KUMA-Shell-Token", SHELL_TOKEN);`,
POST an empty body, parse the JSON with the existing `ArduinoJson` doc pattern.

```cpp
MitigationResult KumaApiClient::mitigate() {
  MitigationResult r;
  HTTPClient http;
  http.begin(String(baseUrl) + "/api/mitigate");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-KUMA-Shell-Token", SHELL_TOKEN);
  int code = http.POST("{}");
  if (code == 200) {
    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, http.getString()) == DeserializationError::Ok) {
      r.applied = doc["applied"] | false;
      r.action  = String((const char*)(doc["action"]  | ""));
      r.target  = String((const char*)(doc["target"]  | ""));
      r.message = String((const char*)(doc["message"] | ""));
    }
  }
  http.end();
  return r;
}
```

(Match `SHELL_TOKEN` / `baseUrl` / doc-size to whatever the existing methods in
this file already use — reuse their identifiers verbatim.)

- [ ] **Step 3: Compile**

Run: `cd firmware/tdeck-ui && pio run`
Expected: SUCCESS (build completes; note flash %).

- [ ] **Step 4: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_api_client.h firmware/tdeck-ui/src/kuma_api_client.cpp
git commit -m "feat(fw): kuma_api::mitigate() client for POST /api/mitigate"
```

---

## Task 6: Firmware — HARDEN move + per-enemy flavor table

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_battle.cpp`

- [ ] **Step 1: Add the flavor table near the top (by the `EN_NAME` / `AB_NAME` block)**

```cpp
// Turns 2+: cosmetic, enemy-specific flavor moves (no backend effect).
// Indexed by enemy index `en` (same order as EN_NAME[10]).
const char* FLAVOR[10][3] = {
  {"SSID SPOOF SLAP","BEACON BONK","FAKE-PORTAL FAKEOUT"},  // ROGUE AP
  {"MIRROR MATCH","DOPPLE-DENY","TWIN FLAME"},              // EVIL TWIN
  {"FRAME SHRED","PACKET PARRY","RESEND STORM"},            // DEAUTHER
  {"PINEAPPLE PULP","PROBE PUREE","JUICE BOX"},             // WIFI PINEAPPLE
  {"FLOOD GATE","SSID TSUNAMI","BEACON BREAKER"},           // BEACON FLOOD
  {"BAD KARMA","LURE REVERSAL","PROBE BAIT"},               // KARMA LURE
  {"EAPOL ELBOW","HASH CRUNCH","4-WAY WHIFF"},              // HANDSHAKE HARV
  {"PEEK-A-BOO","PROMISC POUNCE","TCPDUMP THUMP"},          // SNIFFER
  {"NOISE CANCEL","SPECTRUM SMACK","DEAFEN"},               // RF JAMMER
  {"C2 SEVER","SEGFAULT STOMP","FORK-BOMB FLICK"},          // BOTNET WORM
};
```

- [ ] **Step 2: Track whether HARDEN has been spent, default the turn-1 menu to HARDEN only**

In the battle loop in `kuma_battle.cpp`, add a flag before the turn loop:

```cpp
  bool hardened = false;     // turn 1 offers only HARDEN; after it fires, flavor moves
  MitigationResult mit;      // remembered for the victory screen
```

In the FIGHT branch, when `!hardened`, present a single-option menu labelled
`HARDEN` (no 4-way ability select). On Select:

```cpp
    if (!hardened) {
      scene("KUMA used HARDEN!", MENU_NONE, 0, pAttack(), kHp,kMax,eHp,eMax,en,lvl);
      mit = kuma_api::mitigate();
      String mline = mit.applied
        ? (String("MITIGATION: ") + mit.action + " -> " + mit.target)
        : "No live attacker to mitigate.";
      scene(mline.c_str(), MENU_NONE, 0, pDefend(), kHp,kMax,eHp,eMax,en,lvl);
      delay(1100);
      int dmg = max(20, eMax / 2);       // HARDEN lands the decisive real blow
      eHp = max(0, eHp - dmg);
      hardened = true;
      delay(700);
      if (eHp <= 0) break;
      continue;                          // next turn -> flavor menu
    }
```

- [ ] **Step 3: After HARDEN, render the 3 flavor moves as the ability menu**

Replace the ability-name source for turns 2+ so the menu shows `FLAVOR[en][0..2]`
(3 options instead of 4). Each flavor pick is cosmetic:

```cpp
    // turns 2+: pick a flavor move (3 options), cosmetic damage only
    int sel = 0; bool dirty = true; unsigned long t0 = millis(); int ab = -1;
    while (ab == -1 && millis() - t0 < 30000) {
      if (dirty) { sceneFlavor("CHOOSE A MOVE", sel, FLAVOR[en], kHp,kMax,eHp,eMax,en,lvl); dirty=false; }
      InputEvent e = input::poll();
      if (e==InputEvent::Up||e==InputEvent::Left){sel=(sel+2)%3;dirty=true;}
      else if(e==InputEvent::Down||e==InputEvent::Right){sel=(sel+1)%3;dirty=true;}
      else if(e==InputEvent::Select){ab=sel;}
      else if(e==InputEvent::Back){ab=-2;}
      delay(20);
    }
    if (ab == -2) continue;
    if (ab < 0) ab = 0;
    scene((String("KUMA used ")+FLAVOR[en][ab]+"!").c_str(), MENU_NONE, 0, pAttack(), kHp,kMax,eHp,eMax,en,lvl);
    eHp = max(0, eHp - (int)random(12, 28));   // cosmetic
    delay(800);
    if (eHp <= 0) break;
```

`sceneFlavor(...)` is a thin wrapper over the existing `scene(...)` ability-menu
renderer that takes a 3-entry `const char*[3]` instead of the old 4-entry
`AB_NAME`. Implement it by copying the `MENU_ABIL` rendering path and looping 3
entries. (If simpler, generalize the existing `scene` menu renderer to accept a
count + name array and pass 3.)

- [ ] **Step 4: Show the real mitigation on the victory screen**

In the victory block (after `kuma_api::postBattleWin()`), add a line under
"DATA SECURED":

```cpp
    if (mit.applied) {
      g2->setTextColor(CYAN); g2->setCursor(40, 116);
      g2->print((String("DEF: ")+mit.action).c_str());
    }
```

- [ ] **Step 5: Compile**

Run: `cd firmware/tdeck-ui && pio run`
Expected: SUCCESS.

- [ ] **Step 6: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_battle.cpp
git commit -m "feat(fw): HARDEN turn-1 real mitigation + per-enemy flavor moveset"
```

---

## Task 7: Deploy + verify on hardware

- [ ] **Step 1: Deploy backend to the Pi** (config/ excluded; never touch lab_targets.json)

```bash
scp -i ~/.ssh/id_ed25519 backend/kuma_core/mitigation.py jax@kuma1:/home/jax/Kuma/backend/kuma_core/
scp -i ~/.ssh/id_ed25519 backend/detectors/responder.py jax@kuma1:/home/jax/Kuma/backend/detectors/
scp -i ~/.ssh/id_ed25519 backend/kuma_api/routes.py backend/kuma_api/schemas.py jax@kuma1:/home/jax/Kuma/backend/kuma_api/
ssh -i ~/.ssh/id_ed25519 jax@kuma1 'sudo systemctl restart kuma-backend && sleep 2 && systemctl is-active kuma-backend'
```

- [ ] **Step 2: Smoke-test the endpoint on the Pi**

```bash
ssh -i ~/.ssh/id_ed25519 jax@kuma1 'curl -s -X POST localhost:8080/api/mitigate -H "X-KUMA-Shell-Token: $KUMA_SHELL_TOKEN" | head -c 300'
```
Expected: JSON with `"applied"` (false if no live high-sev attacker — that's fine).

- [ ] **Step 3: Flash the T-Deck**

Run: `cd firmware/tdeck-ui && pio run -t upload`
Expected: upload OK.

- [ ] **Step 4: Live check** — trigger/await a high-sev event, enter a battle, confirm turn 1 shows only HARDEN, that selecting it shows `MITIGATION: ...`, and turns 2+ show the enemy's 3 flavor moves; victory screen shows `DEF: <action>`.

---

## Self-Review Notes
- **Spec coverage:** §3.1 engine (T1–2), §3.2 canonical map (T1), §3.3 endpoint+attribution (T4), §3.4 KUMA battle flow (T6), §4.1 flavor set (T6), ApexResponder reuse/refactor (T3). Phase-1 scope only; offense (§3.5/3.6/4.2) deliberately absent.
- **No lab_mode** on `/api/mitigate` — matches "active defense from day one."
- **Graceful no-op** verified in T2 so a device with no controller config is safe.
- `mark_hostile` uses a fresh `Gate` in Phase 1 (audit/record only). Phase 3 will inject a shared `Gate` so the mark persists for the counterstrike target.
- Firmware `sceneFlavor` / menu-count generalization is the one place the engineer must adapt to the existing `scene()` renderer — flagged explicitly in T6 Step 3.
