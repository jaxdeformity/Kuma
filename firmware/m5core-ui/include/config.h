// KUMA Guard M5Core - build-time config.
// Sprint 1: edit these here. Sprint 2: move to an on-device config screen.
#pragma once

// --- Wi-Fi (station mode; the M5Core joins your LAN to reach the Pi) -------
#define KUMA_WIFI_SSID      "YOUR_WIFI"
#define KUMA_WIFI_PASSWORD  "YOUR_PASSWORD"

// --- Backend (the Raspberry Pi running kuma_api) ---------------------------
#define KUMA_BACKEND_HOST   "192.168.1.50"
#define KUMA_BACKEND_PORT   8080

// --- Polling cadence (ms) --------------------------------------------------
#define KUMA_STATUS_POLL_MS 2000   // /api/status every 1-3s
#define KUMA_EVENTS_POLL_MS 5000   // /api/events every 5s or on button press
