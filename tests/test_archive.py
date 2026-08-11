from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from conftest import build_minimal_scene_graph
from storage.archive import export_zip, import_zip
from storage.json_store import StorageError
from storage.library import Library
from storage.paths import config_path, data_dir


def test_export_import_round_trip(data_root: Path, tmp_path: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    scene = build_minimal_scene_graph(lib)
    lib.save()

    archive = export_zip(tmp_path / "show.zip", data_root)
    assert archive.is_file()

    restore_root = tmp_path / "restored"
    import_zip(archive, restore_root, replace=True)

    restored = Library.open(restore_root, sync_ilda=False)
    assert scene.id in restored.scenes
    assert restored.scenes[scene.id].sensitivity == 0.5


def test_zip_slip_rejected(data_root: Path, tmp_path: Path) -> None:
    Library.open(data_root, sync_ilda=False)  # layout
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../outside.txt", "nope")

    with pytest.raises(StorageError, match="outside the data folder"):
        import_zip(evil, data_root)


def test_export_skips_logs_and_backups_by_default(data_root: Path, tmp_path: Path) -> None:
    lib = Library.open(data_root, sync_ilda=False)
    build_minimal_scene_graph(lib)
    lib.save()
    (data_root / "logs" / "lightsapp.log").write_text("log\n", encoding="utf-8")
    (data_root / "backups" / "keep").mkdir(parents=True)
    (data_root / "backups" / "keep" / "x.txt").write_text("x", encoding="utf-8")

    archive = export_zip(tmp_path / "data.zip", data_root)
    names = zipfile.ZipFile(archive).namelist()
    assert not any(n.startswith("logs/") for n in names)
    assert not any(n.startswith("backups/") for n in names)
    assert any(n.startswith("data/") for n in names)
    assert config_path(data_root).name in {Path(n).name for n in names}
