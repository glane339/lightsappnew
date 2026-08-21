"""
The boundary between beat detection and lighting.

Everything downstream consumes discrete beat events, never BPM. BPM is an estimate over
a window that lags tempo changes by seconds; using it to drive sequencing would create a
resync problem that counting beats does not have. It is carried here for display only.

Keeping this a protocol means the whole show can be built and tested against
``ManualBeatSource`` before any audio library is chosen, and swapping that library later
touches nothing but the adapter.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Protocol

logger = logging.getLogger(__name__)

# Detected sources provide immutable beat metadata; manual sources retain their no-argument
# callback behavior so existing manual callers stay compatible.
BeatCallback = Callable[..., None]


class BeatSource(Protocol):
    @property
    def bpm(self) -> Optional[float]: ...

    @property
    def beat_count(self) -> int: ...

    def subscribe(self, callback: BeatCallback) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


class ManualBeatSource:
    """
    Beats supplied by the caller — a scripted list in tests, or a tap-tempo key.

    Nothing here estimates anything: ``bpm`` is whatever was last set, or None. A real
    detector will implement the same protocol and be dropped in behind it.
    """

    def __init__(self, bpm: Optional[float] = None) -> None:
        self._bpm = bpm
        self._beat_count = 0
        self._running = False
        self._subscribers: List[BeatCallback] = []

    @property
    def bpm(self) -> Optional[float]:
        return self._bpm

    @bpm.setter
    def bpm(self, value: Optional[float]) -> None:
        self._bpm = value

    @property
    def beat_count(self) -> int:
        return self._beat_count

    @property
    def running(self) -> bool:
        return self._running

    def subscribe(self, callback: BeatCallback) -> None:
        self._subscribers.append(callback)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def beat(self, count: int = 1) -> None:
        """
        Emit beats to every subscriber.

        Silence is the absence of calls to this, which is why a stopped or quiet source
        leaves the current look lit rather than advancing: no beats, no change.
        """
        if not self._running:
            return
        for _ in range(count):
            self._beat_count += 1
            for callback in self._subscribers:
                callback()
