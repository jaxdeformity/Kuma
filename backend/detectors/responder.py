"""Apex Mode - automated active defense.

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
import time

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
        from kuma_core.mitigation import MitigationEngine
        self._engine = MitigationEngine(cfg=self.cfg)

    def reload(self) -> None:
        self.cfg = _load_lab()
        self._engine.cfg = self.cfg

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
        # Only respond to a SIGNIFICANT attack, not routine AP deauths.
        raw = event.get("raw_json") or {}
        min_frames = self.cfg.get("min_response_frames", 100)
        if event.get("severity") != "high" and raw.get("frame_count", 0) < min_frames:
            return None
        self._last = time.time()

        resp = self.cfg.get("responses", {})
        actions: list[str] = []
        raw = event.get("raw_json") or {}
        actions.append(
            f"evidence: attacker {attacker}, {raw.get('frame_count', '?')} frames, "
            f"ch{event.get('channel')}"
        )
        if resp.get("harden_pmf"):
            actions.append(self._engine.harden_pmf())
        if resp.get("redirect"):
            actions.append(self._engine.redirect())
        if resp.get("contain"):
            actions.append(self._engine.contain(attacker))

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

    # Defensive action bodies now live in kuma_core.mitigation.MitigationEngine,
    # shared with the manual /api/mitigate path. ApexResponder delegates via
    # self._engine (see on_deauth) and keeps only its automated-response gating.
