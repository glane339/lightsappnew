from __future__ import annotations

import threading
from typing import Dict, List, Optional, Sequence

from dmx_slots import clamp_dmx_slots
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


class UniverseState:
    """
    One process-owned universe: the buffer a sender reads, the dirty flag that wakes it,
    and a publish counter so the show thread can tell whether a command produced a frame.

    Each ``ShowEngine`` holds its own instance. Nothing here is a module global, so two
    engines in one process cannot share a universe by accident (F-03 / AF-M03 / WS-3.4).
    Writes take a lock; the sender snapshots under the same lock so it never reads a
    half-replaced list.
    """

    def __init__(self, channels: Optional[Active_DMX_Channels] = None) -> None:
        self._channels = channels if channels is not None else Active_DMX_Channels()
        self.dirty = threading.Event()
        self._lock = threading.Lock()
        self._publish_count = 0

    @property
    def channels(self) -> Active_DMX_Channels:
        return self._channels

    def publish(self) -> None:
        """Announce that the buffer holds a new frame."""
        with self._lock:
            self._publish_count += 1
        self.dirty.set()

    def publish_count(self) -> int:
        with self._lock:
            return self._publish_count

    def snapshot(self) -> List[int]:
        with self._lock:
            return list(self._channels.channels)

    def replace(self, values: Sequence[int]) -> None:
        """Swap in a full universe (clamped, padded) and wake the sender."""
        clamped = clamp_dmx_slots(values)
        if len(clamped) < UNIVERSE_SIZE:
            clamped = clamped + [0] * (UNIVERSE_SIZE - len(clamped))
        elif len(clamped) > UNIVERSE_SIZE:
            clamped = clamped[:UNIVERSE_SIZE]
        with self._lock:
            self._channels.channels = clamped
        self.publish()


def build_channels(library, dmx_preset_id: str) -> List[int]:
    """
    Resolve a look into one universe buffer using each device's patched address.

    A device's slot comes from its DMX_Device record rather than from the order of
    the look, so address gaps are expressible and two devices claiming the same
    channel is an error instead of a silent overwrite. Values are clamped 0–255
    so a bypass of the model still cannot put an illegal slot on the wire.
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

        values = clamp_dmx_slots(list(device_preset.channel_values)[: device.channel_count])
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
