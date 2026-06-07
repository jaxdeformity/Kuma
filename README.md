<!-- KUMA Guard — root README -->
# 🐻 KUMA Guard

**An open-source, DIY, blue-team cyber-defense gadget.**

Where [Pwnagotchi](https://github.com/evilsocket/pwnagotchi), [Bjorn](https://github.com/infinition/Bjorn), [HashMonster](https://github.com/G4lile0/ESP32-WiFi-Hash-Monster), and [Bruce](https://github.com/pr3y/Bruce) are pocket gadgets built for *attacking* wireless networks, KUMA Guard is built for **watching, detecting, and logging attacks against them** — with a pixel-art bear mascot for a face.

> Hibernate = conserve · Foraging = discover · Honey = deceive · Sentinel = detect · Apex = respond

It is deliberately a reproducible build from purchasable parts. **No custom PCB. No sealed product. Build ugly and working first.**

---

## Status: v0.0 — live on hardware

KUMA runs as a real, autonomous blue-team sensor on a Raspberry Pi (systemd-managed, auto-arming). The full pipeline works on **live attack traffic** — verified by catching a real WiFi-Pineapple deauth flood (`deauth_burst` HIGH, bear → ALERT, on the dashboard).

```
802.11 frame (monitor mode) → detector → scoring → SQLite → HTTP API → dashboard / handheld face
```

**Live detectors** ([docs/detection-logic.md](docs/detection-logic.md)): deauth/disassoc burst · beacon/SSID flood · rogue-AP · evil-twin (incl. nzyme-style AP fingerprinting that survives BSSID spoofing) · karma/PineAP · EAPOL handshake-harvest. Plus **Apex Mode** automated active *defense* (detect → harden-PMF / redirect / controller-containment) — defensive only, KUMA never transmits attack frames.

A `KUMA_MOCK=1` mode still runs the whole pipeline with **zero Wi-Fi hardware** for development.

## Hardware (v0.0 prototype)

| Part | Role |
|------|------|
| **Raspberry Pi 4 Model B** | Brain — runs the backend, capture, detection, scoring, SQLite, API |
| **USB Wi-Fi dongle (monitor-mode capable)** | Ears — live monitor-mode packet capture |
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
[ USB Wi-Fi dongle, monitor mode ]   the EARS (live capture)
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
