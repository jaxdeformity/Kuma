"""Test fixtures: point KUMA at a temp DB so tests never touch real data."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Redirect the database + jsonl to a temp dir and re-init the schema."""
    from kuma_core import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "kuma.db")
    monkeypatch.setattr(database, "EVENTS_JSONL", tmp_path / "events.jsonl")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.init_db()
    return database
