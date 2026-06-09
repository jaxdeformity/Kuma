# Kuroshuna Offensive Mode — Design Spec

Date: 2026-06-09
Status: approved (brainstorming) → ready for implementation plan
Owner: Jax

## Summary

Kuma is today a passive blue-team IDS. **Kuroshuna mode** is its active / "gloves-off"
tier: an on-device-armed state in which Kuma generates real offensive WiFi/RF and
network traffic to (a) hack-back confirmed hostiles and (b) validate Jax's own lab
defenses against both targeted and broadcast attacks. The Kuroshuna ("Dark Shuna")
sprite is the on-screen avatar for this state.

This is **lab tooling for authorized security testing on Jax's own equipment and
networks.** Default posture is unchanged (passive blue-team); every offensive
capability is off until deliberately armed.

## Authorization context

- All targets are equipment Jax owns or is explicitly authorized to test (his lab,
  his pwnagotchi/Bjorn attacker rigs, his APs, his subnet).
- Purpose: hack-back against confirmed hostiles + defensive resilience validation.
- Two operating tiers with different gating (below). Tier A is target-gated; Tier B
  (broadcast) cannot be target-gated by construction and is instead gated by an
  explicit lab+broadcast arm, time-boxing, and footprint limits.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │  authz gate  (backend/kuma_core/authz.py) │
                    │  single chokepoint + append-only audit    │
                    └───────────────┬───────────────────────────┘
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   Tier A targeted            Tier B broadcast            orchestrator
   (gate-bound)               (lab+bcast armed)           (auto loop)
        │                           │                           │
  ┌─────┴─────┐               ┌─────┴─────┐                     │
  │           │               │           │                     │
T-Deck      Pi/Alfa        T-Deck      Pi/Alfa        iterates authorized
(ESP32 RF)  (capture+LAN)  (ESP32 RF)  (Alfa RF)      target set, chains
                                                       recon→attack, cooldowns
        ▲                                                        │
        └──────── /api control + status ◄── Kuroshuna skin ──────┘
                                            (T-Deck face)
