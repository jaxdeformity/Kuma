#!/usr/bin/env python3
"""KUMA sprite generator. Authors symmetric 32x32 pixel grids as half-rows,
mirrors them, renders large PNGs for review, and emits JS-embeddable grids.

Run: python build_sprites.py
Outputs preview PNGs in this dir and prints the full grids.
"""
from PIL import Image
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- palette -------------------------------------------------------------
# shared bear palette (Ursaring-class brown bear)
BEAR = {
    '.': None,
    'o': '#241405',  # outline / deep shadow
    'B': '#8a5a30',  # fur base
    'b': '#5e3c1f',  # fur shadow
    'H': '#ab7a46',  # fur highlight
    'T': '#e8cd9a',  # cream (muzzle, chest ring)
    't': '#c7a874',  # cream shadow
    'E': '#0d0805',  # eye / nose black
    'w': '#fdf7e6',  # eye shine
    'f': '#fdf7e6',  # fang
    'c': '#f2ead2',  # claw
    'r': '#7a1f12',  # mouth interior / scar red
}

def mirror(half):
    """half: list of 16-char strings -> 32-char symmetric rows."""
    return [h + h[::-1] for h in half]

def render(rows, palette, path, px=16):
    h = len(rows); w = len(rows[0])
    img = Image.new('RGBA', (w * px, h * px), (0, 0, 0, 0))
    pix = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            col = palette.get(ch)
            if not col:
                continue
            r = int(col[1:3], 16); g = int(col[3:5], 16); b = int(col[5:7], 16)
            for dy in range(px):
                for dx in range(px):
                    pix[x * px + dx, y * px + dy] = (r, g, b, 255)
    img.save(path)
    return path

def check(half, name):
    bad = [i for i, r in enumerate(half) if len(r) != 16]
    if bad:
        print(f"!! {name}: rows with wrong length (need 16): {[(i,len(half[i])) for i in bad]}")
        sys.exit(1)
    if len(half) != 32:
        print(f"!! {name}: need 32 rows, got {len(half)}")
        sys.exit(1)

# ---- KUMA bear (fierce, standing, Ursaring build) ------------------------
# left half, columns 0..15 (15 = center). will be mirrored.
KUMA_HALF = [
    "................",  # 0
    ".......oo.......",  # 1  ear tip
    "......oHHo......",  # 2  ear
    "......oBBo......",  # 3  ear
    ".....oBBBBBBBBBB",  # 4  head top
    "....oBBBBBBBBBBB",  # 5  head
    "....oBBBBBBBBBBB",  # 6  head
    "...oBBBBooobBBBB",  # 7  angry brow (slant)
    "...oBBBBBwEEBBBB",  # 8  eye glint + pupil
    "...oBBBBBEEEBBBB",  # 9  eye
    "...oBBBBBBBBBoTT",  # 10 cheek -> muzzle top
    "..oBBBBBBBBoTTTT",  # 11 muzzle
    "..oBBBBBBBoTTTEE",  # 12 nose (center)
    "..oBBBBBBoTTrrrr",  # 13 snarl mouth (center)
    "..oBBBBBBoTfTTfT",  # 14 fangs
    "...oBBBBBBoTTTTo",  # 15 jaw
    "...oBBBBBBBooooo",  # 16 chin / neck
    "....oBBBBBBBBBBB",  # 17 neck -> shoulder
    "...oBBBBBBBBBBBB",  # 18 shoulder
    "..oBBBBBBBBBBBBB",  # 19 shoulders broad
    ".oBBBBoTTTTTTTTT",  # 20 chest ring top
    "oBBBBoTTTTTTTTTT",  # 21 chest ring
    "oBBBoTTTTTTTTTTT",  # 22 chest ring
    "oBBBBoTTTTTTTTTT",  # 23 chest ring
    "oBBBBBoTTTTTTTTT",  # 24 chest ring bottom
    "boBBBBBBoTTTTBBB",  # 25 arm + belly
    "cboBBBBBBBBBBBBB",  # 26 claw + arm
    "ccboBBBBBBBBBBBB",  # 27 claws
    "cccboBBBBBBBBBBB",  # 28 big claw paw (corner)
    "ccccboBBBBBBBBBB",  # 29 claws
    ".cccboBBBBBBBBBB",  # 30 taper
    "..ccboBBBBBBBBBB",  # 31 claw tip
]

