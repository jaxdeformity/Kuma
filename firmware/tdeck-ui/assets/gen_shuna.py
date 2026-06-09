#!/usr/bin/env python3
"""KUMA -> SHUNA character sprite-pack generator.

Slices the "SHUNA // STATES" sheet (designs/sprites/shuna/_source.png, a 5x2 grid
on a flat teal background) into the 7 frames the firmware renders, in the same
order as the bear packs:

    0 hibernating  1 foraging  2 sentinel  3 honey  4 apex  5 alert  6 investigating

Background removal is done CAREFULLY to avoid the two classic failures:
  - NO global color-key (which would hole-punch her body / FX where they sit near
    the bg teal). We FLOOD-FILL from the cell border, so only background-connected
    teal is removed; her outfit + the cyan state FX (Zzz, wifi, hearts, glow) are
    preserved.
  - A second TIGHT pass removes flat-teal pockets trapped inside the silhouette
    (exact bg color, small radius) without touching her darker outfit teal or the
    brighter FX cyan.
  - We trim with getbbox() AFTER keying, so the crop is exact and never clips her.

Emits src/shuna_sprites_data.h (SHUNA_SPRITES[7], reuses BearSprite; include AFTER
bear_sprites_data.h).

Run:  python assets/gen_shuna.py
"""
import io
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
SHEET = os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "designs", "sprites", "shuna", "_source.png"))
OUTDIR = os.path.dirname(SHEET)

BG = (1, 107, 122)        # flat teal sheet background
FLOOD_TOL = 44            # border flood-fill radius around BG -> transparent
# Pocket key removes flat-bg teal trapped in the silhouette AND the soft teal
# ground-shadow under her feet. Safe at this radius: her own teal/cyan accents are
# bright cyan (dist >100 from BG) and her outfit is dark (also far), so only the
# flat-teal background/shadow falls in range.
POCKET_TOL = 44
TARGET_H = 128

# 5 columns x 2 rows. Character ROI per row EXCLUDES the label text band.
COL_X = [(6, 295), (301, 587), (593, 875), (881, 1167), (1173, 1463)]
ROW_Y = [(100, 478), (558, 938)]   # (row1, row2) character bands, labels excluded
# 7 home/state frames + 3 battle poses, as (row, col) into the 5x2 grid.
FRAMES = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 0), (1, 1),
          (1, 2), (1, 3), (1, 4)]
NAMES = ["01_hibernating", "02_foraging", "03_sentinel", "04_honey",
         "05_apex", "06_alert", "07_investigating",
         "08_defending", "09_attacking", "10_victory"]


def dist(c):
    return math.sqrt((c[0] - BG[0]) ** 2 + (c[1] - BG[1]) ** 2 + (c[2] - BG[2]) ** 2)


def flood_key(cell, tol=FLOOD_TOL):
    """Make border-connected background transparent (4-connected flood fill)."""
    px = cell.load()
    w, h = cell.size
    seen = bytearray(w * h)
    stack = []
    for x in range(w):
        stack.append((x, 0)); stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y)); stack.append((w - 1, y))
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y * w + x]:
            continue
        seen[y * w + x] = 1
        r, g, b, a = px[x, y]
        if a == 0 or dist((r, g, b)) <= tol:
            px[x, y] = (r, g, b, 0)
            stack.append((x + 1, y)); stack.append((x - 1, y))
            stack.append((x, y + 1)); stack.append((x, y - 1))
    return cell


def key_pockets(cell, tol=POCKET_TOL):
    """Remove flat-bg teal trapped inside the silhouette (tight exact-bg match)."""
    px = cell.load()
    w, h = cell.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and dist((r, g, b)) <= tol:
                px[x, y] = (r, g, b, 0)
    return cell


def defringe(cell, passes=4):
    """Bleed opaque colors into adjacent transparent pixels (alpha stays 0) so
    LANCZOS downscaling can't smear keyed teal back in as a halo."""
    w, h = cell.size
    px = cell.load()
    for _ in range(passes):
        updates = []
        for y in range(h):
            for x in range(w):
                if px[x, y][3] != 0:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] > 0:
                        nr, ng, nb, _ = px[nx, ny]
                        updates.append((x, y, (nr, ng, nb, 0)))
                        break
        if not updates:
            break
        for x, y, c in updates:
            px[x, y] = c
    return cell


