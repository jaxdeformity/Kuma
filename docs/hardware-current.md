# KUMA Guard — Current Hardware (v0.0)

## The prototype stack

```
Raspberry Pi 4 Model B
  + monitor-mode USB Wi-Fi dongle
  + M5Stack M5Core with battery pack
  = KUMA Guard v0.0
```

| Part | Role | Notes |
|------|------|-------|
| **Raspberry Pi 4 Model B** | Brain | Runs the FastAPI backend, SQLite, detectors, scoring. Any Pi 4 / Pi 5 works; dev also runs on any Linux/macOS/Windows. |
| **USB Wi-Fi adapter (monitor mode)** | Ears | Must support monitor mode + frame injection-free passive capture. Used in Sprint 2. The Pi's built-in `wlan0` stays on your LAN. |
| **M5Stack M5Core + battery** | Face | ESP32, 320×240 ILI9341 TFT, 3 buttons (A/B/C), speaker, battery base. Pure UI client. |
| **microSD** | Storage | Pi OS + KUMA. |

## Assumptions

- The Pi keeps **two interfaces**: `wlan0` (or Ethernet) for the LAN/API, and `wlan1` (the USB dongle) for monitor-mode capture.
- The M5Core and the Pi are on the **same network**; the M5Core reaches the Pi at `KUMA_BACKEND_HOST:8080` (set in `firmware/m5core-ui/include/config.h`).
- v0.0 needs **no** monitor-mode dongle at all — mock mode runs on the Pi (or your laptop) alone.

## Deliberately NOT in v0.0

Per the brief, none of these are designed for yet (they're Sprint-2+/future):
custom PCB · sealed enclosure · T-Deck · Cardputer · Pi Zero 2 W · BLE dongle · NFC · Sub-GHz · RTL-SDR.

## Future hardware options (post-v0.0)

- **Shrink the brain**: evaluate Pi Zero 2 W once the pipeline + detections are stable (Sprint 2 candidate #10).
- **Better face**: M5Core2 (touch), or a Cardputer for a keyboard.
- **More ears**: a second dongle for dual-band / dedicated channel-hopping; later, optional Sub-GHz / BLE sensing modules.
- **Enclosure**: 3D-printed pocket shell — only after it earns the pocket on the desk.
