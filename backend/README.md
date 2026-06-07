# KUMA - Backend

Python / FastAPI / SQLite backend. Runs on the Raspberry Pi 4 (or any Linux/macOS/Windows box for development). Sprint 1 runs entirely on a **mock detector** - no Wi-Fi hardware required.

## Layout

```
backend/
├── kuma_api/        FastAPI app + routes + schemas + runtime state
│   ├── app.py         entrypoint + lifespan + background mock loop
│   ├── routes.py      /api/status /api/events /api/baseline /api/mode /api/action
│   ├── schemas.py     pydantic models (the M5Core contract)
│   └── state.py       shared mode engine, uptime, action handling
├── kuma_core/       mode engine, events, scoring, config, database
├── detectors/       mock_detector (live) + wifi/deauth/rogue/evil-twin (skeleton)
├── config/          kuma_settings.json, trusted_networks.json, lab_targets.json
├── data/            kuma.db (gitignored) + events.jsonl (sample committed)
├── scripts/         setup_pi.sh, start_kuma.sh, set_monitor_mode.sh
└── tests/           pytest suite (modes, scoring, events, db, api)
```

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn kuma_api.app:app --host 0.0.0.0 --port 8080
```

Environment toggles:

| Var | Default | Effect |
|-----|---------|--------|
| `KUMA_MOCK` | `1` | `0` disables the background synthetic-event loop |
| `KUMA_MOCK_INTERVAL` | `12` | seconds between mock events |
| `KUMA_HOST` / `KUMA_PORT` | `0.0.0.0` / `8080` | bind address (via `start_kuma.sh`) |

## Test

```bash
pip install -r requirements-dev.txt
pytest -q
```

## On the Pi

```bash
./scripts/setup_pi.sh        # venv + deps + db init
./scripts/start_kuma.sh      # mock mode
# Sprint 2: sudo ./scripts/set_monitor_mode.sh wlan1
```
