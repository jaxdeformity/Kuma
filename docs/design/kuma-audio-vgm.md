# KUMA Chiptune / VGM Audio System

## Integration decisions (2026-06-07)

- **Web Audio first, firmware port later.** Build the chiptune engine in the battle UI
  using the Web Audio API (oscillators: square / pulse via duty, triangle bass, noise
  buffer). Jax hears the real music in the browser battle demo now; the T-Deck (the
  eventual speaker target) isn't flashed yet (still has Bruce).
- **Shared, portable note data.** Songs/SFX are plain `SongPattern` / `NoteEvent` data
  (note name or Hz, durationMs, channel, volume, waveform, optional effect) in a JS module
  that mirrors the C++ struct in the spec below, so the ESP32 `AudioEngine` (LEDC/PWM) can
  consume the same patterns when the T-Deck is flashed. The web engine is the reference
  implementation; the firmware engine is the future port.
- **Scope (MVP):** the cues in "MINIMUM VIABLE IMPLEMENTATION" below: one original battle
  loop + the threat / lock-on / intro / victory stings + the 4 ability SFX + select/cancel,
  wired to the battle UI event hooks (encounter -> stings, ability menu -> loop, ability
  tap -> SFX + status cue, resolve -> stop loop + victory). Mute + volume control. Audio is
  non-blocking (Web Audio scheduler) and the battle UI never depends on audio working.
- **Original only.** Compose from the original E-minor note vocabulary in this doc; no
  copyrighted melodies, no Pokemon motifs. Syncs to the visual side in
  `battle-intro-animation.md`.

The rest of this document is the full audio context/spec (firmware-oriented; the web
engine implements the same cue set and note data).

---

# KUMA Chiptune / VGM Audio Context for Claude CLI

You are working on KUMA, an open-source DIY blue-team Wi-Fi defense gadget with a LilyGo T-Deck / ESP32-style handheld face.

Your task is to design and implement a lightweight original chiptune / VGM-style audio system for KUMA’s threat encounter and battle UI.

DO NOT copy Pokémon music.
DO NOT recreate Pokémon melodies, motifs, battle themes, encounter jingles, basslines, intervals, or recognizable rhythms.
DO NOT use copyrighted music or sampled audio.
DO NOT import Pokémon-like MIDIs or chiptune covers.
DO NOT write “make it sound like Pokémon” into the implementation.

Instead, create original music inspired by broad early handheld / 8-bit / 16-bit monster-battle VGM conventions:

- short looping battle music
- square-wave lead melody
- pulse-wave bass
- arpeggiated chords
- noise-channel percussion
- small encounter sting
- simple victory sting
- low CPU usage
- tiny-speaker friendly
- readable, memorable, original

The desired vibe is:

dark cyber bear defender + retro handheld battle screen + blue-team RF threat encounter

Not:

Nintendo clone
Pokémon clone
copyright problem with a speaker

================================================================================
PROJECT CONTEXT
================================================================================

KUMA is a defensive Wi-Fi monitoring gadget.

The visual UI has:

- dashboard idle state
- encounter animation when a threat is detected
- battle intro animation when enemy and Kuma enter
- battlefield screen with four abilities:
  - SIGNAL MAUL
  - HONEY SNARE
  - CHANNEL ROAR
  - PAWLOCK

The audio system should support these UI moments:

1. Dashboard ambient idle
2. Threat detected alert sting
3. Encounter lock-on sting
4. Battle intro sting
5. Battle loop music
6. Ability sound effects
7. Status effect sound effects
8. Victory / resolved sting
9. Critical threat escalation sting
10. Mute / volume control

The LilyGo T-Deck screen is small, and the device should stay lightweight. The audio must be simple, efficient, and not interfere with UI responsiveness or network polling.

================================================================================
IMPLEMENTATION GOAL
================================================================================

Implement a small original chiptune audio engine or audio event system suitable for the current firmware stack.

Before coding, inspect the repo to determine:

1. What firmware platform is used:
   - PlatformIO
   - Arduino framework
   - ESP-IDF
   - LVGL
   - TFT_eSPI
   - other

2. What hardware output is available:
   - built-in speaker
   - buzzer
   - DAC
   - I2S amp
   - PWM output
   - tone() support
   - LEDC PWM support

3. Whether the project already has:
   - audio code
   - button/input handling
   - config settings
   - UI event bus
   - mode state
   - battle state
   - alert events

Do not assume exact pins. Inspect the repo and hardware docs.

