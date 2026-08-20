"""
The authoring layer: every Library mutation outside tests goes through here (WS-10.5).

Why this exists. Raw ``Library`` calls require knowing ``COLLECTION_ORDER``,
forward-reference rules, and cascade semantics — easy to get wrong from a route
handler or UI. This service owns that knowledge once: it validates first, mutates
in leaf-first order, and saves once per operation.

Concurrency (resolves F-06 / AF2-H01). Writers — authoring calls on FastAPI's
threadpool and the LEDfx scene-sync thread — serialize on ``library.mutation_lock``.
The show thread never takes the lock: it reads by id (GIL-atomic) and snapshots cue
lists at activation, which stays safe because every mutation here *swaps* list
fields for new list objects rather than editing them in place. A save happens off
the event loop, so authoring never stalls ``/ws/show`` delivery.

Failure discipline. Validation happens before any mutation, so expected errors
(bad input) leave nothing to undo. If a mutation fails partway anyway, the library
reloads from disk — which still holds the pre-operation state, because the save
only runs after every mutation succeeded. In-memory state therefore always matches
disk plus at most the operation in flight.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from pydantic import ValidationError

from models.DMX_Device_Preset import DMX_Device_Preset
from models.DMX_Preset import DMX_Preset
from models.DMX_Preset_List import DMX_Preset_List
from models.Preset import Preset
from models.Scene import Scene
from models.WLED_Preset import WLED_Preset
from models.WLED_Preset_List import WLED_Preset_List
from storage.library import COLLECTION_BY_TYPE, DeletePlan, IntegrityError, Library
from storage.records import (
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    ILDA_FRAME_LISTS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)

logger = logging.getLogger(__name__)


class AuthoringError(Exception):
    """Base for everything the authoring layer refuses to do."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthoringNotFound(AuthoringError):
    """The addressed object does not exist."""


class AuthoringInvalid(AuthoringError):
    """The request body is wrong: bad values, missing references, empty lists."""


class AuthoringConflict(AuthoringError):
    """The operation collides with existing state: duplicate id, delete in use."""


# What the authoring layer manages. Devices are seeded by scripts and read-only
# here; ILDA is parked.
DELETABLE_COLLECTIONS = (
    SCENES,
    PRESETS,
    DMX_PRESET_LISTS,
    WLED_PRESET_LISTS,
    DMX_PRESETS,
    DMX_DEVICE_PRESETS,
    WLED_PRESETS,
)
READABLE_COLLECTIONS = DELETABLE_COLLECTIONS + (DMX_DEVICES,)

# Ordered id lists whose last remaining entry must not be detached while a parent
# still points at them (D-022 for cue lists; the same rule for looks).
_LIST_CHILD_COLLECTION = {
    DMX_PRESET_LISTS: DMX_PRESETS,
    WLED_PRESET_LISTS: WLED_PRESETS,
    DMX_PRESETS: DMX_DEVICE_PRESETS,
}


