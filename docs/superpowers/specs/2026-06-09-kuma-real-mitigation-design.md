# KUMA Real Mitigation — Design Spec

**Date:** 2026-06-09
**Status:** Approved design, pending implementation plan
**Scope:** Item B of the events/mitigation track — make KUMA's battle moves apply
*real* defensive mitigation, with an **unlock-aware moveset** that gains a real
offensive counterstrike once Shuna is unlocked. Folds in the relevant part of item
C (battle flow: HARDEN once, then flavor / counter). Designed as one coherent
battle vision, implemented in three phases (§7). Explicitly excludes item A (event
detail UI) and item D (Shuna audio bug).

---

## 1. Problem

KUMA's on-device battle (`firmware/tdeck-ui/src/kuma_battle.cpp`) is currently
**cosmetic**. When a sustained high/critical threat triggers an encounter, the
player picks from four generic abilities (SIGNAL MAUL / HONEY SNARE / CHANNEL ROAR
/ PAWLOCK) that only run on-device HP/damage math and post battle-win XP. Nothing
real happens to the attacker. The whole point of KUMA is real defense with an
auditable record — so a move must actually mitigate.

A blocking constraint: the firmware's `KumaStatus` threat block carries
`severity / eventType / confidence / ssid` but **not the attacker's BSSID/MAC**.
You cannot "block a MAC" the device doesn't hold. Attribution therefore happens
**server-side**, where the events DB and the authz/mitigation logic already live.

The defensive actions we need already exist inside `ApexResponder`
(`detectors/responder.py`): `harden_pmf` (PMF=required), `redirect` (failover to a
backup connection), `contain` (dispatch attacker MAC to a controller blacklist).
They are wired only to the *automated* deauth responder. We reuse them.

## 2. Goals / Non-goals

**Goals**
- A battle move applies one real, attack-appropriate defensive mitigation per
  encounter, against the server-attributed attacker.
- KUMA's active defense works **from day one** — no `lab_mode` required (it is a
  human-in-the-loop, purely defensive action).
- Persist a structured "mitigation applied" record (feeds item A later).
- Redesign the battle's move flow around a single real `HARDEN` opener followed by
  an **unlock-aware** move set: enemy flavor moves for KUMA, and — once Shuna is
  unlocked — a real targeted counterstrike against the attacker.
- Define the Shuna-flag unlock + one-tap per-session arm gate that enables the
  counterstrike (and the standalone Kuroshuna offensive tier).

