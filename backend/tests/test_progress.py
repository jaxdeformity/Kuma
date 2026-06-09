"""Leveling / EXP (rising-cost curve, capped at 99) + level-gated evolution."""
from kuma_core import progress


def test_xp_for_level_curve():
    assert progress.xp_for_level(1) == 0
    assert progress.xp_for_level(2) == 2
    assert progress.xp_for_level(5) == 32
    assert progress.xp_for_level(10) == 162
    assert progress.xp_for_level(99) == 19208
    assert progress.xp_for_level(150) == progress.xp_for_level(99)   # clamped


def test_level_for_curve():
    assert progress.level_for(0) == 1
    assert progress.level_for(1) == 1
    assert progress.level_for(2) == 2     # xp_for_level(2) == 2
    assert progress.level_for(7) == 2
    assert progress.level_for(8) == 3     # xp_for_level(3) == 8
    assert progress.level_for(32) == 5    # evo1 threshold
    assert progress.level_for(180) == 10  # ~60 discoveries (x3) -> rewarding
    assert progress.level_for(19208) == 99
    assert progress.level_for(10 ** 6) == 99   # hard cap


def test_rewards_weighting():
    assert progress.REWARDS == {"discover": 3, "connect": 30, "battle_win": 15}


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


def test_award_discover_and_connect(temp_db):
    p = progress.award("connect")           # +30 -> level 4 (xp_for_level(4)=18)
    assert p["xp"] == 30 and p["level"] == 4 and p["active"] == 0
    p = progress.award("discover")          # +3 -> 33 -> level 5 (xp_for_level(5)=32)
    assert p["xp"] == 33 and p["level"] == 5 and p["active"] == 1
    assert p["xp_into_level"] == 1          # 33 - 32
    assert p["xp_to_next"] == 17            # xp_for_level(6)=50 -> 50-33
    assert p["sprite_set"] == "evo1"


def test_battle_win_reward(temp_db):
    p = progress.award("battle_win")        # +15 -> level 3 (xp_for_level(3)=8)
    assert p["xp"] == 15 and p["level"] == 3


def test_evolves_to_evo1_at_level_5(temp_db):
    progress.award("connect")               # 30
    progress.award("discover")              # 33 -> level 5
    p = progress.get_progress()
    assert p["level"] == 5 and p["active"] == 1 and p["sprite_set"] == "evo1"
    assert p["next_evo_level"] == 12


def test_level_capped_at_99(temp_db):
    for _ in range(1000):                   # 30000 XP, well past the cap
        progress.award("connect")
    p = progress.get_progress()
    assert p["level"] == 99
    assert p["max_level"] == 99
    assert p["active"] == 5 and p["sprite_set"] == "evo5"
    assert p["next_evo_level"] is None
    assert p["xp_to_next"] == 0             # nothing past max


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