# ---- enemy palettes ------------------------------------------------------
PINE = {
    '.': None, 'o': '#26200a',
    'Y': '#e0a82e', 'y': '#b07d1c', 'h': '#f6d36a',   # body yellow / shadow / highlight
    'G': '#3f8a2e', 'g': '#1f4a14',                    # leaf green / dark
    'R': '#ff3b30', 'm': '#4a140c', 'w': '#fff6df',    # red eye / mouth / tooth
    'A': '#9aa0a6', 't': '#ff3b30',                    # antenna / tip
}
ROGUE = {
    '.': None, 'o': '#0a0812',
    'B': '#3c3660', 'b': '#241d3e', 'H': '#5a5288',    # chassis indigo / shadow / highlight
    'A': '#9aa0b4', 'a': '#5a5d6c',                    # antenna
    'R': '#ff2a2a', 'r': '#8a1414', 'w': '#ffe0e0', 'E': '#1a0606',  # eye glow / dark / shine / pupil
    'c': '#25d0ff', 'm': '#0d0a1a',                    # signal arc / mouth
}
DEAUTH = {
    '.': None, 'o': '#240606',
    'B': '#c0392b', 'b': '#7a1710', 'H': '#e8604a',    # body crimson / shadow / highlight
    'Y': '#ffcc1f', 'y': '#c99500',                    # lightning / shadow
    'E': '#0d0303', 'w': '#ffffff', 'm': '#3a0606',    # eye / fang / maw
}

# ---- PINEAPPLE (WiFi Pineapple monster) ----------------------------------
PINE_HALF = [
    "..........g.....",  # 0  frond tips
    "....g.....G.t...",  # 1  side frond + antenna tip
    "...gGg...gGGA...",  # 2  fronds + antenna
    "..gGGGg.gGGGA...",  # 3
    "..gGGGGgGGGGGg..",  # 4
    "...gGGGGGGGGGGg.",  # 5
    "....ggGGGGGGGGGg",  # 6
    ".....oggGGGGGGGG",  # 7  leaf base
    "....oyYYYYYYYYYY",  # 8  body top
    "...oYYhYYYYYYhYY",  # 9  crosshatch hi
    "..oYYYYYYhYYYYYY",  # 10
    "..oYYhYYYYYYYYhY",  # 11
    ".oYYYYYRRYYYYYYY",  # 12 eye (red)
    ".oYYhYYRRYYYYYhY",  # 13 eye
    "oYYYYYYYYYYYYYYY",  # 14
    "oYYhYYYYYYYhYYYY",  # 15
    "oYYYYYmmmmmmmmmm",  # 16 grin
    "oYYhYYmwmwmwmwmw",  # 17 teeth
    "oYYYYYmmmmmmmmmm",  # 18
    "oYYYYhYYYYYYhYYY",  # 19
    "oYYhYYYYYhYYYYYY",  # 20
    ".oYYYYhYYYYYYhYY",  # 21
    ".oYYhYYYYhYYYYYY",  # 22
    "..oYYYYhYYYYYhYY",  # 23
    "..oYYhYYYYhYYYYY",  # 24
    "...oYYYYhYYYYhYY",  # 25
    "....oYYhYYYYYYYY",  # 26
    ".....oYYYYhYYYYY",  # 27
    "......ooYYYYYYYY",  # 28
    "........ooYYYYYY",  # 29
    "..........oooooo",  # 30
    "................",  # 31
]

# ---- ROGUE AP / EVIL TWIN (router-demon) ---------------------------------
ROGUE_HALF = [
    ".....A..........",  # 0  antenna tip
    ".....A..........",  # 1
    "....cAc.........",  # 2  signal arc
    "...c.A.c........",  # 3
    "...oAAo.........",  # 4  antenna base
    "..oBBBBBBBBBBBBB",  # 5  chassis top
    ".oHBBBBBBBBBBBBB",  # 6  highlight edge
    "oBBBBBBBBBBBBBBB",  # 7
    "oBBBBBBBBBBBBBBB",  # 8
    "oBBBBBBBoooooooo",  # 9  angry brow
    "oBBBBBBBrRRRRRRR",  # 10 cyclops eye
    "oBBBBBBBrRRRREEw",  # 11 pupil (center)
    "oBBBBBBBrRRRREEw",  # 12 pupil
    "oBBBBBBBrRRRRRRR",  # 13
    "oBBBBBBBBrrrrrrr",  # 14 eye base
    "oBBBBBBBBBBBBBBB",  # 15
    "oBBBBoommmmmmmmm",  # 16 mouth top
    "oBBBBomcmcmcmcmc",  # 17 LED teeth
    "oBBBBoommmmmmmmm",  # 18 mouth base
    "oBBBBBBBBBBBBBBB",  # 19
    "oBcBcBBBBBBBBBBB",  # 20 status LEDs
    ".oBBBBBBBBBBBBBB",  # 21
    ".oBBBBBBBBBBBBBB",  # 22
    "..oooooooooooooo",  # 23 base
    "...a....a...a...",  # 24 feet
    "...a....a...a...",  # 25
    "................",  # 26
    "................",  # 27
    "................",  # 28
    "................",  # 29
    "................",  # 30
    "................",  # 31
]

