# KUMA Project Context

## Project Summary

You are helping build an open-source defensive cybersecurity hardware/software project called **KUMA**.

KUMA is a portable blue-team cyber defense gadget inspired by the portability, personality, and hands-on usefulness of tools like Pwnagotchi, Flipper Zero, and Bruce, but defender-focused.

The goal is **not** to build a sealed commercial product or expensive custom gadget. The goal is to build an open-source, DIY, reproducible platform using purchasable parts and 3D-printed enclosures later.

The first version should work on a desk before optimizing for a pocket enclosure.

Core principle:

- Build ugly and working first.
- No custom PCB for v0.0.
- No unnecessary new hardware.
- Everything should be open-source and reproducible.
- Favor modular code and honest limitations.
- Do not overpromise detection certainty.
- Treat "known bad/suspicious" as confidence-scored, not absolute truth.

---

## Current Prototype Hardware

The user already owns:

- Raspberry Pi 4 Model B
- USB Wi-Fi adapter capable of monitor mode
- M5Core with battery pack
- microSD cards
- normal USB cables/adapters
- soldering/dev gear as needed

Assume this is the current KUMA v0.0 prototype stack.

Do **not** design Sprint 1 around:

- custom PCBs
- sealed commercial enclosures
- expensive new hardware
- T-Deck
- Cardputer
- Pi Zero 2 W
- BLE dongle
- NFC module
- Sub-GHz module
- RTL-SDR

Those can come later.

For now:

    Raspberry Pi 4 Model B
    + monitor-mode USB Wi-Fi dongle
    + M5Core with battery pack
    = KUMA v0.0 prototype

---

## Product Identity

Name: **KUMA**

Theme: **pixel-art blue-team bear mascot**

Purpose:

- detect suspicious wireless/network behavior
- classify events with confidence scoring
- log observations and evidence
- show status through a handheld mascot UI
- eventually support controlled active-response workflows in authorized lab environments

KUMA should feel like a defender-focused counterpart to portable hacker gadgets, but it must be practical and modular.

Core philosophy:

- Open source
- Buildable from purchasable parts
- No custom PCB for v0.0
- No sealed consumer-product fantasy
- Build ugly and working first
- Favor modular code
- Favor honest limitations
- Do not overpromise attribution or detection certainty
- Treat suspicious activity as confidence-scored, not absolute truth

---

## Core Operating Modes

KUMA has five first-class operating modes.

### 1. Hibernate Mode

Purpose:

- low-power / idle / quiet state
- minimal scanning
- background watch
- preserve battery
- wake on user input or serious event

Bear state:

- sleeping
- one eye open
- cave / moon visual

Security role:

- conserve
- idle safely
- keep low-rate heartbeat

---

### 2. Foraging Mode

Purpose:

- discovery
- network inventory
- RF/network baseline creation

Foraging Mode should collect:

- SSID
- BSSID
- channel
- signal/RSSI if available
- security hints if available
- first_seen
- last_seen
- known/unknown status
- trusted boolean

Bear state:

- walking
- sniffing
- carrying basket
- looking around

Security role:

- discover
- inventory
- build trusted baseline

---

### 3. Honey Mode

Purpose:

- deception
- bait
- decoy logic
- trap telemetry

Sprint 1 Honey Mode is simulated/conceptual only.

Implement:

- mock honey events
- fake service metadata
- decoy profile config
- Honey Mode screen/status
- event logging for manually injected or mock honey interactions

Later versions may support actual decoy services, honey SSIDs, fake clients, or lab-only deception behavior.

Bear state:

- setting honey trap
- honey jar
- hiding behind tree
- bait/trap visual

Security role:

- deceive
- bait
- observe interaction patterns

---

### 4. Sentinel Mode

Purpose:

- active monitoring
- detection
- alerting
- evidence logging

Sentinel Mode should detect:

- new BSSID advertising a known SSID
- known SSID drift
- suspected rogue AP
- suspected evil twin
- unexpected channel drift
- possible security downgrade if observable
- deauth/disassoc burst
- EAPOL activity if observable
- unknown AP flood / beacon flood if observable

