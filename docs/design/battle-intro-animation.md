# KUMA Battle Encounter & Ability UI — Design Spec

Status: design, awaiting build. Consolidates `Battleanimation/` (Jax's spec, addtl
context, enemy mapping, full context) plus the two design decisions made in chat.
Storyboard references: `reference/storyboard-encounter.png`,
`reference/storyboard-battle-intro.png` — **pacing/layout reference only, never traced
or used as a static background.**

## 1. What this is

A retro creature-battle-style **encounter screen** that triggers when KUMA identifies a
high-confidence active Wi-Fi threat. It is a defensive RF encounter console — a "bear SOC
analyst battle UI" — built from KUMA's own pixel sprite sheets, not a Pokémon clone. We
use only the abstract interaction pattern (threat detected → encounter → enemy appears →
KUMA appears → threat summary → 4 ability buttons → user picks → ability animation +
status effect). No copied UI, fonts, sounds, layouts, or art.

## 2. Decisions (locked)

- **Front-end only.** No backend changes. The battle is a UI layer over the existing
  `/api/status` + `/api/events` data. Abilities are game/UI state, not real RF actions.
- **Interactive with a 30s auto-fallback.** The player can tap an ability each turn; if no
  choice is made within 30s, KUMA auto-picks a super-effective ability and plays on. Works
  unattended on the always-on dashboard.
- **It's the top of the dashboard's state ladder.** The minimal face stays for calm states;
  battle takes over the viewport at the high-confidence-threat tier and returns to the face
  when the threat clears or the foe is contained.
- **Real sprites only.** KUMA = `designs/sprites/anim/<action>/0..4.png` (5-frame actions)
  and `designs/sprites/states/NN_*.png` (10 mode portraits). Enemies =
  `designs/sprites/enemies/NN_*.png`. (Mirrored into the dashboard static dir when deployed.)

## 3. State ladder (driven by /api/status)

```
hibernate / sleeping        -> calm face          (most of the time)
foraging / suspicious / alert -> sentinel face     (interesting traffic / spike)
high-confidence rogue        -> ENCOUNTER -> BATTLE (threat high|critical + malicious event)
```

