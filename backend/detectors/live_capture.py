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
import subprocess
import threading
import time

from scapy.all import AsyncSniffer, Dot11, Dot11Deauth, Dot11Disas  # type: ignore

from detectors.responder import ApexResponder

# Updated by the channel-hopper thread; used to label events with where we were.
_current_channel = 0

from kuma_core import database, events

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

    def handle(pkt) -> None:
        if not pkt.haslayer(Dot11):
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
            eid = database.insert_event(ev)
            print(f"[{ev['severity'].upper()}] {ev['event_type']} "
                  f"conf={ev['confidence']} -> event #{eid}: {ev['message']}",
                  flush=True)
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
