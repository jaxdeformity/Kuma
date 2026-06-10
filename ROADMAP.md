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

## Sprint 2 - Make it real ✅

> **Status 2026-06-09: shipped.** Live on a Pi (systemd, always-on, reboot-validated) with real monitor-mode capture and a full detector suite - deauth/disassoc, beacon flood, rogue-AP, evil-twin + AP fingerprinting, karma/PineAP, EAPOL handshake-harvest - plus Apex active defense and an overhauled dashboard with a real pixel bear (Shuna character skin). Verified live against a WiFi-Pineapple deauth, a Pwnagotchi, and Bjorn. T-Deck (Lily) flashed. See [build-log.md](docs/build-log.md).

- [x] **Real Foraging** - `wifi_forager` wraps `iw`/`nmcli`; populate `observations` + `known_aps`.
- [x] **Trusted baseline** - promote observations to `trusted_networks.json` via explicit confirm.
- [x] **Rogue-AP detection** - baseline comparison → `new_bssid_for_known_ssid`, `ssid_drift`.
- [x] **Evil-twin detection** - security-downgrade / RSSI-jump escalation.
- [x] **Passive deauth/disassoc** - scapy/tshark window counting (no TX), EAPOL counter.
- [x] **Firmware HTTP client** - `WiFi` + `HTTPClient` + `ArduinoJson` to `/api/status` & `/api/events`; Event List / Detail / Action-Confirm screens (now a Cases view).
- [x] **Pixel bear sprites** - real RGB565 frames per mood, off-screen canvas animation; full Shuna character skin + evolution packs.
- [x] **Severity/confidence tuning** - reduce roaming/mesh false positives (vendor OUI hints).
- [ ] **Exportable event report** - JSON/CSV from `/api/events`. *(carryover)*
- [ ] **Optional local web dashboard** - read-only event view served by the Pi. *(carryover)*

## Sprint 3 - Kuroshuna offense + real mitigation ✅

> **Status 2026-06-10: shipped + pushed (origin/main).** History was security-purged before publishing (see [[handoff:0022]]). Default posture is unchanged blue-team; all offense is behind the authorization gate (`lab_mode` + allowlist/auto-hostile + confirm + JSONL audit + hard-deny of protected BSSIDs/own-infra). On-device hardware validation by Jax still pending.

- [x] **Authorization gate** - `kuma_core/authz.py` tiered gating, hard-deny floor, auto-hostile, broadcast-arm, JSONL audit.
- [x] **Tier-A RF offense** - gated deauth + handshake capture (Pi/Alfa + ESP32 handheld), `--no-tx` dry-run.
- [x] **Tier-A network offense** - nmap scan + 6-proto brute (SSH/FTP/SMB/RDP/Telnet/SQL) + SSH/SFTP steal.
- [x] **Tier-B broadcast** - time-boxed flood/spam.
- [x] **Orchestrator** - scoped auto-loop; never auto-fires broadcast.
- [x] **Kuroshuna API + firmware skin** - arm/broadcast/authorize endpoints; クロシュナ blood-red mirrored dashboard + combat stats (TX/PWNED/UPTIME); terminal arm.
- [x] **Real mitigation** - `MitigationEngine` + `POST /api/mitigate` (attribute attacker → canonical defense); Apex delegates to it; firmware HARDEN turn-1 + per-enemy flavor moveset.
- [x] **Zero-config defense** - auto-detect active Wi-Fi → harden/avoid, config optional; capability-aware PMF (require only on 802.11w-capable APs, `pmf_strict` opt-in).

**Pending on-device (Jax):** flash-verify Kuroshuna skin + RF on Lily/Pi · reconcile Pi git (`fetch && reset --hard origin/main`) · install `requirements-offense.txt` (paramiko/impacket/pymysql) for net brute/steal · delete `../kuma-prepurge-backup.bundle` once satisfied.

## Sprint 4 - Queued (planned, not built)

- [ ] **XP/leveling UI** - surface the existing `progress.py` engine: XP bar + level on both dashboard skins, "+EXP" on battle victory, network-discovered EXP toast. Plan: `docs/superpowers/plans/2026-06-09-kuma-xp-ui.md`.
- [ ] **Kuroshuna attack menu** - armed-home Select → BROADCAST/TARGETED; named attacks GEMINI/DEAUTH/AOI/RENGOKU/BANKAI (BANKAI = unscoped harvest behind the hard-deny floor); `POST /api/kuroshuna/broadcast`. Plan: `docs/superpowers/plans/2026-06-09-kuroshuna-attack-menu.md`.
- [ ] **Networks view redesign** - add GPS.
- [ ] **Shuna battle audio** - fix audio bug.

## Later / future

- Evaluate shrinking the brain to **Pi Zero 2 W**.
- 3D-printed pocket enclosure concept.
- Honey Mode: real (lab-only) decoy services.
- Apex Mode: first authorized lab action behind the full safety gate (`lab_mode` + allowlist + confirm + logging + rate limit + human review).
- BLE / Sub-GHz passive sensing modules.
- **HashMonster (M5Core) - proper port.** Upstream `G4lile0/ESP32-WiFi-Hash-Monster` is bitrotted: LovyanGFX 0.4.3 + Chimera-Core 1.2.4 won't build on any current toolchain, and modernizing the deps surfaces a Chimera-Core ↔ M5Stack-SD-Updater font-API clash. Needs an exact compatible lib matrix (or source patches). Low priority - it's a *passive* capture tool, so it's a weak KUMA test source vs. Bruce/Pwnagotchi.

## Gated lab-only capabilities (formerly non-goals)

Active RF countermeasures · deauth TX · credential capture · broadcast flood/spam are **implemented in Kuroshuna offensive mode** as of Sprint 3. They are NOT default behavior: every path is behind the authorization gate (`lab_mode` + allowlist/auto-hostile + confirm + audit log) with a hard-deny floor for protected BSSIDs / own infrastructure. Lawful, authorized lab use only (CFAA/CMA/FCC) - see README's Offensive Capability section.

## Non-goals (still, and on purpose)

Custom PCB · sealed enclosure · jamming · evil portal / phishing · unscoped/un-gated automatic client blocking · pocket-size optimization before it works on a desk.
