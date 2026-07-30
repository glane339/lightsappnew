from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from storage.json_store import StorageError
from storage.paths import (
    BACKUPS_DIR_NAME,
    LOGS_DIR_NAME,
    config_path,
    data_dir,
    data_root,
    ensure_layout,
    ilda_dir,
)


def default_archive_name() -> str:
    return f"lightsapp-data-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"


def export_zip(dest: Path, root: Optional[Path] = None, include_backups: bool = False) -> Path:
    """Zip the whole data folder. dest may be a file path or an existing directory."""
    resolved = ensure_layout(root)
    dest = Path(dest).expanduser()
    if dest.is_dir():
        dest = dest / default_archive_name()
    dest.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(resolved.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(resolved)
            if not include_backups and relative.parts[0] == BACKUPS_DIR_NAME:
                continue
            if relative.parts[0] == LOGS_DIR_NAME:
                continue
            archive.write(path, relative.as_posix())
    return dest


def _safe_members(archive: zipfile.ZipFile) -> List[zipfile.ZipInfo]:
    """Reject absolute paths and traversal, so a hostile zip cannot write outside the folder."""
    members: List[zipfile.ZipInfo] = []
    for member in archive.infolist():
        if member.is_dir():
            continue
        name = member.filename
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts or Path(name).is_absolute():
            raise StorageError(f"archive member '{name}' points outside the data folder")
        members.append(member)
    return members


def import_zip(src: Path, root: Optional[Path] = None, replace: bool = False) -> Path:
    """
    Restore a data folder from a zip, snapshotting the current contents into backups/ first.

    With replace=True the existing config, data and ilda folders are cleared before
    extracting, so the result matches the archive exactly.
    """
    src = Path(src).expanduser()
    if not src.is_file():
        raise StorageError(f"no archive at {src}")
    resolved = ensure_layout(root)

    # Imported here to avoid a cycle: migrations snapshots, and importing may downgrade the folder.
    from storage.migrations import migrate, snapshot

    snapshot("pre-import", resolved)

    with zipfile.ZipFile(src) as archive:
        members = _safe_members(archive)
        if replace:
            for path in (data_dir(resolved), ilda_dir(resolved)):
                shutil.rmtree(path, ignore_errors=True)
            config_path(resolved).unlink(missing_ok=True)
            ensure_layout(resolved)
        for member in members:
            target = resolved / Path(member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)

    migrate(resolved)
    return resolved


def archive_root(root: Optional[Path] = None) -> Path:
    """The folder that export_zip captures, for showing the user where their data lives."""
    return data_root(root)
