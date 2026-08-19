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


class LedfxHealth(BaseModel):
    enabled: bool
    reachable: bool


class StatusResponse(BaseModel):
    active_scene_id: Optional[str]
    is_active: bool
    sensitivity: Optional[float]
    sender: SenderHealth
    ledfx: LedfxHealth
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


@router.get("/status")
def get_status(engine: EngineDep) -> StatusResponse:
    state = engine.state()
    return StatusResponse(
        active_scene_id=state.active_scene_id,
        is_active=state.is_active,
        sensitivity=state.sensitivity,
        sender=SenderHealth(**engine.sender_health()),
        ledfx=LedfxHealth(
            enabled=engine.ledfx_enabled,
            reachable=engine.ledfx_client.reachable,
        ),
        latency=engine.latency.summary(),
    )
