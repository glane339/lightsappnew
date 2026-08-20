from __future__ import annotations

import time
import sys
from types import ModuleType

from audio.beat_source import ManualBeatSource
from fastapi.testclient import TestClient
from server.commands import CommandKind
from server.engine import ShowBusyError
from storage.config import AppConfig, AudioConfig


def test_detected_beat_bridge_submits_one_show_command_with_receipt_clock() -> None:
    from server.app import _submit_detected_beat

    class RecordingEngine:
        def __init__(self) -> None:
            self.commands = []

        def submit(self, command: object) -> None:
            self.commands.append(command)

    engine = RecordingEngine()
    before = time.perf_counter_ns()
    _submit_detected_beat(engine)

    assert len(engine.commands) == 1
    assert engine.commands[0].kind is CommandKind.BEAT
    assert engine.commands[0].received_ns >= before


def test_detected_beat_queue_overflow_is_dropped_without_affecting_manual_source() -> None:
    from server.app import _submit_detected_beat

    class BusyEngine:
        def submit(self, command: object) -> None:
            raise ShowBusyError("full")

    _submit_detected_beat(BusyEngine())

    manual = ManualBeatSource()
    received: list[None] = []
    manual.subscribe(lambda: received.append(None))
    manual.start()
    manual.beat()

    assert received == [None]


def test_invalid_configured_audio_selector_leaves_manual_show_beat_available(
    data_root, monkeypatch
) -> None:
    from server.app import create_app

    class RejectingSoundDeviceAudioSource:
        def __init__(self, device: str) -> None:
            raise ValueError(f"invalid input device selector: {device!r}")

    audio_engine = ModuleType("lights_audio_engine")
    audio_engine.AudioEngine = object
    capture = ModuleType("lights_audio_engine.capture")
    capture.SoundDeviceAudioSource = RejectingSoundDeviceAudioSource
    capture.run_engine = lambda source, engine: ()
    monkeypatch.setitem(sys.modules, "lights_audio_engine", audio_engine)
    monkeypatch.setitem(sys.modules, "lights_audio_engine.capture", capture)

    app = create_app(
        AppConfig(audio=AudioConfig(input_device="")),
        data_root=data_root,
    )

    assert app.state.audio_source is None
    with TestClient(app) as client:
        response = client.post("/api/show/beat")

    assert response.status_code == 200
    assert response.json()["accepted"] is True
