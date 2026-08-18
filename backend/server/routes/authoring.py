"""Typed authoring HTTP: presets, cue lists, looks, WLED names, and the patch."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from models.DMX_Device_Preset import DMX_Device_Preset
from models.DMX_Preset import DMX_Preset
from models.DMX_Preset_List import DMX_Preset_List
from models.Preset import Preset
from models.WLED_Preset import WLED_Preset
from models.WLED_Preset_List import WLED_Preset_List
from server.deps import AuthoringDep
from storage.library import DeletePlan
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    PRESETS,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)

router = APIRouter(prefix="/api", tags=["authoring"])


class RemovedRef(BaseModel):
    collection: str
    id: str


class DetachedRef(BaseModel):
    collection: str
    id: str
    attribute: str


class DeletePlanResponse(BaseModel):
    removes: List[RemovedRef]
    detaches: List[DetachedRef]


class CreateDevicePresetRequest(BaseModel):
    device_id: str
    channel_values: List[int]
    id: Optional[str] = None


class UpdateDevicePresetRequest(BaseModel):
    channel_values: List[int]


class CreateLookRequest(BaseModel):
    dmx_device_preset_ids: List[str]
    id: Optional[str] = None


class UpdateLookRequest(BaseModel):
    dmx_device_preset_ids: List[str]


class CreateDmxListRequest(BaseModel):
    dmx_preset_ids: List[str]
    beats: int
    id: Optional[str] = None


class UpdateDmxListRequest(BaseModel):
    dmx_preset_ids: List[str]
    beats: int


class CreateWledListRequest(BaseModel):
    wled_preset_ids: List[str]
    beats: int
    id: Optional[str] = None


class UpdateWledListRequest(BaseModel):
    wled_preset_ids: List[str]
    beats: int


class CreatePresetRequest(BaseModel):
    dmx_preset_list_id: str
    wled_preset_list_id: str
    id: Optional[str] = None


class UpdatePresetRequest(BaseModel):
    dmx_preset_list_id: str
    wled_preset_list_id: str


class RegisterWledPresetRequest(BaseModel):
    name: str


class DeviceResponse(BaseModel):
    id: str
    name: str
    model: Optional[str]
    mode: Optional[str]
    universe: int
    start_address: int
    channel_count: int
    end_address: int


def plan_response(plan: DeletePlan) -> DeletePlanResponse:
    return DeletePlanResponse(
        removes=[RemovedRef(collection=collection, id=obj_id) for collection, obj_id in plan.removes],
        detaches=[
            DetachedRef(collection=collection, id=obj_id, attribute=attr)
            for collection, obj_id, attr in plan.detaches
        ],
    )


# ------------------------------------------------------------------ device presets

@router.get("/dmx-device-presets")
def list_dmx_device_presets(authoring: AuthoringDep) -> dict:
    return {"dmx_device_presets": authoring.list_all(DMX_DEVICE_PRESETS)}


@router.get("/dmx-device-presets/{preset_id}")
def get_dmx_device_preset(preset_id: str, authoring: AuthoringDep) -> DMX_Device_Preset:
    return authoring.get(DMX_DEVICE_PRESETS, preset_id)


@router.post("/dmx-device-presets", status_code=status.HTTP_201_CREATED)
def create_dmx_device_preset(
    body: CreateDevicePresetRequest, authoring: AuthoringDep
) -> DMX_Device_Preset:
    return authoring.create_dmx_device_preset(
        body.device_id, body.channel_values, preset_id=body.id
    )


@router.put("/dmx-device-presets/{preset_id}")
def update_dmx_device_preset(
    preset_id: str, body: UpdateDevicePresetRequest, authoring: AuthoringDep
) -> DMX_Device_Preset:
    return authoring.update_dmx_device_preset(preset_id, body.channel_values)


@router.get("/dmx-device-presets/{preset_id}/delete-plan")
def plan_delete_dmx_device_preset(
    preset_id: str, authoring: AuthoringDep
) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(DMX_DEVICE_PRESETS, preset_id))


@router.delete("/dmx-device-presets/{preset_id}")
def delete_dmx_device_preset(
    preset_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(DMX_DEVICE_PRESETS, preset_id, force=force))


# ------------------------------------------------------------------ looks

@router.get("/dmx-presets")
def list_dmx_presets(authoring: AuthoringDep) -> dict:
    return {"dmx_presets": authoring.list_all(DMX_PRESETS)}


@router.get("/dmx-presets/{preset_id}")
def get_dmx_preset(preset_id: str, authoring: AuthoringDep) -> DMX_Preset:
    return authoring.get(DMX_PRESETS, preset_id)


@router.post("/dmx-presets", status_code=status.HTTP_201_CREATED)
def create_dmx_preset(body: CreateLookRequest, authoring: AuthoringDep) -> DMX_Preset:
    return authoring.create_dmx_preset(body.dmx_device_preset_ids, preset_id=body.id)


@router.put("/dmx-presets/{preset_id}")
def update_dmx_preset(
    preset_id: str, body: UpdateLookRequest, authoring: AuthoringDep
) -> DMX_Preset:
    return authoring.update_dmx_preset(preset_id, body.dmx_device_preset_ids)


@router.get("/dmx-presets/{preset_id}/delete-plan")
def plan_delete_dmx_preset(preset_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(DMX_PRESETS, preset_id))


@router.delete("/dmx-presets/{preset_id}")
def delete_dmx_preset(
    preset_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(DMX_PRESETS, preset_id, force=force))


# ------------------------------------------------------------------ DMX cue lists

@router.get("/dmx-preset-lists")
def list_dmx_preset_lists(authoring: AuthoringDep) -> dict:
    return {"dmx_preset_lists": authoring.list_all(DMX_PRESET_LISTS)}


@router.get("/dmx-preset-lists/{list_id}")
def get_dmx_preset_list(list_id: str, authoring: AuthoringDep) -> DMX_Preset_List:
    return authoring.get(DMX_PRESET_LISTS, list_id)


@router.post("/dmx-preset-lists", status_code=status.HTTP_201_CREATED)
def create_dmx_preset_list(body: CreateDmxListRequest, authoring: AuthoringDep) -> DMX_Preset_List:
    return authoring.create_dmx_preset_list(body.dmx_preset_ids, body.beats, list_id=body.id)


@router.put("/dmx-preset-lists/{list_id}")
def update_dmx_preset_list(
    list_id: str, body: UpdateDmxListRequest, authoring: AuthoringDep
) -> DMX_Preset_List:
    return authoring.update_dmx_preset_list(list_id, body.dmx_preset_ids, body.beats)


@router.get("/dmx-preset-lists/{list_id}/delete-plan")
def plan_delete_dmx_preset_list(list_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(DMX_PRESET_LISTS, list_id))


@router.delete("/dmx-preset-lists/{list_id}")
def delete_dmx_preset_list(
    list_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(DMX_PRESET_LISTS, list_id, force=force))


# ------------------------------------------------------------------ WLED cue lists

@router.get("/wled-preset-lists")
def list_wled_preset_lists(authoring: AuthoringDep) -> dict:
    return {"wled_preset_lists": authoring.list_all(WLED_PRESET_LISTS)}


@router.get("/wled-preset-lists/{list_id}")
def get_wled_preset_list(list_id: str, authoring: AuthoringDep) -> WLED_Preset_List:
    return authoring.get(WLED_PRESET_LISTS, list_id)


@router.post("/wled-preset-lists", status_code=status.HTTP_201_CREATED)
def create_wled_preset_list(
    body: CreateWledListRequest, authoring: AuthoringDep
) -> WLED_Preset_List:
    return authoring.create_wled_preset_list(body.wled_preset_ids, body.beats, list_id=body.id)


@router.put("/wled-preset-lists/{list_id}")
def update_wled_preset_list(
    list_id: str, body: UpdateWledListRequest, authoring: AuthoringDep
) -> WLED_Preset_List:
    return authoring.update_wled_preset_list(list_id, body.wled_preset_ids, body.beats)


@router.get("/wled-preset-lists/{list_id}/delete-plan")
def plan_delete_wled_preset_list(list_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(WLED_PRESET_LISTS, list_id))


@router.delete("/wled-preset-lists/{list_id}")
def delete_wled_preset_list(
    list_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(WLED_PRESET_LISTS, list_id, force=force))


# ------------------------------------------------------------------ lighting presets

@router.get("/presets")
def list_presets(authoring: AuthoringDep) -> dict:
    return {"presets": authoring.list_all(PRESETS)}


@router.get("/presets/{preset_id}")
def get_preset(preset_id: str, authoring: AuthoringDep) -> Preset:
    return authoring.get(PRESETS, preset_id)


@router.post("/presets", status_code=status.HTTP_201_CREATED)
def create_preset(body: CreatePresetRequest, authoring: AuthoringDep) -> Preset:
    return authoring.create_preset(
        body.dmx_preset_list_id,
        body.wled_preset_list_id,
        preset_id=body.id,
    )


@router.put("/presets/{preset_id}")
def update_preset(preset_id: str, body: UpdatePresetRequest, authoring: AuthoringDep) -> Preset:
    return authoring.update_preset(preset_id, body.dmx_preset_list_id, body.wled_preset_list_id)


@router.get("/presets/{preset_id}/delete-plan")
def plan_delete_preset(preset_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(PRESETS, preset_id))


@router.delete("/presets/{preset_id}")
def delete_preset(
    preset_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(PRESETS, preset_id, force=force))


# ------------------------------------------------------------------ WLED presets (LEDfx scene names)

@router.get("/wled-presets")
def list_wled_presets(authoring: AuthoringDep) -> dict:
    return {"wled_presets": authoring.list_all(WLED_PRESETS)}


@router.get("/wled-presets/{preset_id}")
def get_wled_preset(preset_id: str, authoring: AuthoringDep) -> WLED_Preset:
    return authoring.get(WLED_PRESETS, preset_id)


@router.post("/wled-presets", status_code=status.HTTP_201_CREATED)
def register_wled_preset(body: RegisterWledPresetRequest, authoring: AuthoringDep) -> WLED_Preset:
    return authoring.register_wled_preset(body.name)


@router.get("/wled-presets/{preset_id}/delete-plan")
def plan_delete_wled_preset(preset_id: str, authoring: AuthoringDep) -> DeletePlanResponse:
    return plan_response(authoring.plan_delete(WLED_PRESETS, preset_id))


@router.delete("/wled-presets/{preset_id}")
def delete_wled_preset(
    preset_id: str,
    authoring: AuthoringDep,
    force: bool = Query(False),
) -> DeletePlanResponse:
    return plan_response(authoring.delete(WLED_PRESETS, preset_id, force=force))


# ------------------------------------------------------------------ patch (read-only)

@router.get("/dmx-devices")
def list_dmx_devices(authoring: AuthoringDep) -> dict:
    return {
        "dmx_devices": [
            DeviceResponse(
                id=device.id,
                name=device.name,
                model=device.model,
                mode=device.mode,
                universe=device.universe,
                start_address=device.start_address,
                channel_count=device.channel_count,
                end_address=device.end_address,
            )
            for device in authoring.list_dmx_devices()
        ]
    }