**Non-goals (separate specs)**
- Item A: per-event case-management detail UI (consumes this spec's records).
- Item D: Shuna battle audio regression.
- The full standalone Kuroshuna offensive menu (user-initiated, anytime). This spec
  defines the *unlock + arm gate* it depends on and the *in-battle* counterstrike;
  the broader standalone offensive UI is its own spec built on this gate.

## 3. Architecture

### 3.1 `kuma_core/mitigation.py` — the shared engine
A pure, HTTP-free `MitigationEngine` holding the defensive actions, extracted from
`ApexResponder` so both the automated responder and the manual battle path share
one implementation (no duplication).

```
class MitigationEngine:
    def harden_pmf() -> str
    def redirect() -> str
    def contain(mac: str) -> str
    def mark_hostile(mac: str, evidence: str) -> str   # delegates to Gate.auto_hostile_add
    def canonical_for(event_type: str) -> str          # attack type -> action name
    def apply(attacker: str, event_type: str) -> dict   # {action, target, result, message}
```

- `harden_pmf` / `redirect` / `contain` keep their current `nmcli` / controller-API
  behavior, including **graceful no-op** when `protected_connection` /
  `backup_connection` / `containment.blacklist_url` are unset (return a
  "skipped — configure X" message). This is what makes manual mitigation safe out
  of the box.
- `mark_hostile` delegates to the existing `Gate.auto_hostile_add(target, evidence)`
  (`kuma_core/authz.py:183`).
- `ApexResponder` is refactored to delegate its action calls to the engine. Its own
  gates (lab_mode + apex_active_response, cooldown, min-frames, protect_bssids) stay
  in the responder — only the *action bodies* move to the engine.

### 3.2 Canonical action map (`canonical_for`)
Strongest *real* defense per attack type. The player always sees `HARDEN`; the
engine selects the action from the triggering event's type:

| Attack type (event substring) | Canonical mitigation |
|---|---|
| `deauth` / `disassoc` / `handshake` / `eapol` | `harden_pmf` + `redirect` (defeat the deauth — the real "don't get deauthed") |
| `rogue` / `bssid` / `twin` / `pineapple` / `karma` | `contain` (blacklist attacker BSSID via controller) |
| `beacon` / `ssid` flood / `botnet` / `worm` | `mark_hostile` + `contain` |
| `sniff` / `jam` (passive / RF) | `mark_hostile` (nothing to block; mark + log) |
| (fallthrough/unknown) | `mark_hostile` |

`apply()` runs the mapped action(s), returns `{action, target, result, message}`,
where `action` is a short label (e.g. `"harden+redirect"`, `"contain"`,
`"mark"`), `target` is the attacker BSSID, `message` is human-readable.

### 3.3 `POST /api/mitigate` — the manual endpoint
- **Auth:** token-gated via `X-KUMA-Shell-Token` (same `_check_ctrl_token` pattern
  as the offensive endpoints; fail-closed 503 if `KUMA_SHELL_TOKEN` unset, 403 on
  mismatch). The firmware already sends this header.
- **No `lab_mode` gate** — KUMA defense is on by default (Jax's call). The actions
  are inherently defensive and no-op without operator network config.
- **Flow:**
  1. Resolve the attacker: query `database.get_events(...)` for the newest
     high/critical event that carries a BSSID (the encounter trigger). If none,
     return `{applied: false, message: "no attributable attacker"}`.
  2. `engine.apply(attacker, event_type)`.
  3. Persist an action record via `database.insert_action({... action:"mitigate",
     target: attacker, message, raw_json:{engine_action, event_type, result}})`.
  4. Return `{applied: true, action, target, result, message}`.
- The persisted action record is the canonical "real mitigation we applied" datum
  item A's detail view will surface.

### 3.4 Battle flow (firmware) — HARDEN, then an unlock-aware move set
`firmware/tdeck-ui/src/kuma_battle.cpp` + `kuma_api_client`:
- New client call `kuma_api::mitigate() -> MitigationResult { applied, action,
  target, message }` (POST `/api/mitigate`, sends shell-token header).
- **Turn 1 (always):** the only move offered is **`HARDEN`**. Selecting it calls
  `mitigate()`, shows `MITIGATION: <action> -> <target>` (or the no-op/no-attacker
  message), and lands the decisive narrative hit on the enemy.
- **Turns 2+ — the move set depends on unlock state:**
  - **KUMA (Shuna locked):** the **enemy-specific flavor set** (§4.1). Cosmetic:
    in-game damage + animation only, **no backend call**.
  - **SHUNA unlocked:** the same flavor set **plus one real counterstrike move**
    (§4.2). Selecting it actually attacks the offending device back.
- Battle resolves as today (enemy HP → 0 → victory → `postBattleWin`). The victory
  screen shows the real mitigation (and counterstrike, if used).
- Flee/cancel **before** selecting HARDEN applies nothing (no real action until the
  player commits).

### 3.5 Shuna-flag unlock + one-tap session arm (the offense gate)
The counterstrike (and the future standalone offensive tier) is gated by two
layers — a persistent *progression* unlock and a per-session *safety* arm:

- **Unlock (persistent):** finding the Shuna flag (the challenge) sets a persisted
  `shuna_unlocked` flag in the settings table and flips `character` to `shuna`.
  This is the one-way progression gate: no flag → no offensive tier, ever.
- **One-tap session arm (ephemeral):** firing offense additionally requires an arm
  that the player toggles on-device with a single confirm — showing the
  physical-isolation / lawful-use warning — and which lasts the session (in-memory,
  cleared on backend restart). This replaces hand-editing `lab_targets.json` for
  the live flow while preserving the deliberate safety acknowledgment.
- **Backend representation:** the engine that authorizes offense (`Gate` in
  `kuma_core/authz.py`) checks `shuna_unlocked` (persistent) AND a session-armed
  flag. The targeted counterstrike's victim is the **auto-attributed confirmed
  attacker** — which `Gate` already authorizes as an auto-hostile target
  (`authz.py:105`, "auto-hostile (confirmed attacker)"). `protect_bssids` and
  `own_infra` remain hard-denied always.
- Git-tracked config stays blue-team-safe: `shuna_unlocked` defaults `false`, the
  session arm defaults off, all `lab_targets.json` offensive flags stay `false`.

### 3.6 The counterstrike action (backend)
A real targeted offensive action against the attributed attacker, reusing the
existing Tier-A targeted path (`offense/rf_targeted.py` / `net_offense.py` via the
Kuroshuna authorize flow). Endpoint `POST /api/mitigate/counter` (token-gated):
1. Require `shuna_unlocked` + session-armed; else 409 with the reason.
2. Resolve the attacker (same attribution as §3.3) and `mark_hostile` it so the
   `Gate` authorizes targeting it.
3. Run the targeted counter (e.g. a time-boxed, channel-pinned targeted deauth at
   the attacker's BSSID) through the gate; hard-deny if the target is in
   `protect_bssids` / `own_infra`.
4. Persist an action record (`action:"counter"`) and return the result.

## 4. Move sets

### 4.1 KUMA flavor moves (3 per enemy, cosmetic only)

| Enemy | Flavor moves |
|---|---|
| ROGUE AP | SSID SPOOF SLAP · BEACON BONK · FAKE-PORTAL FAKEOUT |
| EVIL TWIN | MIRROR MATCH · DOPPLE-DENY · TWIN FLAME |
| DEAUTHER | FRAME SHRED · PACKET PARRY · RESEND STORM |
| WIFI PINEAPPLE | PINEAPPLE PULP · PROBE PURÉE · JUICE BOX |
| BEACON FLOOD | FLOOD GATE · SSID TSUNAMI · BEACON BREAKER |
| KARMA LURE | BAD KARMA · LURE REVERSAL · PROBE BAIT |
| HANDSHAKE HARV | EAPOL ELBOW · HASH CRUNCH · 4-WAY WHIFF |
| SNIFFER | PEEK-A-BOO · PROMISC POUNCE · TCPDUMP THUMP |
| RF JAMMER | NOISE CANCEL · SPECTRUM SMACK · DEAFEN |
| BOTNET WORM | C2 SEVER · SEGFAULT STOMP · FORK-BOMB FLICK |

Stored as a `const char*` table indexed by the existing enemy index (`en`, 0–9,
the `EN_NAME` order). Individual names may be tweaked during implementation.

### 4.2 Shuna counterstrike move (real offense, unlock-gated)
When Shuna is unlocked, the turns-2+ menu gains **one** real move (slot 4) that
fires the §3.6 counterstrike against the attacker. It is the only move in the whole
battle besides HARDEN that does something real — and the only *offensive* one.

- **Working name: `RETALIATE`** (flavor alias over a targeted counter-deauth).
  Final name is Jax's to set — themed to the Kuroshuna line (cf. GEMINI / RENGOKU /
  BANKAI). One universal move, not per-enemy.
- Selecting it when **unlocked but not session-armed** triggers the one-tap arm
  confirm (§3.5, with the isolation warning) first; on confirm, it fires.
- Disarmed/declined → the move is shown but greys out with "arm to retaliate".
- Locked (no Shuna flag) → the move is absent entirely.

## 5. Safety posture

- **KUMA mitigation (HARDEN) is defensive only**: harden own link, redirect own
  link, blacklist via the operator's own controller, mark hostile in-memory. No
  attack frames transmitted. Token-gated; unconfigured actions no-op with guidance.
- **The Shuna counterstrike (RETALIATE) does transmit** — it is real Tier-A
  offense. It is gated by THREE independent layers: (1) persistent Shuna-flag
  unlock, (2) one-tap per-session arm with the isolation/lawful-use warning, (3)
  the existing `Gate` authz, which only permits targeting the auto-attributed
  confirmed attacker and hard-denies `protect_bssids` / `own_infra` always. It is
  time-boxed and channel-pinned like the rest of the Kuroshuna targeted path.
- **Git-tracked config stays blue-team-safe**: `shuna_unlocked` defaults `false`,
  the session arm defaults off, all `lab_targets.json` offensive flags stay
  `false`. A device fresh from git is purely blue-team until the flag is found.

## 6. Testing

**Backend (pytest)**
- `canonical_for` returns the correct action for each attack-type substring +
  fallthrough.
- `apply()` with config present → action message; with config absent → graceful
  "skipped" no-op (no exception).
- `/api/mitigate` attribution: picks the newest high/critical BSSID-bearing event;
  returns `applied:false` when none exists.
- Token gating: 403 on bad token, 503 when `KUMA_SHELL_TOKEN` unset.
- Regression: `ApexResponder` behavior unchanged after delegating to the engine
  (existing responder tests stay green).

- **Unlock + arm gate:** `shuna_unlocked` persists across reload; session arm is
  in-memory and clears on restart; counter endpoint returns 409 when locked or
  disarmed, fires when both satisfied.
- **Counterstrike authz:** targets only the auto-attributed attacker; hard-denies a
  `protect_bssids` / `own_infra` target even when unlocked + armed.

**Firmware**
- Compiles clean; `mitigate()` wired; HARDEN-then-moveset transition; move set is
  unlock-aware (RETALIATE absent when locked, greyed when disarmed, fires when
  armed); one-tap arm confirm shows the isolation warning.

## 7. Phasing (single design, incremental build)
1. **Phase 1 — KUMA real defense (shippable alone):** `MitigationEngine`,
   `POST /api/mitigate`, server-side attribution, `ApexResponder` refactor, HARDEN
   move + per-enemy flavor set. Item A's record exists from here.
2. **Phase 2 — the offense gate:** `shuna_unlocked` persistence + flag-find wiring +
   one-tap session arm + `Gate` checks.
3. **Phase 3 — the counterstrike:** `POST /api/mitigate/counter`, the RETALIATE move,
   unlock-aware menu. Depends on Phases 1 + 2.

## 8. Downstream (separate specs)
- Item A: per-event case-management list + detail UI (reads the §3.3 / §3.6 action
  records as "mitigation applied" / "counter fired").
- Standalone Kuroshuna offensive menu (user-initiated anytime), built on the §3.5
  gate.
- Item D: Shuna battle audio regression fix (independent).
