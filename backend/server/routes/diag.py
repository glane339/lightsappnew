"""
The measurement harness.

``/api/diag/latency`` reports the ring buffer; ``/api/diag/selftest`` drives the acceptance
run — 1000 activations with p99 under 10 ms is the M1 gate. The self-test measures the
server-side path only, from command-accepted to packet-sent, so it isolates the server
from browser and network jitter.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from server.commands import CommandKind, ShowCommand
from server.deps import EngineDep

router = APIRouter(prefix="/api/diag", tags=["diag"])

# Long enough for a slow machine to drain 5000 commands, short enough to fail visibly.
_DRAIN_TIMEOUT_S = 30.0
_DRAIN_POLL_S = 0.005


class SelfTestRequest(BaseModel):
    scene_id: str = Field(min_length=1)
    count: int = Field(default=1000, ge=1, le=5000)
    gap_ms: float = Field(
        default=1.0,
        ge=0.0,
        le=100.0,
        description="pause between activations, so each is timed on an idle sender",
    )


class SelfTestResponse(BaseModel):
    requested: int
    measured: int
    latency: Dict[str, int]
    within_budget: bool


class LatencyResponse(BaseModel):
    count: int
    p50_us: int
    p95_us: int
    p99_us: int
    max_us: int


BUDGET_US = 10_000


@router.get("/latency")
def get_latency(engine: EngineDep) -> LatencyResponse:
    return LatencyResponse(**engine.latency.snapshot())


@router.post("/selftest")
def selftest(body: SelfTestRequest, engine: EngineDep) -> SelfTestResponse:
    """
    Activate one scene repeatedly and report the distribution.

    Runs in FastAPI's threadpool rather than on the event loop, so the sleeps between
    activations do not stall the server being measured.

    Refused against a live transport: thousands of activations would strobe the rig and
    wipe the operational latency window mid-show.
    """
    transport = engine.sender_health()["transport"]
    if transport != "null":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"self-test refuses to run against the {transport!r} transport; "
                "set dmx.transport to 'null' to measure the software path"
            ),
        )

    engine.latency.clear()
    gap_s = body.gap_ms / 1000.0

    for _ in range(body.count):
        try:
            engine.submit(
                ShowCommand(
                    kind=CommandKind.ACTIVATE,
                    received_ns=time.perf_counter_ns(),
                    scene_id=body.scene_id,
                    ack_id=uuid.uuid4().hex,
                )
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        if gap_s:
            time.sleep(gap_s)

    deadline = time.monotonic() + _DRAIN_TIMEOUT_S
    while engine.latency.snapshot()["count"] < body.count and time.monotonic() < deadline:
        time.sleep(_DRAIN_POLL_S)

    snapshot = engine.latency.snapshot()
    return SelfTestResponse(
        requested=body.count,
        measured=snapshot["count"],
        latency=snapshot,
        within_budget=bool(snapshot["count"]) and snapshot["p99_us"] <= BUDGET_US,
    )