Bear state:

- watchtower
- shield
- squinting
- alert posture

Security role:

- detect
- classify
- alert
- log evidence

---

### 5. Apex Mode

Purpose:

- controlled active-response framework
- action queue
- validation framework
- lab-mode workflow

Sprint 1 Apex Mode must be safe and non-disruptive.

Implement only:

- Apex Mode screen/status
- action queue
- action log
- allowlist config
- lab_mode config flag
- mock action execution
- confirmation workflow

Do **not** implement disruptive RF behavior in Sprint 1.

Apex Mode is where future authorized lab actions may live, but the first build must only create the framework and UI/API plumbing.

Bear state:

- armored
- roaring
- shield slam
- apex_ready

Security role:

- respond
- validate
- execute controlled actions
- log actions

---

## Current Hardware Architecture

The correct v0.0 architecture is:

    [M5Core + Battery]
      - Pixel bear UI
      - Mode selector
      - Alerts
      - Buttons/touch controls
      - Calls Pi API over Wi-Fi

            ⇅ HTTP / WebSocket / MQTT

    [Raspberry Pi 4]
      - KUMA backend
      - Wi-Fi monitor mode
      - Foraging/Sentinel logic
      - SQLite logs
      - Event scoring
      - Local API/dashboard

            ⇅

    [USB Wi-Fi Dongle]
      - Monitor-mode packet capture
      - AP discovery
      - Deauth/disassoc detection
      - Rogue/evil twin baseline

The M5Core is **not** responsible for packet capture.

The M5Core is the face/controller.

The Raspberry Pi 4 does the heavy lifting.

---

## Backend Requirements

The Raspberry Pi 4 runs the backend.

Use:

- Python 3
- FastAPI or Flask
- SQLite
- JSON config files
- Linux Wi-Fi tooling
- optional scapy/tshark later

Backend responsibilities:

- mode engine
- API
- event logging
- baseline management
- Wi-Fi discovery
- Sentinel detection logic
- mock detector
- scoring
- local dashboard/API
- action framework

---

## Initial Repository Structure

Create this repo structure:

    kuma-guard/
    ├── backend/
    │   ├── kuma_api/
    │   │   ├── app.py
    │   │   ├── routes.py
    │   │   └── schemas.py
    │   ├── kuma_core/
    │   │   ├── modes.py
    │   │   ├── events.py
    │   │   ├── scoring.py
    │   │   ├── config.py
    │   │   └── database.py
    │   ├── detectors/
    │   │   ├── wifi_forager.py
    │   │   ├── deauth_detector.py
    │   │   ├── rogue_ap_detector.py
    │   │   ├── evil_twin_detector.py
    │   │   └── mock_detector.py
    │   ├── data/
    │   │   ├── kuma.db
    │   │   └── events.jsonl
    │   ├── config/
    │   │   ├── kuma_settings.json
    │   │   ├── trusted_networks.json
    │   │   └── lab_targets.json
    │   ├── scripts/
    │   │   ├── setup_pi.sh
    │   │   ├── start_kuma.sh
    │   │   └── set_monitor_mode.sh
    │   ├── tests/
    │   └── README.md
    ├── firmware/
    │   └── m5core-ui/
    │       ├── platformio.ini
    │       ├── src/
    │       │   ├── main.cpp
    │       │   ├── kuma_api_client.cpp
    │       │   ├── kuma_ui.cpp
    │       │   ├── bear_sprites.cpp
    │       │   └── modes.cpp
    │       ├── include/
    │       └── README.md
    ├── docs/
    │   ├── architecture.md
    │   ├── hardware-current.md
    │   ├── modes.md
    │   ├── api.md
    │   ├── detection-logic.md
    │   └── build-log.md
    └── README.md

---

## Backend: Mode Engine

Implement the five KUMA modes as first-class states:

