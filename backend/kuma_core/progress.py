"""KUMA leveling / EXP with prestige-style evolution.

Network mapping is the XP engine (Jax's rules):

    30 XP = 1 level
    discover a NEW network   ->  1 XP   (1/30 of a level)
    connect to a NEW network -> 30 XP   (a full level)
    win a battle             -> 10 XP
    level = 1 + floor(xp / 30), capped at 99

Prestige: KUMA has 6 sprite forms (base + 5 evolutions). XP goes to the ACTIVE
form. When the newest form hits level 99 it EVOLVES: the next form unlocks at
level 1 and becomes active (like a "prestige"). Each unlocked form keeps its own
level, and the user can switch which unlocked form battles. Only one battles at a
time. (Future: forms also unlock display themes.)

State is one JSON blob in the settings table (key 'kuma_progress').
"""
from __future__ import annotations

import json

from kuma_core import database

XP_PER_LEVEL = 30
MAX_LEVEL = 99
MAX_XP = (MAX_LEVEL - 1) * XP_PER_LEVEL  # 2940
REWARDS = {"discover": 1, "connect": 30, "battle_win": 10}

NUM_FORMS = 6                                   # base + 5 evolutions
FORMS = ["states", "evo1", "evo2", "evo3", "evo4", "evo5"]  # sprite-pack dir names

_KEY = "kuma_progress"
_LEGACY_KEY = "kuma_xp"


def level_for(xp: int) -> int:
    return min(MAX_LEVEL, 1 + int(xp) // XP_PER_LEVEL)


def _state() -> dict:
    raw = database.get_setting(_KEY)
    if raw:
        try:
            s = json.loads(raw)
            s.setdefault("xp", [0] * NUM_FORMS)
            s.setdefault("unlocked", 1)
            s.setdefault("active", 0)
            if len(s["xp"]) < NUM_FORMS:
                s["xp"] += [0] * (NUM_FORMS - len(s["xp"]))
            return s
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    # migrate the old single-value xp, if any
    legacy = database.get_setting(_LEGACY_KEY)
    base = 0
    try:
        base = max(0, min(MAX_XP, int(legacy)))
    except (TypeError, ValueError):
        base = 0
    return {"xp": [base] + [0] * (NUM_FORMS - 1), "unlocked": 1, "active": 0}


def _save(s: dict) -> None:
    database.set_setting(_KEY, json.dumps(s))


def add_xp(amount: int, reason: str = "") -> dict:
    s = _state()
    a = s["active"]
    s["xp"][a] = min(MAX_XP, s["xp"][a] + max(0, int(amount)))
    # evolve: the newest form maxing out unlocks + activates the next form
    if (level_for(s["xp"][a]) >= MAX_LEVEL and a == s["unlocked"] - 1
            and s["unlocked"] < NUM_FORMS):
        s["unlocked"] += 1
        s["active"] = s["unlocked"] - 1
    _save(s)
    return get_progress()


def award(reason: str) -> dict:
    return add_xp(REWARDS.get(reason, 0), reason)


def select_form(index: int) -> dict:
    s = _state()
    if 0 <= int(index) < s["unlocked"]:
        s["active"] = int(index)
        _save(s)
    return get_progress()


def get_progress() -> dict:
    s = _state()
    a = s["active"]
    xp = s["xp"][a]
    lvl = level_for(xp)
    into = xp - (lvl - 1) * XP_PER_LEVEL
    to_next = 0 if lvl >= MAX_LEVEL else XP_PER_LEVEL - into
    return {
        "level": lvl,
        "xp": xp,
        "xp_into_level": into,
        "xp_to_next": to_next,
        "max_level": MAX_LEVEL,
        "active": a,
        "unlocked": s["unlocked"],
        "num_forms": NUM_FORMS,
        "sprite_set": FORMS[a],
        "forms": [
            {"form": i, "sprite_set": FORMS[i], "level": level_for(s["xp"][i]),
             "xp": s["xp"][i], "unlocked": i < s["unlocked"]}
            for i in range(NUM_FORMS)
        ],
    }
