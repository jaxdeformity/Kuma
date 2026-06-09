"""API response-shape tests using FastAPI's TestClient.

Disables the background mock loop so tests are deterministic.
"""
import os

import pytest

os.environ["KUMA_MOCK"] = "0"  # no background events during tests

from fastapi.testclient import TestClient  # noqa: E402

from kuma_api.app import app  # noqa: E402


@pytest.fixture()
def client(temp_db):
    with TestClient(app) as c:
        yield c


def test_status_shape(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    for key in ("device", "version", "mode", "threat_level", "bear_state",
                "uptime_seconds", "wifi_interface", "events_last_10m"):
        assert key in body
    assert body["device"] == "KUMA"


def test_mode_switch(client):
    r = client.post("/api/mode", json={"mode": "foraging"})
    assert r.status_code == 200
    assert r.json()["mode"] == "foraging"
    assert r.json()["bear_state"] == "foraging"


def test_mode_switch_invalid(client):
    r = client.post("/api/mode", json={"mode": "turbo"})
    assert r.status_code == 400


def test_action_safe(client):
    r = client.post("/api/action", json={"action": "acknowledge_alert",
                                         "confirm": True})
    assert r.status_code == 200
    assert r.json()["accepted"] is True


def test_action_unpermitted(client):
    r = client.post("/api/action", json={"action": "deauth_everyone",
                                         "confirm": True})
    assert r.status_code == 400


def test_events_endpoint(client):
    r = client.get("/api/events?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_status_has_level_and_networks(client):
    b = client.get("/api/status").json()
    assert b["level"] == 1 and b["xp"] == 0 and b["network_count"] == 0


def test_progress_endpoint(client):
    b = client.get("/api/progress").json()
    assert b["level"] == 1 and b["max_level"] == 99  # capped at 99
    assert b["sprite_set"] == "states" and b["next_evo_level"] == 5


def test_networks_export_csv(client, temp_db):
    temp_db.record_network("AA:BB:CC:DD:EE:FF", "Net", "WPA2", 6, -50)
    r = client.get("/api/networks/export")
    assert r.status_code == 200
    assert r.text.startswith("WigleWifi-1.4")
    assert "AA:BB:CC:DD:EE:FF" in r.text


def test_battle_win_awards_xp(client):
    b = client.post("/api/progress/battle-win").json()
    assert b["xp"] == 15 and b["level"] == 3   # battle_win=15 -> level 3 on the curve
