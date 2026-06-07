"""SQLite persistence for KUMA.

Single-file DB at backend/data/kuma.db. Tables mirror the spec: events,
known_aps, observations, actions, settings. Events are also mirrored to
events.jsonl for grep-friendly debugging.

Deliberately uses the stdlib sqlite3 with row factories instead of an ORM -
this runs on a Pi, dependencies are a cost, and the schema is tiny.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import DATA_DIR, settings


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

DB_PATH = DATA_DIR / "kuma.db"
EVENTS_JSONL = DATA_DIR / "events.jsonl"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    mode        TEXT,
    event_type  TEXT,
    severity    TEXT,
    confidence  INTEGER,
    source      TEXT,
    target      TEXT,
    ssid        TEXT,
    bssid       TEXT,
    channel     INTEGER,
    rssi        INTEGER,
    message     TEXT,
    raw_json    TEXT
);
CREATE TABLE IF NOT EXISTS known_aps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ssid        TEXT,
    bssid       TEXT UNIQUE,
    security    TEXT,
    pmf         TEXT,
    channel     INTEGER,
    vendor      TEXT,
    trusted     INTEGER DEFAULT 0,
    first_seen  TEXT,
    last_seen   TEXT,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT,
    ssid        TEXT,
    bssid       TEXT,
    channel     INTEGER,
    rssi        INTEGER,
    security    TEXT,
    source      TEXT,
    raw_json    TEXT
);
CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT,
    mode        TEXT,
    action      TEXT,
    target      TEXT,
    confirmed   INTEGER,
    result      TEXT,
    message     TEXT,
    raw_json    TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS networks (
    bssid       TEXT PRIMARY KEY,
    ssid        TEXT,
    security    TEXT,
    channel     INTEGER,
    best_rssi   INTEGER,
    first_seen  TEXT,
    last_seen   TEXT,
    times_seen  INTEGER DEFAULT 1,
    lat         REAL,
    lon         REAL
);
CREATE TABLE IF NOT EXISTS connections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ssid            TEXT UNIQUE,
    bssid           TEXT,
    first_connected TEXT,
    last_connected  TEXT,
    times           INTEGER DEFAULT 1
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if missing. Safe to call on every boot."""
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


# --- events -------------------------------------------------------------
def insert_event(event: dict) -> int:
    cols = (
        "timestamp", "mode", "event_type", "severity", "confidence",
        "source", "target", "ssid", "bssid", "channel", "rssi",
        "message", "raw_json",
    )
    row = {c: event.get(c) for c in cols}
    raw = row["raw_json"]
    if isinstance(raw, (dict, list)):
        row["raw_json"] = json.dumps(raw)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO events ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)})",
            [row[c] for c in cols],
        )
        conn.commit()
        event_id = cur.lastrowid
    _append_jsonl({**event, "id": event_id})
    return event_id


def get_events(
    limit: int = 50,
    severity: str | None = None,
    event_type: str | None = None,
    since: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ?", params
        ).fetchall()
    return [_event_row(r) for r in rows]


def count_events_since(iso_timestamp: str) -> int:
    with connect() as conn:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM events WHERE timestamp >= ?", (iso_timestamp,)
        ).fetchone()
    return int(n)


def clear_events() -> int:
    with connect() as conn:
        cur = conn.execute("DELETE FROM events")
        conn.commit()
    if EVENTS_JSONL.exists():
        EVENTS_JSONL.unlink()
    return cur.rowcount


# --- known_aps / baseline ----------------------------------------------
def get_known_aps() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM known_aps ORDER BY last_seen DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_known_ap(ap: dict) -> None:
    cols = (
        "ssid", "bssid", "security", "pmf", "channel", "vendor",
        "trusted", "first_seen", "last_seen", "notes",
    )
    with connect() as conn:
        conn.execute(
            f"INSERT INTO known_aps ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)}) "
            "ON CONFLICT(bssid) DO UPDATE SET "
            "last_seen=excluded.last_seen, channel=excluded.channel",
            [ap.get(c) for c in cols],
        )
        conn.commit()


# --- actions ------------------------------------------------------------
def insert_action(action: dict) -> int:
    cols = (
        "timestamp", "mode", "action", "target", "confirmed",
        "result", "message", "raw_json",
    )
    row = {c: action.get(c) for c in cols}
    if isinstance(row["raw_json"], (dict, list)):
        row["raw_json"] = json.dumps(row["raw_json"])
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO actions ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)})",
            [row[c] for c in cols],
        )
        conn.commit()
        return cur.lastrowid