- `hibernate`
- `foraging`
- `honey`
- `sentinel`
- `apex`

Each mode should expose:

- mode name
- description
- current status
- allowed actions
- bear_state string for UI animation

Example `bear_state` values:

- sleeping
- foraging
- suspicious
- alert
- honey_trap
- apex_ready
- logging
- error

Mode switching should be clean, testable, and logged.

---

## Backend: API Requirements

Implement these endpoints at minimum.

### GET /api/status

Returns:

    {
      "device": "KUMA",
      "version": "0.0.1",
      "mode": "sentinel",
      "threat_level": "low",
      "bear_state": "suspicious",
      "uptime_seconds": 1234,
      "wifi_interface": "wlan1mon",
      "events_last_10m": 3
    }

### GET /api/events

Returns recent events.

Support basic query parameters if easy:

- limit
- severity
- event_type
- since

### GET /api/baseline

Returns known SSIDs/BSSIDs/devices.

### POST /api/mode

Body:

    {
      "mode": "foraging"
    }

### POST /api/action

Body:

    {
      "action": "start_capture",
      "target": "optional target",
      "confirm": true
    }

For Sprint 1, actions should be safe placeholders or local-only operations:

- acknowledge_alert
- start_mock_capture
- export_events
- enter_foraging
- enter_sentinel
- enter_honey
- enter_apex

Do not implement disruptive RF actions in Sprint 1.

Apex Mode should have a pluggable action framework with lab-mode and allowlist enforcement, but active RF countermeasure code is out of scope for the first working build.

---

## Backend: SQLite Database

Use SQLite with tables:

- events
- known_aps
- observations
- actions
- settings

### events table fields

- id
- timestamp
- mode
- event_type
- severity
- confidence
- source
- target
- ssid
- bssid
- channel
- rssi
- message
- raw_json

### known_aps table fields

- id
- ssid
- bssid
- security
- pmf
- channel
- vendor
- trusted
- first_seen
- last_seen
- notes

### observations table fields

- id
- timestamp
- ssid
- bssid
- channel
- rssi
- security
- source
- raw_json

### actions table fields

- id
- timestamp
- mode
- action
- target
- confirmed
- result
- message
- raw_json

### settings table fields

- key
- value
- updated_at

Also write events to JSONL for simple debugging:

    backend/data/events.jsonl

---

## Backend: Config Files

Create sample config files.

### config/kuma_settings.json

    {
      "device_name": "KUMA",
      "version": "0.0.1",
      "default_mode": "sentinel",
      "wifi_interface": "wlan1",
      "monitor_interface": "wlan1mon",
      "lab_mode": false,
      "api_host": "0.0.0.0",
      "api_port": 8080,
      "event_retention_days": 30,
      "threat_thresholds": {
        "low": 25,
        "medium": 50,
        "high": 75,
        "critical": 90
      }
    }

### config/trusted_networks.json

    {
      "networks": [
        {
          "ssid": "HomeLab",
          "trusted": true,
          "bssids": [
            "AA:BB:CC:11:22:33"
          ],
          "expected_security": "WPA2/WPA3",
          "expected_pmf": "required",
          "expected_channels": [6, 36],
          "notes": "Example trusted lab network"
        }
      ]
    }

### config/lab_targets.json

    {
      "lab_mode": false,
      "approved_targets": [],
      "notes": "Future Apex Mode lab action allowlist. No disruptive actions in Sprint 1."
    }

---

## Backend: Wi-Fi Foraging Mode

Build a module that can collect nearby AP data using Linux tools first.

Prefer simple reliable command wrappers before complex packet parsing.

Acceptable tools:

- `iw`
- `iwlist` if needed
- `nmcli` if useful
- `tcpdump` later
- `tshark` later
- `scapy` later

Foraging Mode should collect:

- SSID
- BSSID
- channel
- signal/RSSI if available
- security hints if available
- first_seen
- last_seen
- trusted boolean

Output should update:

- SQLite database
- trusted_networks.json only when explicitly accepted
- observations table for raw observations