# ---- DEAUTHER (electric packet gremlin) ----------------------------------
DEAUTH_HALF = [
    "................",  # 0
    ".......Y........",  # 1  lightning
    "......Y.....b...",  # 2
    "..b..Y....bBBb..",  # 3  spikes
    ".bBb.Y...bBBBBb.",  # 4
    ".bBBb...bBBBBBBb",  # 5  head spikes
    "..bBBboBBBBBBBBB",  # 6
    "...bBBBBBBBBBBBB",  # 7
    "...bBBBBBBBBBBBB",  # 8
    "..bBBBwEEBBBBBBB",  # 9  eye (white+pupil)
    "..bBBBwEEBBBBBBB",  # 10 eye
    "...bBBBBBBoTTTTT",  # 11 -> jagged maw
    "...bBBBBBBmmmmmm",  # 12 maw
    "...bBBBBBmwmwmww",  # 13 fangs
    "....bBBBBmmmmmmm",  # 14
    "....bBBBBBBBBBBB",  # 15
    ".....bBBBBBBBBBB",  # 16
    "..Y..bBBBBBBBBBB",  # 17 lightning arms
    ".Y..bBBBBBBBBBBB",  # 18
    "Y..bBBBBBBBBBBBB",  # 19
    "Y.bBBBBBBBBBBBBB",  # 20
    ".bBBBBBBBBBBBBBB",  # 21
    ".bBBBBBBBBBBBBBB",  # 22
    "..bBBBBoBBBBBBBB",  # 23
    "..bBBBo.oBBBBBBB",  # 24 legs split
    ".bBBBo...oBBBBBB",  # 25
    ".bBBo.....oBBBBB",  # 26 jagged
    "bBBo.......oBBBB",  # 27
    "bBo.........oBBB",  # 28
    "Yo...........oBB",  # 29
    "..............oB",  # 30
    "................",  # 31
]

def emit(name, half, palette):
    check(half, name)
    rows = mirror(half)
    p = render(rows, palette, os.path.join(HERE, f"{name}.png"), px=14)
    print("rendered", p)
    return rows

def js_palette(pal):
    items = []
    for k, v in pal.items():
        items.append(f'"{k}":' + ('null' if v is None else f'"{v}"'))
    return "{" + ",".join(items) + "}"

def js_sprite(grid, pal, eye_rows=None):
    rows = ",".join(f'"{r}"' for r in grid)
    er = "" if not eye_rows else f',eyeRows:[{",".join(map(str, eye_rows))}]'
    return f'{{grid:[{rows}],pal:{js_palette(pal)}{er}}}'

def emit_js(path, sprites):
    parts = [f'  {key}: {js_sprite(*spec)}' for key, spec in sprites.items()]
    body = "// generated by build_sprites.py - do not hand-edit\nconst SPRITES = {\n" + ",\n".join(parts) + "\n};\n"
    with open(path, "w") as f:
        f.write(body)
    print("wrote", path)

def main():
    specs = {
        'kuma':      (KUMA_HALF, BEAR, [8, 9]),
        'pineapple': (PINE_HALF, PINE, None),
        'rogue_ap':  (ROGUE_HALF, ROGUE, None),
        'deauther':  (DEAUTH_HALF, DEAUTH, None),
    }
    png = {'kuma': 'kuma_bear', 'pineapple': 'enemy_pineapple',
           'rogue_ap': 'enemy_rogue_ap', 'deauther': 'enemy_deauther'}
    sprites = {}
    for key, (half, pal, eye) in specs.items():
        emit(png[key], half, pal)
        sprites[key] = (mirror(half), pal, eye)
    emit_js(os.path.join(HERE, "sprites.gen.js"), sprites)

if __name__ == "__main__":
    main()
