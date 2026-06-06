# KUMA Guard — M5Core Firmware (the Face)

PlatformIO project for the **M5Stack M5Core BASIC** (ESP32). The M5Core is a thin UI client: it joins Wi-Fi, polls the Pi backend over HTTP, renders the pixel bear + status, and lets you switch modes / confirm safe actions. **It does no packet capture.**

## Build & flash

```bash
# install PlatformIO core: https://platformio.org/install
cd firmware/m5core-ui
# 1. set Wi-Fi + Pi IP:
$EDITOR include/config.h
# 2. build + flash:
pio run -t upload
pio device monitor
```

## Layout

```
m5core-ui/
├── platformio.ini      board=m5stack-core-esp32, libs: M5Unified, ArduinoJson
├── include/
│   ├── config.h          Wi-Fi creds, backend host/port, poll cadence
│   ├── modes.h           KumaMode + BearState enums (mirror the backend)
│   ├── kuma_api_client.h  HTTP client interface
│   └── kuma_ui.h         screen rendering interface
└── src/
    ├── main.cpp          setup/loop, button nav (A=prev B=select C=next)
    ├── kuma_api_client.cpp  Wi-Fi + HTTP (STUB → Sprint 2)
    ├── kuma_ui.cpp       screen drawing (M5GFX), bear placeholder
    ├── modes.cpp         string↔enum mapping
    └── bear_sprites.cpp  pixel bear frames (placeholder → Sprint 2)
```

## Screens (Sprint 1)

- **Home** — `KUMA GUARD / SENTINEL MODE / Threat / Events / Backend` + bear
- **Mode Select** — Hibernate · Foraging · Honey · Sentinel · Apex

Event List / Event Detail / Action Confirm screens are stubbed and land in Sprint 2 alongside the real HTTP client.

## Buttons

`A` = previous / menu · `B` = select / confirm · `C` = next / back

## Status

Skeleton. Compiles, control loop + screens + button nav are real; `kuma_api_client.cpp` returns a stubbed offline status until Sprint 2 wires `HTTPClient` + `ArduinoJson` against [`/api/status`](../../docs/api.md).
