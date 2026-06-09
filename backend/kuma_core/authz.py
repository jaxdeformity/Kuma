"""Kuroshuna authorization gate.

Single chokepoint between every offensive capability and every action. Default
posture is passive blue-team: nothing is authorized unless lab_mode + the
relevant arm are set, and even then only against Jax's authorized target set.
Protected BSSIDs and Kuma's own infrastructure are hard-denied, always.

  Tier A (targeted)  -> is_authorized(target, action)
  Tier B (broadcast) -> broadcast_allowed()   (no target; arm + footprint gated)

Every decision is written to an append-only JSONL audit log.
"""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path

from kuma_core.config import DATA_DIR, LAB_TARGETS_FILE
from kuma_core.events import utcnow_iso

AUDIT_FILE = DATA_DIR / "kuroshuna_audit.jsonl"
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _is_mac(t: str) -> bool:
    return bool(_MAC_RE.match(t.lower()))


def _norm(target: str) -> str:
    """Trim a target; upper-case MACs, leave IPs/CIDRs as-is."""
    t = (target or "").strip()
    return t.upper() if _is_mac(t) else t


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class Gate:
    def __init__(self, config: dict | None = None,
                 audit_file: Path | None = None) -> None:
        self.cfg = config if config is not None else _load_lab()
        self.audit_file = audit_file or AUDIT_FILE
        self._auto_hostile: set[str] = set()

    def reload(self) -> None:
        self.cfg = _load_lab()

    def armed(self) -> bool:
        return bool(self.cfg.get("lab_mode")) and bool(
            self.cfg.get("kuroshuna_armed"))

    def is_authorized(self, target: str, action: str) -> tuple[bool, str]:
        return self._decide(target, action)

    def _decide(self, target: str, action: str) -> tuple[bool, str]:
        if not self.armed():
            return False, "disarmed (need lab_mode + kuroshuna_armed)"
        t = _norm(target)
        if not t:
            return False, "empty target"
        if self._matches(t, self._protected()):
            return False, "protected/own-infra (hard deny)"
        if t in self._auto_hostile:
            return True, "auto-hostile (confirmed attacker)"
        approved = {_norm(a) for a in self.cfg.get("approved_targets", [])}
        if self._matches(t, approved):
            return True, "approved_targets allowlist"
        return False, "not in authorized set"

    def _protected(self) -> set[str]:
        prot = {_norm(b) for b in self.cfg.get("protect_bssids", [])}
        prot |= {_norm(b) for b in self.cfg.get("own_infra", [])}
        return prot

    def _matches(self, target: str, allow: set[str]) -> bool:
        if target in allow:
            return True
        if not _is_mac(target):
            try:
                ip = ipaddress.ip_address(target)
            except ValueError:
                return False
            for entry in allow:
                if "/" in entry:
                    try:
                        if ip in ipaddress.ip_network(entry, strict=False):
                            return True
                    except ValueError:
                        continue
        return False

    def broadcast_allowed(self) -> tuple[bool, str]:
        if not self.cfg.get("lab_mode"):
            return False, "lab_mode off"
        if not self.cfg.get("allow_broadcast"):
            return False, "allow_broadcast off"
        if not self.cfg.get("broadcast_armed"):
            return False, "broadcast_armed off"
        return True, "broadcast armed"

    def broadcast_limits(self) -> dict:
        b = self.cfg.get("broadcast", {})
        return {
            "channel": b.get("channel", 6),
            "max_tx_power_dbm": b.get("max_tx_power_dbm", 5),
            "max_burst_seconds": b.get("max_burst_seconds", 30),
            "honor_protect_bssids": b.get("honor_protect_bssids", True),
        }

    def auto_hostile_add(self, mac: str, evidence: str = "") -> bool:
        t = _norm(mac)
        if not t or self._matches(t, self._protected()):
            return False
        self._auto_hostile.add(t)
        return True

    def audit(self, event: dict) -> None:  # filled in Task 7
        pass
