from __future__ import annotations

from pathlib import Path

import pytest

from conftest import build_cycling_scene_graph, build_minimal_scene_graph
from models.DMX_Device_Preset import DMX_Device_Preset
from models.Preset import Preset
from models.WLED_Preset import WLED_Preset
from storage.library import DanglingReferenceError, IntegrityError, Library
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_PRESETS,
    ILDA_FRAME_LISTS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)


def test_round_trip_preserves_graph(data_root: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    scene = build_minimal_scene_graph(lib)
    lib.save()

    reloaded = Library.open(data_root, sync_ilda=False)
    assert scene.id in reloaded.scenes
    loaded = reloaded.scenes[scene.id]
    assert loaded.preset_id == scene.preset_id
    preset = reloaded.presets[loaded.preset_id]
    wled_list = reloaded.wled_preset_lists[preset.wled_preset_list_id]
    assert wled_list.wled_preset_ids == ["scene-alpha"]
    assert reloaded.contains(WLED_PRESETS, "scene-alpha")
    assert len(reloaded.dmx_device_presets) == 1
    # Beat counts are configuration and have to survive the round trip.
    assert wled_list.beats == 4
    assert reloaded.dmx_preset_lists[preset.dmx_preset_list_id].beats == 2


def test_add_rejects_dangling_reference(library: Library) -> None:
    with pytest.raises(DanglingReferenceError):
        library.add(
            Preset(dmx_preset_list_id="missing-list", wled_preset_list_id="missing-wled-list")
        )


def test_load_rejects_dangling_reference_on_disk(data_root: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    build_minimal_scene_graph(lib)
    lib.save()

    lib.presets[next(iter(lib.presets))].wled_preset_list_id = "gone"
    from storage.json_store import write_collection
    from storage.migrations import SCHEMA_VERSION
    from storage.records import PRESETS as PRESETS_NAME

    items = {
        obj_id: lib._to_record(PRESETS_NAME, obj).model_dump()
        for obj_id, obj in lib.presets.items()
    }
    write_collection(PRESETS_NAME, items, SCHEMA_VERSION, data_root)

    with pytest.raises(DanglingReferenceError):
        Library.open(data_root, sync_ilda=False)


def test_delete_refuses_without_force(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    list_id = library.presets[scene.preset_id].wled_preset_list_id
    with pytest.raises(IntegrityError):
        library.delete(WLED_PRESET_LISTS, list_id)


def test_force_delete_wled_list_cascades_through_required_parents(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    list_id = library.presets[scene.preset_id].wled_preset_list_id

    deleted = library.delete(WLED_PRESET_LISTS, list_id, force=True)
    deleted_keys = set(deleted)

    assert (WLED_PRESET_LISTS, list_id) in deleted_keys
    assert (PRESETS, scene.preset_id) in deleted_keys
    assert (SCENES, scene.id) in deleted_keys
    assert scene.id not in library.scenes
    assert scene.preset_id not in library.presets
    # Leaf WLED preset is unlinked from the list, not force-cascaded as a required parent.
    assert library.contains(WLED_PRESETS, "scene-alpha")


def test_force_delete_wled_preset_unlinks_from_list(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    list_id = library.presets[scene.preset_id].wled_preset_list_id

    deleted = library.delete(WLED_PRESETS, "scene-alpha", force=True)
    assert (WLED_PRESETS, "scene-alpha") in deleted
    assert (WLED_PRESET_LISTS, list_id) not in deleted
    assert library.wled_preset_lists[list_id].wled_preset_ids == []
    assert scene.id in library.scenes


def test_force_delete_unlinks_from_list_without_removing_list(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    device_id = next(iter(library.dmx_device_presets))
    dmx_preset_id = next(iter(library.dmx_presets))

    deleted = library.delete(DMX_DEVICE_PRESETS, device_id, force=True)
    assert (DMX_DEVICE_PRESETS, device_id) in deleted
    assert (DMX_PRESETS, dmx_preset_id) not in deleted
    assert library.dmx_presets[dmx_preset_id].dmx_device_preset_ids == []
    assert scene.id in library.scenes


def test_prune_orphans_keeps_reachable_and_drops_unreachable(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    device_id = next(iter(library.dmx_devices))
    orphan = DMX_Device_Preset(device_id=device_id, channel_values=[1])
    library.add(orphan)

    removed = library.prune_orphans()
    assert DMX_DEVICE_PRESETS in removed
    assert orphan.id in removed[DMX_DEVICE_PRESETS]
    assert orphan.id not in library.dmx_device_presets
    assert scene.id in library.scenes
    assert len(library.dmx_device_presets) == 1


def test_add_rejects_duplicate_id_with_different_instance(library: Library) -> None:
    library.add(WLED_Preset(id="dup"))
    with pytest.raises(IntegrityError):
        library.add(WLED_Preset(id="dup"))


def test_wled_preset_list_is_storable(library: Library) -> None:
    from models.WLED_Preset_List import WLED_Preset_List

    library.add(WLED_Preset(id="only"))
    wled_list = WLED_Preset_List(wled_preset_ids=["only"], beats=4)
    library.add(wled_list)
    assert library.contains(WLED_PRESET_LISTS, wled_list.id)


def test_a_scene_needs_no_ilda_frame_list(library: Library) -> None:
    scene = build_cycling_scene_graph(library)

    loaded = library.get(SCENES, scene.scene_id)
    assert loaded.ilda_frame_list_id is None
    library.check_integrity()


def test_deleting_an_ilda_list_detaches_it_instead_of_killing_the_scene(
    library: Library,
) -> None:
    scene = build_minimal_scene_graph(library)
    frame_list_id = library.get(SCENES, scene.id).ilda_frame_list_id
    assert frame_list_id is not None

    deleted = library.delete(ILDA_FRAME_LISTS, frame_list_id, force=True)

    # An optional reference is nulled out; only a required parent goes down with its child.
    assert (ILDA_FRAME_LISTS, frame_list_id) in deleted
    assert (SCENES, scene.id) not in deleted
    assert scene.id in library.scenes
    assert library.get(SCENES, scene.id).ilda_frame_list_id is None
    library.check_integrity()


def test_a_required_reference_still_cascades(library: Library) -> None:
    scene = build_minimal_scene_graph(library)
    preset_id = scene.preset_id

    deleted = library.delete(PRESETS, preset_id, force=True)

    # Scene.preset_id is required, so the scene cannot survive losing it.
    assert (SCENES, scene.id) in deleted
    assert scene.id not in library.scenes


def test_prune_orphans_keeps_unreferenced_wled_presets(library: Library) -> None:
    build_minimal_scene_graph(library)
    extra = WLED_Preset(id="unsynced-scene")
    library.add(extra)

    removed = library.prune_orphans()

    assert extra.id not in (removed.get(WLED_PRESETS) or ())
    assert extra.id in library.wled_presets
