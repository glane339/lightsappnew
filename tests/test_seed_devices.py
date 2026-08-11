from __future__ import annotations

from models.DMX_Device_Preset import DMX_Device_Preset
from models.DMX_Preset import DMX_Preset
from runtime.active import build_channels
from seed_devices import RIG, seed_devices
from storage.library import Library
from storage.records import DMX_DEVICES


def test_seed_creates_the_documented_patch(library: Library) -> None:
    added = seed_devices(library)

    assert {device.name for device in added} == {"GigBAR 2", "Keobin Light Bar"}

    by_name = {device.name: device for device in library.all(DMX_DEVICES)}
    gigbar = by_name["GigBAR 2"]
    keobin = by_name["Keobin Light Bar"]

    assert (gigbar.start_address, gigbar.end_address, gigbar.channel_count) == (1, 23, 23)
    assert (keobin.start_address, keobin.end_address, keobin.channel_count) == (25, 42, 18)
    assert gigbar.model == "chauvet_gigbar_2"
    assert keobin.model == "keobin_light_bar"
    assert all(device.universe == 1 for device in (gigbar, keobin))


def test_seed_is_idempotent(library: Library) -> None:
    seed_devices(library)

    assert seed_devices(library) == []
    assert len(library.all(DMX_DEVICES)) == len(RIG)


def test_seed_survives_a_save_and_reload(data_root) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    seed_devices(lib)
    lib.save()

    reloaded = Library.open(data_root, sync_ilda=False)
    assert len(reloaded.all(DMX_DEVICES)) == len(RIG)


def test_seeded_addresses_do_not_overlap(library: Library) -> None:
    devices = seed_devices(library)

    device_presets = [
        DMX_Device_Preset(device_id=device.id, channel_values=[255] * device.channel_count)
        for device in devices
    ]
    for device_preset in device_presets:
        library.add(device_preset)
    look = DMX_Preset(dmx_device_preset_ids=[dp.id for dp in device_presets])
    library.add(look)

    channels = build_channels(library, look.id)

    # Each device's block is lit; the channel the old 24-wide patch left spare stays
    # dark, as does everything past the last device.
    assert channels[0:23] == [255] * 23
    assert channels[23] == 0
    assert channels[24:42] == [255] * 18
    assert channels[42:] == [0] * (len(channels) - 42)
