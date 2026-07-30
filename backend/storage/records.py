from __future__ import annotations

from typing import Dict, List, Tuple, Type

from pydantic import BaseModel

SCENES = "scenes"
PRESET_LISTS = "preset_lists"
PRESETS = "presets"
DMX_PRESETS = "dmx_presets"
DMX_DEVICE_PRESETS = "dmx_device_presets"
WLED_PRESETS = "wled_presets"
ILDA_FRAME_LISTS = "ilda_frame_lists"
ILDA_FRAMES = "ilda_frames"
ACTIVE_DMX_CHANNELS = "active_dmx_channels"


class SceneRecord(BaseModel):
    id: str
    preset_list_id: str
    ilda_frame_list_id: str
    sensitivity: float


class PresetListRecord(BaseModel):
    id: str
    preset_ids: List[str] = []


class PresetRecord(BaseModel):
    id: str
    dmx_preset_id: str
    wled_preset_id: str


class DMXPresetRecord(BaseModel):
    id: str
    dmx_device_preset_ids: List[str] = []


class DMXDevicePresetRecord(BaseModel):
    id: str
    order: int
    channel_count: int
    channel_values: List[int] = []


class WLEDPresetRecord(BaseModel):
    id: str


class ILDAFrameListRecord(BaseModel):
    id: str
    ilda_frame_ids: List[str] = []


class ILDAFrameRecord(BaseModel):
    """Just the id, which is the name of the file in ilda/ that the ILDA system plays."""

    id: str


class ActiveDMXChannelsRecord(BaseModel):
    id: str
    channels: List[int] = []


RECORD_TYPES: Dict[str, Type[BaseModel]] = {
    SCENES: SceneRecord,
    PRESET_LISTS: PresetListRecord,
    PRESETS: PresetRecord,
    DMX_PRESETS: DMXPresetRecord,
    DMX_DEVICE_PRESETS: DMXDevicePresetRecord,
    WLED_PRESETS: WLEDPresetRecord,
    ILDA_FRAME_LISTS: ILDAFrameListRecord,
    ILDA_FRAMES: ILDAFrameRecord,
    ACTIVE_DMX_CHANNELS: ActiveDMXChannelsRecord,
}

# Leaves first: a collection only ever points at collections listed before it.
COLLECTION_ORDER: Tuple[str, ...] = (
    WLED_PRESETS,
    DMX_DEVICE_PRESETS,
    DMX_PRESETS,
    PRESETS,
    PRESET_LISTS,
    ILDA_FRAMES,
    ILDA_FRAME_LISTS,
    SCENES,
    ACTIVE_DMX_CHANNELS,
)

# Anchors for orphan pruning. Scenes and channel maps because nothing points at them, and
# ILDA frames because their .ild files are dropped into the folder and own their own lifetime.
ROOT_COLLECTIONS: Tuple[str, ...] = (SCENES, ACTIVE_DMX_CHANNELS, ILDA_FRAMES)

# parent collection -> (id attribute, child collection, attribute holds a list of ids)
# The attribute name is the same on the model and on the record.
REFERENCES: Dict[str, Tuple[Tuple[str, str, bool], ...]] = {
    SCENES: (
        ("preset_list_id", PRESET_LISTS, False),
        ("ilda_frame_list_id", ILDA_FRAME_LISTS, False),
    ),
    PRESET_LISTS: (("preset_ids", PRESETS, True),),
    PRESETS: (
        ("dmx_preset_id", DMX_PRESETS, False),
        ("wled_preset_id", WLED_PRESETS, False),
    ),
    DMX_PRESETS: (("dmx_device_preset_ids", DMX_DEVICE_PRESETS, True),),
    ILDA_FRAME_LISTS: (("ilda_frame_ids", ILDA_FRAMES, True),),
}
