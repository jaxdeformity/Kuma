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

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from kuma_core import authz, database, kuroshuna_stats, progress
from kuma_core.authz import Gate
from kuma_core.config import settings
from . import schemas
from . import state

router = APIRouter(prefix="/api")


def _check_ctrl_token(token_header: str) -> None:
    """Gate the offensive control surface. FAIL-CLOSED: if no KUMA_SHELL_TOKEN is set
    in the backend env, these endpoints are DISABLED (503); otherwise the caller must
    present the token. Stops anyone on the LAN from arming/firing Kuma."""
    token = settings.shell_token
    if not token:
        raise HTTPException(status_code=503, detail="offensive control disabled (no KUMA_SHELL_TOKEN set)")
    if token_header != token:
        raise HTTPException(status_code=403, detail="bad control token")

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
    lab = authz._load_lab()
    ks = kuroshuna_stats.read()
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
        xp_into_level=prog.get("xp_into_level", 0),
        xp_to_next=prog.get("xp_to_next", 30),
        network_count=database.count_networks(),
        sprite_set=prog["sprite_set"],
        background=prog.get("background", "backg1"),
        creator=prog.get("creator", False),
        character=settings.character,
        kuroshuna_armed=bool(lab.get("kuroshuna_armed")),
        broadcast_armed=bool(lab.get("broadcast_armed")),
        pwned_count=ks["pwned"],
        tx_frames=ks["tx_frames"],
        tx_active=ks["tx_active"],
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


@router.post("/progress/select-form")
def select_form(req: schemas.FormRequest) -> dict:
    return progress.select_form(req.form)


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


@router.post("/shell")
def post_shell(req: schemas.ShellRequest,
               x_kuma_shell_token: str = Header(default="")) -> dict:
    """Run a real shell command on the Pi. Disabled unless KUMA_SHELL_TOKEN is set
    in the backend environment and the caller presents it."""
    token = settings.shell_token
    if not token:
        raise HTTPException(status_code=503, detail="shell disabled (no token set)")
    if x_kuma_shell_token != token:
        raise HTTPException(status_code=403, detail="bad shell token")
    return state.run_shell(req.cmd)


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


# ---------------------------------------------------------------------------
# KUMA real defense — manual mitigation (blue-team, on by default)
# ---------------------------------------------------------------------------

def _resolve_attacker() -> tuple[str | None, str | None]:
    """Newest high/critical event that carries a BSSID = the encounter's attacker."""
    for ev in database.get_events(limit=50):
        if ev.get("severity") in ("high", "critical") and ev.get("bssid"):
            return ev["bssid"], ev.get("event_type")
    return None, None


@router.post("/mitigate", response_model=schemas.MitigateResponse)
def post_mitigate(x_kuma_shell_token: str = Header(default="")):
    """KUMA real defense: attribute the current attacker and apply the canonical
    defensive mitigation. Token-gated; no lab_mode (active defense is on by default)."""
    _check_ctrl_token(x_kuma_shell_token)
    attacker, etype = _resolve_attacker()
    if not attacker:
        return schemas.MitigateResponse(
            applied=False, action="", target="", result="none",
            message="no attributable attacker")
    from kuma_core.mitigation import MitigationEngine
    res = MitigationEngine().apply(attacker, etype or "")
    database.insert_action({
        "timestamp": _now(), "mode": "kuma", "action": "mitigate",
        "target": attacker, "confirmed": 1, "result": res["result"],
        "message": res["message"],
        "raw_json": {"engine_action": res["action"], "event_type": etype}})
    return schemas.MitigateResponse(
        applied=True, action=res["action"], target=attacker,
        result=res["result"], message=res["message"])


# ---------------------------------------------------------------------------
# Kuroshuna control surface
# ---------------------------------------------------------------------------

def _arm_response(lab: dict) -> schemas.KuroshunaArmResponse:
    return schemas.KuroshunaArmResponse(
        lab_mode=bool(lab.get("lab_mode")),
        kuroshuna_armed=bool(lab.get("kuroshuna_armed")),
        broadcast_armed=bool(lab.get("broadcast_armed")))


@router.post("/kuroshuna/arm", response_model=schemas.KuroshunaArmResponse)
def kuroshuna_arm(req: schemas.KuroshunaArmRequest,
                  x_kuma_shell_token: str = Header(default="")):
    _check_ctrl_token(x_kuma_shell_token)
    lab = authz._load_lab()
    if req.armed and not lab.get("lab_mode"):
        raise HTTPException(status_code=409,
                            detail="cannot arm: lab_mode is off")
    lab["kuroshuna_armed"] = bool(req.armed)
    if not req.armed:
        lab["broadcast_armed"] = False   # disarming Kuroshuna drops broadcast too
    authz.save_lab(lab)
    database.insert_action({
        "timestamp": _now(), "mode": "kuroshuna",
        "action": "kuroshuna_arm", "target": "self",
        "confirmed": 1, "result": "ok",
        "message": f"kuroshuna_armed -> {bool(req.armed)}", "raw_json": {}})
    return _arm_response(lab)


