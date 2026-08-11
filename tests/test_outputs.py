from __future__ import annotations

from typing import List, Optional

import pytest
from conftest import build_cycling_scene_graph

from ledfx.client import LedFxError, LedFxScene, NullLedFxClient
from models.Active_DMX_Channels import UNIVERSE_SIZE, Active_DMX_Channels
from runtime.outputs import DmxOutput, WledOutput
from storage.library import Library


class FailingLedFxClient:
    """A client whose activations always fail, to prove a dead LEDfx is survivable."""

    def __init__(self) -> None:
        self.attempts: List[str] = []

    @property
    def reachable(self) -> bool:
        return False

    def list_scenes(self) -> List[LedFxScene]:
        return []

    def activate_scene(self, name: str) -> None:
        self.attempts.append(name)
        raise LedFxError(f"boom: {name}")

    def deactivate_scene(self, name: str) -> None:
        raise LedFxError("boom")

    def slug_for(self, name: str) -> Optional[str]:
        return None

    def close(self) -> None:
        return None


def test_dmx_output_writes_the_look_into_the_buffer(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    buffer = Active_DMX_Channels()
    output = DmxOutput(library, buffer)

    output.apply(graph.dmx_preset_ids[1])

    assert buffer.channels[0:3] == [20, 20, 20]
    assert len(buffer.channels) == UNIVERSE_SIZE


def test_dmx_output_replaces_rather_than_merges(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    buffer = Active_DMX_Channels()
    output = DmxOutput(library, buffer)

    output.apply(graph.dmx_preset_ids[2])
    output.apply(graph.dmx_preset_ids[0])

    # No trace of the previous look survives.
    assert buffer.channels[0:3] == [10, 10, 10]


def test_dmx_blackout_zeroes_the_buffer(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    buffer = Active_DMX_Channels()
    output = DmxOutput(library, buffer)
    output.apply(graph.dmx_preset_ids[0])

    output.blackout()

    assert buffer.channels == [0] * UNIVERSE_SIZE


def test_wled_output_activates_the_scene_by_name() -> None:
    client = NullLedFxClient()
    output = WledOutput(client)

    output.apply("wled-one")

    assert client.calls == [("activate_scene", "wled-one")]


def test_wled_failure_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    client = FailingLedFxClient()
    output = WledOutput(client)

    with caplog.at_level("WARNING"):
        output.apply("wled-one")

    assert client.attempts == ["wled-one"]
    assert "did not accept scene" in caplog.text
