"""KUMA backend entrypoint.

    uvicorn kuma_api.app:app --host 0.0.0.0 --port 8080

On startup it initializes SQLite and, in mock mode (the Sprint 1 default),
launches a background task that drips synthetic Sentinel events so the M5Core
face has something to react to with no Wi-Fi hardware attached.

Set KUMA_MOCK=0 to disable the mock event loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import random
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from kuma_core import database
from kuma_core.config import settings
from detectors import mock_detector
from . import routes, state

MOCK_ENABLED = os.environ.get("KUMA_MOCK", "1") != "0"
MOCK_INTERVAL_SECONDS = int(os.environ.get("KUMA_MOCK_INTERVAL", "12"))


async def _mock_loop() -> None:
    """Emit a synthetic event every few seconds while in an active mode."""
    rng = random.Random()
    while True:
        await asyncio.sleep(MOCK_INTERVAL_SECONDS)
        if state.engine.current in ("sentinel", "foraging", "honey"):
            event = mock_detector.generate_event(mode=state.engine.current, rng=rng)
            database.insert_event(event)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    task: asyncio.Task | None = None
    if MOCK_ENABLED:
        task = asyncio.create_task(_mock_loop())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="KUMA",
    version=settings.version,
    description="Blue-team defensive gadget backend. Mock pipeline in v0.0.",
    lifespan=lifespan,
)
app.include_router(routes.router)


_DASHBOARD = Path(__file__).parent / "static" / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Read-only web face for headless KUMA (poll the API, draw the bear)."""
    try:
        return _DASHBOARD.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<h1>KUMA</h1><p>Dashboard missing. API at /api/status</p>"
