from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Type, get_args

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

from models.DMX_Device import DMX_Device
from models.DMX_Device_Preset import DMX_Device_Preset
from models.DMX_Preset import DMX_Preset
from models.DMX_Preset_List import DMX_Preset_List
from models.ILDA_Frame import ILDA_Frame
from models.ILDA_Frame_List import ILDA_Frame_List
from models.Preset import Preset
from models.Scene import Scene
from models.WLED_Preset import WLED_Preset
from models.WLED_Preset_List import WLED_Preset_List
from storage.config import AppConfig, ensure_config, save_config
from storage.ilda_blobs import (
    MissingFrameFileError,
    delete_frame_file,
    frame_path,
    stored_frame_ids,
    store_ild_file,
)
from storage.json_store import StorageError, read_collection, write_collection
from storage.migrations import SCHEMA_VERSION, migrate
from storage.paths import collection_path, ensure_layout
from storage.records import (
    COLLECTION_ORDER,
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    ILDA_FRAME_LISTS,
    ILDA_FRAMES,
    PRESETS,
    RECORD_TYPES,
    REFERENCES,
    ROOT_COLLECTIONS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
    DMXDevicePresetRecord,
    DMXDeviceRecord,
    DMXPresetListRecord,
    DMXPresetRecord,
    ILDAFrameListRecord,
    ILDAFrameRecord,
    PresetRecord,
    SceneRecord,
    WLEDPresetListRecord,
    WLEDPresetRecord,
)


class IntegrityError(StorageError):
    """An operation would leave a reference pointing at nothing."""


class DanglingReferenceError(StorageError):
    """A stored record points at an id that is not in the collection it names."""


MODEL_TYPES: Dict[str, Type[BaseModel]] = {
    SCENES: Scene,
    PRESETS: Preset,
    DMX_PRESET_LISTS: DMX_Preset_List,
    DMX_PRESETS: DMX_Preset,
    DMX_DEVICE_PRESETS: DMX_Device_Preset,
    DMX_DEVICES: DMX_Device,
    WLED_PRESET_LISTS: WLED_Preset_List,
    WLED_PRESETS: WLED_Preset,
    ILDA_FRAME_LISTS: ILDA_Frame_List,
    ILDA_FRAMES: ILDA_Frame,
}

COLLECTION_BY_TYPE: Dict[Type[BaseModel], str] = {model: name for name, model in MODEL_TYPES.items()}


def _ref_ids(obj: Any, attr: str, is_list: bool) -> List[str]:
    """The ids held by one reference attribute, as a list whether or not the field is one."""
    value = getattr(obj, attr)
    if is_list:
        return list(value)
    return [] if value is None else [value]


def _is_optional_ref(collection: str, attr: str) -> bool:
    """Whether a single-id attribute can hold None, and so can be detached on delete."""
    field = MODEL_TYPES[collection].model_fields.get(attr)
    if field is None:
        return False
    return type(None) in get_args(field.annotation)


