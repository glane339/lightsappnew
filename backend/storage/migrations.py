from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from storage.json_store import StorageError, read_collection, read_json, write_collection, write_json
from storage.paths import config_path, data_dir, ensure_layout, ilda_dir, new_backup_dir
from storage.records import DMX_DEVICE_PRESETS, DMX_DEVICES, PRESETS, WLED_PRESET_LISTS

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

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
    logger.info("migrating data folder from schema version %s", version)
    while version < SCHEMA_VERSION:
        step = _STEPS.get(version)
        if step is None:
            raise StorageError(f"no migration registered from schema version {version}")
        step(resolved)
        version += 1
        _record_version(resolved, version)
        logger.info("data folder now at schema version %s", version)
    return version


def _record_version(root: Path, version: int) -> None:
    payload = read_json(config_path(root), root) or {}
    payload["schema_version"] = version
    write_json(config_path(root), payload)


@migration(1)
def migrate_preset_wled_list_reference(root: Path) -> None:
    """
    Schema 1 → 2: ``Preset.wled_preset_id`` becomes ``wled_preset_list_id``.

    Each former single WLED preset reference is wrapped in a new one-entry
    ``WLED_Preset_List`` so existing libraries keep a usable graph.
    """
    presets = read_collection(PRESETS, root)
    lists: Dict[str, Dict[str, Any]] = read_collection(WLED_PRESET_LISTS, root)
    updated_presets: Dict[str, Dict[str, Any]] = {}

    for preset_id, item in presets.items():
        if "wled_preset_list_id" in item and "wled_preset_id" not in item:
            updated_presets[preset_id] = item
            continue

        old_wled_id = item.get("wled_preset_id")
        if not isinstance(old_wled_id, str) or not old_wled_id:
            raise StorageError(
                f"preset '{preset_id}' has no usable wled_preset_id to migrate"
            )

        list_id = uuid4().hex
        lists[list_id] = {
            "id": list_id,
            "wled_preset_ids": [old_wled_id],
            "beats": 0,
        }
        updated = dict(item)
        updated.pop("wled_preset_id", None)
        updated["wled_preset_list_id"] = list_id
        updated_presets[preset_id] = updated

    write_collection(WLED_PRESET_LISTS, lists, 2, root)
    write_collection(PRESETS, updated_presets, 2, root)


@migration(2)
def migrate_device_presets_to_devices(root: Path) -> None:
    """
    Schema 2 → 3: ``DMX_Device_Preset.order`` becomes ``device_id``.

    One ``DMX_Device`` is synthesised per distinct ``order``, and addresses are
    assigned by the packing rule the runtime used before — each device starts where
    the previous order ended — so existing looks resolve to the same channels.
    """
    device_presets = read_collection(DMX_DEVICE_PRESETS, root)
    devices: Dict[str, Dict[str, Any]] = read_collection(DMX_DEVICES, root)

    legacy = {
        preset_id: item
        for preset_id, item in device_presets.items()
        if "device_id" not in item
    }

    counts_by_order: Dict[int, int] = {}
    for preset_id, item in legacy.items():
        order = item.get("order")
        count = item.get("channel_count")
        if not isinstance(order, int) or not isinstance(count, int) or count < 1:
            raise StorageError(
                f"dmx_device_presets '{preset_id}' has no usable order/channel_count to migrate"
            )
        # Looks may disagree; the widest claim wins so no device loses channels.
        counts_by_order[order] = max(counts_by_order.get(order, 0), count)

    device_id_by_order: Dict[int, str] = {}
    cursor = 1
    for order in sorted(counts_by_order):
        channel_count = counts_by_order[order]
        device_id = uuid4().hex
        devices[device_id] = {
            "id": device_id,
            "name": f"Device {order}",
            "model": None,
            "mode": None,
            "universe": 1,
            "start_address": cursor,
            "channel_count": channel_count,
        }
        device_id_by_order[order] = device_id
        cursor += channel_count

    updated_presets: Dict[str, Dict[str, Any]] = {}
    for preset_id, item in device_presets.items():
        if preset_id not in legacy:
            updated_presets[preset_id] = item
            continue
        updated = dict(item)
        order = updated.pop("order")
        updated.pop("channel_count", None)
        updated["device_id"] = device_id_by_order[order]
        updated_presets[preset_id] = updated

    write_collection(DMX_DEVICES, devices, 3, root)
    write_collection(DMX_DEVICE_PRESETS, updated_presets, 3, root)
