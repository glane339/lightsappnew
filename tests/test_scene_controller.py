from __future__ import annotations

from typing import List

import pytest
from conftest import build_cycling_scene_graph

from audio.beat_source import ManualBeatSource
from ledfx.client import NullLedFxClient
from models.Active_DMX_Channels import Active_DMX_Channels
from models.DMX_Preset_List import DMX_Preset_List
from models.WLED_Preset_List import WLED_Preset_List
from runtime.outputs import DmxOutput, WledOutput
from runtime.scene_controller import SceneController
from storage.json_store import StorageError
from storage.library import Library
from storage.records import DMX_PRESET_LISTS, PRESETS, SCENES, WLED_PRESET_LISTS


class RecordingOutput:
    """Captures the cues it is handed, so ordering can be asserted directly."""

    def __init__(self) -> None:
        self.applied: List[str] = []

    def apply(self, preset_id: str) -> None:
        self.applied.append(preset_id)


@pytest.fixture
def rig(library: Library):
    graph = build_cycling_scene_graph(library, dmx_beats=2, wled_beats=3)
    dmx = RecordingOutput()
    wled = RecordingOutput()
    controller = SceneController(library, dmx, wled)
    return graph, controller, dmx, wled


def test_activation_applies_cue_zero_without_waiting_for_a_beat(rig) -> None:
    graph, controller, dmx, wled = rig

    controller.activate(graph.scene_id)

    # A scene selected in silence must still produce light.
    assert dmx.applied == [graph.dmx_preset_ids[0]]
    assert wled.applied == [graph.wled_preset_ids[0]]
    assert controller.active_scene_id == graph.scene_id
    assert controller.is_active is True


def test_the_two_lists_advance_independently(rig) -> None:
    graph, controller, dmx, wled = rig
    controller.activate(graph.scene_id)

    for _ in range(6):
        controller.on_beat()

    # DMX at 2 beats over 3 looks: advances on beats 2, 4, 6.
    assert dmx.applied == [
        graph.dmx_preset_ids[0],
        graph.dmx_preset_ids[1],
        graph.dmx_preset_ids[2],
        graph.dmx_preset_ids[0],
    ]
    # WLED at 3 beats over 2 cues: advances on beats 3 and 6.
    assert wled.applied == [
        graph.wled_preset_ids[0],
        graph.wled_preset_ids[1],
        graph.wled_preset_ids[0],
    ]


def test_no_beats_means_the_look_holds(rig) -> None:
    graph, controller, dmx, wled = rig
    controller.activate(graph.scene_id)

    # Silence is the absence of beats, so nothing further is applied.
    assert dmx.applied == [graph.dmx_preset_ids[0]]
    assert wled.applied == [graph.wled_preset_ids[0]]


def test_beats_before_activation_are_ignored(rig) -> None:
    graph, controller, dmx, wled = rig

    for _ in range(4):
        controller.on_beat()

    assert dmx.applied == []
    assert wled.applied == []


def test_switching_scenes_discards_outgoing_sequence_state(library: Library) -> None:
    first = build_cycling_scene_graph(library, dmx_beats=2)
    second = build_cycling_scene_graph(library, dmx_beats=2)
    dmx = RecordingOutput()
    controller = SceneController(library, dmx, RecordingOutput())

    controller.activate(first.scene_id)
    controller.on_beat()
    controller.on_beat()  # first scene is now on its second look
    controller.activate(second.scene_id)

    assert controller.active_scene_id == second.scene_id
    # The incoming scene starts at index 0 rather than inheriting a position.
    assert dmx.applied[-1] == second.dmx_preset_ids[0]

    controller.on_beat()
    controller.on_beat()
    assert dmx.applied[-1] == second.dmx_preset_ids[1]


def test_deactivate_stops_sequencing_and_holds(rig) -> None:
    graph, controller, dmx, wled = rig
    controller.activate(graph.scene_id)
    controller.deactivate()

    applied_before = list(dmx.applied)
    for _ in range(8):
        controller.on_beat()

    assert controller.is_active is False
    assert controller.active_scene_id is None
    # Nothing further is sent, and nothing blacks out: the last look stays lit.
    assert dmx.applied == applied_before


def test_deactivate_is_idempotent(rig) -> None:
    graph, controller, _, _ = rig

    controller.deactivate()
    controller.activate(graph.scene_id)
    controller.deactivate()
    controller.deactivate()

    assert controller.is_active is False


def test_empty_dmx_cue_list_is_a_clean_activation_error(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    _dmx_list_of(library, graph).dmx_preset_ids = []
    controller = SceneController(library, RecordingOutput(), RecordingOutput())

    with pytest.raises(StorageError, match="holds no presets"):
        controller.activate(graph.scene_id)


def test_empty_wled_cue_list_is_a_clean_activation_error(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    _wled_list_of(library, graph).wled_preset_ids = []
    controller = SceneController(library, RecordingOutput(), RecordingOutput())

    with pytest.raises(StorageError, match="holds no presets"):
        controller.activate(graph.scene_id)


def test_a_failed_activation_leaves_the_previous_scene_running(library: Library) -> None:
    good = build_cycling_scene_graph(library)
    broken = build_cycling_scene_graph(library)
    _dmx_list_of(library, broken).dmx_preset_ids = []

    dmx = RecordingOutput()
    controller = SceneController(library, dmx, RecordingOutput())
    controller.activate(good.scene_id)

    with pytest.raises(StorageError):
        controller.activate(broken.scene_id)

    assert controller.active_scene_id == good.scene_id
    assert dmx.applied == [good.dmx_preset_ids[0]]


def test_beat_source_drives_the_controller_end_to_end(library: Library) -> None:
    graph = build_cycling_scene_graph(library, dmx_beats=2, wled_beats=3)
    buffer = Active_DMX_Channels()
    client = NullLedFxClient()
    controller = SceneController(library, DmxOutput(library, buffer), WledOutput(client))

    beats = ManualBeatSource(bpm=128.0)
    beats.subscribe(controller.on_beat)
    beats.start()

    controller.activate(graph.scene_id)
    assert buffer.channels[0:3] == [10, 10, 10]

    beats.beat(2)
    assert buffer.channels[0:3] == [20, 20, 20]

    beats.beat(1)  # third beat completes the WLED entry
    assert client.calls[-1] == ("activate_scene", graph.wled_preset_ids[1])

    assert beats.beat_count == 3
    assert beats.bpm == 128.0


def test_a_stopped_beat_source_emits_nothing(library: Library) -> None:
    graph = build_cycling_scene_graph(library)
    dmx = RecordingOutput()
    controller = SceneController(library, dmx, RecordingOutput())
    beats = ManualBeatSource()
    beats.subscribe(controller.on_beat)

    controller.activate(graph.scene_id)
    beats.beat(10)  # never started

    assert dmx.applied == [graph.dmx_preset_ids[0]]
    assert beats.beat_count == 0


def _dmx_list_of(library: Library, graph) -> DMX_Preset_List:
    preset = library.get(PRESETS, library.get(SCENES, graph.scene_id).preset_id)
    return library.get(DMX_PRESET_LISTS, preset.dmx_preset_list_id)


def _wled_list_of(library: Library, graph) -> WLED_Preset_List:
    preset = library.get(PRESETS, library.get(SCENES, graph.scene_id).preset_id)
    return library.get(WLED_PRESET_LISTS, preset.wled_preset_list_id)
