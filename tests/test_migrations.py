from __future__ import annotations

from pathlib import Path

import pytest

from storage.json_store import StorageError, read_json, write_collection, write_json
from storage.migrations import SCHEMA_VERSION, migrate, snapshot, stored_version
from storage.paths import backups_dir, config_path, ensure_layout
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)


def test_migrate_fresh_folder_records_current_version(data_root: Path) -> None:
    version = migrate(data_root)
    assert version == SCHEMA_VERSION
    assert stored_version(data_root) == SCHEMA_VERSION


def test_migrate_noop_when_already_current(data_root: Path) -> None:
    migrate(data_root)
    before = list(backups_dir(data_root).iterdir()) if backups_dir(data_root).exists() else []
    version = migrate(data_root)
    assert version == SCHEMA_VERSION
    after = list(backups_dir(data_root).iterdir())
    # No migration snapshot when nothing changes.
    assert len(after) == len(before)


def test_migrate_rejects_future_schema(data_root: Path) -> None:
    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": SCHEMA_VERSION + 10})
    with pytest.raises(StorageError, match="upgrade the app"):
        migrate(data_root)


def test_migrate_unknown_step_raises(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 0})

    import storage.migrations as migrations

    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 1)
    monkeypatch.setattr(migrations, "_STEPS", {})

    with pytest.raises(StorageError, match="no migration registered"):
        migrate(data_root)


def test_snapshot_copies_layout(data_root: Path) -> None:
    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": SCHEMA_VERSION})
    (data_root / "data" / "scenes.json").write_text('{"items":{}}\n', encoding="utf-8")
    dest = snapshot("test", data_root)
    assert (dest / "config.json").is_file()
    assert (dest / "data" / "scenes.json").is_file()


def test_migrate_v1_wraps_wled_preset_id_in_list(data_root: Path) -> None:
    from storage.json_store import read_collection

    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 1})
    write_collection(WLED_PRESETS, {"scene-alpha": {"id": "scene-alpha"}}, 1, data_root)
    write_collection(
        PRESETS,
        {
            "preset-1": {
                "id": "preset-1",
                "dmx_preset_list_id": "dmx-list-1",
                "wled_preset_id": "scene-alpha",
            }
        },
        1,
        data_root,
    )

    assert migrate(data_root) == SCHEMA_VERSION

    presets = read_collection(PRESETS, data_root)
    lists = read_collection(WLED_PRESET_LISTS, data_root)
    preset = presets["preset-1"]
    assert "wled_preset_id" not in preset
    list_id = preset["wled_preset_list_id"]
    assert list_id in lists
    assert lists[list_id]["wled_preset_ids"] == ["scene-alpha"]
    # v1→v2 creates the list with the old beats default of 0; v3→v4 lifts it to a
    # playable 1, so a full chain leaves the list usable rather than merely valid.
    assert lists[list_id]["beats"] == 1


def test_migrate_v2_synthesises_devices_from_order(data_root: Path) -> None:
    from storage.json_store import read_collection

    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 2})
    write_collection(
        DMX_DEVICE_PRESETS,
        {
            "dp-a": {"id": "dp-a", "order": 0, "channel_count": 3, "channel_values": [1, 2, 3]},
            "dp-b": {"id": "dp-b", "order": 1, "channel_count": 4, "channel_values": [4, 5, 6, 7]},
            # A second look reusing the same physical devices.
            "dp-c": {"id": "dp-c", "order": 0, "channel_count": 3, "channel_values": [9, 9, 9]},
        },
        2,
        data_root,
    )

    assert migrate(data_root) == SCHEMA_VERSION

    devices = read_collection(DMX_DEVICES, data_root)
    presets = read_collection(DMX_DEVICE_PRESETS, data_root)

    # One device per distinct order, addressed by the old packing rule.
    assert len(devices) == 2
    by_address = {device["start_address"]: device for device in devices.values()}
    assert by_address[1]["channel_count"] == 3
    assert by_address[4]["channel_count"] == 4
    assert all(device["universe"] == 1 for device in devices.values())

    for item in presets.values():
        assert "order" not in item
        assert "channel_count" not in item
        assert item["device_id"] in devices

    # Presets that shared an order now share one device.
    assert presets["dp-a"]["device_id"] == presets["dp-c"]["device_id"]
    assert presets["dp-a"]["device_id"] != presets["dp-b"]["device_id"]
    assert presets["dp-a"]["channel_values"] == [1, 2, 3]


def test_migrate_v2_widest_channel_count_wins(data_root: Path) -> None:
    from storage.json_store import read_collection

    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 2})
    write_collection(
        DMX_DEVICE_PRESETS,
        {
            "dp-a": {"id": "dp-a", "order": 0, "channel_count": 3, "channel_values": [1, 2, 3]},
            "dp-b": {"id": "dp-b", "order": 0, "channel_count": 7, "channel_values": [1] * 7},
        },
        2,
        data_root,
    )

    assert migrate(data_root) == SCHEMA_VERSION

    devices = read_collection(DMX_DEVICES, data_root)
    assert len(devices) == 1
    assert next(iter(devices.values()))["channel_count"] == 7


def test_migrate_v2_rejects_unusable_device_preset(data_root: Path) -> None:
    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 2})
    write_collection(
        DMX_DEVICE_PRESETS,
        {"dp-a": {"id": "dp-a", "channel_values": [1, 2, 3]}},
        2,
        data_root,
    )

    with pytest.raises(StorageError, match="no usable order/channel_count"):
        migrate(data_root)


def test_migrate_v3_makes_cue_lists_playable(data_root: Path) -> None:
    from storage.json_store import read_collection

    ensure_layout(data_root)
    write_json(config_path(data_root), {"schema_version": 3})
    write_collection(
        DMX_PRESET_LISTS,
        {"dl-1": {"id": "dl-1", "dmx_preset_ids": ["look-a", "look-b"]}},
        3,
        data_root,
    )
    write_collection(
        WLED_PRESET_LISTS,
        {
            "wl-zero": {"id": "wl-zero", "wled_preset_ids": ["a"], "beats": 0},
            "wl-set": {"id": "wl-set", "wled_preset_ids": ["b"], "beats": 8},
        },
        3,
        data_root,
    )

    assert migrate(data_root) == SCHEMA_VERSION

    dmx_lists = read_collection(DMX_PRESET_LISTS, data_root)
    wled_lists = read_collection(WLED_PRESET_LISTS, data_root)

    # DMX lists had no beats field at all, so nothing could cycle.
    assert dmx_lists["dl-1"]["beats"] == 1
    assert wled_lists["wl-zero"]["beats"] == 1
    # An operator's real choice is left alone.
    assert wled_lists["wl-set"]["beats"] == 8


def test_migrate_v4_drops_scene_sensitivity(data_root: Path) -> None:
    from storage.json_store import read_collection

    ensure_layout(data_root)
    write_json(
        config_path(data_root),
        {
            "schema_version": 4,
            "audio": {"input_device": None, "default_sensitivity": 0.5},
        },
    )
    write_collection(
        SCENES,
        {
            "high": {"id": "high", "preset_id": "p", "sensitivity": 4.5},
            "fine": {"id": "fine", "preset_id": "p", "sensitivity": 0.25},
        },
        4,
        data_root,
    )

    assert migrate(data_root) == SCHEMA_VERSION

    scenes = read_collection(SCENES, data_root)
    assert "sensitivity" not in scenes["high"]
    assert "sensitivity" not in scenes["fine"]
    assert scenes["high"]["preset_id"] == "p"
    config = read_json(config_path(data_root), data_root)
    assert "default_sensitivity" not in (config or {}).get("audio", {})
