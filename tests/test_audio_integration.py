from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from types import ModuleType
from typing import Optional

from audio.beat_source import ManualBeatSource
from conftest import build_cycling_scene_graph
from fastapi.testclient import TestClient
from server.commands import CommandKind
from server.engine import ShowBusyError
from storage.config import AppConfig, AudioConfig
from storage.library import Library

WAIT_S = 3.0


@dataclass(frozen=True)
class FakeBeat:
    timestamp_seconds: float


@dataclass(frozen=True)
class FakeResult:
    bpm: Optional[float]
    beat_events: tuple[FakeBeat, ...]


class FakeCapture:
    def __init__(self, device: object) -> None:
        self.device = device
        self.closed = False
        self._closed = threading.Event()

    def close(self) -> None:
        self.closed = True
        self._closed.set()

    def wait_closed(self, timeout_s: float = WAIT_S) -> bool:
        return self._closed.wait(timeout_s)


def _wait_until(predicate: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


def _install_fake_audio(
    monkeypatch: object, source_cls: type, runner: Callable[[object, object], Iterator[object]]
) -> None:
    audio_engine = ModuleType("lights_audio_engine")
    audio_engine.AudioEngine = object
    capture = ModuleType("lights_audio_engine.capture")
    capture.SoundDeviceAudioSource = source_cls
    capture.run_engine = runner
    monkeypatch.setitem(sys.modules, "lights_audio_engine", audio_engine)
    monkeypatch.setitem(sys.modules, "lights_audio_engine.capture", capture)


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


def test_resolve_input_device_prefers_configured_and_rejects_blank() -> None:
    from server.app import _resolve_input_device

    assert _resolve_input_device("Loopback") == "Loopback"
    assert _resolve_input_device("") is None
    assert _resolve_input_device("   ") is None


def test_resolve_input_device_uses_host_default_when_unset(monkeypatch) -> None:
    from server.app import _resolve_input_device

    monkeypatch.setattr("server.app._default_input_device_selector", lambda: 4)
    assert _resolve_input_device(None) == 4


def test_invalid_configured_audio_selector_leaves_manual_show_beat_available(
    data_root, monkeypatch
) -> None:
    from server.app import create_app

    class RejectingSoundDeviceAudioSource:
        def __init__(self, device: str) -> None:
            raise ValueError(f"invalid input device selector: {device!r}")

    _install_fake_audio(
        monkeypatch, RejectingSoundDeviceAudioSource, lambda source, engine: iter(())
    )

    app = create_app(
        AppConfig(audio=AudioConfig(input_device="")),
        data_root=data_root,
    )

    assert app.state.audio_source is None
    with TestClient(app) as client:
        response = client.post("/api/show/beat")

    assert response.status_code == 200
    assert response.json()["accepted"] is True


def test_audio_engine_starts_on_app_startup(data_root, monkeypatch) -> None:
    from server.app import create_app

    class HoldingCapture(FakeCapture):
        pass

    def runner(source: FakeCapture, _engine: object) -> Iterator[FakeResult]:
        source.wait_closed()
        yield from ()

    monkeypatch.setattr("server.app._default_input_device_selector", lambda: "default-mic")
    _install_fake_audio(monkeypatch, HoldingCapture, runner)

    app = create_app(AppConfig(), data_root=data_root)
    assert app.state.audio_source is not None

    with TestClient(app):
        assert app.state.audio_source.running is True

    assert app.state.audio_source.running is False


def test_detected_beats_advance_look_cycling(data_root, monkeypatch) -> None:
    from server.app import create_app

    library = Library.open(data_root, sync_ilda=False)
    graph = build_cycling_scene_graph(library, dmx_beats=2, wled_beats=3)
    library.save()

    release_beats = threading.Event()

    class GatedCapture(FakeCapture):
        def close(self) -> None:
            release_beats.set()
            super().close()

    def runner(source: GatedCapture, _engine: object) -> Iterator[FakeResult]:
        if not release_beats.wait(timeout=WAIT_S):
            return
        if source.closed:
            return
        yield FakeResult(120.0, (FakeBeat(0.0), FakeBeat(0.5)))
        source.wait_closed()

    _install_fake_audio(monkeypatch, GatedCapture, runner)

    app = create_app(
        AppConfig(audio=AudioConfig(input_device="test-mic")),
        data_root=data_root,
    )

    with TestClient(app) as client:
        assert app.state.audio_source is not None
        assert client.post("/api/show/activate", json={"id": graph.scene_id}).status_code == 200
        assert _wait_until(
            lambda: client.get("/api/show/state").json()["active_scene_id"] == graph.scene_id
        )

        first_look = list(app.state.engine.transport.last_channels or [])
        release_beats.set()

        assert _wait_until(
            lambda: list(app.state.engine.transport.last_channels or []) != first_look
        )
        assert app.state.audio_source.beat_count == 2
