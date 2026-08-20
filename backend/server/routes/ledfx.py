"""One-shot LEDfx scene sync for the WLED cue-list builder."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from server.deps import EngineDep

router = APIRouter(prefix="/api/ledfx", tags=["ledfx"])


class RefreshResponse(BaseModel):
    added: int


@router.post("/refresh", status_code=status.HTTP_200_OK)
def refresh_scenes(engine: EngineDep) -> RefreshResponse:
    if not engine.ledfx_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LEDfx is disabled; enable it in local config to refresh scenes",
        )
    try:
        added = engine.refresh_ledfx_scenes()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RefreshResponse(added=added)