If no audio hardware is configured yet, implement the audio system behind a clean abstraction and leave pin configuration centralized.

================================================================================
AUDIO DESIGN PRINCIPLES
================================================================================

The music should be original, simple, and chiptune-like.

Use:

- square waves
- pulse waves
- simple triangle-like bass if available
- noise percussion if possible
- short arpeggios
- minor key or modal flavor
- simple battle loop
- short alert stingers
- tiny note arrays
- tempo-driven sequencer
- deterministic timing
- low memory

Avoid:

- sampled music files
- MP3 playback unless the project already supports it
- long WAV files
- complex synthesis
- high polyphony
- blocking delay() loops
- anything that freezes UI/network polling
- copyrighted melodies
- direct references to Pokémon tracks

Preferred approach:

Use procedural note sequencing rather than audio files.

Example architecture:

AudioEngine
-> plays SongPattern objects
-> plays SfxPattern objects
-> receives UI/game events
-> updates non-blockingly from loop/task/timer

================================================================================
AUDIO MOOD
================================================================================

KUMA’s audio identity:

- defensive
- alert
- cyber
- tactical
- slightly cute, but not goofy
- tense when a threat appears
- heroic when Kuma enters
- sharper and more urgent during Apex/high threat

Musical palette:

- root notes around E minor, F minor, or C minor
- square-wave lead
- low pulse bass
- short arpeggio ostinato
- noise tick percussion
- sparse because tiny speaker

Suggested original motif concept:

KUMA motif:
short rising minor pattern, then a firm drop

Example abstract contour:

low -> minor third up -> fourth up -> root down

Do not copy any known game melody. This is only a contour description.

================================================================================
AUDIO EVENTS
================================================================================

Implement named audio cues.

Required cues:

AUDIO_IDLE_PULSE
AUDIO_THREAT_DETECTED
AUDIO_LOCK_ON
AUDIO_ENCOUNTER_INITIATED
AUDIO_BATTLE_INTRO
AUDIO_BATTLE_LOOP
AUDIO_SIGNAL_MAUL
AUDIO_HONEY_SNARE
AUDIO_CHANNEL_ROAR
AUDIO_PAWLOCK
AUDIO_STATUS_MARKED
AUDIO_STATUS_SUPPRESSED
AUDIO_STATUS_CONTAINED
AUDIO_STATUS_DESTABILIZED
AUDIO_VICTORY
AUDIO_CRITICAL
AUDIO_CANCEL
AUDIO_SELECT

================================================================================
CUE DESIGN
================================================================================

AUDIO_IDLE_PULSE

Purpose:
Dashboard is online and calm.

Duration:
Very short pulse every few seconds, or optional low-volume ambient blip.

Sound:
soft low square-wave blip
1 or 2 notes only

Do not make this annoying. The device may sit on a desk for hours.

AUDIO_THREAT_DETECTED

Purpose:
Threat identified, encounter animation begins.

Duration:
300-700ms

Sound:
fast warning sting
minor interval
small noise hit

Mood:
“something is wrong”

AUDIO_LOCK_ON

Purpose:
KUMA is locking onto the hostile signal.

Duration:
400-800ms

Sound:
ascending arpeggio or repeated pulse
ends on tense note

Mood:
radar lock / signal acquisition

AUDIO_ENCOUNTER_INITIATED

Purpose:
Transition from dashboard warning into encounter mode.

Duration:
500-900ms

Sound:
short dramatic sting
low note hit + rising two-note phrase

Mood:
enemy incoming

AUDIO_BATTLE_INTRO

Purpose:
Enemy and Kuma enter battlefield.

Duration:
700-1200ms

Sound:
KUMA motif appears
small heroic rise
resolves into loop key

Mood:
Kuma steps in

AUDIO_BATTLE_LOOP

Purpose:
Main battle screen music while ability menu is active.

Duration:
Looping, 4 or 8 bars.

Sound:
square lead + pulse bass + noise percussion if supported

Requirements:
Must loop cleanly.
Must be original.
Must not sound like any specific existing game track.

Mood:
tense, playful, tactical, retro

AUDIO_SIGNAL_MAUL

Purpose:
Ability SFX for SIGNAL MAUL.

Sound:
quick slash-like ascending square sweep
tiny burst/noise hit

Mood:
direct hit / broadcast tear

AUDIO_HONEY_SNARE

Purpose:
Ability SFX for HONEY SNARE.

Sound:
two cute lure blips then a lock chirp

