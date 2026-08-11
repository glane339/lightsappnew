from __future__ import annotations

import logging
import threading
from typing import Optional

from ledfx.client import LedFxClientProtocol, LedFxError
from models.WLED_Preset import WLED_Preset
from storage.library import Library
from storage.records import WLED_PRESETS

logger = logging.getLogger(__name__)


class LedFxSceneSync:
    """
    Polls LEDfx for scenes and upserts missing ``WLED_Preset`` rows.

    ``WLED_Preset.id`` is the LEDfx scene name. Scenes that disappear from LEDfx are
    left in storage (no auto-delete — cue lists may still reference them).
    """

    def __init__(
        self,
        library: Library,
        client: LedFxClientProtocol,
        interval_s: float = 25.0,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._library = library
        self._client = client
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ledfx-scene-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_s)
        self._thread = None

    def refresh_once(self) -> int:
        """
        Fetch scenes from LEDfx and add any names not already in the library.

        Returns the number of presets added. On LEDfx failure, leaves storage
        untouched and returns 0.
        """
        with self._lock:
            try:
                scenes = self._client.list_scenes()
            except LedFxError as exc:
                logger.warning("LEDfx scene refresh skipped: %s", exc)
                return 0

            added = 0
            for scene in scenes:
                if self._library.contains(WLED_PRESETS, scene.name):
                    continue
                self._library.add(WLED_Preset(id=scene.name))
                added += 1

            if added:
                self._library.save()
                logger.info("Added %d LEDfx scene(s) to wled_presets", added)
            return added

    def _run(self) -> None:
        # Immediate refresh, then wait interval between subsequent polls.
        while not self._stop.is_set():
            self.refresh_once()
            self._stop.wait(self._interval_s)
