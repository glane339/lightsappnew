"""
REST mirror of the control plane.

Every hot-path action is reachable over HTTP as well as the socket, for scripting and as
a fallback when the socket is down. Same queue, same show thread, so the latency ledger
covers both — HTTP just spends more of the budget getting here.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from server.commands import CommandKind, ShowCommand
from server.deps import EngineDep
from server.engine import ShowBusyError, ShowEngine

router = APIRouter(prefix="/api/show", tags=["show"])


class ActivateRequest(BaseModel):
    id: str = Field(min_length=1, description="scene id")


class AcceptedResponse(BaseModel):
    accepted: bool
    ack: str


class StateResponse(BaseModel):
    active_scene_id: str | None
    is_active: bool


def _enqueue(engine: ShowEngine, kind: CommandKind, scene_id: str | None = None) -> AcceptedResponse:
    received_ns = time.perf_counter_ns()
    ack_id = uuid.uuid4().hex
    try:
        engine.submit(
            ShowCommand(kind=kind, received_ns=received_ns, scene_id=scene_id, ack_id=ack_id)
        )
    except ShowBusyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return AcceptedResponse(accepted=True, ack=ack_id)


@router.get("/state")
def get_state(engine: EngineDep) -> StateResponse:
    state = engine.state()
    return StateResponse(
        active_scene_id=state.active_scene_id,
        is_active=state.is_active,
    )


@router.post("/activate")
def activate(body: ActivateRequest, engine: EngineDep) -> AcceptedResponse:
    """
    Queue a scene change.

    202-style semantics on a 200: the command is accepted here and applied on the show
    thread, so a bad scene id surfaces as an ``error`` event on the socket rather than as
    a failure of this call.
    """
    return _enqueue(engine, CommandKind.ACTIVATE, body.id)


@router.post("/deactivate")
def deactivate(engine: EngineDep) -> AcceptedResponse:
    return _enqueue(engine, CommandKind.DEACTIVATE)


@router.post("/blackout")
def blackout(engine: EngineDep) -> AcceptedResponse:
    return _enqueue(engine, CommandKind.BLACKOUT)


@router.post("/beat")
def beat(engine: EngineDep) -> AcceptedResponse:
    """Manual tap, until a detector fills this role (WS-9)."""
    return _enqueue(engine, CommandKind.BEAT)