Mood:
bait placed / enemy marked

AUDIO_CHANNEL_ROAR

Purpose:
Ability SFX for CHANNEL ROAR.

Sound:
descending or expanding pulse
rapid low notes
noise rumble if possible

Mood:
area suppression / RF roar

AUDIO_PAWLOCK

Purpose:
Ability SFX for PAWLOCK.

Sound:
short click-click-lock tone
final low stable note

Mood:
containment applied

AUDIO_STATUS_MARKED

Sound:
bright two-note tag

AUDIO_STATUS_SUPPRESSED

Sound:
short muffled descending blip

AUDIO_STATUS_CONTAINED

Sound:
lock chirp

AUDIO_STATUS_DESTABILIZED

Sound:
glitchy uneven three-note wobble

AUDIO_VICTORY

Purpose:
Threat resolved.

Duration:
800-1500ms

Sound:
short original success sting
rising phrase
ends stable

Mood:
contained, not party music

AUDIO_CRITICAL

Purpose:
Critical threat escalation.

Duration:
300-700ms

Sound:
harsh low-high-low warning
red alert feel

Mood:
urgent

AUDIO_SELECT

Purpose:
Menu select.

Sound:
short bright click/blip

AUDIO_CANCEL

Purpose:
Back/cancel.

Sound:
short lower blip

================================================================================
BATTLE LOOP MUSIC SPEC
================================================================================

Create an original battle loop.

Constraints:

- 120-150 BPM
- 4/4 time
- 4 bars or 8 bars
- loops cleanly
- tiny speaker friendly
- no more than 2-3 simultaneous voices unless hardware supports more
- non-blocking playback
- can be disabled/muted
- low volume by default

Suggested channel model:

Channel 1:
square lead melody

Channel 2:
pulse bass / root movement

Channel 3:
arpeggio or counter melody, optional

Channel 4:
noise percussion, optional

If hardware only supports one voice:
Use prioritized monophonic playback:
1. SFX overrides music briefly
2. lead melody when music active
3. fake percussion with very short low/noise blips if possible

Original battle loop mood:

- tense cyber encounter
- bear defender steps forward
- minor key
- rhythmic but not too busy

Possible original note vocabulary:

Key: E minor or F minor
Scale: natural minor or pentatonic minor
Use notes like:
E, G, A, B, D
or
F, Ab, Bb, C, Eb

Do not use any recognizable melody from existing games.

================================================================================
EXAMPLE ORIGINAL MELODIC CONCEPTS
================================================================================

These are abstract starting points, not final copyrighted references.

Battle loop contour:

bar 1:
root pulse, minor third, fourth, fifth

bar 2:
repeat root pulse, flat seventh, fifth

bar 3:
short rising arpeggio

bar 4:
drop back to root and loop

Example in E minor as note names:

E4, G4, A4, B4
E4, D5, B4, A4
G4, A4, B4, D5
B4, A4, G4, E4

Rhythm:
short-short-long
short-short-long
eighth-note pulse
quarter-note landing

This is original guidance. Claude should compose a small original phrase and store it as note arrays.

Victory contour:

root -> minor third -> fifth -> octave -> fifth -> root

Example in E minor:

E4, G4, B4, E5, B4, E5

Threat detected contour:

octave jump down or tritone-like tension if acceptable

Example:

E5, Bb4, E4

If tritone sounds too harsh on tiny speaker, use:

E5, D5, E4

================================================================================
SUGGESTED DATA REPRESENTATION
================================================================================

Use simple note events.

Example structure:

NoteEvent:
- frequencyHz
- durationMs
- channel
- volume
- waveform
- rest boolean optional

Alternative structure:

NoteEvent:
- noteName
- octave
- durationMs
- channel
- volume
- waveform

A small note parser can map note names to frequency.

Example note names:

C4
C#4
D4
D#4
E4
F4
F#4
G4
G#4
A4
A#4
B4
REST

Example event:

{
  "note": "E4",
  "durationMs": 120,
  "channel": 0,
  "volume": 0.35,
  "waveform": "square"
}

================================================================================
SUGGESTED SONG PATTERN STRUCTURE
================================================================================

Use something like this, adapted to the actual firmware language:

SongPattern:
- id
- bpm
- loop
- tracks
- priority
- interruptible

Track:
- channel
- waveform
- events

AudioEvent:
- note
- duration
- volume
- dutyCycle optional
- effect optional

Possible effect values:

