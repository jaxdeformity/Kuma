"""Unit tests for the Kuroshuna combat-stats tracker."""
from kuma_core import kuroshuna_stats as KS


def _s(tmp_path):
    return tmp_path / "kuroshuna_stats.json"


def test_empty_defaults(tmp_path):
    out = KS.read(stats_file=_s(tmp_path))
    assert out == {"pwned": 0, "tx_frames": 0, "tx_active": False}


def test_record_pwn_dedupes(tmp_path):
    f = _s(tmp_path)
    KS.record_pwn("AA:BB:CC:DD:EE:FF", stats_file=f)
    KS.record_pwn("aa:bb:cc:dd:ee:ff", stats_file=f)   # same target, different case
    KS.record_pwn("11:22:33:44:55:66", stats_file=f)
    assert KS.read(stats_file=f)["pwned"] == 2


def test_record_tx_accumulates_and_marks_active(tmp_path):
    f = _s(tmp_path)
    KS.record_tx(64, stats_file=f, now=lambda: 1000.0)
    KS.record_tx(64, stats_file=f, now=lambda: 1001.0)
    out = KS.read(stats_file=f, now=lambda: 1001.5)   # 0.5s after last tx
    assert out["tx_frames"] == 128
    assert out["tx_active"] is True


def test_tx_goes_inactive_when_stale(tmp_path):
    f = _s(tmp_path)
    KS.record_tx(10, stats_file=f, now=lambda: 1000.0)
    out = KS.read(stats_file=f, now=lambda: 1010.0)    # 10s later > TX_FRESH
    assert out["tx_active"] is False
    assert out["tx_frames"] == 10                       # count persists