Do not auto-trust networks.

---

## Backend: Sentinel Mode

Implement detection logic for:

- new BSSID advertising a known SSID
- known SSID security drift if observable
- unexpected channel drift
- unknown AP burst / beacon flood if observable
- deauth/disassoc burst detection if packet capture is available
- EAPOL activity counter if available

Start simple:

1. Use `mock_detector.py` to generate events before real packet parsing works.
2. Add passive observation with Linux tools.
3. Add scapy/tshark frame parsing only after the mode/API/UI pipeline works.

Do not block the project waiting for perfect packet parsing.

The first goal is an end-to-end pipeline:

    detector event
    → event object
    → scoring
    → SQLite log
    → API response
    → M5Core UI display

---

## Backend: Deauth Detection Logic

Sprint 1 implementation is passive detection only.

Detect:

- deauthentication frames
- disassociation frames
- bursts over time windows
- repeated source/target pairs if observable
- affected channel if observable
- reason codes if observable
- EAPOL activity after bursts if observable

High-level severity:

low:

- small burst
- low confidence
- little or no target repetition

medium:

- repeated frames within time window
- repeated channel or BSSID pattern

high:

- repeated frames targeting known client/AP
- or burst followed by EAPOL activity
- or strong confidence from repeated observations

critical:

- reserved for future use

Event type examples:

- deauth_burst
- disassoc_burst
- handshake_harvest_pattern

Important:

- Do not overclaim attribution.
- MAC addresses may be spoofed.
- Confidence score must be included.
- Events should say "suspected" when uncertain.

---

## Backend: Rogue AP / Evil Twin Detection Logic

Compare observations against baseline.

Signals:

- same SSID + unknown BSSID = suspicious
- same SSID + changed channel = low/medium signal
- same SSID + apparent security downgrade = high signal
- same SSID + suspiciously strong RSSI change = medium signal
- unknown BSSID repeatedly seen = increase confidence
- known BSSID missing for long interval = informational

Event types:

- rogue_ap_suspected
- evil_twin_suspected
- ssid_drift
- security_downgrade_suspected
- new_bssid_for_known_ssid

Example event:

    {
      "event_type": "evil_twin_suspected",
      "severity": "high",
      "confidence": 82,
      "ssid": "HomeLab",
      "bssid": "DE:AD:BE:EF:00:01",
      "channel": 6,
      "message": "Known SSID observed from unknown BSSID with possible security drift"
    }

---

## Backend: Honey Mode

Sprint 1 Honey Mode is conceptual/simulated.

Implement:

- Honey Mode state
- mock honey events
- fake service metadata
- decoy profile config
- manual event injection endpoint if helpful
- UI state showing Honey Mode active

Example honey event types:

- honey_profile_enabled
- honey_interaction_mock
- decoy_service_touched_mock
- bait_ssid_interest_mock

Do not implement real credential capture, phishing, or disruptive behavior.

---

## Backend: Apex Mode

Sprint 1 Apex Mode is an action framework only.

Implement:

- Apex Mode state
- action queue
- action execution framework
- action logging
- lab_mode requirement
- allowlist config
- explicit confirmation requirement
- mock action execution

Allowed Sprint 1 actions:

- acknowledge_alert
- start_mock_capture
- export_events
- enter_foraging
- enter_sentinel
- enter_honey
- enter_apex
- clear_mock_events

Out of scope for Sprint 1:

- active RF countermeasures
- deauth transmission
- jamming
- credential capture
- unapproved network interaction
- automatic blocking

The framework should be modular so future authorized lab actions can be added behind:

- lab_mode=true
- target allowlist
- explicit confirmation
- logging
- short duration
- rate limits
- human review

---

## M5Core Frontend Requirements

The M5Core runs the KUMA handheld UI.

Use Arduino or PlatformIO, whichever is most practical for M5Core.

Responsibilities:

