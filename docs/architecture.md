# KUMA Guard - Architecture

## The split-brain principle

KUMA separates the **brain** (a Linux box that can do real packet capture and run Python) from the **face** (a cheap, friendly, battery-powered handheld). This is the single most important design decision and it's borrowed straight from the prior art: Pwnagotchi and Bjorn put the brain on a Raspberry Pi; KUMA does the same, and pushes the personality out to a separate M5Core so the face can be swapped or upgraded without touching detection logic.

```
┌──────────────────────────────┐
│  M5Core + Battery   (FACE)   │   ESP32 / Arduino / M5Unified
│  • pixel bear UI             │
│  • mode selector             │
│  • alerts / event list       │
│  • buttons (A/B/C)           │
└──────────────┬───────────────┘
               │  HTTP (JSON)   - polls /api/status (1-3s), /api/events (5s)
               │                  posts /api/mode, /api/action
┌──────────────▼───────────────┐
│  Raspberry Pi 4     (BRAIN)  │   Python 3 / FastAPI / SQLite
│  • mode engine               │
│  • detectors + scoring       │
│  • event log (SQLite+JSONL)  │
│  • local HTTP API            │
└──────────────┬───────────────┘
               │  monitor-mode capture (Sprint 2)
┌──────────────▼───────────────┐
│  USB Wi-Fi dongle   (EARS)   │   monitor mode
│  • AP discovery              │
│  • deauth/disassoc frames    │
│  • rogue/evil-twin baseline  │
└──────────────────────────────┘
```

## Backend components (`backend/`)

| Module | Responsibility |
|--------|----------------|
| `kuma_core/config.py` | Loads JSON configs into a reloadable `settings` singleton |
| `kuma_core/modes.py` | The five-mode state machine + `ModeEngine` |
| `kuma_core/events.py` | `make_event()` factory - the one way events are born |
| `kuma_core/scoring.py` | confidence → severity, event list → threat level |
| `kuma_core/database.py` | SQLite (events, known_aps, observations, actions, settings) + JSONL mirror |
| `detectors/mock_detector.py` | Synthetic events that drive the Sprint 1 demo |
| `detectors/*` | Real detector skeletons (forager, deauth, rogue AP, evil twin) |
| `kuma_api/app.py` | FastAPI app + lifespan + background mock loop |
| `kuma_api/routes.py` | The HTTP surface |
| `kuma_api/state.py` | Process-wide mode engine, uptime, action execution |

## Event flow (the pipeline Sprint 1 proves)

```
detector  ─▶  events.make_event()  ─▶  scoring.severity_for()
          ─▶  database.insert_event()  ─▶  (SQLite row + events.jsonl line)
          ─▶  GET /api/status / /api/events
          ─▶  M5Core renders bear_state + counts
```

The same path serves mock and real events - the only thing that changes in Sprint 2 is *who calls `make_event()`*. That's why we build the pipeline first and the packet parsing second.

## Why the M5Core does no capture

The M5Core (ESP32) *can* sniff in promiscuous mode (that's exactly what HashMonster does), but its single radio, small RAM, and the need to also drive the UI make it a poor primary sensor. Keeping capture on the Pi's dedicated monitor-mode dongle gives reliable, channel-hopping capture and keeps the face responsive. The M5Core stays a pure client of the documented [API](api.md).

## Failure posture

- Backend unreachable → M5Core shows `BearState::Error` (grey bear, `Backend: OFFLINE`). The face degrades gracefully; it never blocks.
- Mock loop is opt-out (`KUMA_MOCK=0`) so a real deployment can run silent until real detectors fire.
