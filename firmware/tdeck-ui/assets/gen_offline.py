#!/usr/bin/env python3
"""KUMA offline-animation sprite generator.

Slices the 6-frame "KUMA // OFFLINE" walk/search animation (idle -> check
signal -> no link -> retry -> frustrated -> back to idle) out of Jax's source
sheet, keys out the flat teal background to transparency, trims, normalizes each
frame to 128px tall (matching the base bear sprites), and emits both the per
frame PNGs (designs/sprites/offline/) and an embeddable C header
(src/offline_sprites_data.h, drawn via drawPng like BEAR_SPRITES).

The frames play on the T-Deck home screen when the backend is unreachable, in
place of the old algorithmic grey bear head.

Run:  python assets/gen_offline.py
"""
import io
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))     # repo root
SRC_SHEET = os.path.join(ROOT, "designs", "sprites", "offline", "_source.png")
OUTDIR = os.path.join(ROOT, "designs", "sprites", "offline")
HDR = os.path.normpath(os.path.join(HERE, "..", "src", "offline_sprites_data.h"))

BG = (2, 108, 123)        # flat teal sheet background (very uniform: corners all ~this)
# The bg is FLAT, so we lift it with a low-tolerance FLOOD FILL from the cell
# borders rather than a global color-key. Flood fill only removes teal that is
# connected to the border, which (a) never punches holes in Kuma's body (his
# interior teal-ish shadows aren't border-connected) and (b) preserves the
# cyan wifi/"!"/glitch UI icons (their cores measure >18 from BG). The old
# global KEY_DIST=40 did the opposite: it ate the dim icons and speckled the
# body wherever a pixel happened to fall near teal. Holes AND lost icons: gone.
FLOOD_TOL = 18            # flood-fill radius around BG -> transparent
# Per-frame label text sits at y~984; feet end ~922; icons start ~658. This ROI
# spans icon-top..feet and excludes the labels.
ROI_Y0, ROI_Y1 = 648, 928
SEP_ROW = 640            # a pure-gap row used to auto-detect the cell separators
SEP_INSET = 4            # trim just inside each separator line (not the paws)
FRAMES = 6
TARGET_H = 128


def dist(c):
    return math.sqrt((c[0] - BG[0]) ** 2 + (c[1] - BG[1]) ** 2 + (c[2] - BG[2]) ** 2)


def cell_bounds(im):
    """Auto-detect the 6 frame x-ranges from the vertical separator lines."""
    W, _ = im.size
    px = im.load()
    cols = [x for x in range(W) if dist(px[x, SEP_ROW][:3]) > 30]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 3:
            groups[-1].append(x)
        else:
            groups.append([x])
    seps = [(g[0], g[-1]) for g in groups]
    if len(seps) != FRAMES + 1:
        # Fallback: equal sixths if the sheet layout ever changes.
        cw = W / FRAMES
        return [(int(i * cw) + SEP_INSET, int((i + 1) * cw) - SEP_INSET) for i in range(FRAMES)]
    return [(seps[i][1] + SEP_INSET, seps[i + 1][0] - SEP_INSET) for i in range(FRAMES)]


def flood_key(cell, tol=FLOOD_TOL):
    """Make border-connected background transparent via flood fill (4-connected)."""
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


def defringe(cell, passes=4):
    """Alpha-bleed opaque colors into adjacent transparent pixels so LANCZOS
    downscaling can't smear the keyed teal back in as a halo (alpha stays 0)."""
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
    im = Image.open(SRC_SHEET).convert("RGBA")
    frames = []
    for x0, x1 in cell_bounds(im):
        cell = defringe(flood_key(im.crop((x0, ROI_Y0, x1, ROI_Y1))))
        bbox = cell.getbbox()
        if bbox:
            cell = cell.crop(bbox)
        w, h = cell.size
        cell = cell.resize((max(1, round(w * TARGET_H / h)), TARGET_H), Image.LANCZOS)
        frames.append(cell)
    return frames


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def emit_header(frames):
    lines = [
        "// KUMA Guard T-Deck - offline 'searching for signal' animation",
        "// (generated by assets/gen_offline.py from designs/sprites/offline/_source.png;",
        "// do not hand-edit). 128px-tall RGBA PNGs, drawn via drawPng. Reuses the",
        "// BearSprite struct from bear_sprites_data.h, so include this AFTER it.",
        "#pragma once",
        "#include <Arduino.h>",
        "",
    ]
    for i, f in enumerate(frames, 1):
        data = png_bytes(f)
        body = ",".join(str(b) for b in data)
        lines.append(f"static const uint8_t OFF_{i:02d}[] = {{{body}}};")
    lines.append("")
    arr = ",\n".join(
        f"  {{OFF_{i:02d}, sizeof OFF_{i:02d}, {f.size[0]}, {f.size[1]}}}"
        for i, f in enumerate(frames, 1))
    lines.append(f"static const BearSprite OFFLINE_SPRITES[{len(frames)}] = {{")
    lines.append(arr)
    lines.append("};")
    lines.append(f"static const int OFFLINE_SPRITE_COUNT = {len(frames)};")
    lines.append("")
    with open(HDR, "w", newline="\n") as fh:
        fh.write("\n".join(lines))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    frames = extract()
    for i, f in enumerate(frames, 1):
        f.save(os.path.join(OUTDIR, f"{i:02d}.png"))
    emit_header(frames)
    total = sum(len(png_bytes(f)) for f in frames)
    print(f"wrote {HDR}")
    for i, f in enumerate(frames, 1):
        print(f"  OFF_{i:02d}: {f.size[0]}x{f.size[1]}")
    print(f"  total embedded: {total} bytes ({total / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
