"""Pydantic request/response models - the contract the M5Core firmware reads.

Keep these in lockstep with docs/api.md. The M5Core parses these shapes, so a
breaking change here is a breaking change to the firmware.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    device: str
    version: str
    mode: str
    threat_level: str
    bear_state: str
    uptime_seconds: int
    wifi_interface: str
    events_last_10m: int
    backend_status: str = "online"
    level: int = 1
    xp: int = 0
    network_count: int = 0


class EventModel(BaseModel):
    id: int | None = None
    timestamp: str
    mode: str | None = None
    event_type: str | None = None
    severity: str | None = None
    confidence: int | None = None
    source: str | None = None
    target: str | None = None
    ssid: str | None = None
    bssid: str | None = None
    channel: int | None = None
    rssi: int | None = None
    message: str | None = None
    raw_json: dict | None = None


class ModeRequest(BaseModel):
    mode: str = Field(..., description="One of: hibernate|foraging|honey|sentinel|apex")


class ModeResponse(BaseModel):
    mode: str
    display_name: str
    description: str
    bear_state: str
    allowed_actions: list[str]


class FormRequest(BaseModel):
    form: int = Field(..., description="KUMA form index to make active (0..unlocked-1)")


class ActionRequest(BaseModel):
    action: str
    target: str | None = None
    confirm: bool = False


class ActionResponse(BaseModel):
    action: str
    accepted: bool
    result: str
    message: str
