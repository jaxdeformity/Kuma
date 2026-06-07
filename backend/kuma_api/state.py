"""Process-wide runtime state: the mode engine, uptime, and action handling.

Kept separate from routes.py so tests can drive the engine without spinning up
the HTTP app, and so the background mock loop and the routes share one engine
instance.
"""
from __future__ import annotations

import os
import subprocess
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


# --- real shell (driven from the T-Deck terminal) -----------------------
_shell_cwd = os.path.expanduser("~")


def run_shell(cmd: str) -> dict:
    """Run a command on the Pi and return its combined output + the live cwd.

    Persists cwd across calls and handles `cd` itself so the shell feels real.
    Guarded by a token at the route layer.
    """
    global _shell_cwd
    cmd = (cmd or "").strip()
    if not cmd:
        return {"out": "", "code": 0, "cwd": _shell_cwd}
    if cmd == "cd" or cmd.startswith("cd "):
        target = cmd[2:].strip() or os.path.expanduser("~")
        target = os.path.expanduser(target)
        newdir = target if os.path.isabs(target) else os.path.join(_shell_cwd, target)
        newdir = os.path.abspath(newdir)
        if os.path.isdir(newdir):
            _shell_cwd = newdir
            return {"out": "", "code": 0, "cwd": _shell_cwd}
        return {"out": f"cd: {target}: no such file or directory", "code": 1, "cwd": _shell_cwd}
    # block obviously-interactive commands that need a TTY (would just hang)
    first = cmd.split()[0] if cmd.split() else ""
    INTERACTIVE = {"top", "htop", "nano", "vi", "vim", "less", "more", "man",
                   "ssh", "telnet", "python", "python3", "watch"}
    if first in INTERACTIVE:
        return {"out": f"{first}: interactive command not supported in this shell "
                       f"(no TTY). Use a non-interactive form, e.g. piped output.",
                "code": 1, "cwd": _shell_cwd}
    try:
        print(f"[shell] cwd={_shell_cwd} cmd={cmd!r}", flush=True)   # visible in journalctl
        p = subprocess.run(cmd, shell=True, executable="/bin/bash", cwd=_shell_cwd,
                           capture_output=True, text=True, timeout=20)
        out = (p.stdout or "") + (p.stderr or "")
        print(f"[shell] -> code {p.returncode}, {len(out)} bytes", flush=True)
        return {"out": out[:6000], "code": p.returncode, "cwd": _shell_cwd}
    except subprocess.TimeoutExpired:
        return {"out": "(command timed out after 20s)", "code": 124, "cwd": _shell_cwd}
    except Exception as e:  # noqa: BLE001
        return {"out": f"(error: {e})", "code": 1, "cwd": _shell_cwd}


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
