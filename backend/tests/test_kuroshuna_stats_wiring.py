"""The offense engines must record TX frames + PWNs as they act."""
from kuma_core import kuroshuna_stats as KS
from kuma_core.authz import Gate
from offense.rf_targeted import TargetedRF


def _armed(tmp_path):
    return Gate(config={"lab_mode": True, "kuroshuna_armed": True,
                        "approved_targets": ["aa:bb:cc:dd:ee:ff"]},
               audit_file=tmp_path / "a.jsonl")


def test_deauth_records_tx(tmp_path, monkeypatch):
    sf = tmp_path / "ks.json"
    monkeypatch.setattr(KS, "STATS_FILE", sf)
    rf = TargetedRF(gate=_armed(tmp_path), sender=lambda *a: None)
    # broadcast deauth -> 1 frame * 8 count = 8 tx_frames
    # (unicast would be 2 frames: AP->client + client->AP)
    rf.deauth("AA:BB:CC:DD:EE:FF", count=8)
    assert KS.read(stats_file=sf, now=lambda: 0)["tx_frames"] == 8
