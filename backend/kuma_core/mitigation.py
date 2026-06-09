"""Shared defensive mitigation engine.

The real, attack-appropriate blue-team actions KUMA can take against an attacker.
Pure and HTTP-free so both the automated ApexResponder and the manual
/api/mitigate endpoint share one implementation. Actions no-op gracefully when the
operator network config (protected_connection / backup_connection /
containment.blacklist_url) is unset, so manual mitigation is safe out of the box.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request

from kuma_core.config import LAB_TARGETS_FILE


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class MitigationEngine:
    def __init__(self, cfg: dict | None = None, gate=None) -> None:
        self.cfg = cfg if cfg is not None else _load_lab()
        self._gate = gate

    def canonical_for(self, event_type: str) -> str:
        """Strongest real defense for an attack type. Player always sees HARDEN;
        the engine picks the action from the triggering event's type."""
        e = (event_type or "").lower()
        if any(k in e for k in ("deauth", "disassoc", "handshake", "eapol")):
            return "harden+redirect"
        if any(k in e for k in ("rogue", "bssid", "twin", "pineapple", "karma")):
            return "contain"
        if any(k in e for k in ("beacon", "ssid", "botnet", "worm")):
            return "mark+contain"
        return "mark"   # sniffer / jammer / unknown -> nothing to block, mark + log

    # --- defensive action bodies (moved from ApexResponder) ----------------
    def harden_pmf(self) -> str:
        conn = self.cfg.get("protected_connection")
        if not conn:
            return "harden_pmf skipped (set protected_connection)"
        subprocess.run(
            ["nmcli", "connection", "modify", conn,
             "802-11-wireless-security.pmf", "2"], check=False)
        subprocess.run(["nmcli", "connection", "up", conn], check=False)
        return f"hardened PMF=required on '{conn}'"

    def redirect(self) -> str:
        backup = self.cfg.get("backup_connection")
        if not backup:
            return "redirect skipped (set backup_connection)"
        subprocess.run(["nmcli", "connection", "up", backup], check=False)
        return f"redirected protected link to '{backup}'"

    def contain(self, attacker: str) -> str:
        c = self.cfg.get("containment", {})
        url = c.get("blacklist_url")
        if not url:
            return f"containment dispatched (stub) for {attacker} - set containment.blacklist_url"
        try:
            payload = {"mac": attacker, **c.get("payload", {})}
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                method=c.get("method", "POST"),
                headers=c.get("headers", {"Content-Type": "application/json"}))
            urllib.request.urlopen(req, timeout=5)
            return f"containment: blacklisted {attacker} via controller"
        except Exception as e:  # noqa: BLE001
            return f"containment failed for {attacker}: {e}"

    def mark_hostile(self, attacker: str, evidence: str = "") -> str:
        gate = self._gate
        if gate is None:
            from kuma_core.authz import Gate
            gate = Gate()
        gate.auto_hostile_add(attacker, evidence or "battle mitigation")
        return f"marked {attacker} hostile"

    # --- orchestration -----------------------------------------------------
    def apply(self, attacker: str, event_type: str) -> dict:
        action = self.canonical_for(event_type)
        parts: list[str] = []
        if action == "harden+redirect":
            parts.append(self.harden_pmf())
            parts.append(self.redirect())
        elif action == "contain":
            parts.append(self.contain(attacker))
        elif action == "mark+contain":
            parts.append(self.mark_hostile(attacker, event_type))
            parts.append(self.contain(attacker))
        else:  # "mark"
            parts.append(self.mark_hostile(attacker, event_type))
        return {"action": action, "target": attacker, "result": "ok",
                "message": "; ".join(p for p in parts if p)}
