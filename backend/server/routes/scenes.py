"""Scene picker plus scene authoring CRUD. Handlers delegate to AuthoringService."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from models.Scene import Scene
from server.deps import AuthoringDep
from server.routes.authoring import DeletePlanResponse, plan_response
from storage.records import SCENES

router = APIRouter(prefix="/api", tags=["scenes"])


class SceneSummary(BaseModel):
    id: str
    preset_id: str
    sensitivity: float


class SceneListResponse(BaseModel):
    scenes: List[SceneSummary]


class CreateSceneRequest(BaseModel):
    preset_id: str
    sensitivity: Optional[float] = None
    ilda_frame_list_id: Optional[str] = None
    id: Optional[str] = None


class UpdateSceneRequest(BaseModel):
    preset_id: str
    sensitivity: float
    ilda_frame_list_id: Optional[str] = None


@router.get("/scenes")
def list_scenes(authoring: AuthoringDep) -> SceneListResponse:
    return SceneListResponse(
        scenes=[
            SceneSummary(id=scene.id, preset_id=scene.preset_id, sensitivity=scene.sensitivity)
            for scene in authoring.list_all(SCENES)
        ]
    )


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: str, authoring: AuthoringDep) -> Scene:
    return authoring.get(SCENES, scene_id)


@router.post("/scenes", status_code=status.HTTP_201_CREATED)
def create_scene(body: CreateSceneRequest, authoring: AuthoringDep) -> Scene:
    return authoring.create_scene(
        body.preset_id,
        sensitivity=body.sensitivity,
        ilda_frame_list_id=body.ilda_frame_list_id,
        scene_id=body.id,
    )


@router.put("/scenes/{scene_id}")
def update_scene(scene_id: str, body: UpdateSceneRequest, authoring: AuthoringDep) -> Scene:
    return authoring.update_scene(
        scene_id,
        preset_id=body.preset_id,
        sensitivity=body.sensitivity,
        ilda_frame_list_id=body.ilda_frame_list_id,
    )


@router.get("/scenes/{scene_id}/delete-plan")
def plan_delete_scene(scene_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(SCENES, scene_id))


@router.delete("/scenes/{scene_id}")
def delete_scene(
    scene_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(SCENES, scene_id, force=force))
