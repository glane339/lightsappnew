"""Read-only scene list for the picker. Authoring CRUD lands in M4 (WS-10.6)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from server.deps import LibraryDep
from storage.records import SCENES

router = APIRouter(prefix="/api", tags=["scenes"])


class SceneSummary(BaseModel):
    id: str
    preset_id: str
    sensitivity: float


class SceneListResponse(BaseModel):
    scenes: List[SceneSummary]


@router.get("/scenes")
def list_scenes(library: LibraryDep) -> SceneListResponse:
    return SceneListResponse(
        scenes=[
            SceneSummary(id=scene.id, preset_id=scene.preset_id, sensitivity=scene.sensitivity)
            for scene in library.all(SCENES)
        ]
    )
