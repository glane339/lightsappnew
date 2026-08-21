"""Lights App adapter for the separate synchronous audio-analysis library."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from typing import Any, Optional

from audio.beat_source import BeatCallback
from server.beat_timing import DetectedBeatTiming

logger = logging.getLogger(__name__)

# Capture is "dead" if no analysis result arrives within this window.
_RESULT_STALE_S = 2.0
# Capture is "silent" if results arrive but no beat has for this long.
_BEAT_SILENT_S = 1.5


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
        self._level: Optional[float] = None
        self._beat_count = 0
        self._subscribers: list[BeatCallback] = []
        self._failed = False
        self._last_result_at: Optional[float] = None
        self._last_beat_at: Optional[float] = None

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

    def health(self) -> dict[str, Any]:
        """Operator-visible capture state: off / live / silent / dead."""
        with self._lock:
            failed = self._failed
            bpm = self._bpm
            level = self._level
            last_result = self._last_result_at
            last_beat = self._last_beat_at
        running = self.running
        now = time.monotonic()
        if failed:
            capture = "dead"
        elif not running:
            capture = "off"
        elif last_result is None:
            capture = "live"
        elif now - last_result > _RESULT_STALE_S:
            capture = "dead"
        elif last_beat is None or now - last_beat > _BEAT_SILENT_S:
            capture = "silent"
        else:
            capture = "live"
        return {
            "capture": capture,
            "bpm": bpm,
            "level": level,
            "running": running,
        }

    def subscribe(self, callback: BeatCallback) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        with self._lock:
            self._failed = False
            self._last_result_at = None
            self._last_beat_at = None
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
                level = _result_level(result)
                now = time.monotonic()
                with self._lock:
                    self._bpm = bpm
                    self._level = level
                    self._last_result_at = now
                for _event in getattr(result, "beat_events", ()):
                    if self._stop.is_set():
                        return
                    with self._lock:
                        self._beat_count += 1
                        self._last_beat_at = time.monotonic()
                        subscribers = tuple(self._subscribers)
                    for callback in subscribers:
                        try:
                            callback(
                                DetectedBeatTiming(
                                    detected_beat_published_ns=time.perf_counter_ns()
                                )
                            )
                        except Exception:
                            logger.exception("beat subscriber failed")
        except Exception:
            with self._lock:
                self._failed = True
            logger.exception("audio capture/analysis worker stopped after failure")


def _result_level(result: object) -> Optional[float]:
    for attr in ("current_level", "level", "rms", "energy"):
        value = getattr(result, attr, None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None
