# KUMA Guard — DESIGN.md

> The single source of truth for how KUMA looks and feels. Every surface — the
> web dashboard, the T-Deck handheld face, any future UI — must read like it
> came from the same instrument. AI agents and humans: read this before
> touching UI. (Format per [Google Stitch DESIGN.md](https://stitch.withgoogle.com/docs/design-md/overview/) /
> [awesome-design-md](https://github.com/VoltAgent/awesome-design-md); principles per
> [awesome-design-systems](https://github.com/alexpate/awesome-design-systems).)

## 1. Personality

KUMA is a **field instrument**, not a web app. Think threat-monitoring console,
oscilloscope, a piece of gear with a serial number — bolted together, honest,
a little industrial. It has one living element: a **pixel-art bear mascot** whose
mood is the at-a-glance status. The instrument is calm until something is wrong;
then it is unambiguous.

Three words: **instrument · honest · alert-when-it-matters.**

Voice: terse, technical, never breathless. Detections say *"suspected."* We
never overclaim ("BSSID-SPOOF suspected", not "ATTACKER FOUND"). The bear adds
warmth; the type stays flat and factual.

## 2. Hard rules (do / never)

**Do**
- Dark, near-black surfaces. Monospace everything. Hard edges.
- Corner-bracket framing on panels (`⌐ ¬` ticks), 1px hairline borders.
- Signal colors used **semantically only** (green=ok, amber=elevated, red=alert).
- Dense, scannable, top-anchored (logs grow downward, like a console).
- One living focal point: the bear. Everything else is readout.

**Never (the slop blacklist)**
- No rounded "cards", no soft drop-shadows, no glassmorphism.
- No purple/indigo gradients, no blue→purple anything.
- No centered hero, no 3-up icon-in-a-circle feature grid.
- No sidebar + logo + lucide-icon chrome. No emoji as UI.
- No default font stacks (Inter/Roboto/system) as the brand face.
- No decorative blobs, waves, or filler. Empty space is fine; fill it with data or leave it.

## 3. Color tokens

| Token | Hex | Use |
|-------|-----|-----|
| `--bg` | `#070a09` | page, near-black with a green cast |
| `--panel` | `#0c110f` | panel fills |
| `--faint` | `#2a322d` | hairline borders, dividers |
| `--dim` | `#566` | labels, secondary text |
| `--ink` | `#bfcabf` | body text |
| `--wht` | `#e8f0e8` | values, emphasis |
| `--grn` | `#46e07a` | OK / low / online |
| `--cyn` | `#3fd0d8` | mode / accents |
| `--amb` | `#f2a23c` | medium / elevated / counts |
| `--red` | `#ff4747` | high / critical / alert |

Bear fur tints with threat: brown `#9b7c52` (low) → amber-brown `#b0793b` (med)
→ red-brown `#bf563a` (high). Outline `#33271a`, snout `#e7e0cb`, nose `#19140f`.

CRT touch: a faint `repeating-linear-gradient` scanline overlay at ~50% opacity,
`mix-blend-mode: multiply`. Subtle, never distracting.

## 4. Typography

- Stack: `"JetBrains Mono","Cascadia Mono","SF Mono",ui-monospace,Consolas,monospace`. Monospace is the brand.
- Letter-spacing `.04em` body; wide tracking (`.3–.42em`) on UPPERCASE labels/wordmark.
- Sizes: 10px labels (tracked, dim, uppercase) · 12–13px body · 22–34px readouts (threat level). No more than ~4 sizes.
- Numbers: tabular. Threat level and counts are the loudest text.

## 5. Spacing & layout

- 4px base unit. Hairline (1px) borders, double-weight (2px) only under the header.
- Panels are rectangles with corner-bracket pseudo-elements. Never rounded.
- Grid: a left "viewport" (the bear) + a right readout column; a full-width
  defenses strip; a full-width event console below. Stacks to one column under 600px.
- `table-layout: fixed` for any log/table so long rows truncate, never overrun.

## 6. Components

- **Header strip** — wordmark `KUMA·GUARD`, version, sensor iface, live blip (green pulse = online, red = offline).
- **Bear viewport** — bordered, faint radial glow, the pixel bear centered, a dim state tag bottom-left.
- **Readout** — MODE (cyan, tracked), THREAT LEVEL label + big colored value, a 4-segment gauge, key/value rows (events/10m, uptime, sensor) on dotted dividers.
- **Defenses strip** — one cell per detector with a LED dot; green=armed, amber=hot (firing).
- **Apex banner** — red, flashing, only when active defense fires.
- **Event console** — grouped by type: a clickable summary row (caret · severity · type · `×count` amber badge · latest message), expanding to indented child rows (`└` connector) with timestamps. Newest first.

## 7. The bear (shared spec)

The bear is **algorithmic pixel art**, drawn the same way on the web canvas and
the T-Deck display so they match. Built from primitives (head disk, two ear
disks, snout ellipse, nose), a 1px outline traced around the fur mask, then
mood-specific eyes:

| `bear_state` | Eyes | When |
|--------------|------|------|
| `sleeping` | closed lines | Hibernate |
| `foraging` | dots + highlight | Foraging |
| `suspicious` | half-lidded | Sentinel, calm |
| `alert` | wide + red glint + angry brows | Sentinel, high threat |
| `honey_trap` | dots | Honey |
| `apex_ready` | dots | Apex |
| `error` | grey X | backend unreachable |

Crude-but-charming is the target. The pipeline matters more than the art, but
the art must never be a thing of nightmares.

## 8. Cross-surface

- **Web dashboard** (`backend/kuma_api/static/dashboard.html`) — the reference implementation of this system.
- **T-Deck handheld** (`firmware/tdeck-ui/`) — same palette, same bear, same readouts, rendered with LovyanGFX. It is a *control surface*, not just a display (see ROADMAP): mode switching, alert ack, event browsing, self-test.
- New surfaces inherit this file. If a choice isn't covered here, it should match the dashboard, then this doc gets updated.