- connect to Wi-Fi
- connect to Pi backend API
- display KUMA status
- display pixel bear mascot
- show current mode
- show threat level
- show event count
- show uptime
- show backend connection state
- allow mode switching
- allow basic action confirmation
- show simple event list

The M5Core is not responsible for packet capture.

---

## M5Core API Behavior

The M5Core should:

- connect to configured Wi-Fi
- use configurable backend IP/port
- poll `/api/status` every 1-3 seconds
- poll `/api/events` every 5 seconds or on button press
- send mode changes to `/api/mode`
- send safe actions to `/api/action`

Backend IP should be configurable in code first, then later through config UI.

---

## M5Core Screen Layouts

Implement these screens.

### 1. Home / Status Screen

Display:

    KUMA
    SENTINEL MODE

    Threat: LOW
    Events: 3
    Uptime: 00:31:22
    Backend: ONLINE

    [pixel bear]

### 2. Mode Selection Screen

Display:

    Select Mode

    > Hibernate
      Foraging
      Honey
      Sentinel
      Apex

### 3. Event List Screen

Display:

    Recent Events

    [MED] deauth_burst
    [LOW] new_unknown_ap
    [HIGH] evil_twin_suspected

### 4. Event Detail Screen

Display:

    Event: deauth_burst
    Severity: MEDIUM
    Confidence: 72
    Channel: 6
    SSID: HomeLab

### 5. Action Confirmation Screen

Display:

    Confirm Action?

    Action:
    start_mock_capture

    A: Cancel
    B: Confirm
    C: Back

---

## M5Core Controls

Use whatever mapping is natural for the M5Core, but default to:

- Button A: previous / menu
- Button B: select / confirm
- Button C: next / back

If touchscreen is available and easy, optional touch buttons can be added later.

Do not overbuild UI in Sprint 1.

---

## M5Core Visual Style

Visual style:

- dark background
- blue/cyan for Sentinel
- green for safe/low
- yellow/orange for Honey
- red only for high severity
- simple pixel bear mascot
- readable text
- low animation complexity

Pixel bear states:

- sleeping = Hibernate
- walking = Foraging
- honey_trap = Honey
- suspicious = Sentinel medium
- alert = Sentinel high
- apex_ready = Apex
- logging = capture/logging
- error = backend unreachable

The first pixel bear can be crude. The pipeline matters more than the art.

---

## Documentation Requirements

Create docs as you build.

### README.md

Should include:

- project purpose
- current prototype hardware
- quickstart
- backend setup
- M5Core firmware setup
- current limitations

### docs/architecture.md

Describe:

- Pi backend
- monitor-mode Wi-Fi dongle
- M5Core UI
- API flow
- event flow

### docs/hardware-current.md

Document current hardware:

- Raspberry Pi 4 Model B
- monitor-mode USB Wi-Fi dongle
- M5Core with battery pack
- known assumptions
- future hardware options

### docs/modes.md

Explain:

- Hibernate
- Foraging
- Honey
- Sentinel
- Apex

Include:

- purpose
- backend behavior
- UI bear state
- actions allowed

### docs/api.md

Document endpoints:

- GET /api/status
- GET /api/events
- GET /api/baseline
- POST /api/mode
- POST /api/action

Include example responses.

### docs/detection-logic.md

Document:

- implemented detections
- confidence scoring
- limitations
- what is mock vs real
- known false positive risks

### docs/build-log.md

Maintain:

- what works
- what does not
- setup notes
- next sprint TODOs

---

## Development Priorities

Build in this order:

1. Scaffold repo.
2. Build backend API with mock data.
3. Build mode engine.
4. Build SQLite event logging.
5. Build mock detector events.
6. Build M5Core UI client that displays backend status.
7. Implement mode switching from M5Core to backend.
8. Implement Wi-Fi Foraging Mode using real Wi-Fi observations.
9. Implement basic Sentinel detections.
10. Implement passive deauth/disassoc event detection if monitor-mode capture works.
11. Add docs and setup scripts.
12. Add tests.

Do not get stuck trying to perfect packet capture before the end-to-end mode/API/UI pipeline works.

