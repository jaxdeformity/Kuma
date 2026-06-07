"""Leveling / EXP + prestige (evolution) logic tests."""
from kuma_core import progress


def test_level_for_math():
    assert progress.level_for(0) == 1
    assert progress.level_for(29) == 1
    assert progress.level_for(30) == 2
    assert progress.level_for(60) == 3
    assert progress.level_for(progress.MAX_XP) == 99
    assert progress.level_for(10_000) == 99  # cap


def test_award_discover_and_connect(temp_db):
    p = progress.award("connect")           # +30 -> level 2 (active form 0)
    assert p["level"] == 2 and p["xp"] == 30 and p["active"] == 0
    p = progress.award("discover")          # +1
    assert p["xp"] == 31 and p["level"] == 2
    assert p["xp_into_level"] == 1 and p["xp_to_next"] == 29
    assert p["unlocked"] == 1 and p["sprite_set"] == "states"


def test_battle_win_reward(temp_db):
    p = progress.award("battle_win")
    assert p["xp"] == 10 and p["level"] == 1


def test_evolution_at_99(temp_db):
    # 98 connects = 2940 XP = exactly level 99 -> evolves to form 1 at level 1
    for _ in range(98):
        progress.award("connect")
    p = progress.get_progress()
    assert p["unlocked"] == 2
    assert p["active"] == 1          # auto-switched to the evolved form
    assert p["level"] == 1          # new form starts fresh
    assert p["sprite_set"] == "evo1"
    assert p["forms"][0]["level"] == 99   # base form stays maxed
    assert p["forms"][1]["level"] == 1


def test_select_form(temp_db):
    for _ in range(120):
        progress.award("connect")   # evolve to form 1
    assert progress.get_progress()["active"] == 1
    p = progress.select_form(0)     # switch back to the maxed base form
    assert p["active"] == 0 and p["level"] == 99
    # cannot select a locked form
    p = progress.select_form(5)
    assert p["active"] == 0


def test_six_forms_total(temp_db):
    assert progress.NUM_FORMS == 6
    assert len(progress.get_progress()["forms"]) == 6
