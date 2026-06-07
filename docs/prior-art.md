# KUMA Guard - Prior Art & What We Borrow

KUMA is *not* a from-scratch invention. Four open-source gadgets already do the hard parts - for **red teams**. KUMA inverts their techniques into a **blue-team** posture: their attacks become our detections, their personality systems become our bear, their architectures become our scaffolding.

> Research conducted 2026-06-06 against the live repositories.

## Summary table

| Project | What it is | HW | Stack | License | KUMA borrows |
|---------|-----------|----|-------|---------|--------------|
| [**Bjorn**](https://github.com/infinition/Bjorn) | Autonomous network scanner + offensive toolkit, Tamagotchi-style | Pi Zero W + 2.13" e-Paper HAT | Python | **MIT** ✅ | Orchestrator + pluggable **actions/modules** pattern; Pi-as-brain; e-ink character status; data → `data/output/` |
| [**Pwnagotchi**](https://github.com/evilsocket/pwnagotchi) | A2C "AI" driving bettercap to capture WPA handshakes/PMKIDs | Pi Zero W + e-ink | Python | **GPL-3.0**  | **mood → face state machine** (→ our `bear_state`); **plugin/event hooks** (`on_*`) → our detector model; `config.toml` personality; bettercap-as-sensor → our Pi capture |
| [**ESP32-WiFi-Hash-Monster**](https://github.com/G4lile0/ESP32-WiFi-Hash-Monster) | Captures EAPOL/PMKID to SD on M5Stack (built on spacehuhn's PacketMonitor32) | M5Stack Core (ESP32) | C/Arduino | **MIT** ✅ | M5Stack UI idioms: `M5.Lcd`, `M5.update()`, `BtnA/B/C`; channel-hop logic; promiscuous-mode sniffer scaffolding (we *count*, not capture) |
| [**Bruce**](https://github.com/pr3y/Bruce) | "Predatory" multi-tool ESP32 firmware (WiFi/BLE/RF/IR/RFID) | M5Core/Cardputer/Stick/T-Deck | C++/Arduino | **AGPL-3.0**  | M5 **menu/navigation architecture**; per-device build matrix; config in SPIFFS/LittleFS; WebUI idea (later) |

## License posture (important)

- **Bjorn** and **Hash-Monster** are **MIT** → we may adapt their code directly, with attribution.
- **Pwnagotchi** (GPL-3.0) and **Bruce** (AGPL-3.0) are **copyleft** → we take **architecture and ideas only, no copied code**, to keep KUMA cleanly **MIT**.

---

## How each maps to KUMA

### Bjorn → backend orchestration

Bjorn's strength is an **orchestrator** that sequences modular `actions/` against discovered hosts, with a tiny character on an e-Paper HAT showing status. KUMA mirrors the modular structure: our `detectors/` are the defensive analogue of Bjorn's action modules, and the `ModeEngine` is a (much simpler) orchestrator. Bjorn is also the proof that "Pi + cute status display + autonomous loop" is a winning form factor - we just point it at *defense*. (Note: Bjorn's own install is what kicked this project off - its `libatlas-base-dev` dependency breaks on Bookworm; KUMA deliberately keeps deps lean.)

### Pwnagotchi → the bear's soul

Pwnagotchi's two reusable ideas:

1. **Mood → face.** A small state machine maps internal state to a face glyph (sleeping, excited, bored, ...). KUMA's `bear_state` is the same idea inverted: instead of "how well am I pwning," it's "how worried should I be." Hibernate→sleeping, Sentinel-high→alert.
2. **Plugin/event hooks.** Pwnagotchi plugins implement `on_*` callbacks against a shared event bus. KUMA's detectors are simpler now but the event-factory (`events.make_event`) + central scoring gives us the same "everything funnels through one pipe" property, ready to grow a hook system.

Pwnagotchi also validates **bettercap-as-a-sensor-daemon** on the Pi - directly analogous to our Sprint-2 plan of a monitor-mode dongle feeding the detectors.

### Hash-Monster → the M5Core face

Hash-Monster is the worked example for everything KUMA's M5Core needs at the framework level (these are M5Stack platform APIs, true regardless of Hash-Monster's exact code):

- boot/loop: `M5.begin()` + `M5.update()` each `loop()`
- buttons: `M5.BtnA/B/C.wasPressed()` → our A=prev / B=select / C=next menu
- display: `M5.Lcd` (TFT_eSPI-derived); off-screen `M5Canvas`/sprite for flicker-free bear animation
- channel hopping + promiscuous sniffer - the *capture* half we deliberately leave on the Pi, but the pattern informs any future on-device sensing

### Bruce → M5 firmware architecture

Bruce is the most mature M5/ESP32 **UI framework** of the four - a clean menu/dispatch system across many devices, config in flash, optional WebUI. KUMA's firmware copies the *shape* (menu state machine, per-screen draw functions, button dispatch) without any of Bruce's offensive modules, which are all irrelevant to a read-only defensive client. Bruce's `m5stack-core-esp32` support confirms our target board is well-trodden.

## What KUMA deliberately does NOT copy

- No attack modules (deauth TX, evil portal, beacon spam, BLE/RF/IR/RFID payloads).
- No credential capture or handshake cracking.
- No on-device capture as the primary sensor (kept on the Pi).
- No copyleft code - patterns only from Pwnagotchi/Bruce.

## One-line thesis

> Take Pwnagotchi's soul, Bjorn's body, Hash-Monster's hands, and Bruce's menus - point them all at **defense** - and you get KUMA.
