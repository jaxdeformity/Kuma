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
import logging
import re
from pathlib import Path

from kuma_core.config import DATA_DIR, LAB_TARGETS_FILE
from kuma_core.events import utcnow_iso

AUDIT_FILE = DATA_DIR / "kuroshuna_audit.jsonl"

# FIX 1: accept colon OR dash separators, case-insensitive
_MAC_RE = re.compile(r"^[0-9a-f]{2}([:\-][0-9a-f]{2}){5}$", re.IGNORECASE)

_log = logging.getLogger(__name__)


def _is_mac(t: str) -> bool:
    return bool(_MAC_RE.match(t))


def _norm(target: str) -> str:
    """Trim a target; canonicalize MACs to uppercase colon form, normalize IPs."""
    t = (target or "").strip()
    # FIX 1: canonicalize dash-or-colon MAC to uppercase colon form
    if _is_mac(t):
        return t.replace("-", ":").upper()
    # FIX 2: normalize IP/IPv6 through ipaddress so ::1 == 0:0:0:0:0:0:0:1
    try:
        return str(ipaddress.ip_address(t))
    except ValueError:
        return t


def _valid_target(entry: str) -> bool:
    """Return True if entry normalizes to a valid MAC or IP/CIDR; False otherwise."""
    t = _norm(entry)
    if _is_mac(t):
        return True
    try:
        ipaddress.ip_interface(t)   # bare IP or CIDR
        return True
    except ValueError:
        return False


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_lab(cfg: dict) -> None:
    """Persist the lab_targets config (atomic-ish: write then replace)."""
    tmp = LAB_TARGETS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(LAB_TARGETS_FILE)


class Gate:
    def __init__(self, config: dict | None = None,
                 audit_file: Path | None = None) -> None:
        self.cfg = config if config is not None else _load_lab()
        self.audit_file = audit_file or AUDIT_FILE
        # FIX 7: _auto_hostile is in-memory / session-scoped; cleared on process restart
        self._auto_hostile: set[str] = set()

    def reload(self) -> None:
        self.cfg = _load_lab()

    def armed(self) -> bool:
        return bool(self.cfg.get("lab_mode")) and bool(
            self.cfg.get("kuroshuna_armed"))

    def is_authorized(self, target: str, action: str) -> tuple[bool, str]:
        allowed, reason = self._decide(target, action)
        self.audit({"tier": "A", "action": action, "target": _norm(target),
                    "allowed": allowed, "reason": reason})
        return allowed, reason

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
        # FIX 3: skip invalid approved entries, warn on each skipped one
        approved = set()
        for a in self.cfg.get("approved_targets", []):
            if _valid_target(a):
                approved.add(_norm(a))
            else:
                _log.warning("ignoring invalid target entry: %r", a)
        if self._matches(t, approved):
            return True, "approved_targets allowlist"
        return False, "not in authorized set"

    def _protected(self) -> set[str]:
        # FIX 3: skip invalid protect/own-infra entries, warn on each skipped one
        prot: set[str] = set()
        for b in self.cfg.get("protect_bssids", []):
            if _valid_target(b):
                prot.add(_norm(b))
            else:
                _log.warning("ignoring invalid target entry: %r", b)
        for b in self.cfg.get("own_infra", []):
            if _valid_target(b):
                prot.add(_norm(b))
            else:
                _log.warning("ignoring invalid target entry: %r", b)
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
        """Check whether broadcast operations are permitted.

        FIX 7: broadcast_limits() values are advisory; callers MUST check
        broadcast_allowed() before acting — limits are not a gate by themselves.
        """
        if not self.cfg.get("lab_mode"):
            allowed, reason = False, "lab_mode off"
        elif not self.cfg.get("allow_broadcast"):
            allowed, reason = False, "allow_broadcast off"
        elif not self.cfg.get("broadcast_armed"):
            allowed, reason = False, "broadcast_armed off"
        else:
            allowed, reason = True, "broadcast armed"
        # FIX 6: audit every broadcast decision
        self.audit({"tier": "B", "action": "broadcast", "target": "*",
                    "allowed": allowed, "reason": reason})
        return allowed, reason

    def broadcast_limits(self) -> dict:
        """Return advisory broadcast operating limits.

        These values are advisory — callers MUST check broadcast_allowed() first
        before using any broadcast capability.
        """
        b = self.cfg.get("broadcast", {})
        return {
            "channel": b.get("channel", 6),
            "max_tx_power_dbm": b.get("max_tx_power_dbm", 5),
            "max_burst_seconds": b.get("max_burst_seconds", 30),
            "honor_protect_bssids": b.get("honor_protect_bssids", True),
        }

    def auto_hostile_add(self, target: str, evidence: str = "") -> bool:
        """Mark a target as a confirmed attacker for the session.

        Accepts any valid MAC or IP target. IP-layer attackers (e.g. SSH
        brute-forcers flagged by auth_watch) are legitimate auto-hostile targets.
        FIX 7: the auto-hostile set is in-memory / session-scoped (cleared on
        process restart).

        Returns True if the target was added, False if refused.
        """
        t = _norm(target)
        # FIX 5: reject truly invalid input (not just empty)
        if not t or not _valid_target(t):
            self.audit({"tier": "A", "action": "auto_hostile_add", "target": t,
                        "allowed": False, "reason": "refused: invalid target"})
            return False
        if self._matches(t, self._protected()):
            self.audit({"tier": "A", "action": "auto_hostile_add", "target": t,
                        "allowed": False, "reason": "refused: protected/own-infra"})
            return False
        self._auto_hostile.add(t)
        self.audit({"tier": "A", "action": "auto_hostile_add", "target": t,
                    "allowed": True, "reason": evidence or "confirmed attacker"})
        return True

    def audit(self, event: dict) -> None:
        rec = {"ts": utcnow_iso(), **event}
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        # FIX 4: audit failure is loud and re-raises — fail-closed
        try:
            with self.audit_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError as exc:
            _log.critical("AUDIT WRITE FAILED — record lost: %s | %s", rec, exc)
            raise
