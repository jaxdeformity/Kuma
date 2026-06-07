

```text
# KUMA Battle Intro Animation Context for Claude CLI

You are working on KUMA, an open-source DIY blue-team Wi-Fi defense gadget.

Your job is to implement a battle-introduction animation and battle-screen ability UI that appears when KUMA identifies an active Wi-Fi threat.

This document is intended to be copied into the repo as context, for example:

docs/design/battle-intro-animation.md

Then Claude Code should be run from the repository root with instructions to read this file plus the existing repo docs and implement the feature.

DO NOT stop at design suggestions. Implement the feature in the repo.

================================================================================
PROJECT SUMMARY
================================================================================

KUMA is an open-source, DIY, blue-team Wi-Fi defense gadget.

It is conceptually the opposite of offensive pocket Wi-Fi tools. KUMA sits on the network you want to protect, watches the RF environment, detects suspicious Wi-Fi activity, scores confidence, logs what it sees, and displays the threat state through a dashboard and a pixel-bear mascot.

KUMA’s architecture:

802.11 frame -> detector -> scoring -> SQLite -> HTTP API -> dashboard / handheld

Hardware roles:

- Raspberry Pi 4 or 5: the BRAIN
  Backend, capture, detection, scoring, SQLite, API.

- USB Wi-Fi dongle with monitor mode: the EARS
  Live packet capture.

- LilyGo T-Deck or M5Stack Core: the FACE
  Pixel-bear UI that polls the Pi.

The current KUMA modes are:

- Hibernate: conserve / quiet watch
- Foraging: discover / baseline
- Sentinel: detect / score
- Honey: deceive / lure awareness
- Apex: respond / gated defensive handling

This battle UI is NOT the mode system.

The battle UI is an encounter screen that appears after an active threat is detected.

================================================================================
IMPORTANT SAFETY AND LANGUAGE RULES
================================================================================

The battle UI can use fantasy/disruptive labels such as:

- SIGNAL MAUL
- HONEY SNARE
- CHANNEL ROAR
- PAWLOCK

However, do not implement real offensive RF behavior unless the existing repo already contains safe, legal, lab-gated Apex response functionality.

Separate battle UI flavor from real backend action.

Good implementation:

- Detect threat.
- Show battle intro.
- Show enemy sprite.
- Show Kuma sprite.
- Show confidence-scored observed details.
- Let user select a battle ability.
- Apply a UI status effect.
- Optionally call existing safe/gated backend response endpoints if they already exist.

Bad implementation:

- Add real deauth logic.
- Add jamming.
- Capture credentials.
- Add packet injection attack features.
- Overclaim attribution.
- Treat MAC address as identity.

All displayed detections must avoid overclaiming.

Use language like:

- suspected
- observed
- detected
- confidence
- hostile behavior
- signal behavior
- RF activity

Avoid language like:

- attacker identity confirmed
- hacker caught
- criminal device
- definitely malicious
- owned
- pwned

MAC addresses can be spoofed. Do not make the UI lie.

================================================================================
DESIGN INTENT
================================================================================

Do not tell the UI to copy Pokémon.

Use only the abstract encounter pattern:

1. Active threat is identified.
2. Dashboard shifts into encounter mode.
3. Enemy threat appears.
4. Kuma appears.
5. Threat summary is shown.
6. Four ability buttons appear.
7. User selects a Kuma battle ability.
8. UI plays the corresponding Kuma animation sequence.
9. UI applies the corresponding status effect.

This should feel like:

dark terminal console + pixel-art threat encounter + blue-team RF instrument panel

It should NOT feel like:

- Pokémon clone
- Nintendo UI clone
- generic anime RPG clone
- fake hacker movie dashboard
- glossy blue AI-template slop
- vaporwave cyber gradient mess

Visual style:

- Chunky retro pixel art
- Moody dark cyber aesthetic
- Bold readable silhouettes
- Crisp 1px outlines
- Subtle dithered shading
- Cyan/neon tech accents
- Dark monospace instrument-console feel
- Defensive RF console aesthetic
- Pixel-bear mascot
- Readable at small handheld/dashboard sizes

Use cyan for KUMA/system highlights.

Use red/orange sparingly for threat emphasis.

Avoid heavy bloom, blur, glossy gradients, and modern glassmorphism.

================================================================================
EXPECTED ASSETS
================================================================================

Expected sprite assets:

assets/sprites/kuma-sprite-sheet.png
assets/sprites/kuma-threats-sheet.png

If these exact paths do not exist:

1. Search the repo for sprite/image assets.
2. Use the closest matching KUMA sprite sheet and threat sprite sheet.
3. Do not modify the source sprite sheets destructively.
4. If atlas metadata does not exist, create a mapping/config file.

Suggested atlas config paths:

assets/sprites/kuma-atlas.json
assets/sprites/threats-atlas.json

Alternative frontend data paths if appropriate:

frontend/src/data/kumaSpriteAtlas.ts
frontend/src/data/threatSpriteAtlas.ts
frontend/src/data/battleEnemies.ts
frontend/src/data/battleAbilities.ts

Adapt paths to the actual repo structure.

Do not invent new Kuma sprites.

Use the already-created Kuma sprite states.

================================================================================
EXISTING KUMA SPRITE STATES
================================================================================

The existing Kuma sheet contains 10 states:

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

Battle intro should primarily use:

SENTINEL -> ALERT -> DEFENDING -> APEX

Ability animations should use:

SIGNAL MAUL:
SENTINEL -> ATTACKING -> VICTORY

HONEY SNARE:
HONEY -> INVESTIGATING -> ATTACKING

CHANNEL ROAR:
ALERT -> APEX -> ATTACKING

PAWLOCK:
DEFENDING -> APEX -> VICTORY

Do not request new art.

Do not generate new poses.

Use the existing sheet.

================================================================================
THREAT ENEMY SPRITES
================================================================================

The threat sprite sheet contains 10 enemy creatures:

- ROGUE AP
- EVIL TWIN
- DEAUTHER
- WIFI PINEAPPLE
- BEACON FLOODER
- KARMA LURE
- HANDSHAKE HARVESTER
- SNIFFER
- RF JAMMER
- BOTNET WORM

Each enemy should be front-facing, full-body, centered in its own cell, and visually scaled to stand next to Kuma.

If the sprite sheet lacks atlas metadata, inspect the image and create mapping metadata.

================================================================================
BATTLE TRIGGER
================================================================================

The battle intro should trigger when the backend or mock API reports an active threat event.

Use the actual existing API shape from the repo.

Possible event shape:

{
  "event_id": "evt_123",
  "type": "evil_twin",
  "threat_level": "HIGH",
  "confidence": 0.87,
  "ssid": "Corp-WiFi",
  "bssid": "aa:bb:cc:dd:ee:ff",
  "channel": 6,
  "rssi": -42,
  "timestamp": "2026-06-07T12:00:00Z"
}

If the current API shape differs, adapt to the real codebase instead of inventing a parallel system.

Trigger the battle intro when:

- threat_level is MEDIUM
- OR threat_level is HIGH
- OR threat_level is CRITICAL
- OR event.type is one of the known enemy mappings
- OR mock mode emits a battle-test event

Avoid replaying the intro for the same event repeatedly.

Replay control options:

- event_id
- event timestamp
- event hash
- local lastEncounteredEventId
- cooldown per threat type

Suggested behavior:

If the same event_id was already shown, do not replay battle intro.
If no event_id exists, generate a stable key from type + timestamp + bssid + ssid.
If events are noisy, add a 30-60 second cooldown per threat type.

================================================================================
ENEMY MAPPING
================================================================================

Map detected threat types to enemy sprites and display names.

Use this mapping:

rogue_ap:
  enemyName: ROGUE AP
  battleText: A rogue access point appeared.
  weakTo:
    - SIGNAL_MAUL
    - PAWLOCK
  spriteKey: rogue_ap

evil_twin:
  enemyName: EVIL TWIN
  battleText: A fractured twin is mimicking the network.
  weakTo:
    - SIGNAL_MAUL
    - HONEY_SNARE
  spriteKey: evil_twin

deauth:
  enemyName: DEAUTHER
  battleText: A deauther is flooding disconnect frames.
  weakTo:
    - CHANNEL_ROAR
  spriteKey: deauther

disassoc:
  enemyName: DEAUTHER
  battleText: A disassociation burst is active.
  weakTo:
    - CHANNEL_ROAR
  spriteKey: deauther

wifi_pineapple:
  enemyName: WIFI PINEAPPLE
  battleText: A lure device is baiting nearby clients.
  weakTo:
    - HONEY_SNARE
    - SIGNAL_MAUL
  spriteKey: wifi_pineapple

beacon_flood:
  enemyName: BEACON FLOODER
  battleText: Fake SSIDs are flooding the air.
  weakTo:
    - CHANNEL_ROAR
    - SIGNAL_MAUL
  spriteKey: beacon_flooder

ssid_flood:
  enemyName: BEACON FLOODER
  battleText: Fake SSIDs are flooding the air.
  weakTo:
    - CHANNEL_ROAR
    - SIGNAL_MAUL
  spriteKey: beacon_flooder

karma_lure:
  enemyName: KARMA LURE
  battleText: A lure is answering probe requests.
  weakTo:
    - HONEY_SNARE
  spriteKey: karma_lure

pineap:
  enemyName: KARMA LURE
  battleText: PineAP-style lure behavior detected.
  weakTo:
    - HONEY_SNARE
  spriteKey: karma_lure

handshake_harvester:
  enemyName: HANDSHAKE HARVESTER
  battleText: A harvester is trying to capture handshakes.
  weakTo:
    - PAWLOCK
    - HONEY_SNARE
  spriteKey: handshake_harvester

eapol:
  enemyName: HANDSHAKE HARVESTER
  battleText: Suspicious EAPOL harvesting behavior detected.
  weakTo:
    - PAWLOCK
    - HONEY_SNARE
  spriteKey: handshake_harvester

sniffer:
  enemyName: SNIFFER
  battleText: A passive listener is lurking nearby.
  weakTo:
    - PAWLOCK
  spriteKey: sniffer

rf_jammer:
  enemyName: RF JAMMER
  battleText: RF denial behavior is disrupting the channel.
  weakTo:
    - CHANNEL_ROAR
  spriteKey: rf_jammer

botnet_worm:
  enemyName: BOTNET WORM
  battleText: Linked infected nodes are spreading.
  weakTo:
    - CHANNEL_ROAR
    - PAWLOCK
  spriteKey: botnet_worm

Unknown fallback:

unknown:
  enemyName: UNKNOWN THREAT
  battleText: An unknown hostile signal appeared.
  weakTo:
    - PAWLOCK
  spriteKey: unknown

================================================================================
KUMA BATTLE ABILITIES
================================================================================

The battle menu must show exactly four abilities:

- SIGNAL MAUL
- HONEY SNARE
- CHANNEL ROAR
- PAWLOCK

These are active battle-screen abilities chosen after a threat is identified.

They are not KUMA modes.

They are not passive traits.

They appear on the encounter menu.

Example menu layout:

KUMA
HP: ████████████
THREAT: HIGH

> SIGNAL MAUL     HONEY SNARE
  CHANNEL ROAR    PAWLOCK

================================================================================
ABILITY 1: SIGNAL MAUL
================================================================================

Role:

Direct disruption.

Best against:

- ROGUE AP
- EVIL TWIN
- BEACON FLOODER
- WIFI PINEAPPLE

Sprite sequence:

SENTINEL -> ATTACKING -> VICTORY

Battle effect:

Deals heavy disruption damage to spoofing and broadcast enemies.
Extra effective if the enemy is mimicking a protected SSID.

System-style effect:

DESTABILIZED

UI text:

KUMA used SIGNAL MAUL.
The hostile broadcast destabilized.

================================================================================
ABILITY 2: HONEY SNARE
================================================================================

Role:

Trap / deception / mark.

Best against:

- KARMA LURE
- WIFI PINEAPPLE
- EVIL TWIN
- HANDSHAKE HARVESTER

Sprite sequence:

HONEY -> INVESTIGATING -> ATTACKING

Battle effect:

Tags the enemy and lowers its evasion.
Next Kuma ability has increased accuracy and confidence.

System-style effect:

MARKED

UI text:

KUMA used HONEY SNARE.
The threat took the bait.
Enemy is MARKED.

================================================================================
ABILITY 3: CHANNEL ROAR
================================================================================

Role:

Area disruption / burst suppression.

Best against:

- DEAUTHER
- RF JAMMER
- BEACON FLOODER
- BOTNET WORM

Sprite sequence:

ALERT -> APEX -> ATTACKING

Battle effect:

Hits all active threat entities.
Strong against flood, burst, and swarm enemies.
May reduce enemy action speed.

System-style effect:

SUPPRESSED

UI text:

KUMA used CHANNEL ROAR.
The hostile noise pattern broke apart.
Enemy is SUPPRESSED.

================================================================================
ABILITY 4: PAWLOCK
================================================================================

Role:

Containment / disable.

Best against:

- ROGUE AP
- HANDSHAKE HARVESTER
- SNIFFER
- BOTNET WORM

Sprite sequence:

DEFENDING -> APEX -> VICTORY

Battle effect:

Applies CONTAINED.
Enemy cannot act for the next turn.
If threat confidence is HIGH, containment lasts longer.

System-style effect:

CONTAINED

UI text:

KUMA used PAWLOCK.
The threat was contained.

================================================================================
STATUS EFFECTS
================================================================================

Use these exact status labels:

- MARKED
- SUPPRESSED
- CONTAINED
- DESTABILIZED

MARKED:

Kuma has identified the enemy behavior pattern.
Next move gets a confidence bonus.

SUPPRESSED:

Enemy action rate is reduced.
Useful against floods, bursts, and swarms.

CONTAINED:

Enemy is blocked, isolated, pinned, or disabled in the battle UI.
If backend Apex action exists, containment may map to a safe controller/API handoff.

DESTABILIZED:

Enemy spoofing, broadcast, or lure behavior becomes unreliable.

================================================================================
ENEMY WEAKNESS CHART
================================================================================

ROGUE AP:
Weak to SIGNAL MAUL and PAWLOCK.
Reason: impersonation and unauthorized broadcast.

EVIL TWIN:
Weak to SIGNAL MAUL and HONEY SNARE.
Reason: mimic behavior can be exposed and disrupted.

DEAUTHER:
Weak to CHANNEL ROAR.
Reason: burst attacker, weak to area suppression.

WIFI PINEAPPLE:
Weak to HONEY SNARE and SIGNAL MAUL.
Reason: lure-based attacker.

BEACON FLOODER:
Weak to CHANNEL ROAR and SIGNAL MAUL.
Reason: broadcast spammer.

KARMA LURE:
Weak to HONEY SNARE.
Reason: bait-based enemy gets counter-baited.

HANDSHAKE HARVESTER:
Weak to PAWLOCK and HONEY SNARE.
Reason: needs proximity and repeated capture behavior.

SNIFFER:
Weak to PAWLOCK.
Reason: passive lurker, best handled by containment.

RF JAMMER:
Weak to CHANNEL ROAR.
Reason: noise brute, weak to broader disruption/response.

BOTNET WORM:
Weak to CHANNEL ROAR and PAWLOCK.
Reason: swarm enemy needs suppression plus containment.

================================================================================
BATTLE INTRO ANIMATION TIMELINE
================================================================================

Implement the intro as a deterministic state machine.

Do not scatter random timeouts all over the UI like a raccoon with commit access.

State flow:

idle
-> threat_flash
-> enemy_reveal
-> kuma_enter
-> battle_lock
-> ability_menu
-> ability_animating
-> ability_menu or resolved

================================================================================
PHASE 0: MONITORING
================================================================================

Normal dashboard is visible.

Condition:

No active battle encounter.

Behavior:

Poll status/events as currently implemented.
Do not interrupt the normal dashboard unless active threat trigger conditions are met.

================================================================================
PHASE 1: THREAT FLASH
================================================================================

Duration:

300-500ms

Visual behavior:

- Dashboard flickers or dims.
- Cyan scanline sweep crosses screen.
- Threat banner appears.
- Optional subtle screen shake.

Text:

ACTIVE THREAT IDENTIFIED

Implementation notes:

- Use reduced motion handling.
- Do not flash aggressively.
- Keep animation readable on handheld display sizes.

================================================================================
PHASE 2: ENEMY REVEAL
================================================================================

Duration:

700-1000ms

Visual behavior:

- Enemy sprite enters from the right.
- Enemy silhouette or glitch outline appears first.
- Enemy resolves into full sprite.
- Enemy nameplate appears.
- Threat confidence appears.

Preferred text format:

HOSTILE {ENEMY_NAME} DETECTED
CONFIDENCE: {confidencePercent}
THREAT: {threatLevel}

Avoid:

WILD {ENEMY_NAME} APPEARED

Reason:

"WILD" is too close to creature-battle source material.
Use "HOSTILE" or "SUSPECTED" for KUMA.

================================================================================
PHASE 3: KUMA ENTERS
================================================================================

Duration:

700-1000ms

Visual behavior:

- Kuma enters from the left or rises from bottom-left.
- Use SENTINEL first.
- If threat is HIGH or CRITICAL, quickly transition to ALERT or DEFENDING.
- Add cyan outline pulse.

Text:

KUMA STANDS WATCH

Suggested sprite logic:

MEDIUM threat:
SENTINEL

HIGH threat:
SENTINEL -> ALERT

CRITICAL threat:
SENTINEL -> ALERT -> DEFENDING

================================================================================
PHASE 4: BATTLE FRAME LOCK
================================================================================

Duration:

300ms

Visual behavior:

- Encounter frame locks into place.
- Enemy remains on right.
- Kuma remains on left.
- Threat data panel becomes readable.

Show observed values:

SSID: {ssid || "unknown"}
BSSID: {bssid || "unknown"}
CHANNEL: {channel || "unknown"}
SIGNAL: {rssi || "unknown"}

Important language rule:

Never overclaim identity.
Use observed/suspected language.

Example:

OBSERVED BSSID: aa:bb:cc:dd:ee:ff
SUSPECTED TYPE: EVIL TWIN
CONFIDENCE: 91%

================================================================================
PHASE 5: ABILITY MENU
================================================================================

Duration:

Until user selects action or exits.

Show exactly four abilities:

SIGNAL MAUL     HONEY SNARE
CHANNEL ROAR    PAWLOCK

Keyboard/controller behavior:

- Arrow keys or D-pad moves selection.
- Enter/A selects ability.
- Escape/B exits back to dashboard.
- Mouse/touch click also works on dashboard.

Selected ability should show a one-line description.

Example:

> SIGNAL MAUL
Disrupts hostile broadcast and spoofing behavior.

================================================================================
BATTLE UI LAYOUT
================================================================================

Use a 2D retro battle layout.

Recommended structure:

+----------------------------------------+
| HOSTILE EVIL TWIN DETECTED             |
| THREAT: HIGH        CONF: 87%          |
+----------------------------------------+
|                                        |
|              [ enemy sprite ]          |
|                                        |
| [ kuma sprite ]                        |
|                                        |
+----------------------------------------+
| SSID: Corp-WiFi     CH: 6              |
| BSSID: aa:bb:cc...  OBSERVED ONLY      |
+----------------------------------------+
| > SIGNAL MAUL       HONEY SNARE        |
|   CHANNEL ROAR      PAWLOCK            |
+----------------------------------------+

Visual hierarchy:

1. Enemy name and threat level.
2. Enemy sprite.
3. Kuma sprite.
4. Observed RF details.
5. Ability menu.

Rules:

- Enemy name and threat level must be readable first.
- Kuma and enemy sprites must remain full-body and not cropped.
- Ability menu must not overlap sprites.
- Use pixel-font styling consistent with the existing dashboard.
- Use cyan for KUMA/system highlights.
- Use red/orange sparingly for threat emphasis.

================================================================================
ABILITY SELECTION BEHAVIOR
================================================================================

When user selects an ability:

1. Lock input briefly.
2. Play ability text.
3. Play Kuma sprite sequence.
4. Apply status effect badge.
5. Update local battle state.
6. Optionally call safe backend action if already implemented.
7. Return to ability menu or resolve encounter.

SIGNAL MAUL selection:

Text:
KUMA used SIGNAL MAUL.
The hostile broadcast destabilized.

Status:
DESTABILIZED

Sprite sequence:
SENTINEL -> ATTACKING -> VICTORY

Suggested duration:
900-1400ms

HONEY SNARE selection:

Text:
KUMA used HONEY SNARE.
The threat took the bait.
Enemy is MARKED.

Status:
MARKED

Sprite sequence:
HONEY -> INVESTIGATING -> ATTACKING

Suggested duration:
900-1400ms

CHANNEL ROAR selection:

Text:
KUMA used CHANNEL ROAR.
The hostile noise pattern broke apart.
Enemy is SUPPRESSED.

Status:
SUPPRESSED

Sprite sequence:
ALERT -> APEX -> ATTACKING

Suggested duration:
900-1400ms

PAWLOCK selection:

Text:
KUMA used PAWLOCK.
The threat was contained.

Status:
CONTAINED

Sprite sequence:
DEFENDING -> APEX -> VICTORY

Suggested duration:
900-1400ms

================================================================================
SUGGESTED STATE MODEL
================================================================================

Adapt this to the framework/language actually used.

BattlePhase values:

- idle
- threat_flash
- enemy_reveal
- kuma_enter
- battle_lock
- ability_menu
- ability_animating
- resolved

ThreatLevel values:

- LOW
- MEDIUM
- HIGH
- CRITICAL

KumaAbility values:

- SIGNAL_MAUL
- HONEY_SNARE
- CHANNEL_ROAR
- PAWLOCK

BattleStatus values:

- MARKED
- SUPPRESSED
- CONTAINED
- DESTABILIZED

BattleEncounter fields:

- eventId
- enemyName
- threatType
- threatLevel
- confidence
- ssid
- bssid
- channel
- rssi
- phase
- selectedAbility
- statuses
- createdAt
- resolvedAt

Example object:

{
  "eventId": "mock-evil-twin-001",
  "enemyName": "EVIL TWIN",
  "threatType": "evil_twin",
  "threatLevel": "HIGH",
  "confidence": 0.91,
  "ssid": "Corp-WiFi",
  "bssid": "66:66:66:66:66:66",
  "channel": 6,
  "rssi": -42,
  "phase": "threat_flash",
  "selectedAbility": null,
  "statuses": [],
  "createdAt": "2026-06-07T12:00:00Z"
}

================================================================================
SUGGESTED DATA FILE: BATTLE ENEMIES
================================================================================

Create a frontend data/config file if appropriate.

Example filename:

frontend/src/data/battleEnemies.ts

Suggested content shape:

export const BATTLE_ENEMIES = {
  rogue_ap: {
    enemyName: "ROGUE AP",
    battleText: "A rogue access point appeared.",
    weakTo: ["SIGNAL_MAUL", "PAWLOCK"],
    spriteKey: "rogue_ap"
  },
  evil_twin: {
    enemyName: "EVIL TWIN",
    battleText: "A fractured twin is mimicking the network.",
    weakTo: ["SIGNAL_MAUL", "HONEY_SNARE"],
    spriteKey: "evil_twin"
  },
  deauth: {
    enemyName: "DEAUTHER",
    battleText: "A deauther is flooding disconnect frames.",
    weakTo: ["CHANNEL_ROAR"],
    spriteKey: "deauther"
  },
  disassoc: {
    enemyName: "DEAUTHER",
    battleText: "A disassociation burst is active.",
    weakTo: ["CHANNEL_ROAR"],
    spriteKey: "deauther"
  },
  wifi_pineapple: {
    enemyName: "WIFI PINEAPPLE",
    battleText: "A lure device is baiting nearby clients.",
    weakTo: ["HONEY_SNARE", "SIGNAL_MAUL"],
    spriteKey: "wifi_pineapple"
  },
  beacon_flood: {
    enemyName: "BEACON FLOODER",
    battleText: "Fake SSIDs are flooding the air.",
    weakTo: ["CHANNEL_ROAR", "SIGNAL_MAUL"],
    spriteKey: "beacon_flooder"
  },
  ssid_flood: {
    enemyName: "BEACON FLOODER",
    battleText: "Fake SSIDs are flooding the air.",
    weakTo: ["CHANNEL_ROAR", "SIGNAL_MAUL"],
    spriteKey: "beacon_flooder"
  },
  karma_lure: {
    enemyName: "KARMA LURE",
    battleText: "A lure is answering probe requests.",
    weakTo: ["HONEY_SNARE"],
    spriteKey: "karma_lure"
  },
  pineap: {
    enemyName: "KARMA LURE",
    battleText: "PineAP-style lure behavior detected.",
    weakTo: ["HONEY_SNARE"],
    spriteKey: "karma_lure"
  },
  handshake_harvester: {
    enemyName: "HANDSHAKE HARVESTER",
    battleText: "A harvester is trying to capture handshakes.",
    weakTo: ["PAWLOCK", "HONEY_SNARE"],
    spriteKey: "handshake_harvester"
  },
  eapol: {
    enemyName: "HANDSHAKE HARVESTER",
    battleText: "Suspicious EAPOL harvesting behavior detected.",
    weakTo: ["PAWLOCK", "HONEY_SNARE"],
    spriteKey: "handshake_harvester"
  },
  sniffer: {
    enemyName: "SNIFFER",
    battleText: "A passive listener is lurking nearby.",
    weakTo: ["PAWLOCK"],
    spriteKey: "sniffer"
  },
  rf_jammer: {
    enemyName: "RF JAMMER",
    battleText: "RF denial behavior is disrupting the channel.",
    weakTo: ["CHANNEL_ROAR"],
    spriteKey: "rf_jammer"
  },
  botnet_worm: {
    enemyName: "BOTNET WORM",
    battleText: "Linked infected nodes are spreading.",
    weakTo: ["CHANNEL_ROAR", "PAWLOCK"],
    spriteKey: "botnet_worm"
  }
};

export const UNKNOWN_ENEMY = {
  enemyName: "UNKNOWN THREAT",
  battleText: "An unknown hostile signal appeared.",
  weakTo: ["PAWLOCK"],
  spriteKey: "unknown"
};

================================================================================
SUGGESTED DATA FILE: BATTLE ABILITIES
================================================================================

Create a frontend data/config file if appropriate.

Example filename:

frontend/src/data/battleAbilities.ts

Suggested content shape:

export const KUMA_ABILITIES = {
  SIGNAL_MAUL: {
    label: "SIGNAL MAUL",
    description: "Disrupts hostile broadcast and spoofing behavior.",
    status: "DESTABILIZED",
    text: [
      "KUMA used SIGNAL MAUL.",
      "The hostile broadcast destabilized."
    ],
    spriteSequence: ["SENTINEL", "ATTACKING", "VICTORY"]
  },
  HONEY_SNARE: {
    label: "HONEY SNARE",
    description: "Baits lure-based threats into revealing their pattern.",
    status: "MARKED",
    text: [
      "KUMA used HONEY SNARE.",
      "The threat took the bait.",
      "Enemy is MARKED."
    ],
    spriteSequence: ["HONEY", "INVESTIGATING", "ATTACKING"]
  },
  CHANNEL_ROAR: {
    label: "CHANNEL ROAR",
    description: "Breaks burst, flood, and swarm behavior with area disruption.",
    status: "SUPPRESSED",
    text: [
      "KUMA used CHANNEL ROAR.",
      "The hostile noise pattern broke apart.",
      "Enemy is SUPPRESSED."
    ],
    spriteSequence: ["ALERT", "APEX", "ATTACKING"]
  },
  PAWLOCK: {
    label: "PAWLOCK",
    description: "Pins the threat and applies containment.",
    status: "CONTAINED",
    text: [
      "KUMA used PAWLOCK.",
      "The threat was contained."
    ],
    spriteSequence: ["DEFENDING", "APEX", "VICTORY"]
  }
};

================================================================================
SPRITE SHEET RENDERING GUIDANCE
================================================================================

Preferred approach depends on the frontend.

Option 1: CSS background-position sprite rendering.

Use a fixed-size viewport element with the sprite sheet as a background image.

Concept:

.kuma-sprite {
  width: 96px;
  height: 96px;
  background-image: url("/assets/sprites/kuma-sprite-sheet.png");
  background-repeat: no-repeat;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  transform: scale(2);
  transform-origin: bottom left;
}

Each state gets a background position.

Example only:

.kuma-sprite.sentinel {
  background-position: -192px 0;
}

.kuma-sprite.honey {
  background-position: -288px 0;
}

.kuma-sprite.apex {
  background-position: -384px 0;
}

Do not assume these pixel offsets are correct.

Inspect the actual sprite sheet first.

Option 2: Atlas metadata.

Create a JSON config with real measured frame positions.

Example only:

{
  "frameWidth": 96,
  "frameHeight": 96,
  "kuma": {
    "HIBERNATING": { "x": 0, "y": 0 },
    "FORAGING": { "x": 96, "y": 0 },
    "SENTINEL": { "x": 192, "y": 0 },
    "HONEY": { "x": 288, "y": 0 },
    "APEX": { "x": 384, "y": 0 },
    "ALERT": { "x": 0, "y": 96 },
    "INVESTIGATING": { "x": 96, "y": 96 },
    "DEFENDING": { "x": 192, "y": 96 },
    "ATTACKING": { "x": 288, "y": 96 },
    "VICTORY": { "x": 384, "y": 96 }
  }
}

These are placeholder offsets.

Inspect the real sheet and correct the coordinates.

Do not accidentally render only Kuma’s ear and call it animation. That would be tragic and somehow still pass half of modern QA.

Pixel rendering rules:

Use:

image-rendering: pixelated;
image-rendering: crisp-edges;

Avoid:

- blur filters
- smooth scaling
- anti-aliased canvas scaling
- oversized bloom
- glossy effects

================================================================================
ANIMATION IMPLEMENTATION GUIDANCE
================================================================================

Use a deterministic state machine.

Recommended state flow:

idle
-> threat_flash
-> enemy_reveal
-> kuma_enter
-> battle_lock
-> ability_menu
-> ability_animating
-> ability_menu or resolved

Suggested phase durations:

threat_flash: 450ms
enemy_reveal: 850ms
kuma_enter: 850ms
battle_lock: 300ms

Respect reduced motion.

Reduced-motion users should still see:

- threat banner
- enemy
- Kuma
- threat details
- ability menu

They should not get aggressive flicker or strobing.

Suggested reduced motion CSS concept:

@media (prefers-reduced-motion: reduce) {
  .battle-intro *,
  .battle-intro {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

Avoid rapid flashing, aggressive strobing, or high-contrast repeated pulses.

Use:

- single flash
- brief scanline
- subtle shake
- cyan pulse

Avoid:

- rapid red/white flashes
- strobe effects
- long flicker loops
- screen-filling blinking overlays

================================================================================
SUGGESTED CSS ANIMATION CONCEPTS
================================================================================

Threat flash concept:

@keyframes kuma-threat-flash {
  0% {
    opacity: 0;
    transform: translateY(-4px);
  }
  35% {
    opacity: 1;
    transform: translateY(0);
  }
  100% {
    opacity: 1;
  }
}

Scanline sweep concept:

@keyframes kuma-scanline-sweep {
  0% {
    transform: translateY(-100%);
    opacity: 0;
  }
  20% {
    opacity: 0.75;
  }
  100% {
    transform: translateY(100%);
    opacity: 0;
  }
}

Enemy reveal concept:

@keyframes kuma-enemy-reveal {
  0% {
    opacity: 0;
    transform: translateX(28px) scale(0.96);
    filter: contrast(1.2);
  }
  40% {
    opacity: 0.65;
    transform: translateX(-4px) scale(1);
  }
  100% {
    opacity: 1;
    transform: translateX(0) scale(1);
    filter: none;
  }
}

Kuma enter concept:

@keyframes kuma-enter {
  0% {
    opacity: 0;
    transform: translateX(-28px) translateY(8px);
  }
  70% {
    opacity: 1;
    transform: translateX(4px) translateY(0);
  }
  100% {
    opacity: 1;
    transform: translateX(0) translateY(0);
  }
}

Sprite-sheet animation with steps() concept:

.kuma-ability-animation {
  animation: kuma-ability-frames 600ms steps(3, end) forwards;
}

@keyframes kuma-ability-frames {
  from {
    background-position-x: 0;
  }
  to {
    background-position-x: -288px;
  }
}

Only use steps() if the frames are arranged sequentially and evenly.

If the sheet is a grid with named cells, swap classes/states in code instead.

================================================================================
ACCESSIBILITY AND UX RULES
================================================================================

Text must stay readable.

Minimum requirements:

- Enemy name readable at handheld size.
- Threat level readable.
- Confidence readable.
- Ability labels readable.
- SSID/BSSID details should not overwhelm the screen.

Controls should support:

- keyboard
- mouse
- touch
- D-pad/buttons if handheld UI uses buttons

Expected controls:

Arrow keys / D-pad:
Move ability selection.

Enter / A:
Select ability.

Escape / B:
Exit encounter.

Mouse/touch:
Select ability.

Input should be locked during short ability animation playback to avoid state glitches.

================================================================================
BACKEND / API BEHAVIOR
================================================================================

Use the existing project pipeline:

802.11 frame
-> detector
-> scoring
-> SQLite
-> HTTP API
-> dashboard / handheld
-> battle intro UI

Do not invent a parallel event system.

Before implementing, inspect:

- docs/api.md
- docs/detection-logic.md
- docs/modes.md
- docs/architecture.md
- backend API routes
- dashboard polling code
- mock mode behavior
- static asset serving

Use the actual API structure.

KUMA supports mock mode:

KUMA_MOCK=1

In mock mode, provide a way to emit a HIGH threat battle test event.

Possible options:

1. Add a mock event to the existing mock event generator.
2. Add a dev-only UI button if dashboard already has a dev panel.
3. Add a test endpoint only if the project already uses dev/test endpoints.
4. Add a local fixture consumed by frontend tests.

Do not expose unsafe admin/test endpoints in production mode.

================================================================================
MANUAL TEST SCENARIO
================================================================================

Use this mock event:

{
  "event_id": "mock-evil-twin-001",
  "type": "evil_twin",
  "threat_level": "HIGH",
  "confidence": 0.91,
  "ssid": "Corp-WiFi",
  "bssid": "66:66:66:66:66:66",
  "channel": 6,
  "rssi": -42,
  "timestamp": "2026-06-07T12:00:00Z"
}

Expected battle intro:

ACTIVE THREAT IDENTIFIED
HOSTILE EVIL TWIN DETECTED
CONFIDENCE: 91%
THREAT: HIGH
KUMA STANDS WATCH

Expected UI after intro:

Enemy sprite:
EVIL TWIN

Kuma sprite:
SENTINEL or ALERT

Ability menu:

- SIGNAL MAUL
- HONEY SNARE
- CHANNEL ROAR
- PAWLOCK

Selecting SIGNAL MAUL should show:

KUMA used SIGNAL MAUL.
The hostile broadcast destabilized.

Expected status badge:

DESTABILIZED

Expected Kuma sprite sequence:

SENTINEL -> ATTACKING -> VICTORY

================================================================================
ACCEPTANCE CRITERIA
================================================================================

The work is done when:

1. A mock HIGH threat causes the battle intro to play.
2. The enemy displayed matches the detected threat type.
3. Kuma appears using existing sprite art.
4. The animation progresses through:
   - threat flash
   - enemy reveal
   - Kuma entrance
   - battle frame lock
   - ability menu
5. The four abilities appear exactly as:
   - SIGNAL MAUL
   - HONEY SNARE
   - CHANNEL ROAR
   - PAWLOCK
6. Selecting an ability plays the correct Kuma sprite sequence.
7. Ability selection applies the correct status:
   - SIGNAL MAUL -> DESTABILIZED
   - HONEY SNARE -> MARKED
   - CHANNEL ROAR -> SUPPRESSED
   - PAWLOCK -> CONTAINED
8. The UI remains readable on the dashboard target size.
9. The implementation does not break the existing dashboard/status view.
10. Same event does not replay endlessly.
11. Reduced-motion users still get a usable static transition.
12. Tests or manual verification steps are added.
13. Implementation does not introduce real RF attack logic unless an existing safe, legal, lab-gated Apex action path already exists.

================================================================================
SUGGESTED TEST CASES
================================================================================

Unit tests:

Threat-to-enemy mapping:

evil_twin -> EVIL TWIN
deauth -> DEAUTHER
beacon_flood -> BEACON FLOODER
unknown -> UNKNOWN THREAT

Ability metadata:

SIGNAL_MAUL -> DESTABILIZED
HONEY_SNARE -> MARKED
CHANNEL_ROAR -> SUPPRESSED
PAWLOCK -> CONTAINED

Trigger logic:

LOW threat does not trigger.
MEDIUM threat triggers.
HIGH threat triggers.
CRITICAL threat triggers.
Same event_id does not trigger twice.

UI tests:

Battle banner appears.
Enemy name appears.
Threat confidence appears.
Kuma appears.
Four ability buttons appear.
Ability selection updates text/status.
Escape exits to dashboard.

Manual test:

Run backend in mock mode:

cd backend
KUMA_MOCK=1 uvicorn kuma_api.app:app --host 0.0.0.0 --port 8080

Then open dashboard:

http://localhost:8080/

Trigger or wait for mock HIGH threat event.

Expected result:

Battle intro plays.
Ability menu appears.
No console errors.
Existing dashboard can be resumed.

================================================================================
DELIVERABLES FROM CLAUDE CODE
================================================================================

After implementation, Claude must report:

- Files changed
- New files added
- How to trigger battle intro in mock mode
- How to trigger from a real event
- Any assumptions made
- Any missing sprite coordinates/mappings
- Test results
- Known limitations

Do not accept a response that only says “I designed it.”

Implement the thing.

================================================================================
CLAUDE CODE RECOMMENDED ROOT PROMPT
================================================================================

Run Claude Code from the repository root and give it this prompt:

Read docs/design/battle-intro-animation.md, DESIGN.md, docs/api.md, docs/modes.md, docs/detection-logic.md, docs/architecture.md, and the current dashboard/frontend files.

Implement the KUMA battle intro animation exactly as specified.

Before coding:

1. Inspect the repo structure.
2. Identify the frontend/dashboard framework.
3. Identify how the dashboard polls status/events.
4. Identify the current API event shape.
5. Identify where bear mode/state is rendered.
6. Identify where static assets are served.
7. Identify the test setup.

Then implement:

1. A battle encounter state model.
2. Threat-to-enemy mapping.
3. Kuma ability metadata.
4. Battle intro animation component/screen.
5. Ability selection menu.
6. Sprite rendering using the existing Kuma and threat sprite sheets.
7. Mock-mode battle event support.
8. Tests or manual verification steps.

Do not stop after proposing a design. Implement it in the repo.

After implementation, report:

1. Files changed.
2. New files added.
3. How to trigger the battle intro in mock mode.
4. How to trigger it from a real event.
5. Any assumptions made.
6. Any missing sprite mappings that need correction.
7. Test results.

================================================================================
CLAUDE.MD PROJECT RULE
================================================================================

Add this to the repo root CLAUDE.md if it exists.

KUMA Battle UI Rule:

When implementing battle UI, do not reference or copy Pokémon directly. Use the abstract pattern: threat appears, enemy reveal, Kuma reveal, ability menu, selected ability animation.

Use existing KUMA sprites only. Do not invent new sprites unless explicitly marked as a placeholder fallback.

Keep language confidence-scored and non-attributional. Use “suspected,” “observed,” “detected,” and “confidence.” Avoid “confirmed attacker,” “hacker caught,” or “definitely malicious.”

Disruptive ability names are allowed as battle UI flavor. Do not implement real RF attack logic unless the existing repo already has a safe, legal, lab-gated Apex action system.

================================================================================
EXTERNAL REFERENCES
================================================================================

Use these as background references for implementation patterns.

Do not copy protected game UI.

Claude Code Quickstart:

https://code.claude.com/docs/en/quickstart

Why it matters:

Use this for how Claude Code runs from the terminal, how to start it in a repo, and how it works against project files.

Claude Code Memory / CLAUDE.md docs:

https://code.claude.com/docs/en/memory

Why it matters:

Use this for project-level CLAUDE.md guidance, persistent instructions, imports, and repo context.

Claude Code Best Practices:

https://code.claude.com/docs/en/best-practices

Why it matters:

Use this for writing better Claude Code prompts and managing larger implementation tasks.

Claude Code GitHub repo:

https://github.com/anthropics/claude-code

Why it matters:

Reference for Claude Code itself, install notes, and official repo context.

MDN CSS animation property:

https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/animation

Why it matters:

Reference for CSS animation shorthand, keyframes, duration, fill mode, and multiple animations.

MDN animation-timing-function / steps():

https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/animation-timing-function

Why it matters:

Reference for steps(), which is useful for sprite-sheet frame stepping.

MDN CSS image sprites:

https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_images/Implementing_image_sprites_in_CSS

Why it matters:

Reference for rendering one frame from a sprite sheet using background-position.

Sprite animation without canvas tutorial:

https://dev.to/polluterofminds/how-to-create-a-sprite-animation-without-canvas-57cg

Why it matters:

Shows a DOM/CSS/JS approach to sprite animation without Canvas. Useful if the dashboard is simple HTML/CSS/JS.

Sprite sheet animation tutorial video:

https://www.youtube.com/watch?v=ekI7vjkFrGA

Why it matters:

Walkthrough-style reference for animated sprite sheets in HTML/CSS/JS.

Useful search terms:

CSS sprite sheet animation steps background-position
JavaScript sprite sheet animation state machine
retro battle UI CSS animation
pixel art UI animation reduced motion
game encounter transition UI tutorial
HTML CSS JS sprite atlas animation

================================================================================
FINAL IMPLEMENTATION WARNING
================================================================================

Do not ask Claude Code to “make it like Pokémon.”

Use this wording instead:

Implement a retro creature-battle encounter pattern using KUMA’s original pixel-art assets, cyber defensive dashboard styling, confidence-scored threat language, and a four-ability battle menu.

That keeps the intent clear without turning the repo into IP-adjacent soup.
```