"""Shared defensive mitigation engine.

The real, attack-appropriate blue-team actions KUMA can take against an attacker.
Pure and HTTP-free so both the automated ApexResponder and the manual
/api/mitigate endpoint share one implementation.

ZERO-CONFIG BY DESIGN: every primary action targets what KUMA already has, so it
works on a fresh deploy with no operator setup:

  harden  -> auto-detect KUMA's active Wi-Fi connection and enable PMF (802.11w),
             which genuinely defeats deauth against KUMA's own link.
  avoid   -> pin that connection to the BSSID it is legitimately associated with,
             so KUMA won't roam onto an evil twin; plus mark the attacker hostile.
  mark    -> record the attacker as a confirmed hostile (+ the event log alerts).

Network-WIDE enforcement remains optional and config-gated (it needs infra KUMA
doesn't own): set backup_connection for failover (redirect) and
containment.blacklist_url for controller-side blacklisting (contain). Unset, the
zero-config actions above still fire. Self-protection is the deploy default; the
offensive counter (attacking the offender back) is the Shuna-unlocked tier, not here.
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

    # --- attack-type -> primary zero-config action -------------------------
    def canonical_for(self, event_type: str) -> str:
        e = (event_type or "").lower()
        if any(k in e for k in ("deauth", "disassoc", "handshake", "eapol")):
            return "harden"     # PMF self-harden defeats the deauth
        if any(k in e for k in ("rogue", "bssid", "twin", "pineapple", "karma")):
            return "avoid"      # pin to legit BSSID so we don't roam onto the twin
        return "mark"           # floods / sniffer / jammer / unknown -> mark + alert

    # --- auto-discovery (no config needed) ---------------------------------
    def _active_wifi_connection(self) -> str | None:
        """Name of KUMA's currently-active NetworkManager Wi-Fi connection."""
        try:
            out = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
                capture_output=True, text=True, timeout=4).stdout
        except Exception:  # noqa: BLE001 - nmcli absent / fails -> no auto target
            return None
        for line in out.splitlines():
            if "wireless" in line:
                return line.rsplit(":", 1)[0]
        return None

    def _active_bssid(self) -> str | None:
        """BSSID KUMA's Wi-Fi is currently (legitimately) associated with."""
        try:
            out = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,BSSID", "device", "wifi"],
                capture_output=True, text=True, timeout=4).stdout
        except Exception:  # noqa: BLE001
            return None
        for line in out.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].replace("\\:", ":")
        return None

    def _active_wifi_device(self) -> str | None:
        """Kernel device name (e.g. wlan0) of the active Wi-Fi connection."""
        try:
            out = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"],
                capture_output=True, text=True, timeout=4).stdout
        except Exception:  # noqa: BLE001
            return None
        for line in out.splitlines():
            if "wireless" in line:
                return line.rsplit(":", 1)[1]
        return None

    def _ap_supports_pmf(self) -> bool:
        """True iff the AP KUMA is associated with advertises 802.11w (MFP) in its
        RSN capabilities. Used to upgrade PMF to *required* only when it is SAFE --
        forcing required on a non-PMF AP would disconnect KUMA from its own network."""
        bssid = self._active_bssid()
        dev = self._active_wifi_device()
        if not bssid or not dev:
            return False
        try:
            out = subprocess.run(["iw", "dev", dev, "scan"],
                                 capture_output=True, text=True, timeout=12).stdout
        except Exception:  # noqa: BLE001 - iw absent / scan fails -> assume non-PMF
            return False
        in_bss = False
        for line in out.splitlines():
            low = line.strip().lower()
            if low.startswith("bss "):
                in_bss = bssid.lower() in low
            elif in_bss and "capabilities:" in low and (
                    "mfp-capable" in low or "mfp-required" in low):
                return True
        return False

    # --- defensive action bodies -------------------------------------------
    def harden_pmf(self) -> str:
        conn = self.cfg.get("protected_connection") or self._active_wifi_connection()
        if not conn:
            return "harden skipped (no active Wi-Fi connection)"
        # Capability-aware: require PMF only when the AP supports it (else optional),
        # so we never disconnect KUMA from a non-PMF AP. pmf_strict forces required.
        strict = bool(self.cfg.get("pmf_strict"))
        required = strict or self._ap_supports_pmf()
        pmf = "2" if required else "1"
        subprocess.run(
            ["nmcli", "connection", "modify", conn,
             "802-11-wireless-security.pmf", pmf], check=False)
        subprocess.run(["nmcli", "connection", "up", conn], check=False)
        level = "required" if required else "optional"
        return f"hardened PMF={level} on '{conn}'"

    def avoid(self, attacker: str) -> str:
        conn = self.cfg.get("protected_connection") or self._active_wifi_connection()
        if not conn:
            return "avoid skipped (no active Wi-Fi connection)"
        bssid = self._active_bssid()
        if not bssid:
            return f"avoid: could not read legit BSSID to pin (attacker {attacker})"
        subprocess.run(
            ["nmcli", "connection", "modify", conn,
             "802-11-wireless.bssid", bssid], check=False)
        return f"pinned '{conn}' to legit BSSID {bssid} (won't roam to twin)"

    def redirect(self) -> str:
        backup = self.cfg.get("backup_connection")
        if not backup:
            return ""   # optional upgrade; silent when unconfigured
        subprocess.run(["nmcli", "connection", "up", backup], check=False)
        return f"redirected protected link to '{backup}'"

    def contain(self, attacker: str) -> str:
        c = self.cfg.get("containment", {})
        url = c.get("blacklist_url")
        if not url:
            return ""   # optional upgrade; silent when unconfigured
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
        primary = self.canonical_for(event_type)
        labels: list[str] = []
        parts: list[str] = []

        def add(label: str, msg: str) -> None:
            if msg:
                labels.append(label)
                parts.append(msg)
            elif label in ("harden", "avoid", "mark"):
                labels.append(label)   # primary action always shows, even if skipped

        if primary == "harden":
            add("harden", self.harden_pmf())
            add("redirect", self.redirect())          # optional, silent if unset
        elif primary == "avoid":
            add("avoid", self.avoid(attacker))
            add("mark", self.mark_hostile(attacker, event_type))
            add("contain", self.contain(attacker))    # optional, silent if unset
        else:  # mark
            add("mark", self.mark_hostile(attacker, event_type))
            add("contain", self.contain(attacker))    # optional, silent if unset

        return {"action": "+".join(labels), "target": attacker, "result": "ok",
                "message": "; ".join(parts)}
