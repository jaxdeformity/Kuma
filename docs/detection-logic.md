# KUMA Guard — Detection Logic

## The honesty rule

KUMA never asserts certainty. Every detection carries a **0–100 confidence** score and is phrased as *"suspected."* MAC addresses can be spoofed; an evil twin can look identical to the real AP. We surface signal and let the operator judge. This is the deliberate inversion of the offensive tools we studied: where they *act*, KUMA *observes and scores*.

## Confidence → severity

`backend/kuma_core/scoring.py`, thresholds in `kuma_settings.json`:

| confidence | severity |
|------------|----------|
| ≥ 90 | critical (reserved) |
| ≥ 75 | high |
| ≥ 50 | medium |
| ≥ 25 | low |
| < 25 | low |

Device `threat_level` = the worst severity among recent events.

## What is mock vs real (v0.0)

| Detector | Status | File |
|----------|--------|------|
| **mock_detector** | ✅ live (drives the demo) | `detectors/mock_detector.py` |
| wifi_forager | 🟡 skeleton | `detectors/wifi_forager.py` |
| deauth_detector | 🟡 skeleton | `detectors/deauth_detector.py` |
| rogue_ap_detector | 🟡 skeleton | `detectors/rogue_ap_detector.py` |
| evil_twin_detector | 🟡 skeleton | `detectors/evil_twin_detector.py` |

Mock events are tagged `raw_json.mock = true` so they can never be mistaken for real observations.

## Sentinel detections (Sprint 2 targets)

### Rogue AP / Evil twin (`rogue_ap_detector`, `evil_twin_detector`)

Compare observations against the trusted baseline:

| Signal | Direction |
|--------|-----------|
| same SSID + **unknown BSSID** | suspicious (medium) |
| same SSID + changed channel | low/medium |
| same SSID + **security downgrade** | high (severity pinned) |
| same SSID + suspicious RSSI jump | medium |
| unknown BSSID seen repeatedly | confidence climbs |
| known BSSID missing a long time | informational |

Event types: `new_bssid_for_known_ssid`, `ssid_drift`, `rogue_ap_suspected`, `evil_twin_suspected`, `security_downgrade_suspected`.

### Deauth / disassoc bursts (`deauth_detector`) — **passive only**

Count management frames in a time window; never transmit.

| severity | condition |
|----------|-----------|
| low | small burst, little/no target repetition |
| medium | repeated frames within window; repeated channel/BSSID |
| high | repeated frames at a known client/AP, or burst → EAPOL activity |
| critical | reserved |

Event types: `deauth_burst`, `disassoc_burst`, `handshake_harvest_pattern`.

## Implementation order (don't skip)

1. **mock_detector** — prove the pipeline (done).
2. **Passive Linux-tool observation** — `iw`/`nmcli` AP lists → `observations`.
3. **Baseline comparison** — rogue/evil-twin off the observation stream.
4. **scapy/tshark frame parsing** — deauth/disassoc, EAPOL counters — *only after the above works.*

> Do not block the project waiting for perfect packet parsing.

## Known false-positive risks

- Roaming clients and mesh/repeater APs legitimately advertise an SSID from multiple BSSIDs → `new_bssid_for_known_ssid` noise. Mitigate with the trusted baseline and vendor OUI hints.
- Captive-portal / guest networks change security posture legitimately.
- Spoofed MACs make source attribution unreliable by design — confidence reflects *repetition strength*, not identity.
