from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Set

from storage.json_store import StorageError
from storage.paths import ILDA_BLOB_SUFFIX, ilda_blob_path, ilda_dir


class MissingFrameFileError(StorageError):
    """A frame is known to the library but its .ild file is not in the folder."""


def validate_frame_id(frame_id: str) -> str:
    """A frame id is the bare name of its file, so it must not be able to escape the folder."""
    if not frame_id or frame_id in (".", ".."):
        raise StorageError(f"'{frame_id}' is not a usable ILDA frame id")
    if "/" in frame_id or "\\" in frame_id or frame_id != Path(frame_id).name:
        raise StorageError(f"ILDA frame id '{frame_id}' must be a bare file name")
    return frame_id


def frame_path(frame_id: str, root: Optional[Path] = None) -> Path:
    """Where the ILDA system reads the file from. Contents are never parsed here."""
    return ilda_blob_path(validate_frame_id(frame_id), root)


def frame_exists(frame_id: str, root: Optional[Path] = None) -> bool:
    return frame_path(frame_id, root).is_file()


def stored_frame_ids(root: Optional[Path] = None) -> Set[str]:
    directory = ilda_dir(root)
    if not directory.exists():
        return set()
    return {path.stem for path in directory.glob(f"*{ILDA_BLOB_SUFFIX}") if path.is_file()}


def delete_frame_file(frame_id: str, root: Optional[Path] = None) -> bool:
    path = frame_path(frame_id, root)
    if not path.is_file():
        return False
    path.unlink()
    return True


def available_frame_id(stem: str, root: Optional[Path] = None) -> str:
    """Suffix the name until it does not collide with a file already in the folder."""
    validate_frame_id(stem)
    candidate = stem
    counter = 2
    while ilda_blob_path(candidate, root).exists():
        candidate = f"{stem}-{counter}"
        counter += 1
    return candidate


def store_ild_file(source: Path, root: Optional[Path] = None, frame_id: Optional[str] = None) -> str:
    """
    Copy an .ild file into the folder and return the id it was filed under.

    The file is copied byte for byte; nothing about its contents is inspected.
    """
    source = Path(source).expanduser()
    if not source.is_file():
        raise StorageError(f"no .ild file at {source}")
    if source.suffix.lower() != ILDA_BLOB_SUFFIX:
        raise StorageError(f"{source.name} is not an {ILDA_BLOB_SUFFIX} file")

    stem = validate_frame_id(frame_id if frame_id is not None else source.name[: -len(source.suffix)])
    target_id = available_frame_id(stem, root)
    target = ilda_blob_path(target_id, root)
    target.parent.mkdir(parents=True, exist_ok=True)

    handle_fd, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f"{target.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "wb") as destination, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return target_id
