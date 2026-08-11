from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import build_minimal_scene_graph
from models.Active_DMX_Channels import UNIVERSE_SIZE
from models.DMX_Device import DMX_Device
from models.DMX_Device_Preset import DMX_Device_Preset
from models.DMX_Preset import DMX_Preset
from runtime.active import build_channels
from storage.json_store import StorageError
from storage.library import DanglingReferenceError, IntegrityError, Library
from storage.records import DMX_DEVICE_PRESETS, DMX_DEVICES, DMX_PRESETS


def test_device_round_trip(data_root: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    build_minimal_scene_graph(lib)
    device = DMX_Device(
        name="GigBAR (stage left)",
        model="chauvet_gigbar_move",
        mode="max",
        universe=1,
        start_address=100,
        channel_count=12,
    )
    lib.add(device)
    lib.save()

    reloaded = Library.open(data_root, sync_ilda=False)
    loaded = reloaded.dmx_devices[device.id]
    assert loaded.name == "GigBAR (stage left)"
    assert loaded.model == "chauvet_gigbar_move"
    assert loaded.mode == "max"
    assert loaded.start_address == 100
    assert loaded.channel_count == 12
    assert loaded.end_address == 111


def test_device_address_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        DMX_Device(name="bad", start_address=0, channel_count=4)
    with pytest.raises(ValidationError):
        DMX_Device(name="bad", start_address=1, channel_count=0)
    with pytest.raises(ValidationError):
        DMX_Device(name="bad", start_address=UNIVERSE_SIZE + 1, channel_count=1)


def test_device_preset_requires_existing_device(library: Library) -> None:
    with pytest.raises(DanglingReferenceError):
        library.add(DMX_Device_Preset(device_id="nope", channel_values=[1]))


def test_unused_device_survives_pruning(library: Library) -> None:
    build_minimal_scene_graph(library)
    spare = DMX_Device(name="Not patched into any look", start_address=200, channel_count=4)
    library.add(spare)

    removed = library.prune_orphans()

    assert DMX_DEVICES not in removed
    assert library.contains(DMX_DEVICES, spare.id)


def test_delete_device_refuses_while_referenced(library: Library) -> None:
    build_minimal_scene_graph(library)
    device_id = next(iter(library.dmx_devices))
    with pytest.raises(IntegrityError):
        library.delete(DMX_DEVICES, device_id)


def test_force_delete_device_cascades_to_its_presets(library: Library) -> None:
    build_minimal_scene_graph(library)
    device_id = next(iter(library.dmx_devices))
    device_preset_id = next(iter(library.dmx_device_presets))
    look_id = next(iter(library.dmx_presets))

    deleted = set(library.delete(DMX_DEVICES, device_id, force=True))

    assert (DMX_DEVICES, device_id) in deleted
    assert (DMX_DEVICE_PRESETS, device_preset_id) in deleted
    # The look survives; it just no longer lists that device preset.
    assert (DMX_PRESETS, look_id) not in deleted
    assert library.dmx_presets[look_id].dmx_device_preset_ids == []


def test_build_channels_uses_start_address_with_gaps(library: Library) -> None:
    first = DMX_Device(name="Par 1", start_address=1, channel_count=3)
    second = DMX_Device(name="Par 2", start_address=10, channel_count=2)
    library.add(first)
    library.add(second)

    first_values = DMX_Device_Preset(device_id=first.id, channel_values=[255, 128, 64])
    second_values = DMX_Device_Preset(device_id=second.id, channel_values=[11, 22])
    library.add(first_values)
    library.add(second_values)

    look = DMX_Preset(dmx_device_preset_ids=[first_values.id, second_values.id])
    library.add(look)

    channels = build_channels(library, look.id)

    assert channels[0:3] == [255, 128, 64]
    assert channels[3:9] == [0] * 6
    assert channels[9:11] == [11, 22]
    assert len(channels) == UNIVERSE_SIZE


def test_build_channels_pads_short_and_truncates_long_values(library: Library) -> None:
    device = DMX_Device(name="Par", start_address=1, channel_count=4)
    library.add(device)
    short = DMX_Device_Preset(device_id=device.id, channel_values=[5])
    library.add(short)
    look = DMX_Preset(dmx_device_preset_ids=[short.id])
    library.add(look)

    assert build_channels(library, look.id)[0:4] == [5, 0, 0, 0]

    long = DMX_Device_Preset(device_id=device.id, channel_values=[1, 2, 3, 4, 5, 6])
    library.add(long)
    wide_look = DMX_Preset(dmx_device_preset_ids=[long.id])
    library.add(wide_look)

    assert build_channels(library, wide_look.id)[0:5] == [1, 2, 3, 4, 0]


def test_build_channels_rejects_overlapping_devices(library: Library) -> None:
    first = DMX_Device(name="Par 1", start_address=1, channel_count=4)
    second = DMX_Device(name="Par 2", start_address=3, channel_count=4)
    library.add(first)
    library.add(second)
    first_values = DMX_Device_Preset(device_id=first.id, channel_values=[1, 2, 3, 4])
    second_values = DMX_Device_Preset(device_id=second.id, channel_values=[5, 6, 7, 8])
    library.add(first_values)
    library.add(second_values)
    look = DMX_Preset(dmx_device_preset_ids=[first_values.id, second_values.id])
    library.add(look)

    with pytest.raises(StorageError, match="both claim channel 3"):
        build_channels(library, look.id)


def test_build_channels_rejects_device_past_universe_end(library: Library) -> None:
    device = DMX_Device(name="Too far", start_address=510, channel_count=8)
    library.add(device)
    values = DMX_Device_Preset(device_id=device.id, channel_values=[1] * 8)
    library.add(values)
    look = DMX_Preset(dmx_device_preset_ids=[values.id])
    library.add(look)

    with pytest.raises(StorageError, match="past the"):
        build_channels(library, look.id)


def test_build_channels_rejects_second_universe(library: Library) -> None:
    device = DMX_Device(name="Universe 2 par", universe=2, start_address=1, channel_count=3)
    library.add(device)
    values = DMX_Device_Preset(device_id=device.id, channel_values=[1, 2, 3])
    library.add(values)
    look = DMX_Preset(dmx_device_preset_ids=[values.id])
    library.add(look)

    with pytest.raises(StorageError, match="universe 2"):
        build_channels(library, look.id)
