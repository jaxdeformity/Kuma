# クマ

KUMA. An open-source, DIY, blue-team Wi-Fi defense gadget.

Pwnagotchi, [Bjorn](https://github.com/infinition/Bjorn), [HashMonster](https://github.com/G4lile0/ESP32-WiFi-Hash-Monster), and [Bruce](https://github.com/pr3y/Bruce) are pocket tools built for attacking wireless networks. KUMA is the opposite. It sits on the network you want to protect, watches the air for those attacks, scores what it sees, and shows it on a dashboard with a pixel-bear mascot whose mood tracks the threat. Detection and defense only. The device never transmits attack frames.

Five modes: Hibernate (conserve), Foraging (discover), Sentinel (detect), Honey (deceive), Apex (respond).

Built from parts you can buy. No custom PCB, no sealed product. Ugly and working first.

## Status

Live on hardware. KUMA runs as an autonomous sensor on a Raspberry Pi under systemd and arms itself on boot. The whole path works on real attack traffic, proven by catching a live WiFi Pineapple deauth flood: 1640 frames in ten seconds, threat HIGH, bear on alert, all on the dashboard.

The pipeline:

```
802.11 frame (monitor mode) -> detector -> scoring -> SQLite -> HTTP API -> dashboard / handheld
```

Detectors running live (details in [docs/detection-logic.md](docs/detection-logic.md)):

- deauth and disassoc bursts
- beacon and SSID floods
- rogue access points
- evil twins, caught by security downgrade
- karma and PineAP probe response
- EAPOL handshake harvesting

Apex Mode adds gated, automated defense: harden PMF, fail over to a backup link, or hand the attacker MAC to a managed controller for containment. It is defensive only and off by default. KUMA never sends deauth or jamming frames.

Beacon fingerprinting, which catches a clone that spoofs the real BSSID exactly, also exists but ships opt-in. On a real multi-radio router it false-alarms, so it stays off until the scoring is rebuilt. The detection doc has the honest writeup.

For development, `KUMA_MOCK=1` runs the entire pipeline with no Wi-Fi hardware.

## Hardware

| Part | Role |
|------|------|
| Raspberry Pi 4 or 5 | The brain. Backend, capture, detection, scoring, SQLite, API. |
| USB Wi-Fi dongle, monitor capable | The ears. Live packet capture. A TP-Link WN722N works well. |
| LilyGo T-Deck or M5Stack Core | The face. Pixel-bear UI that polls the Pi. Does no capture itself. |

Details in [docs/hardware-current.md](docs/hardware-current.md).

## Architecture

```
[ T-Deck / M5Core ]              the FACE (ESP32)
  bear UI, mode select, alerts
        |  HTTP (JSON)
[ Raspberry Pi ]                 the BRAIN (Python, FastAPI, SQLite)
  mode engine, detectors, scoring, event log, API
        |
[ USB dongle, monitor mode ]     the EARS
```

More in [docs/architecture.md](docs/architecture.md).

## Quickstart (no hardware, mock mode)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn kuma_api.app:app --host 0.0.0.0 --port 8080
```

Then:

```bash
curl http://localhost:8080/api/status     # mode, threat_level, bear_state, event count
curl http://localhost:8080/api/events     # recent events
curl -X POST http://localhost:8080/api/mode -H 'Content-Type: application/json' -d '{"mode":"foraging"}'
# interactive docs at http://localhost:8080/docs
# dashboard at http://localhost:8080/
```

Run the tests:

```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```

## Firmware

PlatformIO projects under [`firmware/`](firmware/). The T-Deck build (`firmware/tdeck-ui/`) is the current handheld face. Set your Wi-Fi and the Pi address in `include/config.h`, then `pio run -t upload`.

## Design

The look is locked in [DESIGN.md](DESIGN.md): a dark, monospace instrument console, the Akakabuto bear, and a blacklist of AI-template patterns so nothing drifts into slop. Five dashboard directions to choose from live in [`designs/`](designs/).

## Docs

- [architecture.md](docs/architecture.md), system and data flow
- [hardware-current.md](docs/hardware-current.md), the current stack
- [modes.md](docs/modes.md), the five bear modes
- [api.md](docs/api.md), the HTTP API contract
- [detection-logic.md](docs/detection-logic.md), what is detected and how it is scored
- [prior-art.md](docs/prior-art.md), what we took from Bjorn, Pwnagotchi, HashMonster, Bruce
- [build-log.md](docs/build-log.md), running notes on what works and what does not
- [ROADMAP.md](ROADMAP.md), the plan

## Rules

1. If it does not work on a desk, it does not deserve a pocket.
2. Confidence scored, never absolute. Every detection says "suspected." MACs can be spoofed, so we never overclaim attribution.
3. No disruptive RF. Apex is gated behind `lab_mode` and an allowlist. No deauth, no jamming, no credential capture.

## Scope

KUMA is a defensive tool for networks you own or are authorized to monitor. It does not attack. Use it lawfully.

## License

[MIT](LICENSE), 2026 Jax. Patterns mirrored from the MIT-licensed prior art (Bjorn, HashMonster). Architecture inspiration only, no code, from the GPL and AGPL projects (Pwnagotchi, Bruce).