def extract():
    im = Image.open(SHEET).convert("RGBA")
    out = []
    for (row, col), name in zip(FRAMES, NAMES):
        x0, x1 = COL_X[col]
        y0, y1 = ROW_Y[row]
        cell = im.crop((x0, y0, x1, y1))
        cell = defringe(key_pockets(flood_key(cell)))
        bbox = cell.getbbox()                       # exact trim - never clips
        if bbox:
            cell = cell.crop(bbox)
        w, h = cell.size
        cell = cell.resize((max(1, round(w * TARGET_H / h)), TARGET_H), Image.LANCZOS)
        out.append((name, cell))
    return out


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_logo():
    """シュナ wordmark, off-white to match the クマ KUMA_LOGO (52x24). 24px tall."""
    from PIL import ImageDraw, ImageFont
    col = (235, 243, 237, 255)
    font = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 30)
    tmp = Image.new("RGBA", (160, 48), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((2, 2), "シュナ", font=font, fill=col)
    bb = tmp.getbbox()
    im = tmp.crop(bb)
    return im.resize((round(im.width * 24 / im.height), 24), Image.LANCZOS)


def main():
    frames = extract()
    # save per-frame PNGs for inspection
    for name, img in frames:
        img.save(os.path.join(OUTDIR, name + ".png"))
    lines = [
        "// KUMA Guard T-Deck - SHUNA character sprite pack (generated by",
        "// assets/gen_shuna.py from designs/sprites/shuna/_source.png; do not",
        "// hand-edit). 128px-tall RGBA PNGs, drawPng. Reuses BearSprite from",
        "// bear_sprites_data.h, so include this AFTER it.",
        "#pragma once",
        "#include <Arduino.h>",
        "",
    ]
    syms = []
    total = 0
    for i, (name, img) in enumerate(frames, 1):
        data = png_bytes(img)
        total += len(data)
        sym = f"SHUNA_{i:02d}"
        syms.append((sym, img.size))
        body = ",".join(str(b) for b in data)
        lines.append(f"static const uint8_t {sym}[] = {{{body}}};")
    lines.append("")
    # First 7 = home/state pack (same interface + order as BEAR_SPRITES).
    arr = ",\n".join(
        f"  {{{s}, sizeof {s}, {wh[0]}, {wh[1]}}}" for s, wh in syms[:7])
    lines.append("static const BearSprite SHUNA_SPRITES[7] = {")
    lines.append(arr)
    lines.append("};")
    lines.append("")
    # Frames 8/9/10 = battle poses (defend / attack / victory), used in place of
    # KB_DEFEND_S / KB_ATTACK_S / KB_VICTORY_S when the active character is Shuna.
    for pose, idx in (("SHUNA_DEFEND", 7), ("SHUNA_ATTACK", 8), ("SHUNA_VICTORY", 9)):
        s, wh = syms[idx]
        lines.append(
            f"static const BearSprite {pose} = {{{s}, sizeof {s}, {wh[0]}, {wh[1]}}};")
    lines.append("")
    # シュナ wordmark (drawn in place of KUMA_LOGO when the active character is Shuna)
    logo = render_logo()
    logo.save(os.path.join(OUTDIR, "_logo.png"))
    ld = png_bytes(logo)
    total += len(ld)
    lines.append(f"static const uint8_t SHUNA_LOGO[] = {{{','.join(str(b) for b in ld)}}};")
    lines.append(f"static const uint16_t SHUNA_LOGO_W = {logo.size[0]}, "
                 f"SHUNA_LOGO_H = {logo.size[1]};")
    lines.append("")
    out = os.path.join(SRC, "shuna_sprites_data.h")
    with open(out, "w", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {out}")
    for name, img in frames:
        print(f"  {name}: {img.size[0]}x{img.size[1]}")
    print(f"  total embedded: {total} bytes ({total/1024:.1f} KB)")


if __name__ == "__main__":
    main()
