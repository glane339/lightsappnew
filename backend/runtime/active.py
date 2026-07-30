from __future__ import annotations

from typing import List

from models.Active_DMX_Channels import UNIVERSE_SIZE, Active_DMX_Channels
from models.Active_ILDA_Frame import Active_ILDA_Frame
from storage.json_store import StorageError
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    ILDA_FRAME_LISTS,
    PRESETS,
    SCENES,
)

# The two instances the senders read. Rebuilt in place so a sender holding a reference
# always sees the latest values.
active_dmx_channels = Active_DMX_Channels()
active_ilda_frame = Active_ILDA_Frame()


def build_channels(library, dmx_preset_id: str) -> List[int]:
    """
    Lay the preset's device presets end to end into one universe.

    Devices are sorted by `order`, and each one starts where the previous device's
    channels ended, so a device's start address is the sum of the channel_count of
    every device before it.
    """
    preset = library.get(DMX_PRESETS, dmx_preset_id)
    devices = sorted(
        (library.get(DMX_DEVICE_PRESETS, device_id) for device_id in preset.dmx_device_preset_ids),
        key=lambda device: device.order,
    )

    channels = [0] * UNIVERSE_SIZE
    cursor = 0
    for device in devices:
        if cursor + device.channel_count > UNIVERSE_SIZE:
            raise StorageError(
                f"dmx_presets '{dmx_preset_id}' needs more than {UNIVERSE_SIZE} channels: "
                f"dmx_device_presets '{device.id}' would end at channel "
                f"{cursor + device.channel_count}"
            )
        values = list(device.channel_values)[: device.channel_count]
        values += [0] * (device.channel_count - len(values))
        channels[cursor : cursor + device.channel_count] = values
        cursor += device.channel_count
    return channels


def active_dmx_preset_id(library, scene_id: str, index: int = 0) -> str:
    """The DMX preset a scene is currently on. Audio input will pick the index later."""
    scene = library.get(SCENES, scene_id)
    preset = library.get(PRESETS, scene.preset_id)
    preset_list = library.get(DMX_PRESET_LISTS, preset.dmx_preset_list_id)
    if not preset_list.dmx_preset_ids:
        raise StorageError(f"dmx_preset_lists '{preset_list.id}' holds no presets")
    return preset_list.dmx_preset_ids[index]


def active_ilda_frame_id(library, scene_id: str, index: int = 0) -> str:
    """The ILDA frame a scene is currently on. Audio input will pick the index later."""
    scene = library.get(SCENES, scene_id)
    frame_list = library.get(ILDA_FRAME_LISTS, scene.ilda_frame_list_id)
    if not frame_list.ilda_frame_ids:
        raise StorageError(f"ilda_frame_lists '{frame_list.id}' holds no frames")
    return frame_list.ilda_frame_ids[index]


def update_active_dmx_channels(library, scene_id: str, index: int = 0) -> Active_DMX_Channels:
    active_dmx_channels.channels = build_channels(
        library, active_dmx_preset_id(library, scene_id, index)
    )
    return active_dmx_channels


def update_active_ilda_frame(library, scene_id: str, index: int = 0) -> Active_ILDA_Frame:
    active_ilda_frame.frame_id = active_ilda_frame_id(library, scene_id, index)
    return active_ilda_frame
