from __future__ import annotations

from pathlib import Path

import pytest
from conftest import build_minimal_scene_graph

from authoring.service import (
    AuthoringConflict,
    AuthoringInvalid,
    AuthoringNotFound,
    AuthoringService,
)
from models.Active_DMX_Channels import Active_DMX_Channels
from models.DMX_Device import DMX_Device
from models.DMX_Preset import DMX_Preset
from models.DMX_Preset_List import DMX_Preset_List
from models.Preset import Preset
from models.WLED_Preset_List import WLED_Preset_List
from runtime.outputs import DmxOutput
from runtime.scene_controller import SceneController
from storage.library import Library
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)


def _device(library: Library, channel_count: int = 3) -> DMX_Device:
    device = DMX_Device(name="Test Par", start_address=1, channel_count=channel_count)
    library.add(device)
    return device


def _look(authoring: AuthoringService, device: DMX_Device, values=None):
    row = authoring.create_dmx_device_preset(
        device.id, list(values or [10, 20, 30])
    )
    return authoring.create_dmx_preset([row.id])


def _playable_preset(authoring: AuthoringService, library: Library) -> Preset:
    device = _device(library)
    look = _look(authoring, device)
    dmx_list = authoring.create_dmx_preset_list([look.id], 2)
    authoring.register_wled_preset("scene-alpha")
    wled_list = authoring.create_wled_preset_list(["scene-alpha"], 4)
    return authoring.create_preset(dmx_list.id, wled_list.id)


class _SilentWled:
    def apply(self, preset_id: str) -> None:
        return None


def test_create_scene_defaults_sensitivity_from_audio_config(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)

    scene = authoring.create_scene(preset.id, scene_id="red-wash")

    assert scene.id == "red-wash"
    assert scene.preset_id == preset.id
    assert scene.sensitivity == library.config.audio.default_sensitivity
    assert library.get(SCENES, "red-wash").id == "red-wash"


def test_create_scene_rejects_missing_preset(library: Library) -> None:
    authoring = AuthoringService(library)
    with pytest.raises(AuthoringInvalid, match="does not exist"):
        authoring.create_scene("missing-preset")


