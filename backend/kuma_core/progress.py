"""KUMA leveling / EXP.

Gamifies network mapping: discovering and connecting to networks (and winning
battles) earns XP, which raises KUMA's level. The rule set Jax specified:

    30 XP = 1 level
    discover a NEW network  ->  1 XP   (1/30 of a level)
    connect to a NEW network -> 30 XP   (a full level)
    win a battle             -> 10 XP   (configurable)
    level = 1 + floor(total_xp / 30), capped at 99

XP is persisted in the settings table (key 'kuma_xp') so it survives restarts.
Future: milestone levels unlock an evolved KUMA sprite (see EVOLUTIONS hook).
"""
from __future__ import annotations

from kuma_core import database

XP_PER_LEVEL = 30
MAX_LEVEL = 99
MAX_XP = (MAX_LEVEL - 1) * XP_PER_LEVEL  # level 1 @ 0 xp ... level 99 @ 2940 xp
REWARDS = {"discover": 1, "connect": 30, "battle_win": 10}

# level threshold -> evolved sprite set (filled when Jax provides the art sheet).
# spriteSetFor(level) returns the highest unlocked set; default 'states'.
EVOLUTIONS: list[tuple[int, str]] = [(1, "states")]

_XP_KEY = "kuma_xp"


def level_for(xp: int) -> int:
    return min(MAX_LEVEL, 1 + int(xp) // XP_PER_LEVEL)


def _get_xp() -> int:
    raw = database.get_setting(_XP_KEY)
    try:
        return max(0, min(MAX_XP, int(raw)))
    except (TypeError, ValueError):
        return 0


def add_xp(amount: int, reason: str = "") -> dict:
    xp = min(MAX_XP, _get_xp() + max(0, int(amount)))
    database.set_setting(_XP_KEY, str(xp))
    return get_progress()


def award(reason: str) -> dict:
    """Award the XP for a named event ('discover'|'connect'|'battle_win')."""
    return add_xp(REWARDS.get(reason, 0), reason)


def get_progress() -> dict:
    xp = _get_xp()
    lvl = level_for(xp)
    into = xp - (lvl - 1) * XP_PER_LEVEL
    to_next = 0 if lvl >= MAX_LEVEL else XP_PER_LEVEL - into
    return {
        "level": lvl,
        "xp": xp,
        "xp_into_level": into,
        "xp_to_next": to_next,
        "max_level": MAX_LEVEL,
        "sprite_set": sprite_set_for(lvl),
    }


def sprite_set_for(level: int) -> str:
    """Which KUMA sprite set is unlocked at this level (evolution hook)."""
    chosen = "states"
    for threshold, name in EVOLUTIONS:
        if level >= threshold:
            chosen = name
    return chosen
