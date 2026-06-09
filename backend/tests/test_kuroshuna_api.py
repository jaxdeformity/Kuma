"""API tests for the Kuroshuna control surface (lab file redirected to tmp)."""
import json
import os

import pytest

os.environ["KUMA_MOCK"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from kuma_api.app import app  # noqa: E402


@pytest.fixture()
def lab_file(tmp_path, monkeypatch):
    """Redirect lab_targets.json to a temp file with a known starting state."""
    from kuma_core import authz
    p = tmp_path / "lab_targets.json"
    p.write_text(json.dumps({
        "lab_mode": False, "kuroshuna_armed": False, "allow_broadcast": False,
        "broadcast_armed": False, "approved_targets": [], "protect_bssids": [],
    }), encoding="utf-8")
    monkeypatch.setattr(authz, "LAB_TARGETS_FILE", p)
    return p


@pytest.fixture()
def client(temp_db, lab_file):
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Task 1: save_lab roundtrip
# ---------------------------------------------------------------------------

def test_save_lab_roundtrip(lab_file):
    from kuma_core import authz
    cfg = authz._load_lab()
    cfg["kuroshuna_armed"] = True
    authz.save_lab(cfg)
    assert json.loads(lab_file.read_text(encoding="utf-8"))["kuroshuna_armed"] is True
    assert authz._load_lab()["kuroshuna_armed"] is True


# ---------------------------------------------------------------------------
# Task 2: /api/status exposes arm flags
# ---------------------------------------------------------------------------

def test_status_has_kuroshuna_flags(client):
    body = client.get("/api/status").json()
    assert body["kuroshuna_armed"] is False
    assert body["broadcast_armed"] is False


# ---------------------------------------------------------------------------
# Task 3: POST /api/kuroshuna/arm
# ---------------------------------------------------------------------------

def test_arm_requires_lab_mode(client, lab_file):
    # lab_mode is False -> arming Kuroshuna is refused
    r = client.post("/api/kuroshuna/arm", json={"armed": True})
    assert r.status_code == 409
    assert "lab_mode" in r.json()["detail"]


def test_arm_succeeds_when_lab_mode_on(client, lab_file):
    cfg = json.loads(lab_file.read_text()); cfg["lab_mode"] = True
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")
    r = client.post("/api/kuroshuna/arm", json={"armed": True})
    assert r.status_code == 200
    assert r.json()["kuroshuna_armed"] is True
    assert json.loads(lab_file.read_text())["kuroshuna_armed"] is True


def test_disarm_always_allowed(client, lab_file):
    # even with lab_mode False, disarming must work (stand down)
    cfg = json.loads(lab_file.read_text()); cfg["kuroshuna_armed"] = True
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")
    r = client.post("/api/kuroshuna/arm", json={"armed": False})
    assert r.status_code == 200
    assert r.json()["kuroshuna_armed"] is False


# ---------------------------------------------------------------------------
# Task 4: POST /api/kuroshuna/broadcast-arm
# ---------------------------------------------------------------------------

def _set_lab(lab_file, **kw):
    cfg = json.loads(lab_file.read_text()); cfg.update(kw)
    lab_file.write_text(json.dumps(cfg), encoding="utf-8")


def test_broadcast_arm_requires_allow_broadcast(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=False)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": True})
    assert r.status_code == 409
    assert "allow_broadcast" in r.json()["detail"]


def test_broadcast_arm_succeeds_when_enabled(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=True)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": True})
    assert r.status_code == 200
    assert r.json()["broadcast_armed"] is True


def test_broadcast_disarm_always_allowed(client, lab_file):
    _set_lab(lab_file, broadcast_armed=True)
    r = client.post("/api/kuroshuna/broadcast-arm", json={"armed": False})
    assert r.status_code == 200
    assert r.json()["broadcast_armed"] is False


# ---------------------------------------------------------------------------
# Task 5: POST /api/kuroshuna/authorize
# ---------------------------------------------------------------------------

def test_authorize_denies_unapproved(client, lab_file):
    _set_lab(lab_file, lab_mode=True, kuroshuna_armed=True, approved_targets=[])
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "AA:BB:CC:DD:EE:FF", "action": "deauth"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert "not in authorized set" in body["reason"]


def test_authorize_allows_approved(client, lab_file):
    _set_lab(lab_file, lab_mode=True, kuroshuna_armed=True,
             approved_targets=["aa:bb:cc:dd:ee:ff"])
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "AA:BB:CC:DD:EE:FF", "action": "deauth"})
    assert r.json()["allowed"] is True


def test_authorize_broadcast_action_uses_broadcast_gate(client, lab_file):
    _set_lab(lab_file, lab_mode=True, allow_broadcast=True, broadcast_armed=True)
    r = client.post("/api/kuroshuna/authorize",
                    json={"target": "*", "action": "broadcast"})
    assert r.json()["allowed"] is True
    _set_lab(lab_file, broadcast_armed=False)
    r2 = client.post("/api/kuroshuna/authorize",
                     json={"target": "*", "action": "broadcast"})
    assert r2.json()["allowed"] is False


# ---------------------------------------------------------------------------
# Phase 8: /api/status exposes combat stats
# ---------------------------------------------------------------------------

def test_status_has_combat_stats(client):
    body = client.get("/api/status").json()
    assert body["pwned_count"] == 0
    assert body["tx_frames"] == 0
    assert body["tx_active"] is False
