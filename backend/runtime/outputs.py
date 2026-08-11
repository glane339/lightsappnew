"""
Where a cue actually goes.

Both outputs expose the same ``apply(preset_id)`` so the Scene Controller can drive
them identically. They differ in one way that matters: writing the DMX buffer cannot
fail, while talking to LEDfx can, and a LEDfx failure must never take the show down.
"""

from __future__ import annotations

import logging
from typing import Protocol

from ledfx.client import LedFxClientProtocol, LedFxError
from models.Active_DMX_Channels import Active_DMX_Channels
from runtime.active import active_dmx_channels, build_channels

logger = logging.getLogger(__name__)


class CueOutput(Protocol):
    def apply(self, preset_id: str) -> None: ...


class DmxOutput:
    """Resolves a look into the universe buffer a sender reads."""

    def __init__(self, library, channels: Active_DMX_Channels = active_dmx_channels) -> None:
        self._library = library
        self._channels = channels

    @property
    def channels(self) -> Active_DMX_Channels:
        return self._channels

    def apply(self, preset_id: str) -> None:
        # Built fully to the side, then assigned, so a sender never reads a buffer that
        # is half old look and half new.
        self._channels.channels = build_channels(self._library, preset_id)

    def blackout(self) -> None:
        self._channels.channels = [0] * len(self._channels.channels)


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