- none
- slide_up
- slide_down
- vibrato_light
- noise_hit
- arpeggio
- lock_click
- glitch

Keep effects simple.

================================================================================
SUGGESTED AUDIO ENGINE API
================================================================================

Create an audio manager with simple functions.

Required API concept:

audio.init()
audio.update()
audio.setMuted(bool)
audio.setVolume(uint8_t or float)
audio.playCue(AudioCue cue)
audio.playMusic(AudioTrack track, loop=true)
audio.stopMusic()
audio.pauseMusic()
audio.resumeMusic()
audio.isPlaying()

Battle/UI integration:

onDashboardIdle:
  optionally play AUDIO_IDLE_PULSE at low frequency

onThreatDetected:
  audio.playCue(AUDIO_THREAT_DETECTED)

onLockOn:
  audio.playCue(AUDIO_LOCK_ON)

onEncounterInitiated:
  audio.playCue(AUDIO_ENCOUNTER_INITIATED)

onBattleIntro:
  audio.playCue(AUDIO_BATTLE_INTRO)

onAbilityMenu:
  audio.playMusic(AUDIO_BATTLE_LOOP, loop=true)

onAbilitySelected(SIGNAL_MAUL):
  audio.playCue(AUDIO_SIGNAL_MAUL)

onStatusApplied(DESTABILIZED):
  audio.playCue(AUDIO_STATUS_DESTABILIZED)

onBattleResolved:
  audio.stopMusic()
  audio.playCue(AUDIO_VICTORY)

onCancel:
  audio.playCue(AUDIO_CANCEL)

onMenuMove/select:
  audio.playCue(AUDIO_SELECT)

================================================================================
NON-BLOCKING REQUIREMENT
================================================================================

Do not implement audio with blocking delay() calls that freeze the UI.

Bad:

play note
delay(200)
play next note
delay(200)

Good:

audio.update() advances notes based on millis() or a timer.

The UI loop must remain responsive.

Network polling must remain responsive.

Buttons must remain responsive.

If using FreeRTOS, audio can be a lightweight task, but avoid complexity unless the repo already uses that pattern.

================================================================================
ESP32 / LILIGO T-DECK IMPLEMENTATION OPTIONS
================================================================================

Inspect the repo first.

Possible implementation options:

1. PWM square-wave output using ESP32 LEDC.
2. Arduino tone()-style output if supported.
3. I2S audio if the board/project already has I2S speaker support.
4. Existing speaker library if already present.
5. No-op stub if audio hardware is disabled.

Preferred for simplicity:

- Use LEDC/PWM square wave if the hardware supports a speaker/buzzer pin.
- Implement note frequency changes and duty cycle.
- Keep it monophonic first.
- Add optional second channel only if easy and stable.

If the board has I2S speaker support already configured:

- Use the existing I2S path.
- Generate simple square/noise samples.
- Keep sample generation lightweight.

If audio output is uncertain:

- Create AudioEngine abstraction.
- Create SilentAudioBackend fallback.
- Create PWMBackend only when pin/config is known.
- Put pin config in a single config header/file.

================================================================================
CONFIG REQUIREMENTS
================================================================================

Add config options:

KUMA_AUDIO_ENABLED
KUMA_AUDIO_VOLUME
KUMA_AUDIO_PIN or board-specific output config
KUMA_AUDIO_BACKEND
KUMA_AUDIO_MUSIC_ENABLED
KUMA_AUDIO_SFX_ENABLED

Runtime UI/settings if practical:

- mute on/off
- volume low/medium/high
- music on/off
- SFX on/off

Default behavior:

- Audio enabled only if hardware config is known.
- Volume conservative by default.
- Music can be disabled.
- SFX should be short and not annoying.

================================================================================
AUDIO PRIORITY RULES
================================================================================

Audio priority:

1. Critical alert SFX
2. Ability SFX
3. Encounter / intro sting
4. Victory sting
5. Battle loop music
6. Idle pulse

Rules:

- SFX may temporarily duck or interrupt music.
- Critical alerts should override music.
- Menu blips should not restart the battle loop.
- Idle pulse should not play during battle music.
- Victory should stop battle loop first.

================================================================================
ABILITY AUDIO MAPPING
================================================================================

SIGNAL MAUL:
Cue: AUDIO_SIGNAL_MAUL
Status: DESTABILIZED
Sound: slash/sweep, short aggressive square-wave burst

HONEY SNARE:
Cue: AUDIO_HONEY_SNARE
Status: MARKED
Sound: bait chirp, tag lock, slightly playful