---

## Testing Requirements

Include tests for:

- mode transitions
- scoring
- event creation
- config parsing
- mock detector output
- database insert/retrieve
- API response shape

Include:

- mock detector mode
- sample `events.jsonl`
- sample `trusted_networks.json`
- sample API responses

The backend must be runnable without Wi-Fi hardware using mock mode.

---

## Setup Scripts

Create these scripts.

### backend/scripts/setup_pi.sh

Should:

- install Python dependencies
- create venv if appropriate
- install system packages where needed
- initialize database
- print next steps

### backend/scripts/start_kuma.sh

Should:

- activate environment
- start backend API
- optionally select mock or real mode

### backend/scripts/set_monitor_mode.sh

Should:

- accept interface argument
- attempt to set interface down
- set monitor mode
- bring interface up
- print result

Keep scripts readable and conservative.

---

## First Working Demo Goal

The first demo should work like this:

1. Start backend on Pi 4.
2. Backend runs in mock Sentinel Mode.
3. Backend logs mock events to SQLite.
4. `/api/status` returns current mode, threat level, bear state, and event count.
5. `/api/events` returns recent events.
6. M5Core connects to backend API over Wi-Fi.
7. M5Core displays KUMA status and pixel bear state.
8. User can switch modes from M5Core.
9. Backend logs the mode change.
10. UI updates based on new mode.

This proves the system architecture.

Real packet capture comes after this pipeline works.

---

## Example Backend Status Response

    {
      "device": "KUMA",
      "version": "0.0.1",
      "mode": "sentinel",
      "threat_level": "medium",
      "bear_state": "suspicious",
      "uptime_seconds": 1882,
      "wifi_interface": "wlan1mon",
      "events_last_10m": 5,
      "backend_status": "online"
    }

---

## Example Event Object

    {
      "id": 42,
      "timestamp": "2026-06-06T14:32:15Z",
      "mode": "sentinel",
      "event_type": "deauth_burst",
      "severity": "medium",
      "confidence": 74,
      "source": "unknown",
      "target": "unknown",
      "ssid": "HomeLab",
      "bssid": "AA:BB:CC:11:22:33",
      "channel": 6,
      "rssi": -52,
      "message": "Suspected deauth/disassoc burst observed on channel 6",
      "raw_json": {
        "window_seconds": 30,
        "frame_count": 44,
        "reason_codes": [7]
      }
    }

---

## Example Trusted Network Entry

    {
      "ssid": "HomeLab",
      "trusted": true,
      "bssids": [
        "AA:BB:CC:11:22:33"
      ],
      "expected_security": "WPA2/WPA3",
      "expected_pmf": "required",
      "expected_channels": [6, 36],
      "notes": "Example trusted lab network"
    }

---

## Example Mode Model

    {
      "mode": "sentinel",
      "display_name": "Sentinel Mode",
      "description": "Defensive monitoring, alerting, and evidence logging",
      "bear_state": "suspicious",
      "allowed_actions": [
        "acknowledge_alert",
        "start_mock_capture",
        "export_events",
        "enter_foraging",
        "enter_honey",
        "enter_apex"
      ]
    }

---

## Agent Team Instruction Set

Use these agent roles if multiple agents are available.

### Agent 1: Architect

Own:

- repo structure
- architecture.md
- mode model
- API contract
- integration plan

Responsibilities:

- keep scope tight
- prevent custom-PCB fantasy
- prevent hardware shopping creep
- ensure backend/UI contract is clean
- ensure v0.0 works with Pi 4 + M5Core + monitor-mode dongle

Deliverables:

- architecture.md
- api.md draft
- mode model spec
- task breakdown

---

### Agent 2: Backend

Own:

- Python backend
- FastAPI/Flask API
- SQLite schema
- mode engine
- config loader
- event logger
- mock detector

Responsibilities:

- build backend API first
- make it runnable without hardware
- implement mock events
- implement database writes
- expose status/events/baseline/mode/action endpoints

