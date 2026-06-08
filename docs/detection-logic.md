# KUMA - Detection Logic

## The honesty rule

KUMA never asserts certainty. Every detection carries a **0-100 confidence** score and is phrased as *"suspected."* MAC addresses can be spoofed; an evil twin can look identical to the real AP. We surface signal and let the operator judge. This is the deliberate inversion of the offensive tools we studied (Bjorn, Pwnagotchi, Bruce, the WiFi Pineapple): where they *act*, KUMA *observes, scores, and defends*.

## Confidence → severity

`backend/kuma_core/scoring.py`, thresholds in `kuma_settings.json`:

| confidence | severity |
|------------|----------|
| ≥ 90 | critical |
| ≥ 75 | high |
| ≥ 50 | medium |
| ≥ 25 | low |
| < 25 | low |

Device `threat_level` = the worst severity among recent events.

## Live detectors

All real detection runs in **`detectors/live_capture.py`** - a scapy monitor-mode sniffer that runs as a root systemd service (`kuma-capture`) on the Pi's USB Wi-Fi dongle and writes events into the same SQLite DB the API/dashboard read. Passive RX only - KUMA never transmits attack frames.

| Detector | Event type(s) | Signature |
|----------|---------------|-----------|
| **Deauth / disassoc burst** | `deauth_burst`, `disassoc_burst` | sliding-window count of deauth/disassoc frames over threshold; severity scales with volume + target repetition |
| **Beacon / SSID flood** | `beacon_flood` | anomalous count of distinct BSSIDs on one channel, or one BSSID advertising many SSIDs (Marauder/PineAP/Bruce spam) |
| **Rogue AP** | `new_bssid_for_known_ssid` | a trusted SSID advertised by a BSSID not in its baseline |
| **Evil twin** | `evil_twin_suspected` | rogue AP **+** a security downgrade, **or** a fingerprint mismatch (see below) |
| **Karma / PineAP** | `karma_suspected` | one BSSID probe-responding for many distinct SSIDs (a real AP only answers for its own) |
| **Handshake harvest** | `handshake_harvest_pattern` | EAPOL (4-way handshake) spike, escalated to high when it follows a deauth burst within 30s (Pwnagotchi/hcxdumptool pattern) |
| **Apex response** | `apex_response` | KUMA's own automated active defense fired (see Apex below) |

The skeleton modules `deauth_detector.py` / `rogue_ap_detector.py` / `evil_twin_detector.py` remain as the documented single-purpose reference implementations; `live_capture.py` is the integrated, deployed detector. `mock_detector.py` drives the hardware-free demo (`KUMA_MOCK=1`); mock events are tagged `raw_json.mock=true`.

## AP fingerprinting (evil-twin that survives BSSID spoofing)

Plain BSSID matching fails when an attacker spoofs the trusted BSSID. KUMA also builds a **stable fingerprint** of each beacon - supported rates, extended rates, the RSN (security) element, and vendor OUIs. These are fixed by the AP's config/hardware, so a real AP produces one fingerprint while a clone (different driver/hostapd) produces a different one.

KUMA learns the good fingerprint of each trusted BSSID, then flags a **fingerprint change on a trusted BSSID** as impersonation (`evil_twin_suspected`, high) - catching clones that match the BSSID exactly.

> Methodology inspired by [nzyme](https://github.com/nzymedefense/nzyme) (which is SSPL-licensed - KUMA uses the *technique*, not its code; our implementation is clean-room and MIT).
>
> **Lesson learned the hard way:** the fingerprint must use only *stable* fields (an early version included capability flags / beacon interval / the full IE set, which toggle on real APs and produced a false-positive storm). And even stable-field exact-hash fingerprinting is **too noisy on a real multi-radio router** - a radio that beacons rarely on the watched channel never learns its variants and false-alarms (in red-vs-blue testing it caught the real spoof but buried it 13:2 under false positives on a legit router radio). So **fingerprint-spoof detection is OPT-IN, off by default** (`fingerprint_detection` in `kuma_settings.json`). Robust clone detection really wants signal-track scoring (nzyme's approach), not exact hashes. The reliable detectors - deauth, beacon flood, rogue-AP, evil-twin-via-downgrade, karma, handshake - stay on and trustworthy.

## Apex Mode - automated active **defense**

`detectors/responder.py`. When a significant `deauth_burst` fires and Apex is armed (`lab_targets.json`: `lab_mode=true` + `apex_active_response=true`, detector run with `--apex`), KUMA orchestrates **defensive** responses and emits an `apex_response` event:

- **evidence** - log the attacker MAC, frame count, channel
- **harden_pmf** - set the protected connection to PMF-required (forged deauths get rejected - the real "don't get deauthed")
- **redirect** - fail the protected link over to a backup connection / band
- **contain** - POST the attacker MAC to a managed AP/controller's blacklist API (the sanctioned device does enforcement)

Hard gates: never acts against `protect_bssids` (your own gear), only on high-severity / high-volume bursts, with a cooldown. **KUMA never transmits deauth/jamming** - active *defense*, not counter-attack. That's an explicit non-goal (see README).

## Known false-positive risks

- **Multi-band / mesh routers** legitimately advertise one SSID from several BSSIDs → `new_bssid_for_known_ssid` noise. Mitigate by adding all of your AP's BSSIDs to `trusted_networks.json` (the Foraging → trusted workflow).
- **Fingerprint drift** - see the lesson above; keep the fingerprint to stable fields.
- **Routine AP deauths** - APs send deauths during normal operation; Apex only responds to significant bursts and never to `protect_bssids`.
- **Spoofed MACs** make source attribution unreliable by design - confidence reflects *repetition / fingerprint strength*, not identity.

## Channel strategy

The dongle captures on one channel at a time. KUMA locks to the protected network's channel by default (the `--channel` flag on `kuma-capture`); `--hop` cycles channels for broader coverage at the cost of lower per-channel frame counts. The Realtek WN722N v2/v3 does monitor RX fine once NetworkManager is told to leave it alone (`unmanaged-devices`).

### Coverage limits (be honest about the blind spots)

KUMA only sees what reaches the radio on the channel it is tuned to. Two real blind spots, both *physics, not bugs*:

- **2.4 GHz only.** The WN722N v2/v3 (RTL8188EUS) is a 2.4 GHz radio. **It cannot see any 5 GHz traffic at all** - a deauth/evil-twin/flood against a 5 GHz AP is completely invisible. Confirmed the hard way: a manual `aireplay-ng` deauth against a 5 GHz target produced zero events because the frames never hit the dongle. For 5 GHz coverage you need a 5 GHz-capable monitor NIC (and even then, one band/channel at a time unless you run a second radio).
- **One channel at a time.** Locked mode is deaf on every channel except the one watched; auto-channel routers can also drift off the pinned channel. `--hop` widens coverage but dilutes per-channel frame counts (a short low-volume burst can fall entirely between dwells).

Diagnostic when an attack isn't caught: run `sudo tcpdump -i wlan1 -e -n type mgt subtype deauth` during the attack. Frames in tcpdump but no KUMA event = software bug. No frames = wrong channel/band (the frames never reached the radio).
