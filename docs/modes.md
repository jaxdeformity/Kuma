# KUMA Guard — Modes

KUMA has five first-class modes. Each one is both a *behaviour* and a *face*. The lifecycle reads as a defender's day:

> **Hibernate** = conserve · **Foraging** = discover · **Honey** = deceive · **Sentinel** = detect · **Apex** = respond

Modes are defined in `backend/kuma_core/modes.py`. Switching is validated, logged to the `actions` table, and reflected immediately in `/api/status`.

---

## 🐻 Hibernate — *conserve*

| | |
|---|---|
| **Purpose** | Low-power idle watch; minimal scanning; low-rate heartbeat. |
| **Backend** | Mock loop idles (no events generated in hibernate). |
| **Bear state** | `sleeping` |
| **Allowed actions** | acknowledge_alert, export_events, enter_* |

## 🐻 Foraging — *discover*

| | |
|---|---|
| **Purpose** | Discovery + inventory; builds the trusted baseline. |
| **Backend** | Sprint 2: `wifi_forager` wraps `iw`/`nmcli` to collect SSID/BSSID/channel/RSSI/security → `observations` table. Never auto-trusts. |
| **Bear state** | `foraging` |
| **Allowed actions** | + start_mock_capture |

## 🐻 Honey — *deceive*

| | |
|---|---|
| **Purpose** | Deception / bait / decoy telemetry. **Simulated only in v0.0.** |
| **Backend** | Mock honey events (`honey_profile_enabled`, `honey_interaction_mock`, …). No real services, no credential capture. |
| **Bear state** | `honey_trap` |
| **Allowed actions** | + clear_mock_events |

## 🐻 Sentinel — *detect* (the core)

| | |
|---|---|
| **Purpose** | Active monitoring, detection, alerting, evidence logging. |
| **Backend** | Sprint 1: mock detector. Sprint 2: rogue-AP, evil-twin, deauth/disassoc, channel/security drift. See [detection-logic.md](detection-logic.md). |
| **Bear state** | `suspicious` (calm) → escalates to `alert` when threat level is high/critical |
| **Allowed actions** | acknowledge_alert, start_mock_capture, export_events, clear_mock_events, enter_* |

## 🐻 Apex — *respond* (framework only)

| | |
|---|---|
| **Purpose** | Controlled action framework. **No disruptive RF in v0.0.** |
| **Backend** | Action queue + log + allowlist + `lab_mode` flag + explicit confirmation. Sprint 1 actions are safe placeholders only. |
| **Bear state** | `apex_ready` |
| **Allowed actions** | acknowledge_alert, export_events, enter_* |

**Apex safety gate** — any future action must clear *all* of: `lab_mode=true` · target in `lab_targets.json` allowlist · explicit per-action confirm · logged · rate-limited · short duration · human review. Until those exist, Apex only does framework/UI plumbing.

---

## Bear state reference (drives the M5Core face)

| bear_state | Meaning |
|------------|---------|
| `sleeping` | Hibernate |
| `foraging` | Foraging |
| `honey_trap` | Honey |
| `suspicious` | Sentinel, calm |
| `alert` | Sentinel, high threat |
| `apex_ready` | Apex |
| `logging` | capture/logging in progress |
| `error` | backend unreachable (set by the M5Core itself) |