CHANNEL ROAR:
Cue: AUDIO_CHANNEL_ROAR
Status: SUPPRESSED
Sound: expanding low pulse, RF wave, broader and heavier

PAWLOCK:
Cue: AUDIO_PAWLOCK
Status: CONTAINED
Sound: click-click-lock, stable final tone

================================================================================
STATUS AUDIO MAPPING
================================================================================

MARKED:
Cue: AUDIO_STATUS_MARKED
Sound: bright tag chirp

SUPPRESSED:
Cue: AUDIO_STATUS_SUPPRESSED
Sound: dampened descending tone

CONTAINED:
Cue: AUDIO_STATUS_CONTAINED
Sound: lock chirp

DESTABILIZED:
Cue: AUDIO_STATUS_DESTABILIZED
Sound: unstable glitch wobble

================================================================================
FILE ORGANIZATION SUGGESTION
================================================================================

Adapt to actual repo structure.

Possible firmware files:

firmware/tdeck-ui/src/audio/AudioEngine.h
firmware/tdeck-ui/src/audio/AudioEngine.cpp
firmware/tdeck-ui/src/audio/AudioPatterns.h
firmware/tdeck-ui/src/audio/AudioPatterns.cpp
firmware/tdeck-ui/src/audio/AudioBackend.h
firmware/tdeck-ui/src/audio/PwmAudioBackend.h
firmware/tdeck-ui/src/audio/PwmAudioBackend.cpp
firmware/tdeck-ui/src/audio/SilentAudioBackend.h
firmware/tdeck-ui/src/audio/SilentAudioBackend.cpp

Possible config file:

firmware/tdeck-ui/include/audio_config.h

Possible UI integration:

firmware/tdeck-ui/src/ui/BattleScreen.cpp
firmware/tdeck-ui/src/ui/DashboardScreen.cpp
firmware/tdeck-ui/src/main.cpp

If the project does not use this structure, adapt to what exists.

================================================================================
MINIMUM VIABLE IMPLEMENTATION
================================================================================

The minimum acceptable implementation:

1. AudioEngine abstraction exists.
2. Mute/volume config exists.
3. Non-blocking playback exists.
4. At least these cues work:
   - AUDIO_THREAT_DETECTED
   - AUDIO_LOCK_ON
   - AUDIO_BATTLE_INTRO
   - AUDIO_BATTLE_LOOP
   - AUDIO_SIGNAL_MAUL
   - AUDIO_HONEY_SNARE
   - AUDIO_CHANNEL_ROAR
   - AUDIO_PAWLOCK
   - AUDIO_VICTORY
5. Battle loop is original and loops cleanly.
6. Ability selections trigger correct SFX.
7. Audio does not freeze UI.
8. No copyrighted melodies are used.

================================================================================
NICE-TO-HAVE IMPLEMENTATION
================================================================================

Nice-to-have features:

- Music ducking when SFX plays.
- Separate music and SFX volume.
- Tiny noise percussion channel.
- Different battle loop intensity for MEDIUM/HIGH/CRITICAL.
- Critical threat variation.
- Persistent mute setting.
- Button combo to mute.
- On-screen mute indicator.

================================================================================
BATTLE MUSIC VARIANTS
================================================================================

If time permits, implement three variants.

MEDIUM threat battle loop:
- slower
- sparse
- less percussion

HIGH threat battle loop:
- normal battle theme
- more active bass

CRITICAL threat battle loop:
- faster or denser
- warning pulse
- more dissonant

Do not make all three first if it delays the MVP.

MVP is one good original battle loop plus cue SFX.

================================================================================
EXAMPLE ORIGINAL NOTE PATTERNS
================================================================================

These are allowed as starting points because they are original generic note arrays.

Do not compare them to Pokémon.
Do not call them Pokémon-like in comments.

Use note names or convert to frequencies.

Threat detected sting:

E5 90ms
REST 40ms
D5 90ms
REST 40ms
E4 220ms

Lock-on sting:

E4 80ms
G4 80ms
B4 80ms
D5 80ms
E5 180ms

Encounter initiated:

E3 120ms
REST 40ms
B3 120ms
E4 180ms
D4 120ms
E4 240ms

Battle intro:

E4 100ms
G4 100ms
B4 100ms
E5 180ms
B4 100ms
D5 160ms
E5 260ms

Battle loop lead, 4 bars, E minor-ish:

Bar 1:
E4 120ms
G4 120ms
A4 120ms
B4 240ms
REST 120ms