class Library:
    """
    The in-memory library, backed by one normalized JSON file per model class.

    Models hold the ids of the things they point at rather than the objects themselves,
    so a Preset used by two Scenes is stored once and read through this library. Look
    children up with get() or find(); nothing can be reached by attribute traversal.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = ensure_layout(root)
        migrate(self.root)
        self.config: AppConfig = ensure_config(self.root)

        self.scenes: Dict[str, Scene] = {}
        self.presets: Dict[str, Preset] = {}
        self.dmx_preset_lists: Dict[str, DMX_Preset_List] = {}
        self.dmx_presets: Dict[str, DMX_Preset] = {}
        self.dmx_device_presets: Dict[str, DMX_Device_Preset] = {}
        self.dmx_devices: Dict[str, DMX_Device] = {}
        self.wled_preset_lists: Dict[str, WLED_Preset_List] = {}
        self.wled_presets: Dict[str, WLED_Preset] = {}
        self.ilda_frame_lists: Dict[str, ILDA_Frame_List] = {}
        self.ilda_frames: Dict[str, ILDA_Frame] = {}
        self.ilda_sync: Dict[str, List[str]] = {}

        self._maps: Dict[str, Dict[str, Any]] = {
            SCENES: self.scenes,
            PRESETS: self.presets,
            DMX_PRESET_LISTS: self.dmx_preset_lists,
            DMX_PRESETS: self.dmx_presets,
            DMX_DEVICE_PRESETS: self.dmx_device_presets,
            DMX_DEVICES: self.dmx_devices,
            WLED_PRESET_LISTS: self.wled_preset_lists,
            WLED_PRESETS: self.wled_presets,
            ILDA_FRAME_LISTS: self.ilda_frame_lists,
            ILDA_FRAMES: self.ilda_frames,
        }

    @classmethod
    def open(cls, root: Optional[Path] = None, sync_ilda: bool = False) -> "Library":
        return cls(root).load(sync_ilda=sync_ilda)

    # ------------------------------------------------------------------ loading

    def load(self, sync_ilda: bool = False) -> "Library":
        """
        Read every collection from disk and check the graph.

        ILDA folder sync is opt-in: laser support is parked, and syncing made opening
        the library a write ([AF-M05](../../docs/audit_findings.md#af-m05)).
        """
        records = {collection: self._read_records(collection) for collection in COLLECTION_ORDER}
        self.clear()

        for collection in COLLECTION_ORDER:
            target = self._maps[collection]
            for record in records[collection].values():
                target[record.id] = self._from_record(collection, record)

        # Ids are copied across verbatim, so nothing else would notice a broken reference.
        self.check_integrity()

        if sync_ilda:
            self.ilda_sync = self.sync_ilda_folder()
        return self

    def _from_record(self, collection: str, record: Any) -> Any:
        if collection == SCENES:
            return Scene(
                id=record.id,
                preset_id=record.preset_id,
                ilda_frame_list_id=record.ilda_frame_list_id,
                sensitivity=record.sensitivity,
            )
        if collection == PRESETS:
            return Preset(
                id=record.id,
                dmx_preset_list_id=record.dmx_preset_list_id,
                wled_preset_list_id=record.wled_preset_list_id,
            )
        if collection == DMX_PRESET_LISTS:
            return DMX_Preset_List(
                id=record.id,
                dmx_preset_ids=list(record.dmx_preset_ids),
                beats=record.beats,
            )
        if collection == DMX_PRESETS:
            return DMX_Preset(
                id=record.id, dmx_device_preset_ids=list(record.dmx_device_preset_ids)
            )
        if collection == DMX_DEVICE_PRESETS:
            return DMX_Device_Preset(
                id=record.id,
                device_id=record.device_id,
                channel_values=list(record.channel_values),
            )
        if collection == DMX_DEVICES:
            return DMX_Device(
                id=record.id,
                name=record.name,
                model=record.model,
                mode=record.mode,
                universe=record.universe,
                start_address=record.start_address,
                channel_count=record.channel_count,
            )
        if collection == WLED_PRESET_LISTS:
            return WLED_Preset_List(
                id=record.id,
                wled_preset_ids=list(record.wled_preset_ids),
                beats=record.beats,
            )
        if collection == WLED_PRESETS:
            return WLED_Preset(id=record.id)
        if collection == ILDA_FRAME_LISTS:
            return ILDA_Frame_List(id=record.id, ilda_frame_ids=list(record.ilda_frame_ids))
        if collection == ILDA_FRAMES:
            return ILDA_Frame(id=record.id)
        raise StorageError(f"unknown collection '{collection}'")

    def _read_records(self, collection: str) -> Dict[str, Any]:
        record_type = RECORD_TYPES[collection]
        parsed: Dict[str, Any] = {}
        for item_id, item in read_collection(collection, self.root).items():
            try:
                record = record_type.model_validate(item)
            except ValidationError as exc:
                raise StorageError(
                    f"{collection_path(collection, self.root)}: item '{item_id}' is not a valid "
                    f"{record_type.__name__}: {exc}"
                ) from exc
            if record.id != item_id:
                raise StorageError(
                    f"{collection_path(collection, self.root)}: item is filed under '{item_id}' "
                    f"but its id is '{record.id}'"
                )
            parsed[item_id] = record
        return parsed

    def check_integrity(self) -> None:
        """Raise if any reference names an id that is not in the collection it points at."""
        for collection, refs in REFERENCES.items():
            for obj_id, obj in self._maps[collection].items():
                for attr, child_collection, is_list in refs:
                    for ref_id in _ref_ids(obj, attr, is_list):
                        if ref_id not in self._maps[child_collection]:
                            raise DanglingReferenceError(
                                f"{collection} '{obj_id}' references {child_collection} "
                                f"'{ref_id}', which does not exist"
                            )

    # ------------------------------------------------------------------ saving

    def save(self) -> None:
        self.check_integrity()
        for collection in COLLECTION_ORDER:
            self._write(collection)
        save_config(self.config, self.root)

    def _write(self, collection: str) -> None:
        items = {
            obj_id: self._to_record(collection, obj).model_dump()
            for obj_id, obj in self._maps[collection].items()
        }
        write_collection(collection, items, SCHEMA_VERSION, self.root)

    def _to_record(self, collection: str, obj: Any) -> BaseModel:
        if collection == SCENES:
            return SceneRecord(
                id=obj.id,
                preset_id=obj.preset_id,
                ilda_frame_list_id=obj.ilda_frame_list_id,
                sensitivity=obj.sensitivity,
            )
        if collection == PRESETS:
            return PresetRecord(
                id=obj.id,
                dmx_preset_list_id=obj.dmx_preset_list_id,
                wled_preset_list_id=obj.wled_preset_list_id,
            )
        if collection == DMX_PRESET_LISTS:
            return DMXPresetListRecord(
                id=obj.id,
                dmx_preset_ids=list(obj.dmx_preset_ids),
                beats=obj.beats,
            )
        if collection == DMX_PRESETS:
            return DMXPresetRecord(
                id=obj.id, dmx_device_preset_ids=list(obj.dmx_device_preset_ids)
            )
        if collection == DMX_DEVICE_PRESETS:
            return DMXDevicePresetRecord(
                id=obj.id,
                device_id=obj.device_id,
                channel_values=list(obj.channel_values),
            )
        if collection == DMX_DEVICES:
            return DMXDeviceRecord(
                id=obj.id,
                name=obj.name,
                model=obj.model,
                mode=obj.mode,
                universe=obj.universe,
                start_address=obj.start_address,
                channel_count=obj.channel_count,
            )
        if collection == WLED_PRESET_LISTS:
            return WLEDPresetListRecord(
                id=obj.id,
                wled_preset_ids=list(obj.wled_preset_ids),
                beats=obj.beats,
            )
        if collection == WLED_PRESETS:
            return WLEDPresetRecord(id=obj.id)
        if collection == ILDA_FRAME_LISTS:
            return ILDAFrameListRecord(id=obj.id, ilda_frame_ids=list(obj.ilda_frame_ids))
        if collection == ILDA_FRAMES:
            return ILDAFrameRecord(id=obj.id)
        raise StorageError(f"unknown collection '{collection}'")

    # ------------------------------------------------------------------ CRUD

    def add(self, obj: Any) -> Any:
        """
        Register an object, after checking that everything it names is already here.

        Nothing cascades any more, so build from the leaves up: a DMX_Preset has to be added
        before the DMX_Preset_List that lists its id.
        """
        collection = COLLECTION_BY_TYPE.get(type(obj))
        if collection is None:
            raise StorageError(f"{type(obj).__name__} is not a storable model")

        existing = self._maps[collection].get(obj.id)
        if existing is not None and existing is not obj:
            raise IntegrityError(
                f"{collection} '{obj.id}' is already held by a different object; "
                f"reuse the existing instance instead of creating a second one"
            )

        for attr, child_collection, is_list in REFERENCES.get(collection, ()):
            for ref_id in _ref_ids(obj, attr, is_list):
                if ref_id not in self._maps[child_collection]:
                    raise DanglingReferenceError(
                        f"{collection} '{obj.id}' references {child_collection} '{ref_id}', "
                        f"which is not in the library yet"
                    )

        self._maps[collection][obj.id] = obj
        return obj

    def get(self, collection: str, obj_id: str) -> Any:
        return self._maps[collection][obj_id]

    def find(self, collection: str, obj_id: str) -> Optional[Any]:
        return self._maps[collection].get(obj_id)

    def all(self, collection: str) -> List[Any]:
        return list(self._maps[collection].values())

    def contains(self, collection: str, obj_id: str) -> bool:
        return obj_id in self._maps[collection]

    def clear(self) -> None:
        for mapping in self._maps.values():
            mapping.clear()
        self.ilda_sync = {}

    def referrers(self, collection: str, obj_id: str) -> List[Tuple[str, str]]:
        found: Set[Tuple[str, str]] = set()
        for parent_collection, refs in REFERENCES.items():
            for attr, child_collection, is_list in refs:
                if child_collection != collection:
                    continue
                for parent_id, parent in self._maps[parent_collection].items():
                    if obj_id in _ref_ids(parent, attr, is_list):
                        found.add((parent_collection, parent_id))
        return sorted(found)

    def delete(self, collection: str, obj_id: str, force: bool = False) -> List[Tuple[str, str]]:
        """
        Delete an object. Refuses by default when anything still references it.

        With force=True the object is removed from any list that holds it, and any parent
        that requires it as a single field is deleted along with it. Returns everything
        that was removed, as (collection, id) pairs.
        """
        if obj_id not in self._maps[collection]:
            raise KeyError(f"no {collection} with id '{obj_id}'")

        holders = self.referrers(collection, obj_id)
        if holders and not force:
            listed = ", ".join(f"{name} '{held_id}'" for name, held_id in holders)
            raise IntegrityError(
                f"{collection} '{obj_id}' is referenced by {listed}; pass force=True to delete it anyway"
            )

        deleted: List[Tuple[str, str]] = []
        self._delete_cascade(collection, obj_id, deleted, set())
        if deleted:
            logger.info(
                "deleted %s '%s' (force=%s); removed %s",
                collection,
                obj_id,
                force,
                deleted,
            )
        return deleted

    def _delete_cascade(
        self,
        collection: str,
        obj_id: str,
        deleted: List[Tuple[str, str]],
        visiting: Set[Tuple[str, str]],
    ) -> None:
        key = (collection, obj_id)
        if key in visiting or obj_id not in self._maps[collection]:
            return
        visiting.add(key)

        for parent_collection, refs in REFERENCES.items():
            for attr, child_collection, is_list in refs:
                if child_collection != collection:
                    continue
                for parent_id, parent in list(self._maps[parent_collection].items()):
                    value = getattr(parent, attr)
                    if is_list:
                        remaining = [ref_id for ref_id in value if ref_id != obj_id]
                        if len(remaining) != len(value):
                            setattr(parent, attr, remaining)
                    elif value == obj_id:
                        # An optional parent survives losing this child; a required one
                        # cannot exist without it and goes too.
                        if _is_optional_ref(parent_collection, attr):
                            setattr(parent, attr, None)
                        else:
                            self._delete_cascade(parent_collection, parent_id, deleted, visiting)

        self._maps[collection].pop(obj_id, None)
        deleted.append(key)
        if collection == ILDA_FRAMES:
            self._drop_blob(obj_id)

    def prune_orphans(self) -> Dict[str, List[str]]:
        """
        Drop everything the root collections cannot reach.

        ILDA frames are exempt: their .ild files are dropped into the folder by hand, so an
        unused frame is a file waiting to be used rather than an orphan.
        """
        reachable: Set[Tuple[str, str]] = set()
        for root_collection in ROOT_COLLECTIONS:
            for obj_id in self._maps[root_collection]:
                self._mark_reachable(root_collection, obj_id, reachable)

        removed: Dict[str, List[str]] = {}
        for collection in COLLECTION_ORDER:
            if collection in ROOT_COLLECTIONS:
                continue
            orphans = sorted(
                obj_id for obj_id in self._maps[collection] if (collection, obj_id) not in reachable
            )
            for obj_id in orphans:
                self._maps[collection].pop(obj_id, None)
            if orphans:
                removed[collection] = orphans
        if removed:
            logger.info("pruned orphans: %s", removed)
        return removed

    def _mark_reachable(self, collection: str, obj_id: str, reachable: Set[Tuple[str, str]]) -> None:
        key = (collection, obj_id)
        obj = self._maps[collection].get(obj_id)
        if key in reachable or obj is None:
            return
        reachable.add(key)
        for attr, child_collection, is_list in REFERENCES.get(collection, ()):
            for ref_id in _ref_ids(obj, attr, is_list):
                self._mark_reachable(child_collection, ref_id, reachable)

    # ------------------------------------------------------------------ ILDA files

    def import_ild(self, source: Path, frame_id: Optional[str] = None) -> ILDA_Frame:
        """
        Copy an .ild file into the folder and register a frame for it.

        The file is stored as-is and its id is its file name, so the ILDA system can be
        handed the path straight from the folder. Nothing reads the contents.
        """
        stored_id = store_ild_file(source, self.root, frame_id)
        frame = ILDA_Frame(id=stored_id)
        self.ilda_frames[stored_id] = frame
        return frame

    def import_ild_files(self, sources: Iterable[Path]) -> List[ILDA_Frame]:
        """Bulk version of import_ild, for a drag and drop of several files."""
        return [self.import_ild(source) for source in sources]

    def ilda_path(self, frame_id: str) -> Path:
        """The path to hand to the ILDA system for playback."""
        if frame_id not in self.ilda_frames:
            raise KeyError(f"no ilda_frames with id '{frame_id}'")
        path = frame_path(frame_id, self.root)
        if not path.is_file():
            raise MissingFrameFileError(f"frame '{frame_id}' has no file at {path}")
        return path

    def sync_ilda_folder(self, persist: bool = True) -> Dict[str, List[str]]:
        """
        Reconcile ilda_frames.json with the .ild files actually in the folder.

        Files dropped into ilda/ by hand become frames; frames whose file has since gone
        are removed and detached from any frame list, because a scene cannot play a file
        that is not there. Returns the ids that were added and removed.
        """
        on_disk = stored_frame_ids(self.root)
        added = sorted(on_disk - set(self.ilda_frames))
        vanished = sorted(set(self.ilda_frames) - on_disk)

        for frame_id in added:
            self.ilda_frames[frame_id] = ILDA_Frame(id=frame_id)
        for frame_id in vanished:
            self._delete_cascade(ILDA_FRAMES, frame_id, [], set())

        report: Dict[str, List[str]] = {}
        if added:
            report["added"] = added
        if vanished:
            report["removed"] = vanished
        if report:
            logger.info("ilda folder sync: %s", report)
        if report and persist:
            self._write(ILDA_FRAMES)
            self._write(ILDA_FRAME_LISTS)
        return report

    def _drop_blob(self, frame_id: str) -> None:
        delete_frame_file(frame_id, self.root)
