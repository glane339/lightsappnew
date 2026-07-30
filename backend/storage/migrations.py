from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, Optional

from storage.json_store import StorageError, read_json, write_json
from storage.paths import config_path, data_dir, ensure_layout, ilda_dir, new_backup_dir

SCHEMA_VERSION = 1

MigrationStep = Callable[[Path], None]

# Keyed by the version being upgraded *from*; each step moves the folder forward exactly one version.
_STEPS: Dict[int, MigrationStep] = {}


def migration(from_version: int) -> Callable[[MigrationStep], MigrationStep]:
    def decorator(step: MigrationStep) -> MigrationStep:
        if from_version in _STEPS:
            raise RuntimeError(f"a migration from version {from_version} is already registered")
        _STEPS[from_version] = step
        return step

    return decorator


def stored_version(root: Optional[Path] = None) -> Optional[int]:
    """Version recorded in config.json, or None when the folder has no config yet."""
    payload = read_json(config_path(root), root)
    if payload is None:
        return None
    version = payload.get("schema_version")
    if not isinstance(version, int):
        return SCHEMA_VERSION
    return version


def snapshot(label: str, root: Optional[Path] = None) -> Path:
    destination = new_backup_dir(label, root)
    config = config_path(root)
    if config.exists():
        shutil.copy2(config, destination / config.name)
    for source in (data_dir(root), ilda_dir(root)):
        if source.exists():
            shutil.copytree(source, destination / source.name, dirs_exist_ok=True)
    return destination


def migrate(root: Optional[Path] = None) -> int:
    """Bring the data folder up to SCHEMA_VERSION, snapshotting first if anything must change."""
    resolved = ensure_layout(root)
    version = stored_version(resolved)

    if version is None:
        _record_version(resolved, SCHEMA_VERSION)
        return SCHEMA_VERSION
    if version == SCHEMA_VERSION:
        return version
    if version > SCHEMA_VERSION:
        raise StorageError(
            f"data folder is at schema version {version} but this build only understands "
            f"{SCHEMA_VERSION}; upgrade the app before opening it"
        )

    snapshot("migration", resolved)
    while version < SCHEMA_VERSION:
        step = _STEPS.get(version)
        if step is None:
            raise StorageError(f"no migration registered from schema version {version}")
        step(resolved)
        version += 1
        _record_version(resolved, version)
    return version


def _record_version(root: Path, version: int) -> None:
    payload = read_json(config_path(root), root) or {}
    payload["schema_version"] = version
    write_json(config_path(root), payload)
