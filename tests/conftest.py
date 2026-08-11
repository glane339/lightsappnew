from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest

# Ensure ``backend/`` is on sys.path even when pytest.ini is not picked up.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from logging_setup import reset_logging_for_tests  # noqa: E402
from models.DMX_Device import DMX_Device  # noqa: E402
from models.DMX_Device_Preset import DMX_Device_Preset  # noqa: E402
from models.DMX_Preset import DMX_Preset  # noqa: E402
from models.DMX_Preset_List import DMX_Preset_List  # noqa: E402
from models.ILDA_Frame_List import ILDA_Frame_List  # noqa: E402
from models.Preset import Preset  # noqa: E402
from models.Scene import Scene  # noqa: E402
from models.WLED_Preset import WLED_Preset  # noqa: E402
from models.WLED_Preset_List import WLED_Preset_List  # noqa: E402
from storage.library import Library  # noqa: E402
from storage.records import (  # noqa: E402
    DMX_DEVICE_PRESETS,
    DMX_DEVICES,
    DMX_PRESET_LISTS,
    DMX_PRESETS,
    ILDA_FRAME_LISTS,
    PRESETS,
    SCENES,
    WLED_PRESET_LISTS,
    WLED_PRESETS,
)


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """Isolated data folder; never touches the real LightsApp directory."""
    root = tmp_path / "lightsapp-data"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    reset_logging_for_tests()
    yield
    reset_logging_for_tests()


@pytest.fixture
def library(data_root: Path) -> Library:
    return Library.open(data_root, sync_ilda=False)


def build_minimal_scene_graph(library: Library) -> Scene:
    """
    Leaves-up graph: device → device preset → look → list → wled → preset → ilda → scene.
    """
    device = DMX_Device(name="Test Par", start_address=1, channel_count=3)
    device_preset = DMX_Device_Preset(device_id=device.id, channel_values=[10, 20, 30])
    dmx_preset = DMX_Preset(dmx_device_preset_ids=[device_preset.id])
    dmx_list = DMX_Preset_List(dmx_preset_ids=[dmx_preset.id], beats=2)
    wled = WLED_Preset(id="scene-alpha")
    wled_list = WLED_Preset_List(wled_preset_ids=[wled.id], beats=4)
    preset = Preset(dmx_preset_list_id=dmx_list.id, wled_preset_list_id=wled_list.id)
    frame_list = ILDA_Frame_List()
    scene = Scene(
        preset_id=preset.id,
        ilda_frame_list_id=frame_list.id,
        sensitivity=0.5,
    )

    library.add(device)
    library.add(device_preset)
    library.add(dmx_preset)
    library.add(dmx_list)
    library.add(wled)
    library.add(wled_list)
    library.add(preset)
    library.add(frame_list)
    library.add(scene)
    return scene


@dataclass
class CyclingScene:
    """Ids from a scene whose two cue lists have several entries each."""

    scene_id: str
    device_id: str
    dmx_preset_ids: List[str]
    wled_preset_ids: List[str]
    dmx_beats: int
    wled_beats: int


def build_cycling_scene_graph(
    library: Library,
    dmx_beats: int = 2,
    wled_beats: int = 3,
) -> CyclingScene:
    """
    A scene that can actually cycle: three DMX looks and two WLED cues.

    The lists are deliberately different lengths and beat counts, since the two
    sequencers are meant to advance independently rather than in lockstep.
    """
    device = DMX_Device(name="Cycler", start_address=1, channel_count=3)
    library.add(device)

    dmx_preset_ids: List[str] = []
    for level in (10, 20, 30):
        device_preset = DMX_Device_Preset(device_id=device.id, channel_values=[level] * 3)
        dmx_preset = DMX_Preset(dmx_device_preset_ids=[device_preset.id])
        library.add(device_preset)
        library.add(dmx_preset)
        dmx_preset_ids.append(dmx_preset.id)

    # A WLED preset's id is the LEDfx scene name, so it is a natural key two scenes can
    # legitimately share — reuse it rather than trying to add it twice.
    wled_preset_ids: List[str] = []
    for name in ("wled-one", "wled-two"):
        if not library.contains(WLED_PRESETS, name):
            library.add(WLED_Preset(id=name))
        wled_preset_ids.append(name)

    dmx_list = DMX_Preset_List(dmx_preset_ids=dmx_preset_ids, beats=dmx_beats)
    wled_list = WLED_Preset_List(wled_preset_ids=wled_preset_ids, beats=wled_beats)
    preset = Preset(dmx_preset_list_id=dmx_list.id, wled_preset_list_id=wled_list.id)
    scene = Scene(preset_id=preset.id, sensitivity=0.5)

    library.add(dmx_list)
    library.add(wled_list)
    library.add(preset)
    library.add(scene)

    return CyclingScene(
        scene_id=scene.id,
        device_id=device.id,
        dmx_preset_ids=dmx_preset_ids,
        wled_preset_ids=wled_preset_ids,
        dmx_beats=dmx_beats,
        wled_beats=wled_beats,
    )


__all__ = [
    "DMX_DEVICE_PRESETS",
    "DMX_DEVICES",
    "DMX_PRESET_LISTS",
    "DMX_PRESETS",
    "ILDA_FRAME_LISTS",
    "PRESETS",
    "SCENES",
    "WLED_PRESET_LISTS",
    "WLED_PRESETS",
    "CyclingScene",
    "build_cycling_scene_graph",
    "build_minimal_scene_graph",
]
