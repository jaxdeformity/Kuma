#!/usr/bin/env python3
"""KUMA cyber-space background generator.

Renders a deep-space cyber scene (space gradient + nebula clouds + dense
starfield + a distant planet + a synthwave perspective grid horizon) at a
chunky 160x120 then nearest-upscales to 320x240 for a pixel-art feel. Bakes
three per-screen brightness/tint variants and emits both preview PNGs (assets/)
and an embeddable C header (src/kuma_bg_data.h).

Run:  python assets/gen_bg.py
"""
import io
import math
import os
import random

from PIL import Image, ImageDraw

W0, H0 = 160, 120          # internal (chunky) resolution
SCALE = 2                  # -> 320x240 on device
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def add(px, c, amt):
    return (min(255, int(px[0] + c[0] * amt)),
            min(255, int(px[1] + c[1] * amt)),
            min(255, int(px[2] + c[2] * amt)))


def render_base():
    """The full-brightness cyber-space scene at W0xH0."""
    img = Image.new("RGB", (W0, H0))
    px = img.load()

    SPACE_TOP = (8, 6, 24)        # deep space indigo
    SPACE_MID = (16, 10, 38)      # faint purple void
    HORIZON_GLOW = (40, 12, 60)   # magenta glow where the grid meets space

    horizon = int(H0 * 0.72)      # where the cyber grid takes over (~y=86)

    # --- space gradient -------------------------------------------------
    for y in range(H0):
        if y < horizon:
            t = y / horizon
            base = lerp(SPACE_TOP, SPACE_MID, t)
        else:
            t = (y - horizon) / max(1, (H0 - horizon))
            base = lerp(SPACE_MID, HORIZON_GLOW, t)
        for x in range(W0):
            px[x, y] = base

    # --- nebula clouds (soft additive blobs, deterministic) -------------
    # (cx, cy, radius, color, intensity)
    nebulae = [
        (44, 30, 34, (120, 30, 150), 0.55),   # magenta cloud, upper-left
        (110, 48, 40, (20, 90, 150), 0.45),    # cyan-blue cloud, right
        (80, 18, 26, (90, 40, 130), 0.40),     # violet wisp up top
        (28, 64, 30, (140, 40, 90), 0.30),     # pink low-left, behind grid edge
    ]
    for cx, cy, rad, col, inten in nebulae:
        r2 = 2.0 * rad * rad
        for y in range(horizon):
            dy = y - cy
            for x in range(W0):
                dx = x - cx
                glow = math.exp(-(dx * dx + dy * dy) / r2)
                if glow > 0.02:
                    px[x, y] = add(px[x, y], col, glow * inten)

    # --- distant planet, upper-right ------------------------------------
    draw = ImageDraw.Draw(img)
    pcx, pcy, pr = 124, 28, 18
    PLANET = (46, 36, 92)         # dusty violet body
    PLANET_LIT = (150, 120, 230)  # sunlit rim (upper-left light)
    for y in range(pcy - pr, pcy + pr + 1):
        for x in range(pcx - pr, pcx + pr + 1):
            if not (0 <= x < W0 and 0 <= y < horizon):
                continue
            dx, dy = x - pcx, y - pcy
            if dx * dx + dy * dy <= pr * pr:
                # light from upper-left -> shade toward lower-right
                lit = max(0.0, (-dx - dy) / (pr * 1.6))
                px[x, y] = lerp(PLANET, PLANET_LIT, min(1.0, 0.15 + lit))
    # thin ring
    draw.ellipse([pcx - pr - 6, pcy - 4, pcx + pr + 6, pcy + 4],
                 outline=(120, 90, 180))

    # --- starfield (deterministic, denser than the forest scene) --------
    rng = random.Random(0xB347)
    for _ in range(230):
        sx = rng.randint(0, W0 - 1)
        sy = rng.randint(0, horizon - 2)
        # skip stars that land on the planet disc
        if (sx - pcx) ** 2 + (sy - pcy) ** 2 <= (pr + 1) ** 2:
            continue
        b = rng.random()
        if b < 0.72:                                  # dim star
            px[sx, sy] = add(px[sx, sy], (180, 195, 235), 0.4 + b)
        else:                                         # bright star + tiny glow
            tint = (235, 240, 255) if b < 0.92 else (255, 200, 235)  # a few pink
            px[sx, sy] = tint
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = sx + dx, sy + dy
                if 0 <= nx < W0 and 0 <= ny < horizon:
                    px[nx, ny] = add(px[nx, ny], (160, 175, 220), 0.6)

    # --- synthwave perspective grid (the "cyber" floor) -----------------
    GRID = (0, 230, 255)          # cyan lines
    GRID_FAR = (180, 40, 200)     # magenta near the horizon
    vpx = W0 / 2                  # vanishing point x
    # bright horizon line
    draw.line([(0, horizon), (W0, horizon)], fill=(120, 40, 160))

    # vertical lines converge to the vanishing point at the horizon
    for gx in range(-9, 10):
        bx = vpx + gx * 22        # spread along the bottom edge
        draw.line([(bx, H0), (vpx, horizon)], fill=GRID)
    # horizontal lines get closer together toward the horizon (perspective)
    n_h = 9
    for k in range(1, n_h + 1):
        f = (k / n_h) ** 2.2
        y = int(horizon + (H0 - horizon) * f)
        col = lerp(GRID_FAR, GRID, f)  # magenta far -> cyan near
        draw.line([(0, y), (W0, y)], fill=col)

    return img


