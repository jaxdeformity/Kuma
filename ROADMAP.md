# KUMA - Roadmap

## Sprint 1 - Prove the pipeline ✅ (this commit)

Mock end-to-end so the architecture is demonstrable on a desk with no Wi-Fi hardware.

- [x] Repo scaffold (backend / firmware / docs)
- [x] Prior-art research (`docs/prior-art.md`)
- [x] Backend API (status / events / baseline / mode / action)
- [x] 5-mode engine + bear-state mapping
- [x] SQLite event logging (+ JSONL mirror)
- [x] Mock detector + background event loop
- [x] Confidence → severity scoring
- [x] pytest suite (modes, scoring, events, db, api)
- [x] M5Core firmware skeleton (screens, nav, bear placeholder)
- [x] Docs + setup scripts

**Demo:** start backend (mock Sentinel) → `/api/status` shows mode/threat/bear/event-count → `/api/events` lists mock events → switch mode via `/api/mode`.

## Sprint 2 - Make it real

> **Status 2026-06-07: mostly shipped.** Live on a Pi (systemd) with real monitor-mode capture and a full detector suite - deauth/disassoc, beacon flood, rogue-AP, evil-twin + AP fingerprinting, karma/PineAP, EAPOL handshake-harvest - plus Apex active defense and an overhauled dashboard with a real pixel bear. Verified against a live WiFi-Pineapple deauth. Remaining: flash the T-Deck face, DHCP reservation, wire real controller-containment. See [build-log.md](docs/build-log.md).


1. **Real Foraging** - `wifi_forager` wraps `iw`/`nmcli`; populate `observations` + `known_aps`.
2. **Trusted baseline** - promote observations to `trusted_networks.json` via explicit confirm.
3. **Rogue-AP detection** - baseline comparison → `new_bssid_for_known_ssid`, `ssid_drift`.
4. **Evil-twin detection** - security-downgrade / RSSI-jump escalation.
5. **Passive deauth/disassoc** - scapy/tshark window counting (no TX), EAPOL counter.
6. **M5Core HTTP client** - wire `WiFi` + `HTTPClient` + `ArduinoJson` to `/api/status` & `/api/events`; Event List / Detail / Action-Confirm screens.
7. **Pixel bear sprites** - real RGB565 frames per mood, off-screen canvas animation.
8. **Severity/confidence tuning** - reduce roaming/mesh false positives (vendor OUI hints).
9. **Exportable event report** - JSON/CSV from `/api/events`.
10. **Optional local web dashboard** - read-only event view served by the Pi.

## Later / future

- Evaluate shrinking the brain to **Pi Zero 2 W**.
- 3D-printed pocket enclosure concept.
- Honey Mode: real (lab-only) decoy services.
- Apex Mode: first authorized lab action behind the full safety gate (`lab_mode` + allowlist + confirm + logging + rate limit + human review).
- BLE / Sub-GHz passive sensing modules.
- **HashMonster (M5Core) - proper port.** Upstream `G4lile0/ESP32-WiFi-Hash-Monster` is bitrotted: LovyanGFX 0.4.3 + Chimera-Core 1.2.4 won't build on any current toolchain, and modernizing the deps surfaces a Chimera-Core ↔ M5Stack-SD-Updater font-API clash. Needs an exact compatible lib matrix (or source patches). Low priority - it's a *passive* capture tool, so it's a weak KUMA test source vs. Bruce/Pwnagotchi.

## Non-goals (still, and on purpose)

Custom PCB · sealed enclosure · active RF countermeasures · deauth TX · jamming · credential capture · evil portal / phishing · automatic client blocking · pocket-size optimization before it works on a desk.
