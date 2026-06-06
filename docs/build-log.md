# KUMA Guard — Build Log

Running log of what works, what doesn't, and setup gotchas. Newest first.

---

## 2026-06-06 — Sprint 1 scaffold + mock pipeline

**Shipped:**
- Repo scaffold (backend + firmware + docs) per the brief.
- Prior-art research against Bjorn, Pwnagotchi, ESP32-WiFi-Hash-Monster, Bruce → `docs/prior-art.md`.
- **Working backend mock pipeline**: FastAPI app, `ModeEngine` (5 modes), SQLite (+JSONL mirror), confidence→severity scoring, mock detector, background event loop.
- API: `/api/status`, `/api/events`, `/api/baseline`, `/api/mode`, `/api/action` (safe actions only).
- Detector skeletons: forager, deauth, rogue-AP, evil-twin (documented, not yet wired to capture).
- pytest suite: modes, scoring, events+DB round-trip, API shape.
- M5Core firmware skeleton (PlatformIO, M5Unified): control loop, Home + Mode-Select screens, button nav, bear placeholder. HTTP client stubbed.

**Works:**
- `uvicorn kuma_api.app:app` serves status/events; mock loop drips events; mode switching logs to `actions`.
- Backend runs with **no Wi-Fi hardware** (mock mode) — the Sprint 1 goal.

**Does NOT work yet (by design — Sprint 2):**
- Real Wi-Fi capture / detection (skeletons only).
- M5Core ↔ backend HTTP (firmware client returns stubbed offline status).
- Pixel bear is a colored square, not sprites.

**Notes / gotchas:**
- Keep backend deps lean — this runs on a Pi. (Bjorn's `libatlas-base-dev` install break on Bookworm is the cautionary tale.)
- Mock events are tagged `raw_json.mock=true` so they're never confused with real data.

**Next sprint TODOs:** see [ROADMAP.md](../ROADMAP.md).
