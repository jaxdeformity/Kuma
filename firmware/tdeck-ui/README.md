# KUMA - T-Deck Firmware (flagship face)

PlatformIO firmware for the **LilyGo T-Deck / T-Deck Plus** (ESP32-S3). The T-Deck is KUMA's premium handheld face: it joins Wi-Fi, polls the Pi backend, and renders the bear + status. Keyboard + trackball give real on-device navigation. **No packet capture** - pure UI client.

Chosen over the M5Core face because the T-Deck adds a **keyboard** (on-device config), **trackball + 2.8" screen** (scrollable event list), and **LoRa + GPS** (future: off-Wi-Fi alert paging, geotagged detections).

## Setup

```bash
cd firmware/tdeck-ui
cp include/config.h.example include/config.h   # then edit Wi-Fi + Pi IP
pio run -e t-deck -t upload
pio device monitor -b 115200
```

`include/config.h` is **gitignored** (holds Wi-Fi creds). Set `KUMA_BACKEND_HOST` to the Pi's IP once it's on the network.

## Layout

```
tdeck-ui/
├── platformio.ini        env t-deck (ESP32-S3, 16MB/8MB OPI PSRAM); LovyanGFX + ArduinoJson
├── include/
│   ├── tdeck_pins.h        LilyGo T-Deck pin map (display/keyboard/trackball/LoRa/GPS)
│   ├── display.h           LovyanGFX ST7789 config for the T-Deck panel
│   ├── config.h.example    template -> copy to config.h
│   └── config.h            (gitignored) Wi-Fi creds + backend host
└── src/
    ├── main.cpp            boot + screen state machine (Home/ModeSelect/EventList)
    ├── input.cpp           I2C keyboard (0x55) + trackball
    ├── kuma_api_client.cpp WiFi + HTTPClient + ArduinoJson: /api/status,/events,/mode,/action
    ├── kuma_ui.cpp         screens + procedural pixel bear
    └── kuma_types.cpp      mode/bear-state <-> string mapping (mirrors backend)
```

## Controls

- **Trackball** move = navigate · **click / Enter** = select · **Back / Left** = back
- **Home** → click opens Mode Select; Right opens Event List
- **Mode Select** → Up/Down choose, click applies (`POST /api/mode`); `*` marks current mode

## Status

First cut - compiles against the real T-Deck pin map; HTTP client is fully wired (this is the Sprint 2 firmware work). On-hardware display/keyboard tuning may need small tweaks when first flashed (panel invert/offset, trackball polarity). The Bruce firmware currently on the T-Deck gets overwritten on flash - the M5Core is the Bruce attacker now.