```

### Device split (split-by-strength)

| Capability | Device | Source technique |
|---|---|---|
| Targeted deauth (BSSID+client) | T-Deck ESP32 (own 2.4GHz radio) | Bruce "Target Deauth" |
| Passive packet monitor / sniffer | T-Deck ESP32 | Bruce RAW Sniffer |
| BLE scan | T-Deck ESP32 | Bruce BLE scan |
| Handshake + PMKID capture | Pi + Alfa (monitor/inject) | pwnagotchi (scapy/bettercap) |
| Targeted deauth/assoc → force handshake | Pi + Alfa | pwnagotchi |
| Network scan (nmap) | Pi (LAN) | Bjorn NetworkScanner |
| Multi-protocol brute-force (SSH/FTP/SMB/RDP/Telnet/SQL) | Pi (LAN) | Bjorn *Bruteforce modules |
| File/data steal (SSH/SQL) | Pi (LAN) | Bjorn StealFilesSSH / StealDataSQL |
| Broadcast deauth-flood | T-Deck ESP32 + Pi/Alfa | Bruce Deauth Flood |
| Beacon spam | T-Deck ESP32 | Bruce Beacon Spam |
| BLE advertisement spam | T-Deck ESP32 | Bruce BLE spam |
| Association / auth flood | Pi + Alfa | mdk-style |

Single-radio caveat (Alfa wlan1 RTL8821AU can't capture + inject on two channels at
once) is accepted; design tolerates 1 adapter now, uses a 2nd when Jax adds it.

## The authorization gate — `backend/kuma_core/authz.py`

Built **first**; every offensive action routes through it. Extends
`backend/config/lab_targets.json`.

Config additions:
```jsonc
{
  "lab_mode": false,
  "kuroshuna_armed": false,        // Tier A targeted arm
  "allow_broadcast": false,        // Tier B master enable (off by default)
  "broadcast_armed": false,        // Tier B live arm (on-device, transient)
  "approved_targets": [],          // MACs / IPs / CIDRs / BSSIDs Jax owns (allowlist)
  "protect_bssids": [],            // HARD DENY, always (Jax APs, Pi, Lily)
  "broadcast": {
    "channel": 6,                  // pin a single channel to bound footprint
    "max_tx_power_dbm": 5,         // cap power to bench range
    "max_burst_seconds": 30,       // time-box every broadcast run
    "honor_protect_bssids": true   // exclude protected SSIDs where form allows
  },
  "response_cooldown": 30
}
```

API:
- `is_authorized(target, action) -> (bool, reason)` — single chokepoint for Tier A.
  Denies anything not in `approved_targets` or the live auto-hostile set; always
  denies `protect_bssids` and Kuma's own infra (Pi/Lily/uplink MACs).
- `auto_hostile_add(mac, evidence)` — when a detector confirms a device is attacking
  a `protect_bssid`, it's added to a **session-scoped** allowlist (not persisted).
- `broadcast_allowed() -> (bool, reason)` — requires `lab_mode && allow_broadcast &&
  broadcast_armed`; enforces time-box + channel + power limits at dispatch.
- `audit(event)` — append-only JSONL log (`backend/data/kuroshuna_audit.jsonl`):
  every action, target, tier, channel, duration, timestamp, allow/deny + reason.

## Tier A — Targeted offense (gate-bound)

Every action takes a target, checks `is_authorized(target, action)`, logs, then runs.
- **RF (T-Deck + Pi/Alfa):** deauth a specific BSSID+client; assoc/deauth to force a
  handshake; capture PCAP/PMKID for an approved BSSID → `backend/data/handshakes/`.
- **Network (Pi):** nmap an approved host/CIDR → brute-force approved hosts across
  SSH/FTP/SMB/RDP/Telnet/SQL → steal files/data from approved hosts.
- Targets come from `approved_targets` (proactive/staged) **and** the live
  auto-hostile set (reactive counter-attack on confirmed attackers of `protect_bssids`).

## Tier B — Attack simulation (broadcast / non-targeted)

Indiscriminate by construction; used to prove defenses hold. No target gate — gated
by arm + footprint instead.
- **Capabilities:** deauth-flood (all clients on channel), beacon spam, BLE adv spam,
  assoc/auth flood.
- **Gating:** hard off unless `lab_mode && allow_broadcast && broadcast_armed`;
  on-device arm shows a "transmits to everything in radio range" confirm; **every burst
  is time-boxed** (`max_burst_seconds`, auto-stop); pinned to one channel; TX power
  capped to `max_tx_power_dbm`; `protect_bssids` excluded where the attack form permits
  (beacon SSIDs, targeted reassoc). Every burst is audited.
- **Operational note (documented in config):** these rails shrink but cannot contain
  the RF footprint; only physical isolation (low power + distance, or a shielded/
  attenuated setup) keeps broadcast attacks off non-lab gear. Running it is the lab
  owner's responsibility.

## Autonomous orchestrator — `backend/detectors/kuroshuna.py`

Bjorn/pwnagotchi-style loop, runs only while armed:
- Iterates the **authorized target set** (approved + auto-hostile) — never the open
  air — chaining recon → attack with `response_cooldown` between actions.
- Can drive Tier A continuously; can fire Tier B bursts only when broadcast is armed.
- Re-checks the gate before every action (config can be disarmed mid-loop → loop
  halts offense within one cooldown).
- Emits events to the existing event stream so the dashboard/`/api/status` reflect
  active engagement; surfaces on the T-Deck as Kuroshuna.

## Kuroshuna mode skin (T-Deck)

- Re-bake `designs/sprites/kuroshuna/apex_hackback.png` through the updated
  `gen_shuna.py` pipeline at **192px** (parity with the new per-sprite draw scale)
  → `KUROSHUNA_APEX` header.
- `kuma_ui.cpp` drawHome: when `kuroshuna_armed`, draw Kuroshuna + 黒シュナ wordmark +
  red/purple HUD treatment in place of Shuna.
- On-device **arm/disarm** control (the gloves-off switch); Tier B arm requires the
  extra broadcast confirm screen.
- `/api/status` carries `kuroshuna_armed` + `broadcast_armed` (schema + routes);
  firmware reads them.

## Reference material

Clone the three repos into a **gitignored** `reference/` dir for reading during
implementation:
- `evilsocket/pwnagotchi`, `infinition/Bjorn`, `pr3y/Bruce`.
Port the *techniques* into clean scoped modules — do **not** vendor their code
wholesale (would re-introduce un-gated broadcast paths and bloat). Add `reference/`
to `.gitignore`.

## Build order (phased; one spec, sequential phases)

0. **Mode skin + arm plumbing** — bake KUROSHUNA_APEX (192px), `/api/status` flags,
   HUD + wordmark, on-device arm/disarm + broadcast confirm. No offense yet; fully
   testable (sprite shows when armed, disarmed = unchanged).
1. **Authorization gate** — `authz.py`, config schema, `is_authorized`,
   `auto_hostile_add`, `broadcast_allowed`, audit log. Unit-tested in isolation.
2. **Tier A RF offense** — T-Deck targeted deauth + Pi/Alfa capture.
3. **Tier A network offense** — Bjorn-style scan/brute-force/steal, gate-checked.
4. **Tier B broadcast** — deauth-flood/beacon/BLE-spam/assoc-flood behind the
   broadcast arm + time-box + footprint limits.
5. **Orchestrator** — autonomous scoped loop driving Tier A (and Tier B when armed).

## Out of scope (for now)

- Vendoring the source repos' full code.
- Detection-evasion features aimed at third parties.
- 5GHz RF offense (Alfa regdom AE / hardware limits; revisit with 2nd adapter).
- Evil/captive-portal credential capture — deferred; revisit only as an explicit
  rogue-AP detection test, gated like Tier B, if Jax wants it later.

## Testing

- `authz.py`: unit tests for allow/deny matrix (approved, auto-hostile, protect_bssid,
  own-infra, broadcast arm states, time-box expiry).
- Tier A/B dispatch: dry-run mode (`--no-tx`) that exercises the full path and logs
  intended actions without transmitting, for CI + safe rehearsal.
- Mode skin: flash + on-device verify (arm → Kuroshuna + HUD; disarm → Shuna/Kuma).
- Live lab validation against Jax's own rigs, broadcast in a footprint-limited setup.
