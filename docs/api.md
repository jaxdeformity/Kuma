# KUMA - HTTP API

Base URL: `http://<pi-ip>:8080`. Interactive docs (Swagger) at `/docs`. All bodies are JSON.

This is the contract the M5Core firmware depends on - changes here must stay in sync with `firmware/m5core-ui/` and `backend/kuma_api/schemas.py`.

---

## `GET /api/status`

Device heartbeat. Polled by the M5Core every 1-3s.

```json
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
```

`threat_level` ∈ `low|medium|high|critical` (roll-up of the worst recent event).
`bear_state` drives the face; in Sentinel it becomes `alert` when threat is high+.

---

## `GET /api/events`

Recent events, newest first. Optional query params:

| param | example | meaning |
|-------|---------|---------|
| `limit` | `?limit=20` | max rows (default 50) |
| `severity` | `?severity=high` | filter by severity |
| `event_type` | `?event_type=deauth_burst` | filter by type |
| `since` | `?since=2026-06-06T14:00:00Z` | only at/after this ISO timestamp |

```json
[
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
    "raw_json": { "window_seconds": 30, "frame_count": 44, "reason_codes": [7] }
  }
]
```

---

## `GET /api/baseline`

Known APs (from the `known_aps` table) and the configured trusted networks.

```json
{
  "known_aps": [],
  "trusted_networks": [
    { "ssid": "HomeLab", "trusted": true, "bssids": ["AA:BB:CC:11:22:33"],
      "expected_security": "WPA2/WPA3", "expected_pmf": "required",
      "expected_channels": [6, 36] }
  ]
}
```

---

## `POST /api/mode`

Switch mode. Body:

```json
{ "mode": "foraging" }
```

Returns the new mode spec (`200`), or `400` for an unknown mode:

```json
{
  "mode": "foraging",
  "display_name": "Foraging Mode",
  "description": "Discovery and inventory. Builds the trusted baseline.",
  "bear_state": "foraging",
  "allowed_actions": ["acknowledge_alert", "start_mock_capture", "export_events", "enter_hibernate", "enter_foraging", "enter_honey", "enter_sentinel", "enter_apex"]
}
```

---

## `POST /api/action`

Run a **safe, local-only** action (Sprint 1). Body:

```json
{ "action": "start_mock_capture", "target": null, "confirm": true }
```

Response:

```json
{ "action": "start_mock_capture", "accepted": true, "result": "ok", "message": "mock capture running" }
```

**Permitted actions in v0.0:** `acknowledge_alert`, `start_mock_capture`, `export_events`, `clear_mock_events`, `enter_hibernate`, `enter_foraging`, `enter_honey`, `enter_sentinel`, `enter_apex`.

Anything else → `400`. No disruptive RF action exists. Future Apex actions are gated behind `lab_mode` + allowlist + confirm (see [modes.md](modes.md)).
