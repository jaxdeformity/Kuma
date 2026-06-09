#!/usr/bin/env python3
"""KUMA -> SHUNA character sprite-pack generator (hi-res individual sources).

Processes Jax's 10 detailed SHUNA renders (designs/sprites/shuna/hires/*.png,
1254x1254, each on a near-white background) into the firmware sprite pack, in
the same order as the bear packs:

    0 hibernating  1 foraging  2 sentinel  3 honey  4 apex  5 alert
    6 investigating   (+ battle poses: defending / attacking / victory)

Background removal is careful (the lessons from the offline/teal fix apply):
  - FLOOD-FILL from the border removes only the white that is connected to the
    edge, so her interior whites (hair highlights, eye glints, gear) are kept.
  - We deliberately do NOT global-key white (her own highlights are white too).
  - defringe() alpha-bleeds opaque colour into the keyed pixels so LANCZOS
    downscaling can't smear a white halo onto the dark device screen.
  - getbbox() trims AFTER keying -> exact, never clips her.

Emits src/shuna_sprites_data.h (SHUNA_SPRITES[7] + SHUNA_DEFEND/ATTACK/VICTORY
+ シュナ wordmark). Reuses BearSprite; include AFTER bear_sprites_data.h.

Run:  python assets/gen_shuna.py
"""
import io
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
ART = os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "designs", "sprites", "shuna"))
HIRES = os.path.join(ART, "hires")

WHITE = (255, 255, 255)
FLOOD_TOL = 60            # border flood-fill radius around white -> transparent
TARGET_H = 128

# (source filename stem, output frame name) in firmware order
SOURCES = [
    ("hibernate",   "01_hibernating"),
    ("forage",      "02_foraging"),
    ("sentinel",    "03_sentinel"),
    ("honey",       "04_honey"),
    ("apex",        "05_apex"),
    ("alert",       "06_alert"),
    ("investigate", "07_investigating"),
    ("Defend",      "08_defending"),
    ("attack",      "09_attacking"),
    ("victory",     "10_victory"),
]


def wdist(c):
    return math.sqrt((c[0] - 255) ** 2 + (c[1] - 255) ** 2 + (c[2] - 255) ** 2)


def flood_key(cell, tol=FLOOD_TOL):
    """Make border-connected near-white background transparent (4-connected)."""
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
        if a == 0 or wdist((r, g, b)) <= tol:
            px[x, y] = (r, g, b, 0)
            stack.append((x + 1, y)); stack.append((x - 1, y))
            stack.append((x, y + 1)); stack.append((x, y - 1))
    return cell


def remove_white_pockets(cell, min_size=25, tol=58):
    """Clear near-white components LARGER than min_size that the border flood
    couldn't reach - trapped pockets like the apex/defend shield interiors and
    the gap under her arm. Her own highlights are tiny (<=~19px) so they survive;
    only big enclosed white blobs are removed. (Measured component sizes: clean
    frames <=16, foraging arm-gap 64, defend shield 35-50, apex shield 562-913.)"""
    px = cell.load()
    w, h = cell.size
    seen = bytearray(w * h)

    def is_white(x, y):
        p = px[x, y]
        return p[3] > 150 and wdist((p[0], p[1], p[2])) <= tol

    for sy in range(h):
        for sx in range(w):
            if seen[sy * w + sx] or not is_white(sx, sy):
                continue
            stack = [(sx, sy)]
            comp = []
            while stack:
                x, y = stack.pop()
                if (x < 0 or y < 0 or x >= w or y >= h
                        or seen[y * w + x] or not is_white(x, y)):
                    continue
                seen[y * w + x] = 1
                comp.append((x, y))
                stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            if len(comp) > min_size:
                for x, y in comp:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 0)
    return cell


def defringe(cell, passes=5):
    """Bleed opaque colours into adjacent transparent pixels (alpha stays 0) so
    downscaling can't smear the keyed white back in as a halo."""
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


def process(stem):
    im = Image.open(os.path.join(HIRES, stem + ".png")).convert("RGBA")
    im = defringe(remove_white_pockets(flood_key(im)))
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    return im.resize((max(1, round(w * TARGET_H / h)), TARGET_H), Image.LANCZOS)


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
    frames = []
    for stem, name in SOURCES:
        img = process(stem)
        img.save(os.path.join(ART, name + ".png"))
        frames.append((name, img))

    lines = [
        "// KUMA Guard T-Deck - SHUNA character sprite pack (generated by",
        "// assets/gen_shuna.py from designs/sprites/shuna/hires/*.png; do not",
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
        lines.append(f"static const uint8_t {sym}[] = {{{','.join(str(b) for b in data)}}};")
    lines.append("")
    arr = ",\n".join(
        f"  {{{s}, sizeof {s}, {wh[0]}, {wh[1]}}}" for s, wh in syms[:7])
    lines.append("static const BearSprite SHUNA_SPRITES[7] = {")
    lines.append(arr)
    lines.append("};")
    lines.append("")
    for pose, idx in (("SHUNA_DEFEND", 7), ("SHUNA_ATTACK", 8), ("SHUNA_VICTORY", 9)):
        s, wh = syms[idx]
        lines.append(
            f"static const BearSprite {pose} = {{{s}, sizeof {s}, {wh[0]}, {wh[1]}}};")
    lines.append("")
    logo = render_logo()
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
