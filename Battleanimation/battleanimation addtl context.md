

```text
================================================================================
CRITICAL CLARIFICATION: DO NOT COPY THE MOCKUP DIRECTLY
================================================================================

The battle storyboard/mockup image is NOT the final UI asset and must NOT be copied directly.

It is only a visual reference for:

- overall flow
- screen pacing
- rough transition concept
- basic placement of enemy/Kuma/menu
- simple LilyGo T-Deck-friendly density

Do not recreate the mockup pixel-for-pixel.
Do not trace it.
Do not use it as a static background.
Do not render Kuma as a single static sprite during the encounter.
Do not render the enemy as a single static sprite during the full battle sequence.
Do not hardcode the storyboard frames as final screens.

The actual implementation must use the real KUMA and threat sprite sheets already created for this project.

The goal is a simple battle UI that animates by changing sprite frames/states over time, not a static mockup slideshow.

================================================================================
ASSET USAGE REQUIREMENT
================================================================================

Use the existing sprite sheets as source animation assets.

Expected assets may include:

- KUMA multi-sprite animation sheet
- KUMA 10-state sheet
- KUMA threat enemy sheet
- any extracted sprite frames already present in the repo

Search the repo for actual image assets before implementing.

If sprite metadata does not exist, create an atlas/mapping file.

Do not assume the mockup image contains the final assets.
Do not crop sprites out of the storyboard/mockup unless there is no better source.
Use the original KUMA sprite sheets wherever possible.

================================================================================
KUMA MUST BE ANIMATED
================================================================================

Kuma should not be static during encounter or battle.

Kuma should animate through sprite-state sequences using the existing sprite sheet.

Use sprite frame/state changes, small pixel-position offsets, and simple timing.

Do not overcomplicate this. The LilyGo T-Deck screen is small. Animation should be readable and lightweight.

Kuma animation layers:

1. Dashboard idle loop
2. Encounter alert reaction
3. Battle intro entrance
4. Battle idle stance
5. Ability execution animations
6. Victory / resolved state

================================================================================
KUMA SPRITE STATES AVAILABLE
================================================================================

Use these existing Kuma states:

- HIBERNATING
- FORAGING
- SENTINEL
- HONEY
- APEX
- ALERT
- INVESTIGATING
- DEFENDING
- ATTACKING
- VICTORY

If the older multi-sprite KUMA sheet exists, also use walk/run/turn/attack frames where appropriate.

Preferred source priority:

1. Use true animation frames from the multi-sprite KUMA sheet if available.
2. Use the 10-state KUMA sheet as keyframes if that is the cleanest available source.
3. Use small CSS/canvas position shifts only to support the sprite animation, not replace it.

================================================================================
ENCOUNTER ANIMATION SEQUENCE
================================================================================

The encounter animation happens first, immediately after a hostile event is identified.

This is before the battle intro.

Purpose:

The normal dashboard realizes something is wrong, locks onto the threat, and transitions into encounter mode.

Suggested sequence:

PHASE 1: NORMAL DASHBOARD
- Current dashboard visible.
- Kuma uses current mode sprite.
- If current mode is unknown, use SENTINEL.

PHASE 2: ALERT REACTION
- Threat changes to HIGH/CRITICAL.
- Kuma switches to ALERT.
- Screen briefly flashes or scanline sweeps.
- Text: THREAT DETECTED

PHASE 3: LOCK ON
- Kuma switches ALERT -> INVESTIGATING -> DEFENDING.
- Show short lock-on progress or pulse.
- Text: HOSTILE SIGNAL LOCKED

PHASE 4: HOSTILE APPROACH
- Enemy is not fully visible yet.
- Show silhouette, glitch outline, or partial enemy flicker.
- Kuma remains DEFENDING.
- Text: HOSTILE ENTITY APPROACHING

PHASE 5: ENCOUNTER INITIATED
- Enemy silhouette resolves enough to identify type.
- Kuma transitions DEFENDING -> APEX or SENTINEL depending threat level.
- Text: ENCOUNTER INITIATED

This should be animated using sprite changes and simple effects, not static full-screen storyboard images.

================================================================================
BATTLE INTRO ANIMATION SEQUENCE
================================================================================

The battle intro happens after encounter initiation.

Purpose:

Both sprites enter the battlefield and lock into the battle screen.

Suggested sequence:

PHASE 1: ENEMY REVEAL
- Enemy sprite appears first.
- Use enemy sprite from threat sheet.
- If enemy has only one frame, animate with small flicker, 1-2 px bob, shadow pulse, or glitch offset.
- Text: HOSTILE {ENEMY_NAME} DETECTED

PHASE 2: KUMA ENTERS
- Kuma enters from left side.
- Use actual walking/entering frames if available.
- If no walk frames are available, use SENTINEL -> ALERT -> DEFENDING with small left-to-right movement.
- Do not use a single static Kuma image.
- Text: KUMA STANDS WATCH

PHASE 3: SPRITES FACE OFF
- Kuma settles left.
- Enemy settles right.
- Kuma cycles into battle idle loop.
- Enemy cycles into threat idle loop.
- Text shows enemy name, threat level, confidence.

PHASE 4: BATTLEFIELD LOCK
- Screen stabilizes.
- Bottom stat bar remains.
- Ability menu appears.
- Input becomes active.

================================================================================
BATTLE IDLE LOOP
================================================================================

Once the ability menu appears, both Kuma and the enemy should idle.

Kuma idle loop options:

Preferred if multi-frame sheet exists:
- Use true idle frames from the KUMA animation sheet.

Fallback using 10-state sheet:
- SENTINEL frame
- subtle 1 px vertical bob
- brief ALERT blink every few seconds
- return to SENTINEL

Example Kuma battle idle loop:

SENTINEL for 900ms
SENTINEL shifted down 1px for 300ms
SENTINEL for 900ms
ALERT for 150ms
SENTINEL for 900ms

Enemy idle loop:

If enemy has only one sprite:
- subtle 1 px bob
- slight glow/flicker
- tiny glitch offset for digital enemies
- small pulse for RF/noise enemies

Do not make the screen busy. Small motion only.

================================================================================
ABILITY ANIMATIONS
================================================================================

When an ability is selected, Kuma must animate through the existing sprite states.

Ability animations are short clips, not static text changes.

SIGNAL MAUL:
Sprite sequence:
SENTINEL -> ATTACKING -> VICTORY

Motion:
- Kuma leans/steps forward.
- Small cyan slash/packet streak toward enemy.
- Enemy flickers or shakes.
- Apply DESTABILIZED.

Text:
KUMA used SIGNAL MAUL.
The hostile broadcast destabilized.

HONEY SNARE:
Sprite sequence:
HONEY -> INVESTIGATING -> ATTACKING

Motion:
- Kuma shows HONEY state.
- Small honey/lure icon or cyan marker appears near enemy.
- Enemy flickers as if tagged.
- Apply MARKED.

Text:
KUMA used HONEY SNARE.
The threat took the bait.
Enemy is MARKED.

CHANNEL ROAR:
Sprite sequence:
ALERT -> APEX -> ATTACKING

Motion:
- Kuma shifts ALERT to APEX.
- Concentric cyan wave lines move outward.
- Enemy shakes/flickers.
- Apply SUPPRESSED.

Text:
KUMA used CHANNEL ROAR.
The hostile noise pattern broke apart.
Enemy is SUPPRESSED.

PAWLOCK:
Sprite sequence:
DEFENDING -> APEX -> VICTORY

Motion:
- Kuma raises/holds defense posture.
- Small cyan lock or containment box appears over enemy.
- Enemy movement slows/stops.
- Apply CONTAINED.

Text:
KUMA used PAWLOCK.
The threat was contained.

================================================================================
SPRITE ANIMATION IMPLEMENTATION RULES
================================================================================

Implement animation as stateful sprite changes.

Do not use the storyboard as a final static animation.

Preferred technical approach:

- Create a Sprite component or renderer.
- Create atlas metadata for each sprite sheet.
- Create named animation clips.
- Play animation clips by advancing frame/state over time.
- Keep effects minimal and cheap.

Suggested animation clip structure:

kumaClips = {
  dashboardAlert: ["SENTINEL", "ALERT", "DEFENDING"],
  encounterLock: ["ALERT", "INVESTIGATING", "DEFENDING"],
  battleEnter: ["SENTINEL", "ALERT", "DEFENDING"],
  battleIdle: ["SENTINEL", "SENTINEL", "ALERT", "SENTINEL"],
  signalMaul: ["SENTINEL", "ATTACKING", "VICTORY"],
  honeySnare: ["HONEY", "INVESTIGATING", "ATTACKING"],
  channelRoar: ["ALERT", "APEX", "ATTACKING"],
  pawlock: ["DEFENDING", "APEX", "VICTORY"],
  resolved: ["VICTORY"]
}

Enemy animation clips can be simple:

enemyClips = {
  reveal: ["silhouette", "glitch", "enemy"],
  idle: ["enemy", "enemy_bob", "enemy"],
  hit: ["enemy", "enemy_glitch", "enemy"],
  contained: ["enemy", "enemy_locked"]
}

If actual alternate enemy frames do not exist, implement enemy animation using:
- opacity flicker
- 1 px bob
- 1-2 px horizontal glitch offset
- small glow pulse
- status icon overlay

================================================================================
LILLYGO T-DECK SCREEN CONSTRAINTS
================================================================================

Keep this simple.

The LilyGo T-Deck screen cannot support a huge dense RPG UI.

Design constraints:

- Avoid large multi-panel layouts.
- Avoid lots of tiny text.
- Avoid complex sidebars.
- Avoid many icons at once.
- Avoid full-screen decorative clutter.
- Preserve current dashboard footer style where possible.
- Keep the ability menu readable.
- Use short text only.

Preferred screen structure:

Top:
- KUMA name / online indicator
- enemy name or encounter text

Middle:
- Kuma sprite left
- enemy sprite right

Lower middle:
- short threat line
- confidence/threat level

Bottom:
- existing status/footer OR ability menu

Ability menu should be two rows:

SIGNAL MAUL     HONEY SNARE
CHANNEL ROAR    PAWLOCK

Use selection highlight on one ability.

================================================================================
DO NOT MAKE KUMA STATIC
================================================================================

This is the biggest requirement.

Kuma must visibly change state during:

- dashboard to encounter transition
- encounter lock
- battle intro
- idle battle stance
- ability execution
- resolution

At minimum, implement these sprite changes:

Encounter:
SENTINEL -> ALERT -> INVESTIGATING -> DEFENDING

Battle intro:
DEFENDING -> SENTINEL or ALERT -> DEFENDING

Battle idle:
SENTINEL loop with blink/bob

Signal Maul:
SENTINEL -> ATTACKING -> VICTORY

Honey Snare:
HONEY -> INVESTIGATING -> ATTACKING

Channel Roar:
ALERT -> APEX -> ATTACKING

Pawlock:
DEFENDING -> APEX -> VICTORY

Victory/resolved:
VICTORY

If this is implemented with a single static Kuma sprite, it is wrong.

================================================================================
WHAT THE MOCKUP IS FOR
================================================================================

The mockup/storyboard should be interpreted only as:

- a rough layout guide
- a simple density target
- a transition flow reference
- an example of how small the UI needs to stay

It is not:

- the final UI
- the final sprite asset
- the final layout
- the final animation
- something to directly copy

Use the project’s actual sprites and build a real animated state machine.

================================================================================
ACCEPTANCE CRITERIA ADDENDUM
================================================================================

The feature is not complete unless:

1. KUMA animates through multiple sprite states during encounter.
2. KUMA animates through multiple sprite states during battle intro.
3. KUMA has a visible idle loop during the ability menu.
4. Each ability plays its own Kuma sprite sequence.
5. Enemy sprite has at least a reveal animation and idle motion.
6. The storyboard/mockup is not used as a static final screen.
7. The implementation works on the LilyGo T-Deck-sized display.
8. The UI remains simple and readable.
9. The existing dashboard still works.
10. Same event does not endlessly replay the encounter animation.

================================================================================
FINAL DIRECTIVE
================================================================================

Build an animated battle encounter system using the actual KUMA sprite sheets.

Do not copy the storyboard directly.

Do not use static full-screen mockup frames.

Do not leave Kuma frozen.

Use the mockup only as a reference for pacing and simplicity.

The correct implementation is:

event detected
-> dashboard alert reaction
-> Kuma changes state
-> hostile silhouette/reveal
-> encounter initiated
-> enemy and Kuma enter battlefield
-> both sprites idle
-> ability menu appears
-> selected ability plays Kuma sprite sequence
-> enemy receives status effect
-> battle state updates
```

That should keep Claude from doing the “screenshot cosplay implementation,” which is the frontend equivalent of duct-taping a JPEG over a broken product and calling it v1.