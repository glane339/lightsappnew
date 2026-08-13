"""Liveness and the one aggregate view the operator page polls."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from server.deps import EngineDep

router = APIRouter(prefix="/api", tags=["status"])


class HealthResponse(BaseModel):
    status: str


class SenderHealth(BaseModel):
    running: bool
    transport: str
    frames_sent: Optional[int]


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
