"""Live 802.11 capture -> KUMA events (REAL detection, Sprint 2).

Runs as root (monitor-mode raw capture needs CAP_NET_RAW), sniffs a monitor
interface with scapy, and emits real events into the same SQLite DB the backend
serves. This is the passive, blue-team inverse of what Bruce/Pwnagotchi
transmit: we only ever *count* deauth/disassoc frames and score them.

Usage (on the Pi, as root, from backend/):
    sudo ./.venv/bin/python -m detectors.live_capture --iface wlan1 --channel 10

Honesty rule (see docs/detection-logic.md): MACs can be spoofed, so events say
"suspected" and confidence reflects burst strength, never source identity.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import subprocess
import threading
import time

from scapy.all import (  # type: ignore
    AsyncSniffer, Dot11, Dot11Deauth, Dot11Disas, Dot11Beacon, Dot11Elt,
    Dot11ProbeResp, EAPOL,
)

from detectors.responder import ApexResponder

# Updated by the channel-hopper thread; used to label events with where we were.
_current_channel = 0

from kuma_core import database, events, scoring
from kuma_core.config import settings

# Subtype 12 = deauthentication, 10 = disassociation.
WINDOW_SECONDS = 10
BURST_THRESHOLD = 8        # frames within WINDOW to call it a burst
COOLDOWN_SECONDS = 12      # min gap between emitted events (avoid event spam)


class BurstTracker:
    """Sliding-window counter for one management-frame type."""

    def __init__(self, event_type: str, label: str) -> None:
        self.event_type = event_type
        self.label = label
        self.times: collections.deque[float] = collections.deque()
        self.pairs: collections.Counter = collections.Counter()
        self.reasons: collections.Counter = collections.Counter()
        self.last_emit = 0.0

    def add(self, src: str, dst: str, reason: int | None) -> None:
        now = time.time()
        self.times.append(now)
        self.pairs[(src, dst)] += 1
        if reason is not None:
            self.reasons[reason] += 1
        self._prune(now)

    def _prune(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while self.times and self.times[0] < cutoff:
            self.times.popleft()

    def maybe_emit(self, channel: int) -> dict | None:
        now = time.time()
        self._prune(now)
        count = len(self.times)
        if count < BURST_THRESHOLD or now - self.last_emit < COOLDOWN_SECONDS:
            return None
        self.last_emit = now

        (top_pair, top_n) = (self.pairs.most_common(1) or [((None, None), 0)])[0]
        src, dst = top_pair
        # Confidence scales with how far past threshold + target repetition.
        conf = min(95, 40 + (count - BURST_THRESHOLD) * 3 + min(top_n, 20))
        # Severity floor: repeated frames at one target is the high-impact case.
        severity = "high" if top_n >= 15 else None
        reasons = [r for r, _ in self.reasons.most_common(3)]
        ev = events.make_event(
            mode="sentinel",
            event_type=self.event_type,
            confidence=conf,
            severity=severity,
            message=f"Suspected {self.label} burst on channel {channel} "
                    f"({count} frames/{WINDOW_SECONDS}s)",
            source=src or "unknown",
            target=dst or "unknown",
            bssid=src,
            channel=channel,
            raw_json={
                "window_seconds": WINDOW_SECONDS,
                "frame_count": count,
                "top_pair_count": top_n,
                "reason_codes": reasons,
                "detector": "live_capture",
            },
        )
        # Reset so the next window starts fresh after an emit.
        self.times.clear()
        self.pairs.clear()
        self.reasons.clear()
        return ev


class BeaconFloodTracker:
    """Detect beacon / fake-SSID floods (Bruce/Marauder/PineAP signature).

    Two passive signals over a rolling window:
      - a burst of NEW BSSIDs never seen before (spoofed-AP spam), or
      - a single BSSID advertising many distinct SSIDs (karma / SSID spam).
    Normal environments introduce only a handful of new BSSIDs per window, so a
    spike is a strong flood indicator. Confidence-scored, never absolute.
    """

    NEW_BSSID_THRESHOLD = 25     # new BSSIDs in the window
    SSIDS_PER_BSSID = 5          # distinct SSIDs from one radio
    WINDOW = 10
    COOLDOWN = 15

    def __init__(self) -> None:
        self.seen_bssids: set[str] = set()
        self.events: collections.deque[tuple[float, str, str]] = collections.deque()
        self.last_emit = 0.0

    def add(self, bssid: str, ssid: str) -> dict | None:
        now = time.time()
        self.seen_bssids.add(bssid)
        self.events.append((now, bssid, ssid))
        cutoff = now - self.WINDOW
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        if now - self.last_emit < self.COOLDOWN:
            return None

        window_bssids = {b for _, b, _ in self.events}
        # distinct SSIDs advertised per BSSID (karma / SSID-spam signal)
        per_bssid: dict[str, set[str]] = collections.defaultdict(set)
        for _, b, s in self.events:
            if s:
                per_bssid[b].add(s)
        max_ssids = max((len(v) for v in per_bssid.values()), default=0)
        worst_bssid = max(per_bssid, key=lambda k: len(per_bssid[k]), default=bssid)

        distinct_bssids = len(window_bssids)
        flood = distinct_bssids >= self.NEW_BSSID_THRESHOLD or max_ssids >= self.SSIDS_PER_BSSID
        if not flood:
            return None
        self.last_emit = now
        conf = scoring.clamp_confidence(
            40 + min(distinct_bssids, 50) + (max_ssids * 4))
        ev = events.make_event(
            mode="sentinel",
            event_type="beacon_flood",
            confidence=conf,
            message=f"Suspected beacon/SSID flood: {distinct_bssids} BSSIDs / "
                    f"{max_ssids} SSIDs-per-radio in {self.WINDOW}s",
            source=worst_bssid, bssid=worst_bssid,
            channel=_current_channel or None,
            raw_json={"distinct_bssids": distinct_bssids,
                      "max_ssids_one_bssid": max_ssids,
                      "window_seconds": self.WINDOW,
                      "detector": "beacon_flood"},
        )
        return ev


_RSN_ID = 48
_VENDOR_ID = 221
_SEC_RANK = {"OPEN": 0, "WEP": 1, "WPA": 2, "WPA2": 3,
             "WPA2/WPA3": 4, "WPA3": 5}


def beacon_security(pkt) -> str:
    """Best-effort security class from a beacon: OPEN / WEP / WPA / WPA2."""
    try:
        privacy = bool(pkt[Dot11Beacon].cap.privacy)
    except Exception:  # noqa: BLE001
        privacy = False
    has_rsn = has_wpa = False
    el = pkt.getlayer(Dot11Elt)
    while el is not None:
        eid = getattr(el, "ID", None)
        if eid == _RSN_ID:
            has_rsn = True
        elif eid == _VENDOR_ID:
            try:
                if bytes(el.info)[:4] == b"\x00\x50\xf2\x01":
                    has_wpa = True
            except Exception:  # noqa: BLE001
                pass
        el = el.payload.getlayer(Dot11Elt)
    if has_rsn:
        return "WPA2"
    if has_wpa:
        return "WPA"
    return "WEP" if privacy else "OPEN"


_VOLATILE_IE = {0, 5, 11, 35, 37, 42}   # ssid, tim, qbss-load, tpc, csa, erp


def beacon_fingerprint(pkt) -> str:
    """A stable hash of a beacon's 'shape' — capability flags, beacon interval,
    supported rates, the set of (non-volatile) IE IDs present, and vendor OUIs.

    Inspired by nzyme's AP fingerprinting (clean-room): a real AP and a clone
    spoofing its SSID/BSSID still produce different beacons (different rates,
    vendor elements, capabilities), so a fingerprint change on a trusted BSSID
    betrays impersonation that plain BSSID matching misses.
    """
    parts: list[str] = []
    try:
        parts.append("bi" + str(pkt[Dot11Beacon].beacon_interval))
    except Exception:  # noqa: BLE001
        pass
    try:
        parts.append("cap" + str(int(pkt[Dot11Beacon].cap)))
    except Exception:  # noqa: BLE001
        pass
    rates = ext = b""
    ie_ids: list[int] = []
    vendors: list[str] = []
    el = pkt.getlayer(Dot11Elt)
    while el is not None:
        eid = getattr(el, "ID", None)
        if eid is not None and eid not in _VOLATILE_IE:
            ie_ids.append(eid)
        try:
            if eid == 1:
                rates = bytes(el.info)
            elif eid == 50:
                ext = bytes(el.info)
            elif eid == 221:
                vendors.append(bytes(el.info)[:5].hex())
        except Exception:  # noqa: BLE001
            pass
        el = el.payload.getlayer(Dot11Elt)
    parts.append("ie" + ",".join(str(i) for i in sorted(set(ie_ids))))
    parts.append("r" + rates.hex() + ext.hex())
    parts.append("v" + ",".join(sorted(set(vendors))))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


class EvilTwinTracker:
    """Rogue-AP / evil-twin detection with nzyme-style AP fingerprinting.

    Three signals against the trusted baseline:
      - trusted SSID from a BSSID not in its set -> rogue (new_bssid)
      - + a security downgrade -> evil_twin
      - + (the strong one) a TRUSTED BSSID whose beacon FINGERPRINT changes ->
        BSSID-spoof / impersonation that survives BSSID matching.
    The good fingerprint per trusted BSSID is learned from the first stable
    observations (assumes a clean baseline environment).
    """

    COOLDOWN = 30
    LEARN_HITS = 5

    def __init__(self, trusted: list[dict]) -> None:
        self.trusted = {n["ssid"]: {b.upper() for b in n.get("bssids", [])}
                        for n in trusted}
        self.expected = {n["ssid"]: n.get("expected_security") for n in trusted}
        self.alerted: dict[tuple[str, str], float] = {}
        self.good_fp: dict[str, str] = {}
        self.fp_count: dict[str, collections.Counter] = collections.defaultdict(
            collections.Counter)

    def add(self, ssid, bssid, channel, security, fp="") -> dict | None:
        if not ssid or ssid not in self.trusted:
            return None
        bssid = (bssid or "").upper()
        now = time.time()

        # --- trusted BSSID: learn fingerprint, flag spoof ------------------
        if bssid in self.trusted[ssid]:
            if not fp:
                return None
            self.fp_count[bssid][fp] += 1
            if bssid not in self.good_fp:
                if self.fp_count[bssid][fp] >= self.LEARN_HITS:
                    self.good_fp[bssid] = fp   # established baseline
                return None
            if fp == self.good_fp[bssid]:
                return None
            key = (bssid, fp)
            if now - self.alerted.get(key, 0) < self.COOLDOWN:
                return None
            self.alerted[key] = now
            return events.make_event(
                mode="sentinel", event_type="evil_twin_suspected",
                confidence=88, severity="high",
                message=f"BSSID-SPOOF suspected: trusted AP {bssid} ('{ssid}') "
                        f"beacon fingerprint changed — impersonation",
                ssid=ssid, bssid=bssid, channel=channel, source=bssid,
                raw_json={"good_fp": self.good_fp[bssid], "seen_fp": fp,
                          "detector": "fingerprint"})

        # --- unknown BSSID for a trusted SSID ------------------------------
        key = (ssid, bssid)
        if not bssid or now - self.alerted.get(key, 0) < self.COOLDOWN:
            return None
        self.alerted[key] = now
        exp = self.expected.get(ssid)
        downgrade = bool(exp) and bool(security) and \
            _SEC_RANK.get(security, 99) < _SEC_RANK.get(exp, -1)
        if downgrade:
            etype, conf, sev = "evil_twin_suspected", 85, "high"
            msg = (f"Known SSID '{ssid}' from unknown BSSID {bssid} with "
                   f"security downgrade ({security} vs expected {exp})")
        else:
            etype, conf, sev = "new_bssid_for_known_ssid", 55, None
            msg = f"Known SSID '{ssid}' advertised by unknown BSSID {bssid}"
        return events.make_event(
            mode="sentinel", event_type=etype, confidence=conf, severity=sev,
            message=msg, ssid=ssid, bssid=bssid, channel=channel, source=bssid,
            raw_json={"security_seen": security, "security_expected": exp,
                      "fingerprint": fp, "detector": "evil_twin"})


class KarmaTracker:
    """Karma / PineAP detection: one BSSID answering probe requests for many
    different SSIDs. A legit AP only probe-responds for its own SSID(s); a
    karma radio impersonates whatever a client asks for, so a single source
    emitting probe responses for several distinct SSIDs is the tell.
    """

    SSIDS_THRESHOLD = 4
    WINDOW = 15
    COOLDOWN = 20

    def __init__(self) -> None:
        self.events: collections.deque[tuple[float, str, str]] = collections.deque()
        self.last_emit = 0.0

    def add(self, bssid: str, ssid: str) -> dict | None:
        if not ssid:
            return None
        now = time.time()
        self.events.append((now, bssid, ssid))
        cutoff = now - self.WINDOW
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        if now - self.last_emit < self.COOLDOWN:
            return None
        per_bssid: dict[str, set[str]] = collections.defaultdict(set)
        for _, b, s in self.events:
            per_bssid[b].add(s)
        worst = max(per_bssid, key=lambda k: len(per_bssid[k]), default=bssid)
        n = len(per_bssid.get(worst, set()))
        if n < self.SSIDS_THRESHOLD:
            return None
        self.last_emit = now
        return events.make_event(
            mode="sentinel", event_type="karma_suspected",
            confidence=scoring.clamp_confidence(50 + n * 6),
            severity="high" if n >= 8 else None,
            message=f"Suspected karma/PineAP: BSSID {worst} probe-responded for "
                    f"{n} distinct SSIDs in {self.WINDOW}s",
            source=worst, bssid=worst, channel=_current_channel or None,
            raw_json={"ssid_count": n, "ssids": sorted(per_bssid[worst])[:12],
                      "detector": "karma"})


class HandshakeHarvestTracker:
    """Detect WPA handshake harvesting: a spike of EAPOL (4-way handshake)
    frames, especially right after a deauth burst (deauth -> reconnect ->
    handshake captured). The passive signature of Pwnagotchi/hcxdumptool.
    """

    WINDOW = 15
    EAPOL_THRESHOLD = 6
    COOLDOWN = 20

    def __init__(self) -> None:
        self.times: collections.deque[float] = collections.deque()
        self.last_emit = 0.0
        self.recent_deauth = 0.0    # set by the deauth detector on a burst

    def add_eapol(self) -> dict | None:
        now = time.time()
        self.times.append(now)
        cutoff = now - self.WINDOW
        while self.times and self.times[0] < cutoff:
            self.times.popleft()
        if now - self.last_emit < self.COOLDOWN:
            return None
        count = len(self.times)
        if count < self.EAPOL_THRESHOLD:
            return None
        self.last_emit = now
        post_deauth = (now - self.recent_deauth) < 30
        return events.make_event(
            mode="sentinel", event_type="handshake_harvest_pattern",
            confidence=scoring.clamp_confidence(
                55 + min(count, 30) + (20 if post_deauth else 0)),
            severity="high" if post_deauth else None,
            message="EAPOL/4-way-handshake activity"
                    + (" right after a deauth burst (forced-handshake harvest)"
                       if post_deauth else f" ({count} EAPOL/{self.WINDOW}s)"),
            channel=_current_channel or None,
            raw_json={"eapol_count": count, "post_deauth": post_deauth,
                      "window_seconds": self.WINDOW, "detector": "handshake"})


def set_channel(iface: str, channel: int) -> None:
    global _current_channel
    subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)],
                   check=False)
    _current_channel = channel


def _hopper(iface: str, channels: list[int], dwell: float, stop: threading.Event) -> None:
    while not stop.is_set():
        for ch in channels:
            if stop.is_set():
                break
            set_channel(iface, ch)
            stop.wait(dwell)


def run(iface: str, channel: int, channels: list[int] | None,
        apex: bool = False) -> None:
    global _current_channel
    responder = ApexResponder() if apex else None
    if responder:
        print(f"[live_capture] Apex responder loaded (armed={responder.armed()})",
              flush=True)
    stop = threading.Event()
    hopper = None
    if channels:
        _current_channel = channels[0]
        hopper = threading.Thread(target=_hopper, args=(iface, channels, 0.35, stop),
                                  daemon=True)
        hopper.start()
        print(f"[live_capture] channel-hopping {channels} (0.35s dwell)", flush=True)
    elif channel:
        set_channel(iface, channel)
    deauth = BurstTracker("deauth_burst", "deauth")
    disassoc = BurstTracker("disassoc_burst", "disassoc")
    beacons = BeaconFloodTracker()
    eviltwin = EvilTwinTracker(settings.trusted_networks())
    karma = KarmaTracker()
    harvest = HandshakeHarvestTracker()

    def _emit(ev: dict | None) -> None:
        if not ev:
            return
        eid = database.insert_event(ev)
        print(f"[{ev['severity'].upper()}] {ev['event_type']} "
              f"conf={ev['confidence']} -> event #{eid}: {ev['message']}",
              flush=True)

    def handle(pkt) -> None:
        if not pkt.haslayer(Dot11):
            return
        # --- beacons: SSID flood + evil-twin/rogue-AP ---------------------
        if pkt.haslayer(Dot11Beacon):
            ssid = ""
            elt = pkt.getlayer(Dot11Elt)
            if elt is not None and getattr(elt, "ID", None) == 0:
                try:
                    ssid = bytes(elt.info).decode(errors="ignore")
                except Exception:  # noqa: BLE001
                    ssid = ""
            bssid = pkt[Dot11].addr2 or "?"
            ch = _current_channel or channel
            _emit(beacons.add(bssid, ssid))
            _emit(eviltwin.add(ssid, bssid, ch, beacon_security(pkt),
                               beacon_fingerprint(pkt)))
            return
        # --- probe responses: karma / PineAP ------------------------------
        if pkt.haslayer(Dot11ProbeResp):
            pssid = ""
            elt = pkt.getlayer(Dot11Elt)
            if elt is not None and getattr(elt, "ID", None) == 0:
                try:
                    pssid = bytes(elt.info).decode(errors="ignore")
                except Exception:  # noqa: BLE001
                    pssid = ""
            _emit(karma.add(pkt[Dot11].addr2 or "?", pssid))
            return
        # --- EAPOL: WPA handshake harvest ---------------------------------
        if pkt.haslayer(EAPOL):
            _emit(harvest.add_eapol())
            return
        tracker = None
        reason = None
        if pkt.haslayer(Dot11Deauth):
            tracker = deauth
            reason = getattr(pkt.getlayer(Dot11Deauth), "reason", None)
        elif pkt.haslayer(Dot11Disas):
            tracker = disassoc
            reason = getattr(pkt.getlayer(Dot11Disas), "reason", None)
        if tracker is None:
            return
        d = pkt[Dot11]
        tracker.add(d.addr2 or "?", d.addr1 or "?", reason)
        ev = tracker.maybe_emit(_current_channel or channel)
        if ev:
            _emit(ev)
            if ev["event_type"] == "deauth_burst":
                harvest.recent_deauth = time.time()   # link deauth -> harvest
            if responder:
                responder.on_deauth(ev)   # Apex active defense (gated)

    print(f"[live_capture] sniffing {iface} "
          f"(deauth/disassoc, window={WINDOW_SECONDS}s, thresh={BURST_THRESHOLD})",
          flush=True)
    database.init_db()
    sniffer = AsyncSniffer(iface=iface, prn=handle, store=False, monitor=True)
    sniffer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        sniffer.stop()
        print("[live_capture] stopped", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="KUMA live 802.11 deauth detector")
    ap.add_argument("--iface", default="wlan1")
    ap.add_argument("--channel", type=int, default=0,
                    help="lock to this channel (0 = leave as-is)")
    ap.add_argument("--hop", default="",
                    help="comma-separated channels to hop, e.g. 1,6,10,11")
    ap.add_argument("--apex", action="store_true",
                    help="enable Apex active-defense responses (gated by lab_mode)")
    args = ap.parse_args()
    channels = [int(c) for c in args.hop.split(",") if c.strip()] if args.hop else None
    run(args.iface, args.channel, channels, apex=args.apex)


if __name__ == "__main__":
    main()
