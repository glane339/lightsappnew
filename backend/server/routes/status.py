"""Liveness, operator status, and process shutdown."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

from server.deps import EngineDep

router = APIRouter(prefix="/api", tags=["status"])


class HealthResponse(BaseModel):
    status: str


class SenderHealth(BaseModel):
    running: bool
    transport: str
    frames_sent: Optional[int]
    destination: Optional[str] = None
    send_failures: Optional[int] = None
    reachable: bool = True


class LedfxHealth(BaseModel):
    enabled: bool
    reachable: bool


class AudioHealth(BaseModel):
    capture: str
    bpm: Optional[float] = None
    level: Optional[float] = None
    running: bool = False


class StatusResponse(BaseModel):
    active_scene_id: Optional[str]
    is_active: bool
    sender: SenderHealth
    ledfx: LedfxHealth
    audio: AudioHealth
    last_error: Optional[str] = None
    latency: Dict[str, int]


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


class ShutdownResponse(BaseModel):
    status: str


@router.post("/shutdown")
def shutdown(request: Request, background: BackgroundTasks) -> ShutdownResponse:
    """
    Stop the operator process after the response is sent.

    Uvicorn's lifespan then runs ``engine.stop()``, which blacks out and closes the
    transport. Tests leave ``app.state.request_shutdown`` unset so this is a no-op.
    """
    callback = getattr(request.app.state, "request_shutdown", None)

    def _stop() -> None:
        if callback is not None:
            callback()

    background.add_task(_stop)
    return ShutdownResponse(status="stopping")


def _audio_health(request: Request) -> AudioHealth:
    source = getattr(request.app.state, "audio_source", None)
    if source is None:
        return AudioHealth(capture="off", running=False)
    health_fn = getattr(source, "health", None)
    if callable(health_fn):
        payload = health_fn()
        return AudioHealth(
            capture=str(payload.get("capture", "off")),
            bpm=payload.get("bpm"),
            level=payload.get("level"),
            running=bool(payload.get("running", False)),
        )
    return AudioHealth(capture="off", running=False)


@router.get("/status")
def get_status(request: Request, engine: EngineDep) -> StatusResponse:
    state = engine.state()
    return StatusResponse(
        active_scene_id=state.active_scene_id,
        is_active=state.is_active,
        sender=SenderHealth(**engine.sender_health()),
        ledfx=LedfxHealth(
            enabled=engine.ledfx_enabled,
            reachable=engine.ledfx_client.reachable,
        ),
        audio=_audio_health(request),
        last_error=engine.last_error,
        latency=engine.latency.summary(),
    )