def test_create_scene_rejects_preset_with_empty_cue_list(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    look = _look(authoring, device)
    authoring.register_wled_preset("scene-alpha")
    empty = DMX_Preset_List(dmx_preset_ids=[], beats=1)
    wled_list = WLED_Preset_List(wled_preset_ids=["scene-alpha"], beats=1)
    preset = Preset(dmx_preset_list_id=empty.id, wled_preset_list_id=wled_list.id)
    library.add(empty)
    library.add(wled_list)
    library.add(preset)

    with pytest.raises(AuthoringInvalid, match="empty"):
        authoring.create_scene(preset.id)


def test_create_scene_rejects_out_of_range_sensitivity(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    with pytest.raises(AuthoringInvalid, match="sensitivity"):
        authoring.create_scene(preset.id, sensitivity=1.5)


def test_update_scene_changes_sensitivity_without_replacing_id(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    scene = authoring.create_scene(preset.id, sensitivity=0.2)

    updated = authoring.update_scene(scene.id, preset_id=preset.id, sensitivity=0.8)

    assert updated.id == scene.id
    assert updated.sensitivity == 0.8
    assert library.get(SCENES, scene.id).sensitivity == 0.8


def test_get_unknown_scene_is_not_found(library: Library) -> None:
    authoring = AuthoringService(library)
    with pytest.raises(AuthoringNotFound):
        authoring.get(SCENES, "nope")


def test_create_preset_rejects_missing_wled_list(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    look = _look(authoring, device)
    dmx_list = authoring.create_dmx_preset_list([look.id], 2)

    with pytest.raises(AuthoringInvalid, match="does not exist"):
        authoring.create_preset(dmx_list.id, "missing-wled-list")

    assert authoring.list_all(PRESETS) == []


def test_empty_cue_list_is_refused(library: Library) -> None:
    authoring = AuthoringService(library)
    with pytest.raises(AuthoringInvalid, match="at least one entry"):
        authoring.create_dmx_preset_list([], 2)


def test_cue_list_rejects_dangling_look(library: Library) -> None:
    authoring = AuthoringService(library)
    with pytest.raises(AuthoringInvalid, match="does not exist"):
        authoring.create_dmx_preset_list(["missing-look"], 2)


def test_wled_list_rejects_unregistered_name(library: Library) -> None:
    authoring = AuthoringService(library)
    with pytest.raises(AuthoringInvalid, match="register"):
        authoring.create_wled_preset_list(["Living Room"], 2)


def test_look_rejects_duplicate_device(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    first = authoring.create_dmx_device_preset(device.id, [1, 2, 3])
    second = authoring.create_dmx_device_preset(device.id, [4, 5, 6])
    with pytest.raises(AuthoringInvalid, match="appears twice"):
        authoring.create_dmx_preset([first.id, second.id])


def test_create_device_preset_from_channel_values(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)

    row = authoring.create_dmx_device_preset(
        device.id, [10, 20, 30], preset_id="par-red"
    )

    assert row.id == "par-red"
    assert row.device_id == device.id
    assert row.channel_values == [10, 20, 30]
    stored = authoring.get(DMX_DEVICE_PRESETS, "par-red")
    assert stored.channel_values == [10, 20, 30]


def test_create_device_preset_rejects_wrong_count_and_range(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library, channel_count=3)

    with pytest.raises(AuthoringInvalid, match="exactly 3"):
        authoring.create_dmx_device_preset(device.id, [1, 2])

    with pytest.raises(AuthoringInvalid, match="0-255"):
        authoring.create_dmx_device_preset(device.id, [1, 2, 256])

    with pytest.raises(AuthoringInvalid, match="does not exist"):
        authoring.create_dmx_device_preset("missing-device", [1, 2, 3])


def test_update_device_preset_replaces_values(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    row = authoring.create_dmx_device_preset(device.id, [1, 2, 3])

    updated = authoring.update_dmx_device_preset(row.id, [9, 8, 7])

    assert updated.id == row.id
    assert updated.channel_values == [9, 8, 7]
    assert authoring.get(DMX_DEVICE_PRESETS, row.id).channel_values == [9, 8, 7]


def test_create_look_from_ordered_device_preset_ids(library: Library) -> None:
    authoring = AuthoringService(library)
    par = _device(library)
    bar = DMX_Device(name="Test Bar", start_address=4, channel_count=3)
    library.add(bar)
    first = authoring.create_dmx_device_preset(par.id, [10, 20, 30], preset_id="par-red")
    second = authoring.create_dmx_device_preset(bar.id, [40, 50, 60], preset_id="bar-red")

    look = authoring.create_dmx_preset(
        dmx_device_preset_ids=[first.id, second.id], preset_id="all-red"
    )

    assert look.id == "all-red"
    assert look.dmx_device_preset_ids == [first.id, second.id]
    assert authoring.get(DMX_PRESETS, "all-red").dmx_device_preset_ids == [
        first.id,
        second.id,
    ]


def test_create_look_from_ids_rejects_missing_and_duplicate_device(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    row = authoring.create_dmx_device_preset(device.id, [1, 2, 3])
    other = authoring.create_dmx_device_preset(device.id, [4, 5, 6])

    with pytest.raises(AuthoringInvalid, match="does not exist"):
        authoring.create_dmx_preset(dmx_device_preset_ids=["missing-row"])

    with pytest.raises(AuthoringInvalid, match="appears twice"):
        authoring.create_dmx_preset(dmx_device_preset_ids=[row.id, other.id])


def test_update_look_swaps_ids_without_deleting_old_rows(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    first = authoring.create_dmx_device_preset(device.id, [1, 2, 3])
    second = authoring.create_dmx_device_preset(device.id, [4, 5, 6])
    look = authoring.create_dmx_preset(dmx_device_preset_ids=[first.id])

    updated = authoring.update_dmx_preset(look.id, dmx_device_preset_ids=[second.id])

    assert updated.dmx_device_preset_ids == [second.id]
    assert authoring.get(DMX_DEVICE_PRESETS, first.id).channel_values == [1, 2, 3]


def test_create_cue_list_from_looks(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    red = authoring.create_dmx_device_preset(device.id, [255, 0, 0])
    blue = authoring.create_dmx_device_preset(device.id, [0, 0, 255])
    look_red = authoring.create_dmx_preset(dmx_device_preset_ids=[red.id], preset_id="all-red")
    look_blue = authoring.create_dmx_preset(
        dmx_device_preset_ids=[blue.id], preset_id="all-blue"
    )

    cue_list = authoring.create_dmx_preset_list(
        [look_red.id, look_blue.id, look_red.id], 4, list_id="wash-cycle"
    )

    assert cue_list.id == "wash-cycle"
    assert cue_list.dmx_preset_ids == [look_red.id, look_blue.id, look_red.id]
    assert cue_list.beats == 4
    stored = authoring.get(DMX_PRESET_LISTS, "wash-cycle")
    assert stored.dmx_preset_ids == cue_list.dmx_preset_ids


def test_force_delete_refuses_emptying_a_still_referenced_look(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    row = authoring.create_dmx_device_preset(device.id, [1, 2, 3])
    look = authoring.create_dmx_preset(dmx_device_preset_ids=[row.id])
    authoring.create_dmx_preset_list([look.id], 2)

    with pytest.raises(AuthoringConflict, match="would empty"):
        authoring.delete(DMX_DEVICE_PRESETS, row.id, force=True)

    assert library.contains(DMX_DEVICE_PRESETS, row.id)


def test_create_wled_list_from_ordered_preset_ids(library: Library) -> None:
    authoring = AuthoringService(library)
    authoring.register_wled_preset("Living Room")
    authoring.register_wled_preset("Kitchen")

    cue_list = authoring.create_wled_preset_list(
        ["Living Room", "Kitchen", "Living Room"], 2, list_id="strip-cycle"
    )

    assert cue_list.id == "strip-cycle"
    assert cue_list.wled_preset_ids == ["Living Room", "Kitchen", "Living Room"]
    assert cue_list.beats == 2
    stored = authoring.get(WLED_PRESET_LISTS, "strip-cycle")
    assert stored.wled_preset_ids == cue_list.wled_preset_ids


def test_create_preset_from_existing_lists(library: Library) -> None:
    authoring = AuthoringService(library)
    device = _device(library)
    look = _look(authoring, device)
    dmx_list = authoring.create_dmx_preset_list([look.id], 4, list_id="wash-cycle")
    authoring.register_wled_preset("Living Room")
    wled_list = authoring.create_wled_preset_list(["Living Room"], 2, list_id="strip-cycle")

    preset = authoring.create_preset(dmx_list.id, wled_list.id, preset_id="red-wash-stripes")

    assert preset.id == "red-wash-stripes"
    assert preset.dmx_preset_list_id == dmx_list.id
    assert preset.wled_preset_list_id == wled_list.id


def test_cue_list_rejects_look_without_device_presets(library: Library) -> None:
    authoring = AuthoringService(library)
    empty_look = DMX_Preset(dmx_device_preset_ids=[])
    library.add(empty_look)

    with pytest.raises(AuthoringInvalid, match="no device presets"):
        authoring.create_dmx_preset_list([empty_look.id], 1)


def test_create_scene_rejects_look_without_device_presets(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    look_id = library.get(DMX_PRESET_LISTS, preset.dmx_preset_list_id).dmx_preset_ids[0]
    library.get(DMX_PRESETS, look_id).dmx_device_preset_ids = []

    with pytest.raises(AuthoringInvalid, match="device preset"):
        authoring.create_scene(preset.id)


def test_plan_delete_shows_scene_when_preset_would_cascade(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    scene = authoring.create_scene(preset.id)

    plan = authoring.plan_delete(PRESETS, preset.id)

    assert plan.would_remove(PRESETS, preset.id)
    assert plan.would_remove(SCENES, scene.id)


def test_delete_refuses_while_referenced_unless_forced(library: Library) -> None:
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    scene = authoring.create_scene(preset.id)

    with pytest.raises(AuthoringConflict, match="referenced"):
        authoring.delete(PRESETS, preset.id)

    plan = authoring.delete(PRESETS, preset.id, force=True)

    assert plan.would_remove(SCENES, scene.id)
    with pytest.raises(AuthoringNotFound):
        authoring.get(SCENES, scene.id)


def test_force_delete_refuses_emptying_a_still_referenced_cue_list(library: Library) -> None:
    authoring = AuthoringService(library)
    _playable_preset(authoring, library)

    with pytest.raises(AuthoringConflict, match="would empty"):
        authoring.delete(WLED_PRESETS, "scene-alpha", force=True)

    assert library.contains(WLED_PRESETS, "scene-alpha")


def test_create_scene_round_trips_through_save_load(data_root: Path) -> None:
    library = Library.open(data_root, sync_ilda=False)
    authoring = AuthoringService(library)
    preset = _playable_preset(authoring, library)
    scene = authoring.create_scene(preset.id, sensitivity=0.3, scene_id="round-trip")

    reloaded = Library.open(data_root, sync_ilda=False)
    loaded = reloaded.get(SCENES, "round-trip")
    assert loaded.preset_id == preset.id
    assert loaded.sensitivity == 0.3
    assert reloaded.get(PRESETS, preset.id).dmx_preset_list_id == preset.dmx_preset_list_id


def test_duplicate_wled_name_is_a_conflict(library: Library) -> None:
    authoring = AuthoringService(library)
    authoring.register_wled_preset("Living Room")
    with pytest.raises(AuthoringConflict, match="already exists"):
        authoring.register_wled_preset("Living Room")


def test_build_minimal_graph_still_readable_through_authoring(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    authoring = AuthoringService(library)
    fetched = authoring.get(SCENES, scene.id)
    assert fetched.preset_id == scene.preset_id
    assert len(authoring.list_all(SCENES)) == 1


def test_authored_looks_update_the_universe_when_the_beat_cycles(library: Library) -> None:
    authoring = AuthoringService(library)
    par = _device(library)
    bar = DMX_Device(name="Test Bar", start_address=10, channel_count=2)
    library.add(bar)

    par_red = authoring.create_dmx_device_preset(par.id, [255, 0, 0])
    bar_red = authoring.create_dmx_device_preset(bar.id, [40, 50])
    par_blue = authoring.create_dmx_device_preset(par.id, [0, 0, 255])
    bar_blue = authoring.create_dmx_device_preset(bar.id, [1, 2])

    look_red = authoring.create_dmx_preset([par_red.id, bar_red.id], preset_id="all-red")
    look_blue = authoring.create_dmx_preset([par_blue.id, bar_blue.id], preset_id="all-blue")
    dmx_list = authoring.create_dmx_preset_list([look_red.id, look_blue.id], 1)
    authoring.register_wled_preset("scene-alpha")
    wled_list = authoring.create_wled_preset_list(["scene-alpha"], 8)
    preset = authoring.create_preset(dmx_list.id, wled_list.id)
    scene = authoring.create_scene(preset.id)

    buffer = Active_DMX_Channels()
    controller = SceneController(library, DmxOutput(library, buffer), _SilentWled())
    controller.activate(scene.id)

    assert buffer.channels[0:3] == [255, 0, 0]
    assert buffer.channels[9:11] == [40, 50]

    controller.on_beat()

    assert buffer.channels[0:3] == [0, 0, 255]
    assert buffer.channels[9:11] == [1, 2]

    controller.on_beat()

    assert buffer.channels[0:3] == [255, 0, 0]
    assert buffer.channels[9:11] == [40, 50]


def test_look_posted_before_its_cue_is_picked_up_on_the_beat(library: Library) -> None:
    """Look content is live: rewrite a look while another is showing, then cycle onto it."""
    authoring = AuthoringService(library)
    device = _device(library)
    red = authoring.create_dmx_device_preset(device.id, [255, 0, 0])
    blue = authoring.create_dmx_device_preset(device.id, [0, 0, 255])
    look_red = authoring.create_dmx_preset([red.id], preset_id="all-red")
    look_blue = authoring.create_dmx_preset([blue.id], preset_id="all-blue")
    dmx_list = authoring.create_dmx_preset_list([look_red.id, look_blue.id], 1)
    authoring.register_wled_preset("scene-alpha")
    wled_list = authoring.create_wled_preset_list(["scene-alpha"], 8)
    preset = authoring.create_preset(dmx_list.id, wled_list.id)
    scene = authoring.create_scene(preset.id)

    buffer = Active_DMX_Channels()
    controller = SceneController(library, DmxOutput(library, buffer), _SilentWled())
    controller.activate(scene.id)
    assert buffer.channels[0:3] == [255, 0, 0]

    green = authoring.create_dmx_device_preset(device.id, [0, 255, 0])
    authoring.update_dmx_preset(look_blue.id, [green.id])
    controller.on_beat()

    assert buffer.channels[0:3] == [0, 255, 0]