class AuthoringService:
    """
    Typed create/update/delete for the show graph, one lock, one save per operation.

    Construct one per process and share it; the lock itself lives on the Library, so
    even a second instance would still serialize correctly.
    """

    def __init__(self, library: Library) -> None:
        self._library = library
        self._lock = library.mutation_lock

    # ------------------------------------------------------------------ commit

    @contextmanager
    def _commit(self) -> Iterator[Library]:
        """
        Run mutations, then persist them; reload from disk if a mutation fails.

        The reload is a backstop for bugs, not a code path validation relies on:
        every public operation validates before mutating. A failure in ``save()``
        itself propagates without reloading — disk may then be mid-write, and the
        in-memory state is the intended one that the next successful save persists.
        """
        try:
            yield self._library
        except Exception:
            logger.exception("authoring mutation failed; reloading library from disk")
            self._library.load(sync_ilda=False)
            raise
        self._library.save()

    # ------------------------------------------------------------------ reads

    def get(self, collection: str, obj_id: str) -> Any:
        self._known(collection, READABLE_COLLECTIONS)
        with self._lock:
            found = self._library.find(collection, obj_id)
        if found is None:
            raise AuthoringNotFound(f"no {collection} with id '{obj_id}'")
        return found

    def list_all(self, collection: str) -> List[Any]:
        self._known(collection, READABLE_COLLECTIONS)
        with self._lock:
            return self._library.all(collection)

    def list_dmx_devices(self) -> List[Any]:
        """The rig's patch, in address order, for pickers and look editors."""
        with self._lock:
            devices = self._library.all(DMX_DEVICES)
        return sorted(devices, key=lambda device: (device.universe, device.start_address))

    # ------------------------------------------------------------------ device presets

    def create_dmx_device_preset(
        self,
        device_id: str,
        channel_values: Sequence[int],
        *,
        preset_id: Optional[str] = None,
    ) -> DMX_Device_Preset:
        """Save one device's channel values as a reusable row, validated against the patch."""
        with self._lock:
            values = self._validated_channel_values(device_id, channel_values)
            device_preset = self._construct(
                DMX_Device_Preset,
                id=preset_id,
                device_id=device_id,
                channel_values=values,
            )
            with self._commit() as library:
                self._add(library, device_preset)
            return device_preset

    def update_dmx_device_preset(
        self, preset_id: str, channel_values: Sequence[int]
    ) -> DMX_Device_Preset:
        """Replace channel values on an existing row; the device it belongs to does not change."""
        with self._lock:
            device_preset = self._require(DMX_DEVICE_PRESETS, preset_id)
            values = self._validated_channel_values(device_preset.device_id, channel_values)
            with self._commit():
                device_preset.channel_values = values
            return device_preset

    def _validated_channel_values(self, device_id: str, channel_values: Sequence[int]) -> List[int]:
        device = self._library.find(DMX_DEVICES, device_id)
        if device is None:
            raise AuthoringInvalid(f"dmx_devices '{device_id}' does not exist")
        if len(channel_values) != device.channel_count:
            raise AuthoringInvalid(
                f"device '{device.name}' expects exactly {device.channel_count} "
                f"channel values, got {len(channel_values)}"
            )
        for index, value in enumerate(channel_values):
            if not 0 <= value <= 255:
                raise AuthoringInvalid(
                    f"device '{device.name}' channel {index + 1} is {value}; "
                    "DMX values are 0-255"
                )
        return list(channel_values)

    # ------------------------------------------------------------------ looks (10.1 prerequisite)

    def create_dmx_preset(
        self,
        dmx_device_preset_ids: Sequence[str],
        *,
        preset_id: Optional[str] = None,
    ) -> DMX_Preset:
        """
        Create a look from existing device-preset ids.

        List order is the look's order; patched start addresses decide where values
        land in the universe, not this sequence. Every id must already exist.
        """
        with self._lock:
            ids = self._validated_device_preset_ids(dmx_device_preset_ids)
            preset = self._construct(DMX_Preset, id=preset_id, dmx_device_preset_ids=ids)
            with self._commit() as library:
                self._add(library, preset)
            return preset

    def update_dmx_preset(self, preset_id: str, dmx_device_preset_ids: Sequence[str]) -> DMX_Preset:
        """
        Replace a look's device-preset list wholesale.

        Previous rows stay in place — they are independently authored. A running
        scene picks the new values up the next time the look is applied.
        """
        with self._lock:
            preset = self._require(DMX_PRESETS, preset_id)
            ids = self._validated_device_preset_ids(dmx_device_preset_ids)
            with self._commit():
                preset.dmx_device_preset_ids = ids
            return preset

    def _validated_device_preset_ids(self, ids: Sequence[str]) -> List[str]:
        if not ids:
            raise AuthoringInvalid("a look needs at least one device preset")
        seen_ids: Set[str] = set()
        seen_devices: Set[str] = set()
        ordered: List[str] = []
        for device_preset_id in ids:
            if device_preset_id in seen_ids:
                raise AuthoringInvalid(
                    f"device preset '{device_preset_id}' appears twice in one look"
                )
            seen_ids.add(device_preset_id)
            device_preset = self._library.find(DMX_DEVICE_PRESETS, device_preset_id)
            if device_preset is None:
                raise AuthoringInvalid(
                    f"dmx_device_presets '{device_preset_id}' does not exist"
                )
            if device_preset.device_id in seen_devices:
                device = self._library.get(DMX_DEVICES, device_preset.device_id)
                raise AuthoringInvalid(
                    f"device '{device.name}' appears twice in one look; "
                    "a look holds one set of values per device"
                )
            seen_devices.add(device_preset.device_id)
            ordered.append(device_preset_id)
        return ordered

    # ------------------------------------------------------------------ WLED presets (10.2 support)

    def register_wled_preset(self, name: str) -> WLED_Preset:
        """Manually register an LEDfx scene name, for building lists before a live sync."""
        cleaned = name.strip()
        if not cleaned:
            raise AuthoringInvalid("a WLED preset name cannot be empty")
        with self._lock:
            if self._library.contains(WLED_PRESETS, cleaned):
                raise AuthoringConflict(f"wled_presets '{cleaned}' already exists")
            preset = WLED_Preset(id=cleaned)
            with self._commit() as library:
                self._add(library, preset)
            return preset

    def upsert_wled_presets(self, names: Sequence[str]) -> int:
        """
        Add any names not already registered; the LEDfx scene-sync entry point.

        Idempotent, and silent about duplicates, because the sync thread calls this
        with the full remote scene list every cycle.
        """
        with self._lock:
            missing: List[str] = []
            for name in names:
                cleaned = name.strip()
                if cleaned and cleaned not in missing and not self._library.contains(WLED_PRESETS, cleaned):
                    missing.append(cleaned)
            if not missing:
                return 0
            with self._commit() as library:
                for cleaned in missing:
                    self._add(library, WLED_Preset(id=cleaned))
            return len(missing)

    # ------------------------------------------------------------------ cue lists (10.1 / 10.2)

    def create_dmx_preset_list(
        self,
        dmx_preset_ids: Sequence[str],
        beats: int,
        *,
        list_id: Optional[str] = None,
    ) -> DMX_Preset_List:
        with self._lock:
            cue_list = self._validated_dmx_list(dmx_preset_ids, beats, list_id)
            with self._commit() as library:
                self._add(library, cue_list)
            return cue_list

    def update_dmx_preset_list(
        self, list_id: str, dmx_preset_ids: Sequence[str], beats: int
    ) -> DMX_Preset_List:
        """Replace entries and beats together; reorders are an update with the same ids."""
        with self._lock:
            cue_list = self._require(DMX_PRESET_LISTS, list_id)
            validated = self._validated_dmx_list(dmx_preset_ids, beats, list_id=None)
            with self._commit():
                cue_list.dmx_preset_ids = list(validated.dmx_preset_ids)
                cue_list.beats = validated.beats
            return cue_list

    def create_wled_preset_list(
        self,
        wled_preset_ids: Sequence[str],
        beats: int,
        *,
        list_id: Optional[str] = None,
    ) -> WLED_Preset_List:
        with self._lock:
            cue_list = self._validated_wled_list(wled_preset_ids, beats, list_id)
            with self._commit() as library:
                self._add(library, cue_list)
            return cue_list

    def update_wled_preset_list(
        self, list_id: str, wled_preset_ids: Sequence[str], beats: int
    ) -> WLED_Preset_List:
        with self._lock:
            cue_list = self._require(WLED_PRESET_LISTS, list_id)
            validated = self._validated_wled_list(wled_preset_ids, beats, list_id=None)
            with self._commit():
                cue_list.wled_preset_ids = list(validated.wled_preset_ids)
                cue_list.beats = validated.beats
            return cue_list

    def _validated_dmx_list(
        self, dmx_preset_ids: Sequence[str], beats: int, list_id: Optional[str]
    ) -> DMX_Preset_List:
        # Non-empty by decision D-022: an empty cue list can never activate, so it
        # cannot be authored either. Duplicates are legitimate (A B A C).
        if not dmx_preset_ids:
            raise AuthoringInvalid("a cue list needs at least one entry")
        for entry_id in dmx_preset_ids:
            look = self._library.find(DMX_PRESETS, entry_id)
            if look is None:
                raise AuthoringInvalid(f"dmx_presets '{entry_id}' does not exist")
            self._require_look_traces_to_device_presets(look)
        return self._construct(
            DMX_Preset_List, id=list_id, dmx_preset_ids=list(dmx_preset_ids), beats=beats
        )

    def _validated_wled_list(
        self, wled_preset_ids: Sequence[str], beats: int, list_id: Optional[str]
    ) -> WLED_Preset_List:
        if not wled_preset_ids:
            raise AuthoringInvalid("a cue list needs at least one entry")
        for entry_id in wled_preset_ids:
            if not self._library.contains(WLED_PRESETS, entry_id):
                raise AuthoringInvalid(
                    f"no LEDfx scene named '{entry_id}' is registered; "
                    "sync from LEDfx or register it first"
                )
        return self._construct(
            WLED_Preset_List, id=list_id, wled_preset_ids=list(wled_preset_ids), beats=beats
        )

    def _require_look_traces_to_device_presets(self, look: DMX_Preset) -> None:
        if not look.dmx_device_preset_ids:
            raise AuthoringInvalid(
                f"dmx_presets '{look.id}' has no device presets; "
                "every look must trace to at least one dmx_device_preset"
            )
        for device_preset_id in look.dmx_device_preset_ids:
            device_preset = self._library.find(DMX_DEVICE_PRESETS, device_preset_id)
            if device_preset is None:
                raise AuthoringInvalid(
                    f"dmx_presets '{look.id}' references dmx_device_presets "
                    f"'{device_preset_id}', which does not exist"
                )
            if not self._library.contains(DMX_DEVICES, device_preset.device_id):
                raise AuthoringInvalid(
                    f"dmx_device_presets '{device_preset_id}' references dmx_devices "
                    f"'{device_preset.device_id}', which does not exist"
                )

    # ------------------------------------------------------------------ presets (10.3)

    def create_preset(
        self,
        dmx_preset_list_id: str,
        wled_preset_list_id: str,
        *,
        preset_id: Optional[str] = None,
    ) -> Preset:
        """Pair one existing DMX cue list with one existing WLED cue list."""
        with self._lock:
            self._require_playable_dmx_list(dmx_preset_list_id)
            self._require_playable_wled_list(wled_preset_list_id)
            preset = self._construct(
                Preset,
                id=preset_id,
                dmx_preset_list_id=dmx_preset_list_id,
                wled_preset_list_id=wled_preset_list_id,
            )
            with self._commit() as library:
                self._add(library, preset)
            return preset

    def update_preset(
        self, preset_id: str, dmx_preset_list_id: str, wled_preset_list_id: str
    ) -> Preset:
        """Swap either cue list (or both); the ids are a full replacement."""
        with self._lock:
            preset = self._require(PRESETS, preset_id)
            self._require_playable_dmx_list(dmx_preset_list_id)
            self._require_playable_wled_list(wled_preset_list_id)
            with self._commit():
                preset.dmx_preset_list_id = dmx_preset_list_id
                preset.wled_preset_list_id = wled_preset_list_id
            return preset

    def _require_playable_dmx_list(self, list_id: str) -> None:
        cue_list = self._library.find(DMX_PRESET_LISTS, list_id)
        if cue_list is None:
            raise AuthoringInvalid(f"dmx_preset_lists '{list_id}' does not exist")
        if not cue_list.dmx_preset_ids:
            raise AuthoringInvalid(
                f"dmx_preset_lists '{list_id}' is empty and could never activate; "
                "add at least one look to it first"
            )
        for look_id in cue_list.dmx_preset_ids:
            look = self._library.find(DMX_PRESETS, look_id)
            if look is None:
                raise AuthoringInvalid(f"dmx_presets '{look_id}' does not exist")
            self._require_look_traces_to_device_presets(look)

    def _require_playable_wled_list(self, list_id: str) -> None:
        cue_list = self._library.find(WLED_PRESET_LISTS, list_id)
        if cue_list is None:
            raise AuthoringInvalid(f"wled_preset_lists '{list_id}' does not exist")
        if not cue_list.wled_preset_ids:
            raise AuthoringInvalid(
                f"wled_preset_lists '{list_id}' is empty and could never activate; "
                "add at least one preset to it first"
            )
        for wled_id in cue_list.wled_preset_ids:
            if not self._library.contains(WLED_PRESETS, wled_id):
                raise AuthoringInvalid(
                    f"no LEDfx scene named '{wled_id}' is registered; "
                    "sync from LEDfx or register it first"
                )

    # ------------------------------------------------------------------ scenes (10.4)

    def create_scene(
        self,
        preset_id: str,
        *,
        ilda_frame_list_id: Optional[str] = None,
        scene_id: Optional[str] = None,
    ) -> Scene:
        """
        Create the operator's top-level unit.

        Playability is checked here with the same rules ``SceneController.activate``
        applies, so a stored scene cannot fail activation for structural reasons.
        """
        with self._lock:
            self._require_playable_preset(preset_id)
            self._require_ilda_list(ilda_frame_list_id)
            scene = self._construct(
                Scene,
                id=scene_id,
                preset_id=preset_id,
                ilda_frame_list_id=ilda_frame_list_id,
            )
            with self._commit() as library:
                self._add(library, scene)
            return scene

    def create_scene_from_cue_lists(
        self,
        dmx_preset_list_id: str,
        wled_preset_list_id: str,
        *,
        scene_id: Optional[str] = None,
        ilda_frame_list_id: Optional[str] = None,
    ) -> Scene:
        """
        Create a scene from two cue lists, hiding the lighting ``Preset``.

        Reuses an existing preset with the same pair when one exists, so Builder
        does not accumulate duplicate presets for the same pairing.
        """
        with self._lock:
            self._require_playable_dmx_list(dmx_preset_list_id)
            self._require_playable_wled_list(wled_preset_list_id)
            self._require_ilda_list(ilda_frame_list_id)
            preset = self._find_preset_for_lists(dmx_preset_list_id, wled_preset_list_id)
            with self._commit() as library:
                if preset is None:
                    preset = self._construct(
                        Preset,
                        id=None,
                        dmx_preset_list_id=dmx_preset_list_id,
                        wled_preset_list_id=wled_preset_list_id,
                    )
                    self._add(library, preset)
                scene = self._construct(
                    Scene,
                    id=scene_id,
                    preset_id=preset.id,
                    ilda_frame_list_id=ilda_frame_list_id,
                )
                self._add(library, scene)
            return scene

    def update_scene_from_cue_lists(
        self,
        scene_id: str,
        *,
        dmx_preset_list_id: str,
        wled_preset_list_id: str,
        ilda_frame_list_id: Optional[str] = None,
    ) -> Scene:
        """Replace a scene's cue-list pairing, reusing or creating the hidden preset."""
        with self._lock:
            scene = self._require(SCENES, scene_id)
            self._require_playable_dmx_list(dmx_preset_list_id)
            self._require_playable_wled_list(wled_preset_list_id)
            self._require_ilda_list(ilda_frame_list_id)
            preset = self._find_preset_for_lists(dmx_preset_list_id, wled_preset_list_id)
            with self._commit() as library:
                if preset is None:
                    preset = self._construct(
                        Preset,
                        id=None,
                        dmx_preset_list_id=dmx_preset_list_id,
                        wled_preset_list_id=wled_preset_list_id,
                    )
                    self._add(library, preset)
                scene.preset_id = preset.id
                scene.ilda_frame_list_id = ilda_frame_list_id
            return scene

    def _find_preset_for_lists(
        self, dmx_preset_list_id: str, wled_preset_list_id: str
    ) -> Optional[Preset]:
        for preset in self._library.all(PRESETS):
            if (
                preset.dmx_preset_list_id == dmx_preset_list_id
                and preset.wled_preset_list_id == wled_preset_list_id
            ):
                return preset
        return None

    def update_scene(
        self,
        scene_id: str,
        *,
        preset_id: str,
        ilda_frame_list_id: Optional[str] = None,
    ) -> Scene:
        """
        Full replacement of a scene's fields.

        Safe against a running show: the controller snapshots cue lists at
        activation, so a preset change applies on the next activation.
        """
        with self._lock:
            scene = self._require(SCENES, scene_id)
            self._require_playable_preset(preset_id)
            self._require_ilda_list(ilda_frame_list_id)
            validated = self._construct(
                Scene,
                id=scene_id,
                preset_id=preset_id,
                ilda_frame_list_id=ilda_frame_list_id,
            )
            with self._commit():
                scene.preset_id = validated.preset_id
                scene.ilda_frame_list_id = validated.ilda_frame_list_id
            return scene

    def _require_playable_preset(self, preset_id: str) -> None:
        preset = self._library.find(PRESETS, preset_id)
        if preset is None:
            raise AuthoringInvalid(f"presets '{preset_id}' does not exist")
        self._require_playable_dmx_list(preset.dmx_preset_list_id)
        self._require_playable_wled_list(preset.wled_preset_list_id)

    def _require_ilda_list(self, ilda_frame_list_id: Optional[str]) -> None:
        if ilda_frame_list_id is None:
            return
        if not self._library.contains(ILDA_FRAME_LISTS, ilda_frame_list_id):
            raise AuthoringInvalid(f"ilda_frame_lists '{ilda_frame_list_id}' does not exist")

    # ------------------------------------------------------------------ deletes (10.5)

    def plan_delete(self, collection: str, obj_id: str) -> DeletePlan:
        """Preview a delete: what would be removed, what survives with a reference detached."""
        self._known(collection, DELETABLE_COLLECTIONS)
        with self._lock:
            if not self._library.contains(collection, obj_id):
                raise AuthoringNotFound(f"no {collection} with id '{obj_id}'")
            return self._library.plan_delete(collection, obj_id)

    def delete(self, collection: str, obj_id: str, *, force: bool = False) -> DeletePlan:
        """
        Delete an object, refusing while it is referenced unless forced.

        A forced delete follows the cascade rules the plan reports, with one
        authoring-level refusal on top: it will not leave a still-referenced cue
        list empty, because that would strand an unplayable preset (D-022).
        """
        self._known(collection, DELETABLE_COLLECTIONS)
        with self._lock:
            if not self._library.contains(collection, obj_id):
                raise AuthoringNotFound(f"no {collection} with id '{obj_id}'")

            holders = self._library.referrers(collection, obj_id)
            if holders and not force:
                listed = ", ".join(f"{name} '{held_id}'" for name, held_id in holders)
                raise AuthoringConflict(
                    f"{collection} '{obj_id}' is referenced by {listed}; "
                    "delete with force=true to cascade"
                )

            plan = self._library.plan_delete(collection, obj_id)
            self._refuse_emptying_referenced_lists(plan)
            with self._commit() as library:
                library.delete(collection, obj_id, force=force)
            return plan

    def _refuse_emptying_referenced_lists(self, plan: DeletePlan) -> None:
        removed: Set[Tuple[str, str]] = set(plan.removes)
        removed_by_collection: Dict[str, Set[str]] = {}
        for removed_collection, removed_id in plan.removes:
            removed_by_collection.setdefault(removed_collection, set()).add(removed_id)

        for parent_collection, parent_id, attr in plan.detaches:
            child_collection = _LIST_CHILD_COLLECTION.get(parent_collection)
            if child_collection is None:
                continue
            holder = self._library.get(parent_collection, parent_id)
            targets = removed_by_collection.get(child_collection, set())
            remaining = [
                entry_id for entry_id in getattr(holder, attr) if entry_id not in targets
            ]
            if remaining:
                continue
            surviving_holders = [
                referrer
                for referrer in self._library.referrers(parent_collection, parent_id)
                if referrer not in removed
            ]
            if surviving_holders:
                listed = ", ".join(f"{name} '{held_id}'" for name, held_id in surviving_holders)
                raise AuthoringConflict(
                    f"this delete would empty {parent_collection} '{parent_id}', "
                    f"which is still referenced by {listed}; replace the entry or "
                    "delete the parent instead"
                )

    # ------------------------------------------------------------------ shared helpers

    def _require(self, collection: str, obj_id: str) -> Any:
        found = self._library.find(collection, obj_id)
        if found is None:
            raise AuthoringNotFound(f"no {collection} with id '{obj_id}'")
        return found

    def _known(self, collection: str, allowed: Sequence[str]) -> None:
        if collection not in allowed:
            raise AuthoringInvalid(f"authoring does not manage '{collection}'")

    def _construct(self, model_type: type, *, id: Optional[str], **fields: Any) -> Any:
        """Build a model, mapping pydantic bounds failures to a clean authoring error."""
        if id is not None:
            fields["id"] = id
        try:
            return model_type(**fields)
        except ValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(part) for part in first.get("loc", ()))
            raise AuthoringInvalid(f"{location}: {first.get('msg', 'invalid value')}") from exc

    def _add(self, library: Library, obj: Any) -> None:
        """Add to the library, mapping an id collision to a conflict the API can name."""
        collection = COLLECTION_BY_TYPE.get(type(obj), type(obj).__name__)
        try:
            library.add(obj)
        except IntegrityError as exc:
            raise AuthoringConflict(
                f"{collection} '{obj.id}' already exists; ids must be unique"
            ) from exc
