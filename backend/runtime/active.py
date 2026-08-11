from __future__ import annotations

from typing import Dict, List

from models.Active_DMX_Channels import UNIVERSE_SIZE, Active_DMX_Channels
from storage.json_store import StorageError
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    PRESETS,
    SCENES,
)

# Only one universe is buffered today. Devices carry a universe so the patch can be
# recorded now, but anything other than this is rejected rather than silently dropped.
SUPPORTED_UNIVERSE = 1

# The instance a sender reads. Rebuilt in place so a sender holding a reference always
# sees the latest values. ILDA has no equivalent: the laser path is parked, so nothing
# here resolves frames — see docs/laser_and_haze_safety.md.
active_dmx_channels = Active_DMX_Channels()


def build_channels(library, dmx_preset_id: str) -> List[int]:
    """
    Resolve a look into one universe buffer using each device's patched address.

    A device's slot comes from its DMX_Device record rather than from the order of
    the look, so address gaps are expressible and two devices claiming the same
    channel is an error instead of a silent overwrite.
    """
    preset = library.get(DMX_PRESETS, dmx_preset_id)

    channels = [0] * UNIVERSE_SIZE
    claimed_by: Dict[int, str] = {}

    for device_preset_id in preset.dmx_device_preset_ids:
        device_preset = library.get(DMX_DEVICE_PRESETS, device_preset_id)
        device = library.get(DMX_DEVICES, device_preset.device_id)

        if device.universe != SUPPORTED_UNIVERSE:
            raise StorageError(
                f"dmx_devices '{device.id}' is patched to universe {device.universe}, but only "
                f"universe {SUPPORTED_UNIVERSE} is buffered today"
            )
        if device.end_address > UNIVERSE_SIZE:
            raise StorageError(
                f"dmx_devices '{device.id}' ends at channel {device.end_address}, past the "
                f"{UNIVERSE_SIZE}-channel universe"
            )

        start = device.start_address - 1
        for offset in range(start, start + device.channel_count):
            holder = claimed_by.get(offset)
            if holder is not None and holder != device.id:
                raise StorageError(
                    f"dmx_devices '{device.id}' and '{holder}' both claim channel {offset + 1} "
                    f"in dmx_presets '{dmx_preset_id}'"
                )
            claimed_by[offset] = device.id

        values = list(device_preset.channel_values)[: device.channel_count]
        values += [0] * (device.channel_count - len(values))
        channels[start : start + device.channel_count] = values

    return channels


def active_dmx_preset_id(library, scene_id: str, index: int = 0) -> str:
    """The DMX preset a scene is on at a given cue index."""
    scene = library.get(SCENES, scene_id)
    preset = library.get(PRESETS, scene.preset_id)
    preset_list = library.get(DMX_PRESET_LISTS, preset.dmx_preset_list_id)
    if not preset_list.dmx_preset_ids:
        raise StorageError(f"dmx_preset_lists '{preset_list.id}' holds no presets")
    return preset_list.dmx_preset_ids[index]


def update_active_dmx_channels(library, scene_id: str, index: int = 0) -> Active_DMX_Channels:
    active_dmx_channels.channels = build_channels(
        library, active_dmx_preset_id(library, scene_id, index)
    )
    return active_dmx_channels
