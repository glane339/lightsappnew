"""
The one entry point for running a scene.

Owns which scene is active and the sequence state of its two cue lists. Scene selection
is manual and a scene replaces its predecessor outright — there is no stack, no
crossfade, and no layering.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import List, Optional, Tuple

from runtime.outputs import CueOutput
from runtime.sequencer import CueSequencer
from storage.json_store import StorageError
from storage.records import DMX_PRESET_LISTS, PRESETS, SCENES, WLED_PRESET_LISTS

logger = logging.getLogger(__name__)


class SceneController:
    """
    Resolves a scene once at activation, then advances it on beats.

    The two cue lists advance **independently** off the same beat stream: a 4-entry DMX
    list at 8 beats and a 3-entry WLED list at 4 beats are not synchronised with each
    other, and are not meant to be.
    """

    def __init__(self, library, dmx_output: CueOutput, wled_output: CueOutput) -> None:
        self._library = library
        self._dmx_output = dmx_output
        self._wled_output = wled_output

        self._scene_id: Optional[str] = None
        self._dmx: Optional[CueSequencer] = None
        self._wled: Optional[CueSequencer] = None

    @property
    def active_scene_id(self) -> Optional[str]:
        return self._scene_id

    @property
    def is_active(self) -> bool:
        return self._scene_id is not None

    def activate(self, scene_id: str) -> None:
        """
        Make a scene current and light it immediately.

        Cue 0 is applied here rather than on the first beat, so selecting a scene during
        a silent passage still produces light. Resolution happens once: the sequencers
        get snapshots of the cue lists, not live library references.
        """
        dmx_entries, dmx_beats, wled_entries, wled_beats = self._resolve(scene_id)

        # Built before anything is swapped in, so a bad scene leaves the previous one
        # running rather than half-replacing it.
        dmx = CueSequencer(dmx_entries, dmx_beats)
        wled = CueSequencer(wled_entries, wled_beats)

        self._scene_id = scene_id
        self._dmx = dmx
        self._wled = wled

        self._dmx_output.apply(dmx.current)
        self._wled_output.apply(wled.current)
        logger.info(
            "activated scene '%s': %d dmx cues at %d beats, %d wled cues at %d beats",
            scene_id,
            len(dmx.entries),
            dmx.beats,
            len(wled.entries),
            wled.beats,
        )

    def deactivate(self) -> None:
        """
        Stop sequencing, leaving the last look lit.

        Holding rather than blacking out means no gap between scenes; blackout belongs
        on clean shutdown instead. LEDfx has no equivalent choice — it keeps rendering
        whatever it was last told to run.
        """
        if self._scene_id is None:
            return
        logger.info("deactivated scene '%s'", self._scene_id)
        self._scene_id = None
        self._dmx = None
        self._wled = None

    def on_beat(self, on_action: Callable[[], None] | None = None) -> bool:
        """
        Advance both cue lists one beat, applying only the ones that changed.

        DMX goes first deliberately: applying it is a local buffer write, while the WLED
        call is HTTP and can block for as long as the LEDfx timeout. Doing DMX first
        means a slow LEDfx delays the next beat rather than this beat's lighting.
        """
        if self._dmx is None or self._wled is None:
            return False
        acted = False
        for sequencer, output in ((self._dmx, self._dmx_output), (self._wled, self._wled_output)):
            changed = sequencer.on_beat()
            if changed is not None:
                if not acted and on_action is not None:
                    on_action()
                acted = True
                output.apply(changed)
        return acted

    def _resolve(self, scene_id: str) -> Tuple[List[str], int, List[str], int]:
        """Walk scene → preset → both cue lists, rejecting anything unplayable."""
        scene = self._library.get(SCENES, scene_id)
        preset = self._library.get(PRESETS, scene.preset_id)
        dmx_list = self._library.get(DMX_PRESET_LISTS, preset.dmx_preset_list_id)
        wled_list = self._library.get(WLED_PRESET_LISTS, preset.wled_preset_list_id)

        if not dmx_list.dmx_preset_ids:
            raise StorageError(
                f"scenes '{scene_id}' cannot be activated: dmx_preset_lists "
                f"'{dmx_list.id}' holds no presets"
            )
        if not wled_list.wled_preset_ids:
            raise StorageError(
                f"scenes '{scene_id}' cannot be activated: wled_preset_lists "
                f"'{wled_list.id}' holds no presets"
            )

        return (
            list(dmx_list.dmx_preset_ids),
            dmx_list.beats,
            list(wled_list.wled_preset_ids),
            wled_list.beats,
        )
