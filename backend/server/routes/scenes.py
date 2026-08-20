"""Scene picker plus scene authoring CRUD. Handlers delegate to AuthoringService."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, model_validator

from models.Scene import Scene
from server.deps import AuthoringDep
from server.routes.authoring import DeletePlanResponse, plan_response
from storage.records import SCENES

router = APIRouter(prefix="/api", tags=["scenes"])


class SceneSummary(BaseModel):
    id: str
    preset_id: str


class SceneListResponse(BaseModel):
    scenes: List[SceneSummary]


class CreateSceneRequest(BaseModel):
    preset_id: Optional[str] = None
    dmx_preset_list_id: Optional[str] = None
    wled_preset_list_id: Optional[str] = None
    ilda_frame_list_id: Optional[str] = None
    id: Optional[str] = None

    @model_validator(mode="after")
    def preset_or_lists(self) -> "CreateSceneRequest":
        has_preset = bool(self.preset_id)
        has_lists = bool(self.dmx_preset_list_id) and bool(self.wled_preset_list_id)
        if has_preset == has_lists:
            raise ValueError(
                "provide preset_id, or both dmx_preset_list_id and wled_preset_list_id"
            )
        if (self.dmx_preset_list_id or self.wled_preset_list_id) and not has_lists:
            raise ValueError("both dmx_preset_list_id and wled_preset_list_id are required")
        return self


class UpdateSceneRequest(BaseModel):
    preset_id: Optional[str] = None
    dmx_preset_list_id: Optional[str] = None
    wled_preset_list_id: Optional[str] = None
    ilda_frame_list_id: Optional[str] = None

    @model_validator(mode="after")
    def preset_or_lists(self) -> "UpdateSceneRequest":
        has_preset = bool(self.preset_id)
        has_lists = bool(self.dmx_preset_list_id) and bool(self.wled_preset_list_id)
        if has_preset == has_lists:
            raise ValueError(
                "provide preset_id, or both dmx_preset_list_id and wled_preset_list_id"
            )
        if (self.dmx_preset_list_id or self.wled_preset_list_id) and not has_lists:
            raise ValueError("both dmx_preset_list_id and wled_preset_list_id are required")
        return self


@router.get("/scenes")
def list_scenes(authoring: AuthoringDep) -> SceneListResponse:
    return SceneListResponse(
        scenes=[
            SceneSummary(id=scene.id, preset_id=scene.preset_id)
            for scene in authoring.list_all(SCENES)
        ]
    )


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: str, authoring: AuthoringDep) -> Scene:
    return authoring.get(SCENES, scene_id)


@router.post("/scenes", status_code=status.HTTP_201_CREATED)
def create_scene(body: CreateSceneRequest, authoring: AuthoringDep) -> Scene:
    if body.preset_id:
        return authoring.create_scene(
            body.preset_id,
            ilda_frame_list_id=body.ilda_frame_list_id,
            scene_id=body.id,
        )
    return authoring.create_scene_from_cue_lists(
        body.dmx_preset_list_id or "",
        body.wled_preset_list_id or "",
        scene_id=body.id,
        ilda_frame_list_id=body.ilda_frame_list_id,
    )


@router.put("/scenes/{scene_id}")
def update_scene(scene_id: str, body: UpdateSceneRequest, authoring: AuthoringDep) -> Scene:
    if body.preset_id:
        return authoring.update_scene(
            scene_id,
            preset_id=body.preset_id,
            ilda_frame_list_id=body.ilda_frame_list_id,
        )
    return authoring.update_scene_from_cue_lists(
        scene_id,
        dmx_preset_list_id=body.dmx_preset_list_id or "",
        wled_preset_list_id=body.wled_preset_list_id or "",
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
