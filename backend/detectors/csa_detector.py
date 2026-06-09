"""Channel Switch Announcement (CSA) attack detector — closes a KUMA blind spot.

THE GAP: KUMA's headline defense detects disconnection attacks by watching for
deauth/disassoc frames (BurstTracker). But a forged 802.11 **Channel Switch
Announcement** (CSA element, tag 37; or Extended CSA, tag 60) achieves the same
disconnection/redirection with NO deauth frame at all: an attacker injects a beacon
(or action frame) spoofing a real AP's BSSID and carrying a CSA that tells every
associated client to follow the AP to a new channel. The clients dutifully move to a
dead or attacker-controlled channel and drop off the real network. KUMA's radios
(Alfa RTL8821AU, ESP32) can perform this; KUMA could not SEE it — until now.

This is a real, under-detected evasion of deauth-based WIDS. This tracker flags:
  - CSA to an INVALID channel (0, or outside the real 2.4/5 GHz channel set)
  - CSA whose SSID matches a TRUSTED network (forged switch against your own AP)
  - a CSA STORM (many CSA frames in a short window = attack, not a one-off legit switch)
  - immediate forced switch (switch_count<=1 + mode=1) raises confidence

A single CSA to a VALID channel from a non-trusted AP is plausibly legitimate (APs do
switch channels), so it is NOT alerted on — zero-noise by design.
"""
from __future__ import annotations

import time
from collections import deque

from kuma_core import events

# Real Wi-Fi channels: 2.4 GHz (1-14) + common 5 GHz. A CSA pointing anywhere else
# is bogus — no real AP redirects clients to a non-existent channel.
_VALID_CH = set(range(1, 15)) | {
    36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128,
    132, 136, 140, 144, 149, 153, 157, 161, 165,
}


def parse_csa(pkt):
    """Extract (new_channel, switch_count, switch_mode) from a CSA (tag 37) or
    Extended CSA (tag 60) information element, or None if neither is present."""
    from scapy.all import Dot11Elt  # type: ignore
    el = pkt.getlayer(Dot11Elt)
    while el is not None:
        try:
            eid = getattr(el, "ID", None)
            info = bytes(el.info) if el.info else b""
            if eid == 37 and len(info) >= 3:            # Channel Switch Announcement
                return int(info[1]), int(info[2]), int(info[0])   # ch, count, mode
            if eid == 60 and len(info) >= 4:            # Extended CSA (mode, opclass, ch, count)
                return int(info[2]), int(info[3]), int(info[0])
        except Exception:  # noqa: BLE001
            pass
        el = el.payload.getlayer(Dot11Elt)
    return None


class CsaTracker:
    """Flags forged Channel Switch Announcement attacks. Stateless per-frame scoring
    plus a short sliding window to catch CSA storms."""

    def __init__(self, trusted: list[dict], window: float = 12.0, storm: int = 4) -> None:
        self.trusted_ssids = {
            (n.get("ssid") or "").strip() for n in trusted if n.get("ssid")
        }
        self.window = window
        self.storm = storm
        self._recent: deque = deque()   # timestamps of recent CSA frames

    def add(self, bssid: str, ssid: str, cur_channel, new_ch: int,
            switch_count: int, switch_mode: int) -> dict | None:
        now = time.time()
        self._recent.append(now)
        while self._recent and now - self._recent[0] > self.window:
            self._recent.popleft()
        storming = len(self._recent) >= self.storm

        reasons: list[str] = []
        conf = 0
        if new_ch not in _VALID_CH:
            reasons.append(f"switch to INVALID channel {new_ch}")
            conf = max(conf, 90)
        if ssid and ssid in self.trusted_ssids:
            reasons.append(f"forged CSA spoofing trusted SSID '{ssid}'")
            conf = max(conf, 92)
        if storming:
            reasons.append(f"CSA storm ({len(self._recent)} in {int(self.window)}s)")
            conf = max(conf, 85)
        if switch_count <= 1 and switch_mode == 1 and reasons:
            reasons.append("immediate forced switch (count<=1, mode=1)")
            conf = min(99, conf + 5)

        if not reasons:
            return None   # lone CSA to a valid, non-trusted channel -> plausibly legit
        return events.make_event(
            mode="sentinel", event_type="csa_attack",
            confidence=conf, severity="high",
            message=("Suspected CSA channel-switch attack (silent deauth): "
                     + "; ".join(reasons)
                     + f" [BSSID {bssid} '{ssid}' -> ch{new_ch}]"),
            source=bssid, bssid=bssid, ssid=ssid or None, channel=cur_channel,
            raw_json={"new_channel": new_ch, "switch_count": switch_count,
                      "switch_mode": switch_mode, "reasons": reasons})
