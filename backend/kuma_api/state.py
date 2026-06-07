"""Process-wide runtime state: the mode engine, uptime, and action handling.

Kept separate from routes.py so tests can drive the engine without spinning up
the HTTP app, and so the background mock loop and the routes share one engine
instance.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from kuma_core import database, scoring
from kuma_core.config import settings
from kuma_core.modes import ModeEngine

_START = time.monotonic()

# Single shared engine instance for the whole process.
engine = ModeEngine(current=settings.default_mode)


def uptime_seconds() -> int:
    return int(time.monotonic() - _START)


def bear_state() -> str:
    """Autonomous face, independent of the manual mode.

    Default is hibernate; when calm KUMA drifts between the ambient states
    (hibernate -> forage -> honey). As real threat events arrive only a few
    states surface - sentinel, then investigating - and it goes to alert right
    before an encounter. The mode engine still drives actions/posture; this is
    just the face shown on the dashboard + T-Deck.
    """
    t = threat_level()
    if t in ("high", "critical"):
        return "alert"            # about to engage
    if t == "medium":
        return "investigating"    # activity continuing
    if _recent_events():
        return "suspicious"       # sentinel: something noticed
    # calm: DEFAULT is hibernate, with the occasional forage (gentle idle life)
    return "foraging" if (int(time.time() // 6) % 5 == 0) else "sleeping"


def _recent_events() -> bool:
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return database.count_events_since(since) > 0


def threat_level() -> str:
    return scoring.threat_level_for(database.get_events(limit=50))


def run_action(action: str, target: str | None, confirm: bool):
    """Execute a Sprint-1-safe action. Returns (accepted, result, message)."""
    if action.startswith("enter_"):
        mode = action.removeprefix("enter_")
        if engine.is_valid(mode):
            engine.switch(mode)
            return True, "ok", f"entered {mode} mode"
        return False, "error", f"unknown mode: {mode}"

    if action == "acknowledge_alert":
        return True, "ok", "alert acknowledged"

    if action == "start_mock_capture":
        # Mock-only: the background loop already produces events.
        return True, "ok", "mock capture running"

    if action == "export_events":
        return True, "ok", "events available at data/events.jsonl"

    if action == "clear_mock_events":
        n = database.clear_events()
        return True, "ok", f"cleared {n} events"

    return False, "error", f"unhandled action: {action}"
