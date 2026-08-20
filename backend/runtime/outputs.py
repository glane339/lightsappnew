"""
Where a cue actually goes.

Both outputs expose the same ``apply(preset_id)`` so the Scene Controller can drive
them identically. They differ in one way that matters: writing the DMX buffer cannot
fail, while talking to LEDfx can, and a LEDfx failure must never take the show down.
"""

from __future__ import annotations

import logging
import queue
from typing import Protocol

from ledfx.client import LedFxClientProtocol, LedFxError
from models.Active_DMX_Channels import Active_DMX_Channels
from runtime.active import UniverseState, build_channels

logger = logging.getLogger(__name__)


class CueOutput(Protocol):
    def apply(self, preset_id: str) -> None: ...


class DmxOutput:
    """Resolves a look into the universe buffer a sender reads."""

    def __init__(
        self,
        library,
        universe: UniverseState | Active_DMX_Channels | None = None,
    ) -> None:
        self._library = library
        if isinstance(universe, UniverseState):
            self._universe = universe
        elif isinstance(universe, Active_DMX_Channels):
            self._universe = UniverseState(channels=universe)
        else:
            self._universe = UniverseState()

    @property
    def universe(self) -> UniverseState:
        return self._universe

    @property
    def channels(self) -> Active_DMX_Channels:
        return self._universe.channels

    def apply(self, preset_id: str) -> None:
        # Built fully to the side, then assigned under the universe lock, so a sender
        # never reads a buffer that is half old look and half new.
        self._universe.replace(build_channels(self._library, preset_id))

    def blackout(self) -> None:
        self._universe.replace([0] * len(self._universe.channels.channels))


class AsyncCueOutput:
    """
    Hands a cue to a worker thread instead of applying it.

    Wraps any output whose ``apply`` can block — LEDfx over HTTP, in practice — so the
    caller pays a queue put rather than a network round trip. Latest-wins: when the
    queue is full the oldest pending cue is dropped, because a burst of beats only ever
    needs to end on the newest look.
    """

    def __init__(self, work_queue: "queue.Queue[str]") -> None:
        self._queue = work_queue

    def apply(self, preset_id: str) -> None:
        while True:
            try:
                self._queue.put_nowait(preset_id)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    # A consumer drained it first; the retry will now succeed.
                    pass


class WledOutput:
    """
    Activates a LEDfx scene.

    A WLED preset's id *is* the LEDfx scene name, so no lookup is needed. Failures are
    logged and swallowed: LEDfx being unreachable should cost the strips, not the show.
    """

    def __init__(self, client: LedFxClientProtocol) -> None:
        self._client = client

    def apply(self, preset_id: str) -> None:
        try:
            self._client.activate_scene(preset_id)
        except LedFxError as exc:
            logger.warning("LEDfx did not accept scene %r: %s", preset_id, exc)
        except Exception:
            logger.exception("LEDfx activation failed for scene %r", preset_id)
