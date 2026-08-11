from __future__ import annotations

from pathlib import Path

import pytest

from storage.json_store import StorageError, write_collection, write_json
from storage.migrations import SCHEMA_VERSION, migrate, snapshot, stored_version
from storage.paths import backups_dir, config_path, ensure_layout
from storage.records import PRESETS, WLED_PRESET_LISTS, WLED_PRESETS


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

    assert migrate(data_root) == 2

    presets = read_collection(PRESETS, data_root)
    lists = read_collection(WLED_PRESET_LISTS, data_root)
    preset = presets["preset-1"]
    assert "wled_preset_id" not in preset
    list_id = preset["wled_preset_list_id"]
    assert list_id in lists
    assert lists[list_id]["wled_preset_ids"] == ["scene-alpha"]
    assert lists[list_id]["beats"] == 0
