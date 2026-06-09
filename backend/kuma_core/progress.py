"""KUMA leveling / EXP with level-gated evolution.

Network mapping is the XP engine, on a rising-cost curve (Jax's rules):

    discover a NEW network   ->  3 XP
    connect to a NEW network -> 30 XP
    win a battle             -> 15 XP
    cumulative XP to reach level L = 2 * (L-1)^2    (cheap early, dear late)
    MAX level = 99   (e.g. ~60 discoveries -> level 10; level 99 = 19208 XP)

Evolution: KUMA has 6 sprite forms (base + 5). The active form is a function of
LEVEL - KUMA auto-evolves as it levels up, and there is no max level:

    level >= 5   -> evo1
    level >= 12  -> evo2
    level >= 16  -> evo3
    level >= 25  -> evo4
    level >= 90  -> evo5

State is one JSON blob in the settings table (key 'kuma_progress'): a single
cumulative xp value. (Replaces the old per-form "prestige" pools.)
"""
from __future__ import annotations

import json

from kuma_core import database

# Rising-cost curve: cumulative XP to REACH level L is LEVEL_K*(L-1)^2, capped at
# MAX_LEVEL. Early levels are cheap so discoveries feel rewarding (e.g. ~60 networks
# -> level 10); late levels cost far more so reaching 99 is a real grind, not trivial.
# Rewards are weighted for expected usage (a found network is a meaningful chunk).
MAX_LEVEL = 99
LEVEL_K = 2
REWARDS = {"discover": 3, "connect": 30, "battle_win": 15}

FORMS = ["states", "evo1", "evo2", "evo3", "evo4", "evo5"]  # sprite-pack dir names
NUM_FORMS = len(FORMS)
EVO_LEVELS = [5, 12, 16, 25, 90]   # level at which evo1..evo5 unlock

_KEY = "kuma_progress"
_LEGACY_KEY = "kuma_xp"


def xp_for_level(level: int) -> int:
    """Cumulative XP required to REACH `level` (level 1 -> 0). Rising-cost curve,
    clamped to [1, MAX_LEVEL]."""
    level = max(1, min(MAX_LEVEL, int(level)))
    return LEVEL_K * (level - 1) ** 2


def level_for(xp: int) -> int:
    """Level from cumulative XP on the rising-cost curve, capped at MAX_LEVEL."""
    xp = max(0, int(xp))
    lvl = 1 + int((xp / LEVEL_K) ** 0.5)            # invert K*(L-1)^2 <= xp
    while lvl < MAX_LEVEL and xp_for_level(lvl + 1) <= xp:
        lvl += 1
    while lvl > 1 and xp_for_level(lvl) > xp:        # correct any float edge case
        lvl -= 1
    return min(MAX_LEVEL, lvl)


def form_for(level: int) -> int:
    """Active form index (0=base .. 5=evo5) for a given level."""
    return sum(1 for t in EVO_LEVELS if level >= t)


def _state() -> dict:
    """Load the single-xp state, migrating older formats in place."""
    raw = database.get_setting(_KEY)
    if raw:
        try:
            s = json.loads(raw)
            xp = s.get("xp", 0)
            # migrate the old per-form prestige blob (xp was a list of pools)
            if isinstance(xp, list):
                xp = sum(int(v) for v in xp)
            return {"xp": max(0, int(xp))}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    # migrate the oldest single-value legacy key, if any
    legacy = database.get_setting(_LEGACY_KEY)
    try:
        return {"xp": max(0, int(legacy))}
    except (TypeError, ValueError):
        return {"xp": 0}


def _save(s: dict) -> None:
    database.set_setting(_KEY, json.dumps(s))


def add_xp(amount: int, reason: str = "") -> dict:
    s = _state()
    s["xp"] = max(0, s["xp"] + max(0, int(amount)))
    _save(s)
    return get_progress()


def award(reason: str) -> dict:
    return add_xp(REWARDS.get(reason, 0), reason)


def select_form(index: int) -> dict:
    """No-op kept for API compatibility: the active form now follows LEVEL
    automatically, so a form can't be selected independently of progress."""
    return get_progress()


# Jax's personal showcase unit is permanently locked here (creator_mode).
CREATOR_LEVEL = 69
CREATOR_FORM = 5          # evo5
CREATOR_BACKGROUND = "backgFLAG"


def get_progress() -> dict:
    from kuma_core.config import settings   # local import avoids a cycle

    if settings.creator_mode:
        lvl, form = CREATOR_LEVEL, CREATOR_FORM
        xp = xp_for_level(lvl)
    else:
        xp = _state()["xp"]
        lvl = level_for(xp)
        form = form_for(lvl)

    into = xp - xp_for_level(lvl)
    to_next = 0 if lvl >= MAX_LEVEL else xp_for_level(lvl + 1) - xp
    next_evo = next((t for t in EVO_LEVELS if t > lvl), None)
    out = {
        "level": lvl,
        "xp": xp,
        "xp_into_level": into,
        "xp_to_next": to_next,
        "max_level": MAX_LEVEL,
        "active": form,
        "unlocked": form + 1,
        "num_forms": NUM_FORMS,
        "sprite_set": FORMS[form],
        "next_evo_level": next_evo,        # level of the next evolution (None at evo5)
        "forms": [
            {"form": i, "sprite_set": FORMS[i],
             "unlock_level": (EVO_LEVELS[i - 1] if i > 0 else 1),
             "unlocked": form >= i, "active": i == form}
            for i in range(NUM_FORMS)
        ],
    }
    if settings.creator_mode:
        out["creator"] = True
        out["creator_name"] = settings.creator_name
        out["background"] = CREATOR_BACKGROUND   # firmware picks backgFLAG
        out["locked"] = True
    return out