def tune(base, mul=1.0, tint=(255, 255, 255), tint_amt=0.0,
         bottom_glow=None):
    """Brightness/tint a copy; optional warm/cool glow near the horizon."""
    img = base.copy()
    px = img.load()
    for y in range(H0):
        for x in range(W0):
            r, g, b = px[x, y]
            r = int(r * mul * (1 - tint_amt) + tint[0] * tint_amt * mul)
            g = int(g * mul * (1 - tint_amt) + tint[1] * tint_amt * mul)
            b = int(b * mul * (1 - tint_amt) + tint[2] * tint_amt * mul)
            if bottom_glow:
                gc, gy0 = bottom_glow
                if y > gy0:
                    f = (y - gy0) / (H0 - gy0) * 0.5
                    r = min(255, int(r + gc[0] * f))
                    g = min(255, int(g + gc[1] * f))
                    b = min(255, int(b + gc[2] * f))
            px[x, y] = (min(255, r), min(255, g), min(255, b))
    return img


def upscale(img):
    return img.resize((W0 * SCALE, H0 * SCALE), Image.NEAREST)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def emit_header(variants):
    """variants: list of (name, png_bytes)."""
    lines = [
        "// KUMA Guard T-Deck - night-watch backgrounds (generated by",
        "// assets/gen_bg.py; do not edit by hand). 320x240 RGB PNGs, drawPng.",
        "#pragma once",
        "#include <Arduino.h>",
        "",
        "static const uint16_t KUMA_BG_W = 320, KUMA_BG_H = 240;",
        "",
    ]
    for name, data in variants:
        body = ",".join(str(b) for b in data)
        lines.append(f"static const uint8_t {name}[] = {{{body}}};")
        lines.append(f"static const size_t {name}_LEN = sizeof {name};")
        lines.append("")
    out = os.path.join(SRC, "kuma_bg_data.h")
    with open(out, "w", newline="\n") as f:
        f.write("\n".join(lines))
    return out


def main():
    base = render_base()

    dash = upscale(tune(base, mul=1.0))
    # battle: darker + faint red horizon glow for tension
    battle = upscale(tune(base, mul=0.82, bottom_glow=((60, 8, 8), int(H0 * 0.45))))
    # terminal: heavily dimmed + slight cool tint so green text dominates
    term = upscale(tune(base, mul=0.34, tint=(20, 40, 60), tint_amt=0.12))

    os.makedirs(HERE, exist_ok=True)
    dash.save(os.path.join(HERE, "bg_dashboard.png"))
    battle.save(os.path.join(HERE, "bg_battle.png"))
    term.save(os.path.join(HERE, "bg_terminal.png"))

    variants = [
        ("KUMA_BG_DASH", png_bytes(dash)),
        ("KUMA_BG_BATTLE", png_bytes(battle)),
        ("KUMA_BG_TERM", png_bytes(term)),
    ]
    hdr = emit_header(variants)
    total = sum(len(d) for _, d in variants)
    print(f"wrote {hdr}")
    for name, d in variants:
        print(f"  {name}: {len(d)} bytes")
    print(f"  total embedded: {total} bytes ({total/1024:.1f} KB)")


if __name__ == "__main__":
    main()
