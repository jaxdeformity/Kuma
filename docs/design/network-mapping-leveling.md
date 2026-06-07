# KUMA Network Mapping + Leveling (EXP) — Design Spec

Status: design, building. KUMA passively maps the wireless environment (WiGLE-style)
and turns discovery/connection into an EXP/level system that drives the dashboard +
battle. Art (enemy rank sheet, KUMA evolution sheet) provided by Jax; this builds the
systems with hooks ready for that art.

## 1. Goals

- **Passive network mapping:** while KUMA listens, record every AP it observes (BSSID,
  SSID, security, channel, RSSI, first/last seen, times seen) for future WiGLE export.
- **Connection log:** record every network KUMA's host has connected to.
- **EXP/leveling (gamification):**
  - Discover a *new* network (first sighting of a BSSID) = **1/30 of a level** (1 XP).
  - Connect to a *new* network = **+1 level** (30 XP).
  - Win a battle = XP too (default 10 XP, ~1/3 level; configurable).
  - **Level = 1 + floor(total_xp / 30), capped at 99.**
- Enemy "level" is unknown → shown as **`??`** now; later a small **skull/rank sprite**
  (Jax's enemy rank sheet) indicates threat rank.
- **Evolution (future):** at milestone levels, unlock an alternate KUMA sprite set
  (Jax's evolution sheet). Built as a level→sprite-variant hook, base until art lands.

## 2. Data model (SQLite, existing kuma.db)

New tables (additive; existing `known_aps` stays the *trusted baseline*, separate from
the full observed map):

```sql
CREATE TABLE networks (        -- every AP ever observed (the WiGLE map)
  bssid TEXT PRIMARY KEY, ssid TEXT, security TEXT, channel INTEGER,
  best_rssi INTEGER, first_seen TEXT, last_seen TEXT, times_seen INTEGER DEFAULT 1,
  lat REAL, lon REAL );        -- lat/lon null (no GPS yet); reserved for WiGLE
CREATE TABLE connections (     -- networks KUMA's host connected to
  id INTEGER PK, ssid TEXT, bssid TEXT, first_connected TEXT, last_connected TEXT,
  times INTEGER DEFAULT 1, UNIQUE(ssid,bssid) );
```
XP is stored in the existing `settings` table (`kuma_xp` key) via new
`get_setting/set_setting` helpers. No new progress table needed.

## 3. Modules

- `kuma_core/progress.py` — pure leveling logic + DB-backed XP:
  `XP_PER_LEVEL=30`, `MAX_LEVEL=99`, rewards `{discover:1, connect:30, battle_win:10}`.
  `level_for(xp)`, `add_xp(n, reason)->dict`, `get_progress()->{level,xp,xp_into_level,
  xp_to_next,max_level}`. Capped so XP never exceeds `99*30`.
- `kuma_core/database.py` — `record_network(...) -> bool is_new`,
  `record_connection(ssid,bssid) -> bool is_new`, `get_networks(limit)`,
  `count_networks()`, `wigle_csv()`, `get_setting/set_setting`.
- `kuma_core/netmap.py` — host connection poller: best-effort read of the current
  wlan0 SSID (nmcli/iwgetid), records connection + awards connect XP on a new one.
  No-op off-Pi. Runs as a periodic task in `app.py` lifespan.
- Detectors (`live_capture.py`) call `record_network()` on each observed beacon; a
  `True` (new) return awards discover XP. (Wired in a follow-up Pi-deploy step.)

## 4. API (additions)

- `GET /api/status` adds: `level`, `xp`, `network_count`.
- `GET /api/progress` → full progress object.
- `GET /api/networks?limit=` → observed network list.
- `GET /api/networks/export` → **WiGLE CSV** (`WigleWifi-1.4` pre-header + column
  header; MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,Lat,Lon,Alt,Accuracy,Type=WIFI).
- `POST /api/progress/battle-win` → awards battle XP (the dashboard battle calls this
  on victory). Safe/local.

## 5. WiGLE CSV format

```
WigleWifi-1.4,appRelease=KUMA,model=KUMA,release=0.0.1,device=kuma,display=,board=,brand=kuma
MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,CurrentLatitude,CurrentLongitude,AltitudeMeters,AccuracyMeters,Type
2C:4D:...,MyNet,[WPA2-PSK-CCMP],2026-06-07 10:00:00,6,-52,0.0,0.0,0,0,WIFI
```
No GPS on KUMA yet → lat/lon/alt = 0 (a real WiGLE submission needs GPS; we store the
rest now and reserve the columns). AuthMode derived from observed security.

## 6. Frontend

- **Dashboard:** show KUMA `Lv N` and a network-count stat (replace one of the bar
  cells or add a line). Level comes from `/api/status`.
- **Battle:** KUMA `Lv` from `/api/status` (live) / localStorage (standalone demo);
  enemy = `??` now, skull/rank sprite when art lands; battle win → `POST
  /api/progress/battle-win`. Return to dashboard on resolve (the port step).
- **RECON view (later):** browse the network map; an "export WiGLE" action.

## 7. Evolution / rank art hooks

- `EVOLUTIONS = [(level_threshold, sprite_dir)]` — `spriteSetFor(level)` picks the
  KUMA sprite variant; defaults to the current set until Jax provides the evolution
  sheet. Sliced like states/ into `sprites/states-evo1/…`.
- Enemy rank: `rankSprite(severity|confidence)` → a frame from Jax's rank sheet
  (`sprites/ranks/…`); falls back to the `??` text until provided.

## 8. Tests

`test_progress.py` (level math, cap at 99, reward sums), `test_networks.py`
(record_network new vs duplicate, record_connection dedupe, WiGLE CSV header + a row),
`test_api.py` additions (status carries level/network_count; /api/networks/export is
CSV with the WiGLE pre-header).

## 9. Build order

1. progress.py + DB helpers (settings/networks/connections/wigle) + tests.
2. API: status fields, /api/progress, /api/networks, /api/networks/export,
   /api/progress/battle-win + schema updates + tests.
3. Dashboard: show level + network count.
4. Deploy backend to Pi.
5. Wire detector passive discovery (`record_network` in live_capture) + the netmap
   connection poller; deploy + restart capture. (Touches the live capture loop — done
   carefully as its own step.)
6. Art hooks when Jax delivers the rank + evolution sheets.
