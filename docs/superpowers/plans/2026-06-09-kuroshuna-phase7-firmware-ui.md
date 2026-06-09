# Kuroshuna Phase 7 — Firmware UI (skin + terminal arm) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On-device Kuroshuna: bake the クロシュナ sprite/wordmark, show the armed skin (sprite + クロシュナ wordmark + red/purple HUD) on the home screen when `kuroshuna_armed`, and arm/disarm it (and the broadcast tier) from the **terminal** — a deliberate power-user command with a confirm, the way apex is engaged. No new GUI screen.

**Architecture:** A bake script emits `kuroshuna_sprites_data.h` (`KUROSHUNA_APEX` 192px + `KUROSHUNA_LOGO` = クロシュナ wordmark). `KumaStatus` gains `kuroshunaArmed`/`broadcastArmed`, parsed from `/api/status`. `kuma_api_client` gets `armKuroshuna(bool)` / `armBroadcast(bool)` (POST the Phase-6 endpoints). `drawHome` adds a Kuroshuna branch (highest priority over shuna/kuma). The terminal gets a `kuroshuna` built-in with a line-based confirm (`arm` → warning → `confirm`; `broadcast` → stricter warning → `confirm`; `off`; `status`).

**Tech Stack:** C++ (Arduino/LovyanGFX) on ESP32-S3 T-Deck; Python+PIL for the bake. **Verification is compile-only here** (`pio run -e t-deck`); on-device behavior is validated by Jax over COM8.

**How to verify:** from `firmware/tdeck-ui/`: `pio run -e t-deck` must compile clean (the project builds at ~66% flash today).

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Kuroshuna mode skin"). Design overrides from Jax (2026-06-09): wordmark is **クロシュナ** (katakana, not 黒シュナ); arm is **terminal-only, like apex**. Depends on Phase 6 (the /api/kuroshuna endpoints) on this branch.

---

## File Structure

