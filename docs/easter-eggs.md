# KUMA easter eggs (design spec)

Status: **designed, not built.** Approved by Jax 2026-06-08. Reward delivery:
**bake-into-firmware, gate display** (the reward art ships in the binary; the egg
is the *unlock challenge*, not asset-hiding — like most games' unlockables).

Two hidden background unlocks, both "hackery" the user performs on the device
terminal or over SSH to the Pi. Note: the KUMA device terminal is a **real shell
on the Pi**, so decode steps (`base64 -d`, `xxd`, etc.) can be run right there.

---

## Reward backgrounds

| Egg | Reward bg | Firmware symbol | Difficulty |
|-----|-----------|-----------------|------------|
| Easy | `backgFLAG1` | `KUMA_BG_FLAG1` (to bake, gated) | recognize + decode hex |
| Hard | `backgFLAG`  | `KUMA_BG_FLAG` (already baked)  | binwalk → carve → base64 → XOR |

`backgFLAG` doubles as the creator/hero background AND the hard-egg reward for
non-creator units (creator gets it for free; everyone else earns it).

---

## 🥚 Easy egg — "the bear talks in tongues" (on-device terminal)

**Trigger:** a hidden terminal command NOT shown in `help` — e.g. `purr`.

**Output:** an obfuscated blob (hex of a passphrase line):
```
クマ> purr
44 6f 6e 27 74 20 73 6c 65 65 70 3a 20 48 49 42 45 52 4e 41 54 45
```

**Solve:** decode hex (`echo <hex> | xxd -r -p`, runnable in the same terminal) ->
`Don't sleep: HIBERNATE`.

**Unlock:** `unlock HIBERNATE` -> terminal POSTs to `/api/unlock` -> backend
adds `backgFLAG1` to `unlocked_backgrounds` and (optionally) switches to it.

---

## 🥚 Hard egg — "honey buried in the den" (SSH / filesystem carving)

**Breadcrumb:** planted in the `kuma status` footer (or MOTD):
> "クマ hides her honey past the end of where the offline bear's dream is drawn."

Decoded: data **appended after the PNG `IEND` chunk** of the offline source image
on the Pi (`~/Kuma/designs/sprites/offline/_source.png`, or a planted copy).

**Solve path the user must figure out:**
1. `binwalk _source.png` (or notice file size > image) -> trailing data after IEND.
2. Carve it: `tail -c +<offset>` / `dd`.
3. `base64 -d` -> an XOR'd token.
4. XOR with key = device hostname `kuma1` -> flag `KUMA{apex_predator_69}`.

**Unlock:** `kuma-unlock KUMA{apex_predator_69}` (a small CLI planted on the Pi)
or `curl -X POST .../api/unlock -d token=...` -> backend adds `backgFLAG` to
`unlocked_backgrounds` for that unit.

---

## Plumbing to build

**Backend**
- `unlocked_backgrounds` list persisted (settings table / DB).
- `POST /api/unlock {token}` — compare `sha256(token)` to stored hashes; on match
  add the mapped reward bg; return `{unlocked: [...]}`. (Store hashes, not
  plaintext, so reading the source doesn't hand over the answer.)
- `/api/status` returns `unlocked_backgrounds` so the firmware's picker knows what
  to offer. Creator unit implicitly has all.

**Pi (one-time planting)**
- Append the XOR+base64 token after IEND of the chosen PNG.
- Plant the `kuma-unlock` CLI (thin wrapper that curls `/api/unlock`).
- Add the breadcrumb line to `kuma status` output / MOTD.

**Firmware**
- Bake `backgFLAG1` as `KUMA_BG_FLAG1` (un-gitignore + add to `gen_bg.py` ASSETS).
- Hidden terminal command `purr` (prints the hex blob) + `unlock <phrase>` command
  (POSTs to `/api/unlock`).
- Background picker offers `backg1`, `backg2`, plus any unlocked egg backgrounds.
  `bgDataFor()` already maps names -> packed PNG; extend it for FLAG1.

---

## 🥚🥚🥚 Shuna — "the waifu in the walls" (VERY hard, to design)

Unlocking the **Shuna** character skin (sprite pack + シュナ wordmark, baked but
gated) is the hardest egg. It changes the displayed name to シュナ on the dashboard
and in battle and swaps the whole sprite set. Jax's own unit has it on by default
(`character: shuna` in his Pi config); everyone else must earn it.

Mechanic (to finalize): a multi-step chain that forces real work on the device
terminal AND over SSH — e.g.:
1. A breadcrumb only visible while a live deauth/handshake event is firing (the
   detector logs a one-line hint to a rotating file).
2. That hint points to a flag split across two places (defense-in-depth): part in
   an `IEND`-appended PNG (carve), part in a systemd journal entry (`journalctl`
   grep), XOR-combined.
3. The combined token unlocks `character: shuna` via `POST /api/unlock`.

Reward asset note: Shuna's sprites are **baked into the firmware** (bake-and-gate),
so the unlock flips display only. Keeping the `designs/sprites/shuna/` source out
of the public repo would preserve more surprise — **open decision** (currently the
source IS committed).

## Notes
- The reward pixels live in the firmware binary (decision: bake + gate). The
  challenge is earning the unlock flag, not extracting the asset.
- Keep `backgFLAG1.png` out of the *public* design folder until launch if you want
  to preserve the surprise in the repo (currently gitignored).
