import pytest
from fastapi.testclient import TestClient

from kuma_api.app import app
from kuma_core import events

CTRL = {"X-KUMA-Shell-Token": "test-token"}


@pytest.fixture()
def client(temp_db, monkeypatch):
    monkeypatch.setenv("KUMA_SHELL_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _insert_threat(temp_db, bssid, etype="deauth_burst", severity="high"):
    temp_db.insert_event(events.make_event(
        mode="sentinel", event_type=etype, confidence=90, severity=severity,
        message="x", source=bssid, bssid=bssid, channel=6))


def test_mitigate_requires_token(client):
    r = client.post("/api/mitigate")
    assert r.status_code in (403, 422)  # missing/empty token rejected


def test_mitigate_no_attacker_returns_applied_false(client):
    r = client.post("/api/mitigate", headers=CTRL)
    assert r.status_code == 200
    assert r.json()["applied"] is False


def test_mitigate_attributes_newest_high_sev_bssid(client, temp_db):
    _insert_threat(temp_db, "AA:BB:CC:DD:EE:FF", "deauth_burst", "high")
    r = client.post("/api/mitigate", headers=CTRL)
    body = r.json()
    assert body["applied"] is True
    assert body["target"] == "AA:BB:CC:DD:EE:FF"
    assert body["action"] == "harden+redirect"