Bar 2:
E4 120ms
D5 120ms
B4 120ms
A4 240ms
REST 120ms

Bar 3:
G4 120ms
A4 120ms
B4 120ms
D5 240ms
B4 120ms

Bar 4:
A4 120ms
G4 120ms
E4 120ms
B3 120ms
E4 360ms

Battle loop bass:

E2 240ms
E2 240ms
B2 240ms
E2 240ms

C3 240ms
C3 240ms
B2 240ms
E2 240ms

G2 240ms
G2 240ms
D3 240ms
G2 240ms

A2 240ms
B2 240ms
E2 480ms

Victory sting:

E4 120ms
G4 120ms
B4 120ms
E5 240ms
D5 120ms
E5 360ms

Signal Maul SFX:

E4 40ms
G4 40ms
B4 40ms
E5 80ms
noise_hit 60ms

Honey Snare SFX:

G4 80ms
E5 80ms
REST 50ms
B4 80ms
E5 160ms

Channel Roar SFX:

E3 80ms
E3 80ms
D3 80ms
B2 80ms
E2 220ms
noise_hit 100ms

Pawlock SFX:

C4 60ms
REST 40ms
C4 60ms
REST 40ms
E3 180ms

These patterns are placeholders. Claude may improve them, but must keep them original, short, and hardware-friendly.

================================================================================
CODE QUALITY REQUIREMENTS
================================================================================

Do:

- keep audio code isolated
- make it easy to disable
- avoid blocking delays
- add comments only where useful
- document how to change melodies
- document how to mute audio
- keep patterns readable
- make hardware config explicit

Do not:

- scatter tone calls all over UI code
- hardcode pins in multiple places
- create massive audio files
- use copyrighted music
- block the main loop
- make the battle UI dependent on audio working

================================================================================
TESTING REQUIREMENTS
================================================================================

Manual tests:

1. Boot with audio enabled.
2. Dashboard remains responsive.
3. Threat detected cue plays when mock HIGH event appears.
4. Lock-on cue plays during encounter animation.
5. Battle intro cue plays when sprites enter.
6. Battle loop starts at ability menu.
7. Ability selection plays correct SFX.
8. Victory cue plays when battle resolves.
9. Mute disables all audio.
10. Volume setting changes output level if supported.
11. UI does not lag during music.
12. Network/API polling still works.
13. Device does not crash if audio hardware unavailable.

If automated tests are possible:

- test cue mapping
- test pattern definitions exist
- test no blocking delays in AudioEngine update path
- test mute prevents playback calls
- test battle events call correct audio cues

================================================================================
CLAUDE CODE ROOT PROMPT
================================================================================

Run Claude Code from the repo root and give it this prompt:

Read docs/design/kuma-audio-vgm.md, docs/design/battle-intro-animation.md, DESIGN.md, docs/api.md, docs/modes.md, docs/detection-logic.md, docs/architecture.md, and the current firmware/dashboard files.

Implement an original lightweight chiptune/VGM-style audio system for KUMA’s encounter and battle UI.

Before coding:

1. Inspect the firmware framework.
2. Identify audio hardware support.
3. Identify existing config patterns.
4. Identify UI/battle event flow.
5. Identify where dashboard, encounter, battle intro, ability menu, and ability execution are implemented.
6. Identify whether audio should run in loop(), timer, task, or existing event/update system.

Then implement:

1. AudioEngine abstraction.
2. Hardware backend or silent fallback.
3. Original chiptune note patterns.
4. Event-to-audio cue mapping.
5. Battle loop music.
6. Ability SFX.
7. Mute/volume config.
8. Non-blocking playback.
9. Manual verification steps.

Do not copy Pokémon music.
Do not import copyrighted melodies.
Do not add blocking delay-based playback.
Do not implement offensive RF behavior.

After implementation, report:

1. Files changed.
2. Files added.
3. Audio backend selected.
4. Hardware assumptions.
5. How to enable/disable audio.
6. How to trigger each cue in mock mode.
7. Test results.
8. Known limitations.

================================================================================
FINAL DIRECTIVE
================================================================================

Create original KUMA battle audio.

The target is:

early handheld chiptune energy
+
cyber blue-team threat encounter
+
tiny bear defender battle screen

The target is NOT:

Pokémon music copied sideways with a fake mustache.

Implement it as a lightweight, non-blocking, original audio system that can run on the LilyGo T-Deck firmware without making the UI miserable.