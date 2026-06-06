"""Mode engine: transitions, validation, bear_state, action plumbing."""
import pytest

from kuma_core.modes import ModeEngine, VALID_MODES, MODES


def test_all_modes_have_specs():
    for m in VALID_MODES:
        assert m in MODES
        assert MODES[m].bear_state
        assert MODES[m].allowed_actions


def test_switch_valid_mode():
    eng = ModeEngine(current="sentinel")
    spec = eng.switch("foraging")
    assert eng.current == "foraging"
    assert spec.bear_state == "foraging"
    assert eng.history[-1] == {"from": "sentinel", "to": "foraging"}


def test_switch_invalid_mode_raises():
    eng = ModeEngine(current="sentinel")
    with pytest.raises(ValueError):
        eng.switch("turbo")
    assert eng.current == "sentinel"  # unchanged


def test_describe_shape():
    eng = ModeEngine(current="apex")
    d = eng.describe()
    assert d["mode"] == "apex"
    assert d["bear_state"] == "apex_ready"
    assert isinstance(d["allowed_actions"], list)