**Trigger:** threat_level in {high, critical} AND a malicious event present whose
`event_type` maps to an enemy. **Debounce:** the same triggering event (by id / type+window)
must NOT replay the encounter — once battled, stay in battle or return to face; a new
distinct threat starts a new encounter. (Acceptance criterion #10.)

## 4. Sequences

### 4a. Encounter animation (threat identified) — before the battle intro
1. **Normal dashboard** — current mode sprite (SENTINEL if unknown).
2. **Alert reaction** — threat → HIGH/CRITICAL, KUMA → ALERT, brief flash / scanline sweep,
   text `THREAT DETECTED`.
3. **Lock on** — KUMA ALERT → INVESTIGATING → DEFENDING, lock-on pulse, `HOSTILE SIGNAL LOCKED`.
4. **Hostile approach** — enemy as silhouette / glitch outline / partial flicker, KUMA
   DEFENDING, `HOSTILE ENTITY APPROACHING`.
5. **Encounter initiated** — enemy resolves enough to identify, KUMA → APEX/SENTINEL by
   threat, `ENCOUNTER INITIATED`.

### 4b. Battle intro (sprites enter)
1. **Enemy reveal** — enemy sprite appears (right); single-frame enemies animate via
   flicker / 1-2px bob / shadow pulse / glitch offset. `HOSTILE {ENEMY_NAME} DETECTED`.
2. **KUMA enters** — KUMA walks in from the left (anim walk frames if used, else SENTINEL →
   ALERT → DEFENDING with small L→R movement). Never a single static image. `KUMA STANDS WATCH`.
3. **Face off** — KUMA settles left into battle idle loop, enemy settles right into threat
   idle loop. Show enemy name, threat level, confidence.
4. **Battlefield lock** — screen stabilizes, stat bar remains, ability menu appears, input active.

### 4c. Battle idle loop
KUMA: true idle frames if available, else SENTINEL with 1px bob + brief ALERT blink every
few seconds. Enemy: subtle 1px bob + glow/flicker (glitch offset for digital enemies, pulse
for RF/noise enemies). Small motion only — never busy.

## 5. Abilities

Two-row menu: `SIGNAL MAUL  HONEY SNARE` / `CHANNEL ROAR  PAWLOCK`. Selection highlight on one.

| Ability | KUMA sprite clip | Status effect | Notes |
|---|---|---|---|
| **SIGNAL MAUL** | SENTINEL → ATTACKING → VICTORY | DESTABILIZED | damage; cyan slash/packet streak; enemy flickers |
| **HONEY SNARE** | HONEY → INVESTIGATING → ATTACKING | MARKED | utility: marks foe + boosts KUMA's next action 1.5× |
| **CHANNEL ROAR** | ALERT → APEX → ATTACKING | SUPPRESSED | damage; concentric cyan waves; area disruption flavor |
| **PAWLOCK** | DEFENDING → APEX → VICTORY | CONTAINED | damage; cyan lock/containment box; enemy slows/stops |

**Effectiveness:** `enemy-battle-mapping.json` lists each enemy's `weakTo` abilities. Using a
`weakTo` ability = super-effective (bonus damage + "super effective" line). HONEY SNARE
applies MARKED and buffs the next hit (strong opener vs lures: karma/pineapple/evil twin).

Status effect icons: MARKED, SUPPRESSED, CONTAINED, DESTABILIZED (cyan-on-dark glyphs).

## 6. Battle mechanics (front-end)
- Enemy HP bar; KUMA HP bar. Each turn: player taps (or 30s timeout → KUMA auto-picks a
  `weakTo` ability). Damage = base ± super-effective multiplier × MARKED bonus.
- Enemy takes flavor turns (chips KUMA HP) for tension; not a real loss condition on the
  live dashboard — when the foe's HP hits 0 it's CONTAINED → `THREAT CONTAINED` → return to
  monitoring face.
- Animation hooks are stubbed so the encounter/intro timing can be swapped without rework.

## 7. Sprite-animation architecture
- A small **Sprite renderer** + **named animation clips** (advance frame/state over time).
  Clips per Jax's spec:
  ```js
  kumaClips = {
    dashboardAlert:["SENTINEL","ALERT","DEFENDING"], encounterLock:["ALERT","INVESTIGATING","DEFENDING"],
    battleEnter:["SENTINEL","ALERT","DEFENDING"], battleIdle:["SENTINEL","SENTINEL","ALERT","SENTINEL"],
    signalMaul:["SENTINEL","ATTACKING","VICTORY"], honeySnare:["HONEY","INVESTIGATING","ATTACKING"],
    channelRoar:["ALERT","APEX","ATTACKING"], pawlock:["DEFENDING","APEX","VICTORY"], resolved:["VICTORY"]
  }
  ```
  State names resolve to `states/NN_*.png`; idle/walk use `anim/*` frames where available.
- Enemy clips: reveal (silhouette→glitch→enemy), idle (bob), hit (glitch), contained (locked).
  Single-frame enemies fake these with opacity flicker / bob / glitch offset / glow / status overlay.

## 8. Layout (LilyGo T-Deck-sized: small, readable)
Top: KUMA name + online indicator, enemy name / encounter text. Middle: KUMA left, enemy
right. Lower-middle: short threat line + confidence/threat level. Bottom: stat footer OR the
2-row ability menu. No dense multi-panel RPG UI, no tiny-text walls, no decorative clutter.

## 9. Build approach
Iterate in `designs/kuma-battle.html` (already has KUMA + enemies + a turn loop), upgrade it
to this spec (encounter → intro → battle idle → abilities → resolve, real sprite clips), then
port the working module into the live dashboard as the high-threat escalation layer. Keeps
the live screen stable during iteration.

## 10. Acceptance criteria
1. KUMA animates through multiple sprite states during the encounter.
2. KUMA animates through multiple sprite states during the battle intro.
3. KUMA has a visible idle loop while the ability menu is up.
4. Each ability plays its own KUMA sprite sequence.
5. Enemy has at least a reveal animation + idle motion.
6. The storyboard is never used as a static final screen.
7. Works at LilyGo T-Deck display size.
8. UI stays simple and readable.
9. The existing dashboard still works.
10. The same event does not endlessly replay the encounter.
