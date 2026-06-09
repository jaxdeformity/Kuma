"""Broadcast endpoint + BANKAI unscoped harvest."""
import os
os.environ["KUMA_MOCK"] = "0"

from kuma_core.authz import Gate
from offense import bankai


def _bgate(tmp_path, **extra):
    cfg = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
           "protect_bssids": ["AA:BB:CC:DD:EE:FF"], "own_infra": ["192.168.50.225"],
           "broadcast": {"max_burst_seconds": 1}}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "a.jsonl")


def test_bankai_arms_observed_excludes_own(tmp_path):
    g = _bgate(tmp_path)
    # observed networks: one normal, one that is protected (own AP)
    observed = [{"bssid": "11:22:33:44:55:66", "channel": 6},
                {"bssid": "AA:BB:CC:DD:EE:FF", "channel": 6}]  # protected
    armed = []
    res = bankai.run_bankai(
        g, observed=observed, lan_hosts=[],
        rf_deauth=lambda b, **k: armed.append(b),
        rf_capture=lambda b, ch, **k: None,
        net_scan=lambda h: [], net_brute=lambda h, p: None)
    # the protected AP must NOT be armed/attacked; the other one is
    assert "11:22:33:44:55:66" in armed
    assert "AA:BB:CC:DD:EE:FF" not in armed
    assert res["armed_targets"] >= 1


def test_bankai_refused_when_not_broadcast_armed(tmp_path):
    g = _bgate(tmp_path, broadcast_armed=False)
    hit = []
    res = bankai.run_bankai(g, observed=[{"bssid":"11:22:33:44:55:66","channel":6}],
                            lan_hosts=[], rf_deauth=lambda b,**k: hit.append(b),
                            rf_capture=lambda *a,**k: None, net_scan=lambda h: [],
                            net_brute=lambda h,p: None)
    assert res["ok"] is False
    assert hit == []


# ---------------------------------------------------------------------------
# Broadcast endpoint tests
# ---------------------------------------------------------------------------
import json, pytest
from fastapi.testclient import TestClient
from kuma_api.app import app
from kuma_core import authz


@pytest.fixture()
def client(temp_db, tmp_path, monkeypatch):
    p = tmp_path / "lab.json"
    p.write_text(json.dumps({"lab_mode": True, "allow_broadcast": True,
                             "broadcast_armed": True, "broadcast": {"max_burst_seconds": 1}}),
                 encoding="utf-8")
    monkeypatch.setattr(authz, "LAB_TARGETS_FILE", p)
    with TestClient(app) as c:
        yield c


def test_broadcast_unknown_attack_400(client):
    r = client.post("/api/kuroshuna/broadcast", json={"attack": "nope"})
    assert r.status_code == 400


def test_broadcast_requires_arm(client, tmp_path, monkeypatch):
    p = tmp_path / "lab2.json"
    p.write_text(json.dumps({"lab_mode": True, "allow_broadcast": False,
                             "broadcast_armed": False}), encoding="utf-8")
    monkeypatch.setattr(authz, "LAB_TARGETS_FILE", p)
    r = client.post("/api/kuroshuna/broadcast", json={"attack": "gemini"})
    assert r.status_code == 409


def test_broadcast_started(client):
    r = client.post("/api/kuroshuna/broadcast", json={"attack": "gemini"})
    assert r.status_code == 200
    assert r.json()["started"] is True
    assert r.json()["attack"] == "gemini"
