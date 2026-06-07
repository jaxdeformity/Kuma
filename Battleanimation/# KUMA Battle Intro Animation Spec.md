# KUMA Battle Intro Animation Spec

## Purpose

This document is the implementation reference for adding a battle-introduction animation to KUMA.

KUMA is an open-source, DIY, blue-team Wi-Fi defense gadget. It watches the RF environment, detects hostile Wi-Fi behavior, scores confidence, and displays the threat state through a pixel-bear mascot.

This feature adds a retro creature-battle-style encounter screen that triggers when an active Wi-Fi threat is identified.

Do **not** copy Pokémon directly. Do not copy UI, fonts, sounds, layouts, animations, text, or protected visual identity. Use only the abstract interaction pattern:

1. Active threat detected.
2. Screen shifts from monitoring dashboard into encounter mode.
3. Enemy threat appears.
4. Kuma appears.
5. Threat summary is shown.
6. Four ability buttons appear.
7. User selects a Kuma ability.
8. UI plays the appropriate ability animation and applies a battle status effect.

The intended result is a defensive RF encounter console with chunky pixel art, not a game clone. Yes, a bear SOC analyst battle UI. Humanity has earned this somehow.

---

# Project Context

## KUMA Concept

KUMA is the opposite of offensive pocket Wi-Fi tools.

Pwnagotchi, Bjorn, HashMonster, Bruce, and similar projects are pocket tools built around attacking or experimenting with wireless networks. KUMA is themed as a defensive counterpart.

KUMA sits on the network you want to protect, watches the air for suspicious activity, scores what it observes, and displays findings through a dashboard / handheld UI.

Original project rules:

- Detection and defense focused.
- Confidence scored, never absolute.
- Every detection should say “suspected,” “observed,” or “detected.”
- MAC addresses can be spoofed, so do not overclaim attribution.
- No disruptive RF in the real implementation unless an explicitly safe, legal, lab-gated module already exists.

For this battle UI feature, the abilities may use fantasy/disruptive language like “SIGNAL MAUL” or “CHANNEL ROAR,” but these are UI/game-state concepts unless the real project already exposes safe, gated Apex actions.

---

# Claude Code Usage Notes

## Recommended File Placement

Create this file in the repo as:

```text
docs/design/battle-intro-animation.md