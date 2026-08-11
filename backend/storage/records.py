from __future__ import annotations

from typing import Dict, List, Tuple, Type

from pydantic import BaseModel

SCENES = "scenes"
PRESETS = "presets"
DMX_PRESET_LISTS = "dmx_preset_lists"
DMX_PRESETS = "dmx_presets"
DMX_DEVICE_PRESETS = "dmx_device_presets"
WLED_PRESET_LISTS = "wled_preset_lists"
WLED_PRESETS = "wled_presets"
ILDA_FRAME_LISTS = "ilda_frame_lists"
ILDA_FRAMES = "ilda_frames"


class SceneRecord(BaseModel):
    id: str
    preset_id: str
    ilda_frame_list_id: str
    sensitivity: float


class PresetRecord(BaseModel):
    id: str
    dmx_preset_list_id: str
    wled_preset_list_id: str


class DMXPresetListRecord(BaseModel):
    id: str
    dmx_preset_ids: List[str] = []


class DMXPresetRecord(BaseModel):
    id: str
    dmx_device_preset_ids: List[str] = []


class DMXDevicePresetRecord(BaseModel):
    id: str
    order: int
    channel_count: int
    channel_values: List[int] = []


class WLEDPresetListRecord(BaseModel):
    id: str
    wled_preset_ids: List[str] = []
    beats: int = 0


class WLEDPresetRecord(BaseModel):
    id: str


class ILDAFrameListRecord(BaseModel):
    id: str
    ilda_frame_ids: List[str] = []


class ILDAFrameRecord(BaseModel):
    """Just the id, which is the name of the file in ilda/ that the ILDA system plays."""

    id: str


RECORD_TYPES: Dict[str, Type[BaseModel]] = {
    SCENES: SceneRecord,
    PRESETS: PresetRecord,
    DMX_PRESET_LISTS: DMXPresetListRecord,
    DMX_PRESETS: DMXPresetRecord,
    DMX_DEVICE_PRESETS: DMXDevicePresetRecord,
    WLED_PRESET_LISTS: WLEDPresetListRecord,
    WLED_PRESETS: WLEDPresetRecord,
    ILDA_FRAME_LISTS: ILDAFrameListRecord,
    ILDA_FRAMES: ILDAFrameRecord,
}

# Leaves first: a collection only ever points at collections listed before it.
COLLECTION_ORDER: Tuple[str, ...] = (
    WLED_PRESETS,
    WLED_PRESET_LISTS,
    DMX_DEVICE_PRESETS,
    DMX_PRESETS,
    DMX_PRESET_LISTS,
    PRESETS,
    ILDA_FRAMES,
    ILDA_FRAME_LISTS,
    SCENES,
)

# Anchors for orphan pruning. Scenes because nothing points at them, and ILDA frames
# because their .ild files are dropped into the folder and own their own lifetime.
ROOT_COLLECTIONS: Tuple[str, ...] = (SCENES, ILDA_FRAMES)

# parent collection -> (id attribute, child collection, attribute holds a list of ids)
# The attribute name is the same on the model and on the record.
REFERENCES: Dict[str, Tuple[Tuple[str, str, bool], ...]] = {
    SCENES: (
        ("preset_id", PRESETS, False),
        ("ilda_frame_list_id", ILDA_FRAME_LISTS, False),
    ),
    PRESETS: (
        ("dmx_preset_list_id", DMX_PRESET_LISTS, False),
        ("wled_preset_list_id", WLED_PRESET_LISTS, False),
    ),
    DMX_PRESET_LISTS: (("dmx_preset_ids", DMX_PRESETS, True),),
    DMX_PRESETS: (("dmx_device_preset_ids", DMX_DEVICE_PRESETS, True),),
    WLED_PRESET_LISTS: (("wled_preset_ids", WLED_PRESETS, True),),
    ILDA_FRAME_LISTS: (("ilda_frame_ids", ILDA_FRAMES, True),),
}