Deliverables:

- backend app
- database module
- event model
- mode engine
- config support
- mock detector

---

### Agent 3: Wi-Fi Detection

Own:

- wifi_forager.py
- rogue_ap_detector.py
- evil_twin_detector.py
- deauth_detector.py

Responsibilities:

- start with mock and Linux command wrappers
- implement real Foraging Mode first
- add scapy/tshark only after pipeline works
- avoid overclaiming attribution
- use confidence scoring

Deliverables:

- AP observation collector
- baseline comparison
- basic rogue/evil twin detection
- passive deauth/disassoc detection if monitor capture works

---

### Agent 4: M5Core Firmware/UI

Own:

- PlatformIO/Arduino firmware
- M5Core UI
- API client
- bear state display
- mode switching

Responsibilities:

- connect to Wi-Fi
- call backend API
- display status
- display mode
- display threat level
- display event count
- show pixel bear
- implement simple controls

Deliverables:

- firmware skeleton
- API polling
- status screen
- mode screen
- event screen
- basic pixel bear assets

---

### Agent 5: Docs/Build

Own:

- README
- setup scripts
- documentation
- build notes

Responsibilities:

- keep docs updated as code is built
- document current hardware
- document setup
- document limitations
- maintain build-log.md

Deliverables:

- README.md
- hardware-current.md
- modes.md
- setup scripts
- build-log.md

---

### Agent 6: QA

Own:

- tests
- validation
- API response checks
- mock pipeline checks

Responsibilities:

- write tests for modes, scoring, events, config parsing, database, and mock detector
- ensure backend can run without Wi-Fi hardware
- ensure API responses match docs
- verify mode switching works

Deliverables:

- unit tests
- test fixtures
- sample events
- sample configs
- test run instructions

---

## First Command Objective for Claude CLI

Start here:

    Create the KUMA v0.0 repository scaffold and implement the backend mock API first. The first demo must show mode switching, event logging, mock Sentinel alerts, and an API response that an M5Core UI can consume. Do not implement real packet capture until the mock pipeline works end-to-end.

---

## Sprint 1 Deliverables

The first agent run should produce:

1. Full repo scaffold.
2. Backend API running locally on Pi/Linux.
3. Mock detector producing events.
4. Mode engine implemented.
5. SQLite event logging.
6. M5Core firmware skeleton that can call the API and show KUMA status.
7. Documentation files with setup instructions.
8. A clear TODO list for the next sprint.

---

## Explicit Non-Goals for Sprint 1

Do not implement:

- custom PCB
- final enclosure design
- active RF countermeasures
- deauth transmission
- jamming
- credential capture
- evil portal
- phishing
- automatic client blocking
- controller integrations
- BLE/NFC/Sub-GHz modules
- complex web dashboard
- production-grade UI art

Do not waste time optimizing for pocket size yet.

Do not buy more hardware unless the current hardware cannot support the v0.0 mock/API/UI pipeline.

---

## Sprint 2 Candidate Goals

After Sprint 1 works:

1. Real Wi-Fi Foraging Mode.
2. Trusted network baseline.
3. Basic rogue AP detection.
4. Passive deauth/disassoc detection.
5. Event severity/confidence tuning.
6. Better M5Core pixel bear sprites.
7. Exportable event report.
8. Optional local web dashboard.
9. Begin 3D printed enclosure concept.
10. Evaluate whether to shrink final backend from Pi 4 to Pi Zero 2 W.

---

## Project North Star

KUMA should become:

    A portable open-source blue-team cyber defense gadget that can forage the environment, set honey traps, stand sentinel, and enter apex mode only when explicitly authorized.

Short version of the mode lifecycle:

    Hibernate = conserve
    Foraging = discover
    Honey = deceive
    Sentinel = detect
    Apex = respond

Core design rule:

    If it cannot eventually fit in a jacket pocket, it is not KUMA.

But for v0.0:

    If it does not work on a desk, it does not deserve a pocket.