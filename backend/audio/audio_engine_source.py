"""Lights App adapter for the separate synchronous audio-analysis library."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from typing import Optional

from audio.beat_source import BeatCallback

logger = logging.getLogger(__name__)


class AudioEngineBeatSource:
    """Publish audio-engine beat results from one dedicated worker thread."""

    def __init__(
        self,
        source: object,
        engine: object,
        *,
        runner: Callable[[object, object], Iterable[object]],
    ) -> None:
        self._source = source
        self._engine = engine
        self._runner = runner
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._bpm: Optional[float] = None
        self._beat_count = 0
        self._subscribers: list[BeatCallback] = []

    @property
    def bpm(self) -> Optional[float]:
        with self._lock:
            return self._bpm

    @property
    def beat_count(self) -> int:
        with self._lock:
            return self._beat_count

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def subscribe(self, callback: BeatCallback) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio-engine", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        try:
            close = getattr(self._source, "close")
            close()
        except Exception:
            logger.exception("could not close audio capture")
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_s)
        self._thread = None

    def _run(self) -> None:
        try:
            for result in self._runner(self._source, self._engine):
                if self._stop.is_set():
                    return
                bpm = getattr(result, "bpm", None)
                with self._lock:
                    self._bpm = bpm
                for _event in getattr(result, "beat_events", ()):
                    if self._stop.is_set():
                        return
                    with self._lock:
                        self._beat_count += 1
                        subscribers = tuple(self._subscribers)
                    for callback in subscribers:
                        try:
                            callback()
                        except Exception:
                            logger.exception("beat subscriber failed")
        except Exception:
            logger.exception("audio capture/analysis worker stopped after failure")
