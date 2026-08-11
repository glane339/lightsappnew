from __future__ import annotations

from pathlib import Path

import pytest

from conftest import build_minimal_scene_graph
from models.ILDA_Frame_List import ILDA_Frame_List
from storage.ilda_blobs import MissingFrameFileError, store_ild_file, validate_frame_id
from storage.json_store import StorageError
from storage.library import Library
from storage.paths import ilda_dir
from storage.records import ILDA_FRAMES, ILDA_FRAME_LISTS


def _write_fake_ild(path: Path, content: bytes = b"ILD\x00fake") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_validate_frame_id_rejects_traversal() -> None:
    with pytest.raises(StorageError):
        validate_frame_id("../escape")
    with pytest.raises(StorageError):
        validate_frame_id("a/b")
    with pytest.raises(StorageError):
        validate_frame_id("")


def test_import_ild_and_path(library: Library, tmp_path: Path) -> None:
    source = _write_fake_ild(tmp_path / "burst.ild")
    frame = library.import_ild(source)
    assert frame.id == "burst"
    path = library.ilda_path(frame.id)
    assert path.is_file()
    assert path.read_bytes() == b"ILD\x00fake"


def test_sync_adds_dropped_files(data_root: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    _write_fake_ild(ilda_dir(data_root) / "hand-dropped.ild")

    report = lib.sync_ilda_folder()
    assert report["added"] == ["hand-dropped"]
    assert lib.contains(ILDA_FRAMES, "hand-dropped")


def test_sync_removes_vanished_and_detaches_lists(data_root: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    source = _write_fake_ild(data_root / "tmp" / "gone.ild")
    frame = lib.import_ild(source)
    frame_list = ILDA_Frame_List(ilda_frame_ids=[frame.id])
    lib.add(frame_list)
    lib.save()

    # Delete the blob out from under the library.
    (ilda_dir(data_root) / "gone.ild").unlink()

    report = lib.sync_ilda_folder()
    assert report["removed"] == ["gone"]
    assert not lib.contains(ILDA_FRAMES, "gone")
    assert lib.ilda_frame_lists[frame_list.id].ilda_frame_ids == []


def test_force_delete_frame_unlinks_blob(library: Library, tmp_path: Path) -> None:
    source = _write_fake_ild(tmp_path / "zap.ild")
    frame = library.import_ild(source)
    blob = library.ilda_path(frame.id)
    assert blob.is_file()

    library.delete(ILDA_FRAMES, frame.id, force=True)
    assert not blob.exists()


def test_missing_blob_raises(library: Library) -> None:
    build_minimal_scene_graph(library)
    # Register a frame id with no file.
    from models.ILDA_Frame import ILDA_Frame

    library.ilda_frames["ghost"] = ILDA_Frame(id="ghost")
    with pytest.raises(MissingFrameFileError):
        library.ilda_path("ghost")


def test_store_ild_file_suffixes_collisions(data_root: Path, tmp_path: Path) -> None:
    first = _write_fake_ild(tmp_path / "same.ild", b"one")
    second = _write_fake_ild(tmp_path / "other" / "same.ild", b"two")

    id1 = store_ild_file(first, data_root)
    id2 = store_ild_file(second, data_root)
    assert id1 == "same"
    assert id2 == "same-2"
