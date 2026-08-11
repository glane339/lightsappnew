from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from storage.paths import collection_path, new_backup_dir

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base class for every failure raised by the storage layer."""


class CorruptFileError(StorageError):
    """A file on disk could not be parsed and was moved aside instead of overwritten."""

    def __init__(self, path: Path, quarantined_to: Path, reason: str) -> None:
        super().__init__(f"{path} is unreadable ({reason}); moved to {quarantined_to}")
        self.path = path
        self.quarantined_to = quarantined_to
        self.reason = reason


def quarantine(path: Path, label: str, root: Optional[Path] = None) -> Path:
    destination = new_backup_dir(label, root) / path.name
    shutil.move(str(path), str(destination))
    logger.warning("quarantined %s -> %s (%s)", path, destination, label)
    return destination


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def read_json(path: Path, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the parsed object, or None when the file does not exist yet."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageError(f"Could not read {path}: {exc}") from exc

    if not text.strip():
        raise CorruptFileError(path, quarantine(path, "corrupt", root), "file was empty")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorruptFileError(path, quarantine(path, "corrupt", root), f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        raise CorruptFileError(
            path,
            quarantine(path, "corrupt", root),
            f"expected a JSON object, found {type(payload).__name__}",
        )
    return payload


def read_collection(collection: str, root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Return the raw items of a collection file, keyed by id. Missing file means empty."""
    path = collection_path(collection, root)
    payload = read_json(path, root)
    if payload is None:
        return {}

    items = payload.get("items")
    if not isinstance(items, dict):
        raise CorruptFileError(path, quarantine(path, "corrupt", root), "envelope has no 'items' object")
    for item_id, item in items.items():
        if not isinstance(item, dict):
            raise CorruptFileError(
                path,
                quarantine(path, "corrupt", root),
                f"item '{item_id}' is {type(item).__name__}, expected an object",
            )
    return items


def write_collection(
    collection: str,
    items: Dict[str, Dict[str, Any]],
    schema_version: int,
    root: Optional[Path] = None,
) -> None:
    write_json(
        collection_path(collection, root),
        {"schema_version": schema_version, "collection": collection, "items": items},
    )