- Create: `firmware/tdeck-ui/assets/gen_kuroshuna.py` — bake `KUROSHUNA_APEX` (192px) + `KUROSHUNA_LOGO` (クロシュナ) → `src/kuroshuna_sprites_data.h`. Reuses the gen_shuna pipeline.
- Create: `firmware/tdeck-ui/src/kuroshuna_sprites_data.h` — generated (committed).
- Modify: `firmware/tdeck-ui/src/kuma_types.h` — `KumaStatus` += `kuroshunaArmed`, `broadcastArmed`.
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h` / `.cpp` — parse flags; add `armKuroshuna`/`armBroadcast`.
- Modify: `firmware/tdeck-ui/src/kuma_ui.cpp` — `drawHome` Kuroshuna branch (+ include the new header).
- Modify: `firmware/tdeck-ui/src/kuma_terminal.cpp` — `kuroshuna` command + line-confirm.

References to mirror (already in the codebase):
- `gen_shuna.py`: `flood_key` / `remove_white_pockets(POCKET_MIN)` / `defringe` / `TARGET_H=192` / `render_logo()` (MS Gothic). The kuroshuna sprite is a SINGLE pose (apex_hackback), so bake one frame + one wordmark.
- `kuma_ui.cpp` drawHome (lines ~199-246): the `shuna` branch shows how a skin swaps the wordmark + sprite pack; Kuroshuna uses ONE sprite for all states.
- `kuma_terminal.cpp` `exec()`: the built-in command pattern; add a static pending-confirm.

---

### Task 1: bake KUROSHUNA_APEX (192px) + クロシュナ wordmark

**Files:**
- Create: `firmware/tdeck-ui/assets/gen_kuroshuna.py`
- Create (generated): `firmware/tdeck-ui/src/kuroshuna_sprites_data.h`

- [ ] **Step 1: Write the bake script**

```python
# firmware/tdeck-ui/assets/gen_kuroshuna.py
"""KUMA -> KUROSHUNA (Dark Shuna apex) sprite + wordmark generator.

Bakes the single apex_hackback hi-res render into KUROSHUNA_APEX (192px tall,
matching the Shuna per-sprite draw scale) and a クロシュナ wordmark KUROSHUNA_LOGO.
Reuses the gen_shuna white-bg pipeline (flood-fill + pocket removal + defringe).

Run:  python assets/gen_kuroshuna.py
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

import gen_shuna as S  # reuse flood_key / remove_white_pockets / defringe / POCKET_MIN

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
ART = os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "designs", "sprites", "kuroshuna"))
HIRES = os.path.join(ART, "hires", "apex_hackback.png")
TARGET_H = 192


def process():
    im = Image.open(HIRES).convert("RGBA")
    im = S.defringe(S.remove_white_pockets(S.flood_key(im), min_size=S.POCKET_MIN))
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    return im.resize((max(1, round(w * TARGET_H / h)), TARGET_H), Image.LANCZOS)


def render_logo():
    """クロシュナ wordmark, off-white to match KUMA_LOGO; 24px tall."""
    col = (235, 243, 237, 255)
    font = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 30)
    tmp = Image.new("RGBA", (200, 48), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((2, 2), "クロシュナ", font=font, fill=col)
    bb = tmp.getbbox()
    im = tmp.crop(bb)
    return im.resize((round(im.width * 24 / im.height), 24), Image.LANCZOS)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main():
    sp = process()
    sp.save(os.path.join(ART, "apex_hackback.png"))
    logo = render_logo()
    spd, ld = png_bytes(sp), png_bytes(logo)
    lines = [
        "// KUMA Guard T-Deck - KUROSHUNA (Dark Shuna apex) sprite + クロシュナ",
        "// wordmark (generated by assets/gen_kuroshuna.py; do not hand-edit).",
        "// Include AFTER bear_sprites_data.h (reuses BearSprite).",
        "#pragma once",
        "#include <Arduino.h>",
        "",
        f"static const uint8_t KUROSHUNA_APEX_DATA[] = {{{','.join(str(b) for b in spd)}}};",
        f"static const BearSprite KUROSHUNA_APEX = {{KUROSHUNA_APEX_DATA, "
        f"sizeof KUROSHUNA_APEX_DATA, {sp.size[0]}, {sp.size[1]}}};",
        "",
        f"static const uint8_t KUROSHUNA_LOGO[] = {{{','.join(str(b) for b in ld)}}};",
        f"static const uint16_t KUROSHUNA_LOGO_W = {logo.size[0]}, "
        f"KUROSHUNA_LOGO_H = {logo.size[1]};",
        "",
    ]
    out = os.path.join(SRC, "kuroshuna_sprites_data.h")
    with open(out, "w", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {out}: sprite {sp.size}, logo {logo.size}, "
          f"{(len(spd)+len(ld))/1024:.1f} KB")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the bake + verify**

Run: from `firmware/tdeck-ui/`: `python assets/gen_kuroshuna.py`
Expected: prints `wrote .../kuroshuna_sprites_data.h: sprite (W, 192), logo (W, 24), NN KB`. Open the header and confirm `KUROSHUNA_APEX` (BearSprite) and `KUROSHUNA_LOGO` are present.

- [ ] **Step 3: Commit**

```bash
git add firmware/tdeck-ui/assets/gen_kuroshuna.py firmware/tdeck-ui/src/kuroshuna_sprites_data.h designs/sprites/kuroshuna/apex_hackback.png
git commit -m "feat(fw): bake KUROSHUNA_APEX 192px + クロシュナ wordmark"
```

---

### Task 2: status flags + api client arm helpers

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_types.h`
- Modify: `firmware/tdeck-ui/src/kuma_api_client.h` and `.cpp`

- [ ] **Step 1: Add the status fields** — in `kuma_types.h`, in `struct KumaStatus`, after `character`:

```cpp
  bool      kuroshunaArmed = false;  // Tier A offensive arm (gloves off)
  bool      broadcastArmed = false;  // Tier B broadcast arm
```

- [ ] **Step 2: Parse them** — in `kuma_api_client.cpp`, in the function that parses `/api/status` JSON into `KumaStatus` (where `character`, `creator`, etc. are read), add:

```cpp
  out.kuroshunaArmed = doc["kuroshuna_armed"] | false;
  out.broadcastArmed = doc["broadcast_armed"] | false;
```
(match the existing JSON-read idiom in that file — it uses the same library as the other fields.)

- [ ] **Step 3: Declare + implement the arm POSTs.** In `kuma_api_client.h`, near `setMode`:

```cpp
  bool armKuroshuna(bool armed);   // POST /api/kuroshuna/arm
  bool armBroadcast(bool armed);   // POST /api/kuroshuna/broadcast-arm
```

In `kuma_api_client.cpp`, mirror how `setMode`/`sendAction` POST JSON (same HTTP client + base URL). Body is `{"armed": true|false}`; return true on HTTP 200:

```cpp
bool kuma_api::armKuroshuna(bool armed) {
  String body = String("{\"armed\":") + (armed ? "true" : "false") + "}";
  return postJsonOk("/api/kuroshuna/arm", body);     // use the same POST helper setMode uses
}
bool kuma_api::armBroadcast(bool armed) {
  String body = String("{\"armed\":") + (armed ? "true" : "false") + "}";
  return postJsonOk("/api/kuroshuna/broadcast-arm", body);
}
```
(If there is no shared `postJsonOk` helper, replicate the exact POST code block `setMode` uses, swapping the path + body. A 409 from the backend — arming refused — returns false; that's correct.)

- [ ] **Step 4: Verify compile**

Run: from `firmware/tdeck-ui/`: `pio run -e t-deck`
Expected: compiles clean (SUCCESS).

- [ ] **Step 5: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_types.h firmware/tdeck-ui/src/kuma_api_client.h firmware/tdeck-ui/src/kuma_api_client.cpp
git commit -m "feat(fw): parse kuroshuna/broadcast armed + arm POST helpers"
```

---

### Task 3: drawHome Kuroshuna skin (sprite + クロシュナ + red/purple HUD)

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_ui.cpp`

- [ ] **Step 1: Include the header** — near the other sprite-data includes at the top of `kuma_ui.cpp`:

```cpp
#include "kuroshuna_sprites_data.h"
```

- [ ] **Step 2: Add the Kuroshuna branch in `drawHome`.** Kuroshuna takes priority over the shuna/kuma skin when `s.kuroshunaArmed`. At the wordmark block (currently `bool shuna = (s.character == "shuna"); ...`), add a `kuro` flag and prefer it:

```cpp
  bool kuro  = s.kuroshunaArmed;
  bool shuna = (s.character == "shuna");
  uint16_t logoW = kuro ? KUROSHUNA_LOGO_W : (shuna ? SHUNA_LOGO_W : KUMA_LOGO_W);
  if (kuro)        g->drawPng(KUROSHUNA_LOGO, sizeof KUROSHUNA_LOGO, 8, 3);
  else if (shuna)  g->drawPng(SHUNA_LOGO, sizeof SHUNA_LOGO, 8, 3);
  else             g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 8, 3);
```

In the online sprite-draw block, when `kuro`, draw the single `KUROSHUNA_APEX` for every state (it's one pose) using the SAME per-sprite scale path as Shuna (`SC = DISP_H / sp.h`):

```cpp
    const BearSprite& sp = kuro ? KUROSHUNA_APEX
                                : (shuna ? SHUNA_SPRITES[si]
                                         : (pack ? pack[si] : BEAR_SPRITES[si]));
    float SC = (float)DISP_H / sp.h;
    int dw = (int)(sp.w * SC), dh = (int)(sp.h * SC);
    if (!g->drawPng(sp.data, sp.len, 160 - dw / 2, CY - dh / 2 + bob, 0, 0, 0, 0, SC, SC))
      drawBear(g, bs, 160, CY + bob, 78);
```
(Adapt to the exact local variable names already in that block — keep the existing `pack`/`si` logic for the non-kuro path; only force `KUROSHUNA_APEX` when `kuro`.)

- [ ] **Step 3: Red/purple HUD when armed.** Where the top HUD rule / accent color is set (the `drawFastHLine(0, 26, 320, 0x2945)` and the stat-bar rules), use a red/purple accent when `kuro`. Add near the top of the armed draw:

```cpp
  const uint16_t KURO_ACCENT = 0x901F;   // purple-magenta (RGB565)
  uint16_t accent = kuro ? KURO_ACCENT : 0x2945;
```
and replace the two `0x2945` HUD hairline colors (`drawFastHLine(0, 26, ...)` and `drawFastHLine(0, 206, ...)`) with `accent`. Also tint the "ONLINE" dot/label area or the level text red/purple when `kuro` (use `0xF800`/`KURO_ACCENT`) so the armed state reads as "gloves off". Keep changes minimal and localized.

- [ ] **Step 4: Verify compile**

Run: from `firmware/tdeck-ui/`: `pio run -e t-deck`
Expected: compiles clean. Note the flash % (was ~66%; +~150-250KB for the sprite is fine).

- [ ] **Step 5: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_ui.cpp
git commit -m "feat(fw): drawHome Kuroshuna skin (クロシュナ wordmark + sprite + red/purple HUD)"
```

---

### Task 4: terminal `kuroshuna` command + line-confirm

**Files:**
- Modify: `firmware/tdeck-ui/src/kuma_terminal.cpp`

- [ ] **Step 1: Add a pending-confirm state + the command.** In the anonymous namespace (near `g_cwd`), add:

```cpp
int g_kuroPending = 0;   // 0 none, 1 arm-kuroshuna, 2 arm-broadcast
```

In `exec()`, FIRST handle a pending confirmation (so a bare `confirm`/`y` resolves it), then the `kuroshuna` command. Add before the `if (cmd == "help")` chain:

```cpp
  if (g_kuroPending && (cmd == "confirm" || cmd == "y" || cmd == "yes")) {
    bool ok = (g_kuroPending == 1) ? kuma_api::armKuroshuna(true)
                                   : kuma_api::armBroadcast(true);
    putLine(ok ? "* KUROSHUNA armed - gloves off"
               : "! arm refused (lab_mode/allow_broadcast off on the Pi?)");
    g_kuroPending = 0;
    return;
  }
  if (g_kuroPending) { g_kuroPending = 0; putLine("(kuroshuna confirm cancelled)"); }
```

Then add the command itself in the `else if` chain (after `mode`):

```cpp
  else if (cmd == "kuroshuna" || cmd == "kuro") {
    String a = arg; a.toLowerCase();
    if (a == "status" || a == "") {
      KumaStatus s;
      if (!kuma_api::fetchStatus(s)) { putLine("! backend offline"); return; }
      putLine(String("kuroshuna: ") + (s.kuroshunaArmed ? "ARMED" : "disarmed")
              + "  broadcast: " + (s.broadcastArmed ? "ARMED" : "off"));
    } else if (a == "arm" || a == "on") {
      putLine("! KUROSHUNA = gloves off (active offense vs approved targets).");
      putLine("! type 'kuroshuna confirm' to arm.");
      g_kuroPending = 1;
    } else if (a == "broadcast") {
      putLine("! BROADCAST tier = INDISCRIMINATE: transmits to EVERYTHING in range.");
      putLine("! only with physical RF isolation. type 'kuroshuna confirm' to arm.");
      g_kuroPending = 2;
    } else if (a == "off" || a == "disarm") {
      bool ok = kuma_api::armKuroshuna(false);   // disarm also clears broadcast on the Pi
      putLine(ok ? "* KUROSHUNA disarmed" : "! disarm failed");
    } else {
      putLine("! usage: kuroshuna [status|arm|broadcast|off]");
    }
  }
```

- [ ] **Step 2: Add to HELP** — append to the `HELP[]` array:

```cpp
  " kuroshuna [arm|broadcast|off]  gloves off (confirm)",
```

- [ ] **Step 3: Verify compile**

Run: from `firmware/tdeck-ui/`: `pio run -e t-deck`
Expected: compiles clean.

- [ ] **Step 4: Commit**

```bash
git add firmware/tdeck-ui/src/kuma_terminal.cpp
git commit -m "feat(fw): terminal 'kuroshuna' command (arm/broadcast/off) with confirm"
```

---

## Phase exit criteria

- `python assets/gen_kuroshuna.py` produces `kuroshuna_sprites_data.h` with `KUROSHUNA_APEX` + `KUROSHUNA_LOGO`.
- `pio run -e t-deck` compiles clean after every task (final flash % noted).
- `drawHome` shows the Kuroshuna skin (クロシュナ wordmark + apex sprite + red/purple HUD) when `kuroshunaArmed`, and the normal kuma/shuna skin otherwise.
- The terminal `kuroshuna arm`/`broadcast` commands require a `confirm` line and POST the Phase-6 endpoints; `off` disarms; `status` reports state.

## On-device validation (Jax, COM8)

1. Flash: `pio run -e t-deck -t upload --upload-port COM8`.
2. With the Pi backend running + `lab_mode` true: open the terminal (Home → Down), `kuroshuna arm` → `confirm`; confirm Home flips to the クロシュナ skin + red/purple HUD.
3. `kuroshuna broadcast` → confirm refused unless `allow_broadcast` is set on the Pi.
4. `kuroshuna off` → Home returns to normal skin.
5. Confirm a non-lab_mode Pi refuses the arm (terminal shows the refusal line).

## Next phase

- **Phase 2b — Firmware ESP32 RF:** Bruce-style targeted deauth on the T-Deck's own radio, each TX preceded by a `POST /api/kuroshuna/authorize` allow from the Pi gate (the helper to add next).
