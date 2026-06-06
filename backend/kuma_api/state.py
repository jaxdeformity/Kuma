"""Process-wide runtime state: the mode engine, uptime, and action handling.

Kept separate from routes.py so tests can drive the engine without spinning up
the HTTP app, and so the background mock loop and the routes share one engine
instance.
"""
from __future__ import annotations

import time

from kuma_core import database, scoring
from kuma_core.config import settings
from kuma_core.modes import ModeEngine

_START = time.monotonic()

# Single shared engine instance for the whole process.
engine = ModeEngine(current=settings.default_mode)


def uptime_seconds() -> int:
    return int(time.monotonic() - _START)


def bear_state() -> str:
    """The face. Sentinel escalates to 'alert' when the threat is high+."""
    base = engine.bear_state()
    if engine.current == "sentinel" and threat_level() in ("high", "critical"):
        return "alert"
    return base


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