# --- observations -------------------------------------------------------
def insert_observation(obs: dict) -> int:
    cols = ("timestamp", "ssid", "bssid", "channel", "rssi", "security",
            "source", "raw_json")
    row = {c: obs.get(c) for c in cols}
    if isinstance(row["raw_json"], (dict, list)):
        row["raw_json"] = json.dumps(row["raw_json"])
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO observations ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)})",
            [row[c] for c in cols],
        )
        conn.commit()
        return cur.lastrowid


# --- settings (key/value) ----------------------------------------------
def get_setting(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key,value,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value), _now()),
        )
        conn.commit()


# --- networks (WiGLE-style passive map) --------------------------------
def record_network(bssid: str, ssid: str | None = None, security: str | None = None,
                   channel: int | None = None, rssi: int | None = None,
                   timestamp: str | None = None) -> bool:
    """Upsert an observed AP. Returns True if this BSSID was never seen before."""
    if not bssid:
        return False
    bssid = bssid.upper()
    ts = timestamp or _now()
    with connect() as conn:
        row = conn.execute(
            "SELECT best_rssi FROM networks WHERE bssid=?", (bssid,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO networks (bssid,ssid,security,channel,best_rssi,"
                "first_seen,last_seen,times_seen) VALUES (?,?,?,?,?,?,?,1)",
                (bssid, ssid, security, channel, rssi, ts, ts),
            )
            conn.commit()
            return True
        best = row["best_rssi"]
        new_best = rssi if (best is None or (rssi is not None and rssi > best)) else best
        conn.execute(
            "UPDATE networks SET last_seen=?, times_seen=times_seen+1, best_rssi=?, "
            "ssid=COALESCE(NULLIF(?,''),ssid), security=COALESCE(?,security), "
            "channel=COALESCE(?,channel) WHERE bssid=?",
            (ts, new_best, ssid, security, channel, bssid),
        )
        conn.commit()
        return False


def get_networks(limit: int = 1000) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM networks ORDER BY last_seen DESC LIMIT ?", (int(limit),)
        ).fetchall()
    return [dict(r) for r in rows]


def count_networks() -> int:
    with connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM networks").fetchone()
    return int(n)


def record_connection(ssid: str, bssid: str | None = None,
                      timestamp: str | None = None) -> bool:
    """Log a network KUMA's host connected to. True if it's a new network."""
    if not ssid:
        return False
    ts = timestamp or _now()
    bssid = (bssid or "").upper() or None
    with connect() as conn:
        row = conn.execute("SELECT id FROM connections WHERE ssid=?", (ssid,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO connections (ssid,bssid,first_connected,last_connected,times) "
                "VALUES (?,?,?,?,1)", (ssid, bssid, ts, ts),
            )
            conn.commit()
            return True
        conn.execute(
            "UPDATE connections SET last_connected=?, times=times+1, "
            "bssid=COALESCE(?,bssid) WHERE id=?", (ts, bssid, row["id"]),
        )
        conn.commit()
        return False


def get_connections() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM connections ORDER BY last_connected DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def _wigle_authmode(security: str | None) -> str:
    s = (security or "").upper().strip()
    if not s or s in ("OPEN", "NONE"):
        return "[OPEN][ESS]"
    return "[" + s + "][ESS]"


def _wigle_field(v: Any) -> str:
    s = "" if v is None else str(v)
    if "," in s or '"' in s:
        s = '"' + s.replace('"', '""') + '"'
    return s


def wigle_csv() -> str:
    """Export the observed network map as a WiGLE WigleWifi-1.4 CSV string."""
    pre = ("WigleWifi-1.4,appRelease=KUMA,model=KUMA,release=" + settings.version +
           ",device=kuma,display=,board=,brand=kuma")
    hdr = ("MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,CurrentLatitude,"
           "CurrentLongitude,AltitudeMeters,AccuracyMeters,Type")
    lines = [pre, hdr]
    for n in get_networks(limit=100000):
        lines.append(",".join([
            n.get("bssid") or "", _wigle_field(n.get("ssid")),
            _wigle_authmode(n.get("security")), n.get("first_seen") or "",
            str(n.get("channel") or ""), str(n.get("best_rssi") or ""),
            str(n.get("lat") if n.get("lat") is not None else 0.0),
            str(n.get("lon") if n.get("lon") is not None else 0.0),
            "0", "0", "WIFI",
        ]))
    return "\n".join(lines) + "\n"


# --- helpers ------------------------------------------------------------
def _event_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("raw_json"):
        try:
            d["raw_json"] = json.loads(d["raw_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _append_jsonl(event: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with EVENTS_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
