"""Leveling / EXP logic tests."""
from kuma_core import progress


def test_level_for_math():
    assert progress.level_for(0) == 1
    assert progress.level_for(29) == 1
    assert progress.level_for(30) == 2
    assert progress.level_for(60) == 3
    assert progress.level_for(progress.MAX_XP) == 99
    assert progress.level_for(10_000) == 99  # cap


def test_award_discover_and_connect(temp_db):
    p = progress.award("connect")           # +30 -> level 2
    assert p["level"] == 2 and p["xp"] == 30
    p = progress.award("discover")          # +1
    assert p["xp"] == 31 and p["level"] == 2
    assert p["xp_into_level"] == 1 and p["xp_to_next"] == 29


def test_battle_win_reward(temp_db):
    p = progress.award("battle_win")
    assert p["xp"] == 10 and p["level"] == 1


def test_xp_caps_at_99(temp_db):
    for _ in range(200):
        progress.award("connect")
    p = progress.get_progress()
    assert p["level"] == 99
    assert p["xp"] == progress.MAX_XP
    assert p["xp_to_next"] == 0


def test_sprite_set_default(temp_db):
    assert progress.get_progress()["sprite_set"] == "states"
