"""HTTP routes - the surface the M5Core polls.

    GET  /api/status    device + mode + threat + bear_state + event count
    GET  /api/events    recent events (limit/severity/event_type/since)
    GET  /api/baseline  known SSIDs/BSSIDs
    POST /api/mode      switch mode
    POST /api/action    run a SAFE action (Sprint 1: placeholders only)

Sprint 1 actions are local/non-disruptive by design. The Apex action framework
enforces lab_mode + allowlist + explicit confirm before anything could ever
touch RF - and no RF action exists yet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from kuma_core import database, progress
from kuma_core.config import settings
from . import schemas
from . import state

router = APIRouter(prefix="/api")

# Actions the backend will accept in Sprint 1. All safe / local-only.
SAFE_ACTIONS = {
    "acknowledge_alert", "start_mock_capture", "export_events",
    "clear_mock_events", "enter_hibernate", "enter_foraging",
    "enter_honey", "enter_sentinel", "enter_apex",
}


@router.get("/status", response_model=schemas.StatusResponse)
def get_status() -> schemas.StatusResponse:
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)
                   ).strftime("%Y-%m-%dT%H:%M:%SZ")
    prog = progress.get_progress()
    return schemas.StatusResponse(
        device=settings.device_name,
        version=settings.version,
        mode=state.engine.current,
        threat_level=state.threat_level(),
        bear_state=state.bear_state(),
        uptime_seconds=state.uptime_seconds(),
        wifi_interface=settings.monitor_interface,
        events_last_10m=database.count_events_since(ten_min_ago),
        backend_status="online",
        level=prog["level"],
        xp=prog["xp"],
        network_count=database.count_networks(),
    )


@router.get("/progress")
def get_progress() -> dict:
    return progress.get_progress()


@router.get("/networks")
def get_networks(limit: int = 1000) -> dict:
    return {"count": database.count_networks(),
            "networks": database.get_networks(limit=limit)}


@router.get("/networks/export")
def export_networks() -> PlainTextResponse:
    return PlainTextResponse(database.wigle_csv(), media_type="text/csv",
                             headers={"Content-Disposition":
                                      "attachment; filename=kuma-wigle.csv"})


@router.post("/progress/battle-win")
def battle_win() -> dict:
    return progress.award("battle_win")


@router.get("/events", response_model=list[schemas.EventModel])
def get_events(limit: int = 50, severity: str | None = None,
               event_type: str | None = None, since: str | None = None):
    return database.get_events(limit=limit, severity=severity,
                               event_type=event_type, since=since)


@router.get("/baseline")
def get_baseline() -> dict:
    return {
        "known_aps": database.get_known_aps(),
        "trusted_networks": settings.trusted_networks(),
    }


@router.post("/mode", response_model=schemas.ModeResponse)
def post_mode(req: schemas.ModeRequest):
    if not state.engine.is_valid(req.mode):
        raise HTTPException(status_code=400, detail=f"unknown mode: {req.mode}")
    state.engine.switch(req.mode)
    database.insert_action({
        "timestamp": _now(), "mode": req.mode, "action": "mode_switch",
        "target": req.mode, "confirmed": 1, "result": "ok",
        "message": f"mode -> {req.mode}", "raw_json": {},
    })
    return state.engine.describe()


@router.post("/action", response_model=schemas.ActionResponse)
def post_action(req: schemas.ActionRequest):
    if req.action not in SAFE_ACTIONS:
        raise HTTPException(status_code=400,
                            detail=f"action not permitted in v0.0: {req.action}")
    accepted, result, message = state.run_action(req.action, req.target,
                                                  req.confirm)
    database.insert_action({
        "timestamp": _now(), "mode": state.engine.current,
        "action": req.action, "target": req.target,
        "confirmed": int(req.confirm), "result": result, "message": message,
        "raw_json": {},
    })
    return schemas.ActionResponse(action=req.action, accepted=accepted,
                                  result=result, message=message)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
