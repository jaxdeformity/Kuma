# KUMA - Build Log

Running log of what works, what doesn't, and setup gotchas. Newest first.

---

## 2026-06-07 - Sprint 2: live on hardware, full detector suite

**Shipped (running on the Pi 5 `kuma1`, all systemd-managed, auto-start):**
- `kuma-backend` (real-mode API + dashboard), `kuma-monitor` (wlan1 → monitor), `kuma-capture` (root scapy detector).
- **Live detectors** in `detectors/live_capture.py`: deauth/disassoc burst, beacon/SSID flood, rogue-AP, evil-twin (incl. **nzyme-style AP fingerprinting** for BSSID-spoof), karma/PineAP, EAPOL handshake-harvest.
- **Apex active defense** (`detectors/responder.py`): detect deauth → evidence + harden-PMF + redirect + controller-containment + `apex_response` event. Defensive only.
- **Dashboard overhaul** (`static/dashboard.html`): CRT instrument console + canvas pixel bear + defenses strip + Apex banner. Replaced the AI-slop v1.

**Proven on real hardware:**
- WiFi Pineapple `aireplay-ng` deauth → KUMA caught `deauth_burst` HIGH (1835 frames/10s), bear → ALERT, on the dashboard. Full pipeline on real attack traffic.
- Both Bruce boards (M5Core ESP32 + T-Deck ESP32-S3) confirmed to **not actually transmit** deauth (ESP32 `esp_wifi_80211_tx` block) - KUMA correctly reported zero deauth while seeing hundreds of beacons.

**Gotchas hit (so the next person doesn't):**
- **NetworkManager** kept re-grabbing `wlan1` → monitor mode wedged / `modprobe` hung / "-16 busy". Fix: `/etc/NetworkManager/conf.d/99-kuma-unmanage.conf` `unmanaged-devices=interface-name:wlan1` + `nmcli general reload`. After that the WN722N v2/v3 (RTL8188EUS) does monitor RX rock-solid.
- TP-Link **WN722N v2/v3** is the classic "monitor mode trap" - passive RX works, injection doesn't. Fine for KUMA (passive). Alfa AWUS1900 (RTL8814AU) = power-hungry + out-of-tree driver, skip on a Pi.
- **Fingerprint FP storm**: an early AP fingerprint that included capability flags / beacon interval / full IE set flagged the owner's own router repeatedly. Fix: stable fields only (rates/RSN/vendor OUIs) + recurrence requirement. Caught via `/design-review` screenshot.
- Pi 5 onboard Wi-Fi DHCP lease churn drops SSH mid-command + the IP wanders - use `kuma1.local`, run multi-step work as systemd units. (Pi was NOT power-rebooting; that was a misdiagnosis.)
- Don't `pkill -f 'uvicorn ...'` from an SSH command that also contains that string - it kills its own shell. Use the `[u]vicorn` regex trick, or systemd.

---

## 2026-06-06 - Sprint 1 scaffold + mock pipeline

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
- Backend runs with **no Wi-Fi hardware** (mock mode) - the Sprint 1 goal.

**Does NOT work yet (by design - Sprint 2):**
- Real Wi-Fi capture / detection (skeletons only).
- M5Core ↔ backend HTTP (firmware client returns stubbed offline status).
- Pixel bear is a colored square, not sprites.

**Notes / gotchas:**
- Keep backend deps lean - this runs on a Pi. (Bjorn's `libatlas-base-dev` install break on Bookworm is the cautionary tale.)
- Mock events are tagged `raw_json.mock=true` so they're never confused with real data.

**Next sprint TODOs:** see [ROADMAP.md](../ROADMAP.md).
