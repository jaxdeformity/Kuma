"""Leveling / EXP + level-gated evolution tests."""
from kuma_core import progress


def test_level_for_math():
    assert progress.level_for(0) == 1
    assert progress.level_for(29) == 1
    assert progress.level_for(30) == 2
    assert progress.level_for(60) == 3
    # NO cap any more - keep leveling forever
    assert progress.level_for(3000) == 101
    assert progress.level_for(30_000) == 1001


def test_form_thresholds():
    assert progress.form_for(1) == 0    # base
    assert progress.form_for(4) == 0
    assert progress.form_for(5) == 1    # evo1
    assert progress.form_for(11) == 1
    assert progress.form_for(12) == 2   # evo2
    assert progress.form_for(15) == 2
    assert progress.form_for(16) == 3   # evo3
    assert progress.form_for(24) == 3
    assert progress.form_for(25) == 4   # evo4
    assert progress.form_for(89) == 4
    assert progress.form_for(90) == 5   # evo5
    assert progress.form_for(500) == 5


def test_award_discover_and_connect(temp_db):
    p = progress.award("connect")           # +30 -> level 2, still base form
    assert p["level"] == 2 and p["xp"] == 30 and p["active"] == 0
    p = progress.award("discover")          # +1
    assert p["xp"] == 31 and p["level"] == 2
    assert p["xp_into_level"] == 1 and p["xp_to_next"] == 29
    assert p["sprite_set"] == "states"
    assert p["next_evo_level"] == 5


def test_battle_win_reward(temp_db):
    p = progress.award("battle_win")
    assert p["xp"] == 10 and p["level"] == 1


def test_evolves_to_evo1_at_level_5(temp_db):
    # level 5 needs (5-1)*30 = 120 XP = 4 connects
    for _ in range(4):
        progress.award("connect")
    p = progress.get_progress()
    assert p["level"] == 5
    assert p["active"] == 1
    assert p["sprite_set"] == "evo1"
    assert p["next_evo_level"] == 12
    assert p["forms"][1]["unlocked"] is True
    assert p["forms"][2]["unlocked"] is False


def test_no_level_cap(temp_db):
    # 200 connects = 6000 XP -> level 201, fully evolved (evo5), still climbing
    for _ in range(200):
        progress.award("connect")
    p = progress.get_progress()
    assert p["level"] == 201
    assert p["max_level"] is None
    assert p["active"] == 5 and p["sprite_set"] == "evo5"
    assert p["next_evo_level"] is None


def test_six_forms_total(temp_db):
    assert progress.NUM_FORMS == 6
    assert len(progress.get_progress()["forms"]) == 6
    assert progress.EVO_LEVELS == [5, 12, 16, 25, 90]


def test_creator_mode_locks_showcase(temp_db, monkeypatch):
    from kuma_core.config import settings
    monkeypatch.setitem(settings.settings, "creator_mode", True)
    p = progress.get_progress()
    assert p["level"] == 69
    assert p["active"] == 5 and p["sprite_set"] == "evo5"
    assert p["creator"] is True and p["locked"] is True
    assert p["background"] == "backgFLAG"
    assert p["creator_name"] == "Jax"
    # awarding XP must NOT move a creator unit off the locked showcase
    progress.award("connect")
    assert progress.get_progress()["level"] == 69
