"""Apex Mode — automated active defense.

When the live detector flags a deauth_burst and Apex is armed (lab_mode +
apex_active_response in lab_targets.json), this orchestrates defensive
responses against the attack:

  - evidence   : record the attacker, frame count, channel, timestamp
  - harden_pmf : set the protected NetworkManager connection to PMF=required
                 so forged deauths are rejected (the real "don't get deauthed")
  - redirect   : fail the protected link over to a backup connection / band
  - contain    : dispatch a blacklist of the attacker MAC to a managed
                 AP/controller's API (the sanctioned device does enforcement)

It surfaces an `apex_response` event so the dashboard shows the defense firing.

Gates (ALL required): lab_mode == true, apex_active_response == true, the
detector run with --apex, the attacker not in protect_bssids, and a cooldown
between responses. harden_pmf/redirect touch the protected connection, so set
protected_connection/backup_connection and keep a separate management path
(ethernet) to avoid locking yourself out.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request

from kuma_core import database, events
from kuma_core.config import LAB_TARGETS_FILE


def _load_lab() -> dict:
    try:
        with LAB_TARGETS_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class ApexResponder:
    def __init__(self) -> None:
        self.cfg = _load_lab()
        self._last = 0.0

    def reload(self) -> None:
        self.cfg = _load_lab()

    def armed(self) -> bool:
        return bool(self.cfg.get("lab_mode")) and bool(
            self.cfg.get("apex_active_response")
        )

    def on_deauth(self, event: dict) -> dict | None:
        if not self.armed():
            return None
        if time.time() - self._last < self.cfg.get("response_cooldown", 30):
            return None
        attacker = (event.get("bssid") or "").upper()
        protect = {b.upper() for b in self.cfg.get("protect_bssids", [])}
        if not attacker or attacker in protect:
            return None  # never act against our own / protected gear
        self._last = time.time()

        resp = self.cfg.get("responses", {})
        actions: list[str] = []
        raw = event.get("raw_json") or {}
        actions.append(
            f"evidence: attacker {attacker}, {raw.get('frame_count', '?')} frames, "
            f"ch{event.get('channel')}"
        )
        if resp.get("harden_pmf"):
            actions.append(self._harden_pmf())
        if resp.get("redirect"):
            actions.append(self._redirect())
        if resp.get("contain"):
            actions.append(self._contain(attacker))

        msg = "APEX active defense -> " + "; ".join(a for a in actions if a)
        database.insert_action({
            "timestamp": event.get("timestamp"), "mode": "apex",
            "action": "apex_response", "target": attacker, "confirmed": 1,
            "result": "ok", "message": msg,
            "raw_json": {"actions": actions, "trigger": event.get("event_type")},
        })
        ev = events.make_event(
            mode="apex", event_type="apex_response", confidence=90, severity="high",
            message=msg, source="kuma", target=attacker, bssid=attacker,
            channel=event.get("channel"), raw_json={"actions": actions},
        )
        database.insert_event(ev)
        print("[apex] " + msg, flush=True)
        return ev

    # --- response actions (defensive only) --------------------------------
    def _harden_pmf(self) -> str:
        conn = self.cfg.get("protected_connection")
        if not conn:
            return "harden_pmf skipped (set protected_connection)"
        subprocess.run(
            ["nmcli", "connection", "modify", conn,
             "802-11-wireless-security.pmf", "2"], check=False)
        subprocess.run(["nmcli", "connection", "up", conn], check=False)
        return f"hardened PMF=required on '{conn}'"

    def _redirect(self) -> str:
        backup = self.cfg.get("backup_connection")
        if not backup:
            return "redirect skipped (set backup_connection)"
        subprocess.run(["nmcli", "connection", "up", backup], check=False)
        return f"redirected protected link to '{backup}'"

    def _contain(self, attacker: str) -> str:
        c = self.cfg.get("containment", {})
        url = c.get("blacklist_url")
        if not url:
            return f"containment dispatched (stub) for {attacker} — set containment.blacklist_url"
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
