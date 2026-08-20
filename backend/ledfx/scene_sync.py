from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Sequence

from ledfx.client import LedFxClientProtocol, LedFxError

logger = logging.getLogger(__name__)


class LedFxSceneSync:
    """
    Polls LEDfx for scenes and upserts missing ``WLED_Preset`` rows.

    ``WLED_Preset.id`` is the LEDfx scene name. Scenes that disappear from LEDfx are
    left in storage (no auto-delete — cue lists may still reference them).

    This thread never touches the ``Library`` directly (F-06 / AF2-H01): the names it
    finds go through the authoring service's ``upsert_wled_presets``, which serializes
    with every other library writer on one lock. The HTTP poll itself runs outside
    that lock, so a slow LEDfx never stalls authoring.
    """

    def __init__(
        self,
        upsert: Callable[[Sequence[str]], int],
        client: LedFxClientProtocol,
        interval_s: float = 25.0,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._upsert = upsert
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
        Fetch scenes from LEDfx and register any names not already in the library.

        Returns the number of presets added. On any LEDfx or storage failure, leaves
        storage as-is (best effort) and returns 0 so the poll loop keeps running
        (AF2-M01).
        """
        with self._lock:
            try:
                scenes = self._client.list_scenes()
            except LedFxError as exc:
                logger.warning("LEDfx scene refresh skipped: %s", exc)
                return 0
            except Exception:
                logger.exception("LEDfx scene list failed unexpectedly")
                return 0

            try:
                added = self._upsert([scene.name for scene in scenes])
            except Exception:
                logger.exception("LEDfx scene upsert failed")
                return 0
            if added:
                logger.info("Added %d LEDfx scene(s) to wled_presets", added)
            return added

    def _run(self) -> None:
        # Immediate refresh, then wait interval between subsequent polls.
        while not self._stop.is_set():
            try:
                self.refresh_once()
            except Exception:
                logger.exception("LEDfx scene sync survived an unexpected failure")
            self._stop.wait(self._interval_s)
