<!-- KUMA Guard — root README -->
# 🐻 KUMA Guard

**An open-source, DIY, blue-team cyber-defense gadget.**

Where [Pwnagotchi](https://github.com/evilsocket/pwnagotchi), [Bjorn](https://github.com/infinition/Bjorn), [HashMonster](https://github.com/G4lile0/ESP32-WiFi-Hash-Monster), and [Bruce](https://github.com/pr3y/Bruce) are pocket gadgets built for *attacking* wireless networks, KUMA Guard is built for **watching, detecting, and logging attacks against them** — with a pixel-art bear mascot for a face.

> Hibernate = conserve · Foraging = discover · Honey = deceive · Sentinel = detect · Apex = respond

It is deliberately a reproducible build from purchasable parts. **No custom PCB. No sealed product. Build ugly and working first.**

---

## Status: v0.0 (Sprint 1) — mock pipeline

The current build proves the architecture end-to-end **with zero Wi-Fi hardware** using a mock detector:

```
mock detector → event → scoring → SQLite + JSONL → HTTP API → M5Core bear face
```

Real packet capture (rogue-AP / evil-twin / deauth detection on a monitor-mode dongle) is **Sprint 2** — see [ROADMAP.md](ROADMAP.md). The detector skeletons are already in place and documented.

## Hardware (v0.0 prototype)

| Part | Role |
|------|------|
| **Raspberry Pi 4 Model B** | Brain — runs the backend, capture, detection, scoring, SQLite, API |
| **USB Wi-Fi dongle (monitor-mode capable)** | Ears — packet capture (Sprint 2) |
| **M5Stack M5Core + battery** | Face — pixel bear UI, polls the Pi API. *Does no capture.* |

See [docs/hardware-current.md](docs/hardware-current.md).

## Architecture

```
[ M5Core + Battery ]                 the FACE (ESP32 / Arduino)
  bear UI · mode select · alerts
        ⇅  HTTP (JSON)
[ Raspberry Pi 4 ]                   the BRAIN (Python / FastAPI / SQLite)
  mode engine · detectors · scoring · event log · API
        ⇅
[ USB Wi-Fi dongle, monitor mode ]   the EARS (Sprint 2)
```

Full detail in [docs/architecture.md](docs/architecture.md).

## Quickstart (backend, mock mode — no hardware needed)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn kuma_api.app:app --host 0.0.0.0 --port 8080
```

Then:

```bash
curl http://localhost:8080/api/status          # mode, threat_level, bear_state, event count
curl http://localhost:8080/api/events           # recent (mock) events
curl -X POST http://localhost:8080/api/mode -H 'Content-Type: application/json' -d '{"mode":"foraging"}'
# interactive docs: http://localhost:8080/docs
```

Run the tests:

```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```

## M5Core firmware (skeleton)

PlatformIO project under [`firmware/m5core-ui/`](firmware/m5core-ui/). Set your Wi-Fi + Pi IP in `include/config.h`, then `pio run -t upload`. Sprint 1 ships the control loop, screens, and bear placeholder; HTTP wiring is stubbed for Sprint 2.

## Docs

- [architecture.md](docs/architecture.md) — system + data flow
- [hardware-current.md](docs/hardware-current.md) — the v0.0 stack
- [modes.md](docs/modes.md) — the five bear modes
- [api.md](docs/api.md) — HTTP API contract
- [detection-logic.md](docs/detection-logic.md) — what's detected, scoring, what's mock vs real
- [prior-art.md](docs/prior-art.md) — what we learned/borrow from Bjorn, Pwnagotchi, HashMonster, Bruce
- [build-log.md](docs/build-log.md) — running log of what works / what doesn't
- [ROADMAP.md](ROADMAP.md) — sprint plan

## Design rules (non-negotiable)

1. **If it does not work on a desk, it does not deserve a pocket.**
2. **Confidence-scored, never absolute.** Every detection says *"suspected."* MACs can be spoofed. We never overclaim attribution.
3. **No disruptive RF in v0.0.** Apex Mode is a *framework* gated behind `lab_mode` + allowlist + explicit confirmation. No deauth, no jamming, no capture-of-credentials.

## Ethics & scope

KUMA Guard is a **defensive** tool for monitoring networks **you own or are authorized to monitor**. It does not attack. Use it lawfully.

## License

[MIT](LICENSE) © 2026 Jax. We mirror patterns from MIT-licensed prior art (Bjorn, HashMonster) and take architectural inspiration only — no code — from the GPL/AGPL projects (Pwnagotchi, Bruce).
