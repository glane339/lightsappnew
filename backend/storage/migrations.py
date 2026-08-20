from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from storage.json_store import StorageError, read_collection, read_json, write_collection, write_json
from storage.paths import config_path, data_dir, ensure_layout, ilda_dir, new_backup_dir
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 6

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


@migration(3)
def migrate_cue_list_beats(root: Path) -> None:
    """
    Schema 3 → 4: cue lists carry a usable beat count, and scene sensitivity is bounded.

    DMX lists gain ``beats`` (they had none, so nothing could cycle), WLED lists have
    the old ``beats: 0`` default lifted to 1, and ``Scene.sensitivity`` is clamped into
    0.0–1.0 so the bounds now on the model cannot reject data already on disk.
    """
    dmx_lists = read_collection(DMX_PRESET_LISTS, root)
    for item in dmx_lists.values():
        beats = item.get("beats")
        if not isinstance(beats, int) or beats < 1:
            item["beats"] = 1

    wled_lists = read_collection(WLED_PRESET_LISTS, root)
    for item in wled_lists.values():
        beats = item.get("beats")
        if not isinstance(beats, int) or beats < 1:
            item["beats"] = 1

    scenes = read_collection(SCENES, root)
    for item in scenes.values():
        sensitivity = item.get("sensitivity")
        if not isinstance(sensitivity, (int, float)) or math.isnan(sensitivity):
            item["sensitivity"] = 0.5
        else:
            item["sensitivity"] = min(1.0, max(0.0, float(sensitivity)))

    write_collection(DMX_PRESET_LISTS, dmx_lists, 4, root)
    write_collection(WLED_PRESET_LISTS, wled_lists, 4, root)
    write_collection(SCENES, scenes, 4, root)


@migration(4)
def migrate_drop_scene_sensitivity(root: Path) -> None:
    """
    Schema 4 → 5: scenes no longer carry a detector sensitivity.

    Beat detection lives in the audio engine with its own config. The stored
    per-scene value was unused at runtime, so it is dropped rather than kept as
    dead data. ``AudioConfig.default_sensitivity`` goes with it — it only seeded
    new scenes.
    """
    scenes = read_collection(SCENES, root)
    for item in scenes.values():
        item.pop("sensitivity", None)
    write_collection(SCENES, scenes, 5, root)

    payload = read_json(config_path(root), root)
    if isinstance(payload, dict):
        audio = payload.get("audio")
        if isinstance(audio, dict) and "default_sensitivity" in audio:
            audio.pop("default_sensitivity")
            write_json(config_path(root), payload)


@migration(5)
def migrate_clamp_channel_values(root: Path) -> None:
    """
    Schema 5 → 6: clamp stored ``channel_values`` to 0–255.

    The model and record now reject out-of-range slots. Anything already on disk
    is brought into range so load cannot fail a previously-valid library.
    Non-integers become 0.
    """
    from dmx_slots import clamp_dmx_slot

    presets = read_collection(DMX_DEVICE_PRESETS, root)
    for item in presets.values():
        raw = item.get("channel_values")
        if not isinstance(raw, list):
            item["channel_values"] = []
            continue
        item["channel_values"] = [clamp_dmx_slot(value) for value in raw]
    write_collection(DMX_DEVICE_PRESETS, presets, 6, root)
