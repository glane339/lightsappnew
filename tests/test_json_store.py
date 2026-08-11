from __future__ import annotations

import json
from pathlib import Path

import pytest

from storage.json_store import CorruptFileError, read_collection, read_json, write_collection, write_json
from storage.paths import BACKUPS_DIR_NAME, collection_path, ensure_layout
from storage.records import WLED_PRESETS


def test_write_json_round_trip(data_root: Path) -> None:
    ensure_layout(data_root)
    path = data_root / "sample.json"
    write_json(path, {"a": 1, "b": [2, 3]})
    assert read_json(path, data_root) == {"a": 1, "b": [2, 3]}


def test_corrupt_json_is_quarantined(data_root: Path) -> None:
    ensure_layout(data_root)
    path = collection_path(WLED_PRESETS, data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(CorruptFileError) as excinfo:
        read_collection(WLED_PRESETS, data_root)

    err = excinfo.value
    assert not path.exists()
    assert err.quarantined_to.exists()
    assert BACKUPS_DIR_NAME in err.quarantined_to.parts
    assert "invalid JSON" in err.reason


def test_empty_file_is_quarantined(data_root: Path) -> None:
    ensure_layout(data_root)
    path = data_root / "empty.json"
    path.write_text("   \n", encoding="utf-8")

    with pytest.raises(CorruptFileError) as excinfo:
        read_json(path, data_root)

    assert "empty" in excinfo.value.reason
    assert not path.exists()


def test_collection_missing_items_is_quarantined(data_root: Path) -> None:
    ensure_layout(data_root)
    path = collection_path(WLED_PRESETS, data_root)
    write_json(path, {"schema_version": 1, "collection": WLED_PRESETS})

    with pytest.raises(CorruptFileError) as excinfo:
        read_collection(WLED_PRESETS, data_root)

    assert "items" in excinfo.value.reason


def test_write_collection_envelope(data_root: Path) -> None:
    ensure_layout(data_root)
    write_collection(WLED_PRESETS, {"alpha": {"id": "alpha"}}, 1, data_root)
    payload = json.loads(collection_path(WLED_PRESETS, data_root).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["collection"] == WLED_PRESETS
    assert payload["items"]["alpha"]["id"] == "alpha"