@router.post("/kuroshuna/broadcast-arm", response_model=schemas.KuroshunaArmResponse)
def kuroshuna_broadcast_arm(req: schemas.KuroshunaArmRequest,
                             x_kuma_shell_token: str = Header(default="")):
    _check_ctrl_token(x_kuma_shell_token)
    lab = authz._load_lab()
    if req.armed:
        if not lab.get("lab_mode"):
            raise HTTPException(status_code=409,
                                detail="cannot arm broadcast: lab_mode is off")
        if not lab.get("allow_broadcast"):
            raise HTTPException(status_code=409,
                                detail="cannot arm broadcast: allow_broadcast is off")
    lab["broadcast_armed"] = bool(req.armed)
    authz.save_lab(lab)
    database.insert_action({
        "timestamp": _now(), "mode": "kuroshuna",
        "action": "broadcast_arm", "target": "self", "confirmed": 1,
        "result": "ok", "message": f"broadcast_armed -> {bool(req.armed)}",
        "raw_json": {}})
    return _arm_response(lab)


@router.post("/kuroshuna/authorize",
             response_model=schemas.KuroshunaAuthorizeResponse)
def kuroshuna_authorize(req: schemas.KuroshunaAuthorizeRequest,
                        x_kuma_shell_token: str = Header(default="")):
    """The T-Deck calls this BEFORE its own ESP32 radio transmits, so the Pi gate
    stays authoritative. The gate audits every decision."""
    _check_ctrl_token(x_kuma_shell_token)
    gate = Gate()  # reads current lab_targets.json
    if req.action == "broadcast":
        allowed, reason = gate.broadcast_allowed()
    else:
        allowed, reason = gate.is_authorized(req.target, req.action)
    return schemas.KuroshunaAuthorizeResponse(allowed=allowed, reason=reason)


# ---------------------------------------------------------------------------
# Kuroshuna broadcast attack endpoint
# ---------------------------------------------------------------------------

_BROADCAST_ATTACKS = {"gemini", "deauth", "aoi", "rengoku", "bankai"}


@router.post("/kuroshuna/broadcast", response_model=schemas.BroadcastAttackResponse)
def kuroshuna_broadcast(req: schemas.BroadcastAttackRequest,
                        x_kuma_shell_token: str = Header(default="")):
    _check_ctrl_token(x_kuma_shell_token)
    name = (req.attack or "").lower()
    if name not in _BROADCAST_ATTACKS:
        raise HTTPException(status_code=400, detail=f"unknown attack: {name}")
    gate = Gate()
    allowed, why = gate.broadcast_allowed()
    if not allowed:
        raise HTTPException(status_code=409, detail=why)
    _launch_broadcast(name)            # background thread; time-boxed inside
    return schemas.BroadcastAttackResponse(started=True, attack=name)


def _launch_broadcast(name: str) -> None:
    import threading
    def _run():
        try:
            from kuma_core.authz import Gate as _G
            from offense.rf_broadcast import BroadcastRF
            g = _G()
            rf = BroadcastRF(gate=g)
            if name == "gemini":   rf.beacon_spam()
            elif name == "deauth": rf.deauth_flood()
            elif name == "aoi":    rf.ble_spam()
            elif name == "rengoku":
                # flood the first observed AP the gate will arm. auto_hostile_add
                # HARD-REFUSES protect_bssids/own_infra, so RENGOKU never hits own gear.
                nets = database.get_networks(limit=50)
                tgt = next((n["bssid"] for n in nets
                            if n.get("bssid")
                            and g.auto_hostile_add(n["bssid"], evidence="rengoku")), None)
                if tgt:
                    rf.assoc_flood(tgt)
            elif name == "bankai":
                from offense import bankai
                from offense.rf_targeted import TargetedRF
                from offense.net_offense import NetworkOffense
                trf, no = TargetedRF(gate=g), NetworkOffense(gate=g)
                nets = database.get_networks(limit=200)
                bankai.run_bankai(
                    g, observed=nets, lan_hosts=[],
                    rf_deauth=lambda b: trf.deauth(b),
                    rf_capture=lambda b, ch: trf.capture_handshake(b, ch, timeout=5),
                    net_scan=lambda h: no.scan(h).open_ports if no.scan(h).ok else [],
                    net_brute=lambda h, p: no.bruteforce(h, p))
        except Exception as e:  # noqa: BLE001
            print(f"[broadcast:{name}] error: {e}", flush=True)
    threading.Thread(target=_run, daemon=True).start()
