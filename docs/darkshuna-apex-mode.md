# Dark Shuna (Kuroshuna) — Apex / Hack-Back mode (design note)

Status: **sprite ready, mode NOT built.** Asset processed + stashed; the mode it
drives is future work.

## Concept
**Kuroshuna** (黒シュナ, "Dark Shuna") is Shuna's **apex / hack-back form** — a
darker, aggressive variant (glowing magenta eyes, a purple hex-sigil energy orb).
She is the on-screen avatar for KUMA's **active-defense mode**: when KUMA stops
just *detecting* and starts *acting* (the actual deauthing / containment / the
offensive-defensive capabilities not yet baked in), the character **switches from
Shuna to Kuroshuna** to signal "gloves are off."

## Unlock + gating
- Unlocks together with the **Shuna easter egg** (very-hard unlock, see
  `docs/easter-eggs.md`). No Shuna, no Kuroshuna.
- Kuroshuna only appears while the **apex / hack-back mode is engaged** — it's a
  *mode* skin layered on top of the Shuna character, not a separate selectable
  character. Normal monitoring = Shuna; active hack-back = Kuroshuna.

## What "apex / hack-back mode" means (the capabilities behind her)
This is the active-response tier. KUMA already has the passive/defensive
`ApexResponder` (PMF-harden / containment-API; it never transmits attack frames —
see `backend/config/lab_targets.json`). The Kuroshuna mode is the next tier:
- **Active deauth / counter-deauth** against a confirmed hostile (gated by
  lab_mode + approved_targets), now that the Alfa has injection capability.
- Other offensive-defensive actions TBD (the "capabilities not baked in yet").

All of this stays gated behind explicit lab_mode + approved-target authorization —
KUMA's default posture remains passive blue-team.

## Asset
- Source (hi-res, gitignored): `designs/sprites/kuroshuna/hires/apex_hackback.png`
- Processed sprite (128px, white-bg removed via the gen_shuna pipeline):
  `designs/sprites/kuroshuna/apex_hackback.png`

## To build the mode (later)
1. Bake `apex_hackback.png` into a firmware header (e.g. `KUROSHUNA_APEX`).
2. Add an apex/hack-back mode flag through `/api/status` (like `character`), set
   when active-response engages.
3. Firmware: when the flag is on, draw Kuroshuna + a 黒シュナ wordmark in place of
   Shuna, and a distinct (red/purple) HUD treatment.
4. Wire the active-response capabilities (gated) that the mode represents.
