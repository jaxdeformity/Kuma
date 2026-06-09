"""Kuroshuna combat stats: cumulative PWNED count (deduped by target) + TX frame
count + a TX heartbeat. Written by the offense modules, read by /api/status. Plain
JSON file so the API process and the offense/orchestrator processes share it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from kuma_core.config import DATA_DIR

STATS_FILE = DATA_DIR / "kuroshuna_stats.json"
TX_FRESH_SECONDS = 3.0   # tx_active true only if a frame went out within this window


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pwned_targets": [], "tx_frames": 0, "tx_last_ts": 0.0}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def record_pwn(target: str, *, stats_file: Path | None = None) -> None:
    p = stats_file or STATS_FILE
    d = _load(p)
    t = (target or "").strip().upper()
    if t and t not in d.get("pwned_targets", []):
        d.setdefault("pwned_targets", []).append(t)
        _save(p, d)


def record_tx(frames: int, *, stats_file: Path | None = None, now=time.time) -> None:
    p = stats_file or STATS_FILE
    d = _load(p)
    d["tx_frames"] = int(d.get("tx_frames", 0)) + int(frames)
    d["tx_last_ts"] = now()
    _save(p, d)


def read(*, stats_file: Path | None = None, now=time.time) -> dict:
    d = _load(stats_file or STATS_FILE)
    fresh = (now() - float(d.get("tx_last_ts", 0.0))) < TX_FRESH_SECONDS
    return {
        "pwned": len(d.get("pwned_targets", [])),
        "tx_frames": int(d.get("tx_frames", 0)),
        "tx_active": bool(fresh and d.get("tx_last_ts")),
    }
