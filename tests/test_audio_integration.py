from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from types import ModuleType

from audio.beat_source import ManualBeatSource
from conftest import build_cycling_scene_graph
from fastapi.testclient import TestClient
from server.beat_timing import DetectedBeatTiming
from server.commands import CommandKind, ShowCommand
from server.engine import ShowBusyError, ShowEngine
from storage.config import AppConfig, AudioConfig
from storage.library import Library

WAIT_S = 3.0


@dataclass(frozen=True)
class FakeBeat:
    timestamp_seconds: float


@dataclass(frozen=True)
class FakeResult:
    bpm: float | None
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


def _install_fake_sounddevice(
    monkeypatch: object,
    *,
    query_devices: Callable[[object, str], object],
    query_hostapis: Callable[[int], object],
) -> None:
    sounddevice = ModuleType("sounddevice")
    sounddevice.query_devices = query_devices
    sounddevice.query_hostapis = query_hostapis
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)


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


def test_detected_beat_bridge_preserves_adapter_timestamp_and_submission_boundary(monkeypatch) -> None:
    """The bridge must carry the adapter boundary instead of restamping the beat source."""
    from server.app import _submit_detected_beat

    class RecordingEngine:
        def __init__(self) -> None:
            self.commands = []

        def submit(self, command: object) -> None:
            self.commands.append(command)

    monkeypatch.setattr("server.app.time.perf_counter_ns", lambda: 120)
    engine = RecordingEngine()
    _submit_detected_beat(engine, DetectedBeatTiming(100))

    timing = engine.commands[0].detected_beat_timing
    assert timing.detected_beat_published_ns == 100
    assert timing.command_submitted_ns == 120


def test_detected_beat_queue_full_records_a_drop(monkeypatch) -> None:
    """Queue saturation must be measurable without turning into an audio-thread failure."""
    from server.app import _submit_detected_beat

    class BusyEngine:
        def __init__(self) -> None:
            from server.beat_timing import DetectedBeatTimingTracker

            self.detected_beat_timing = DetectedBeatTimingTracker()

        def submit(self, command: object) -> None:
            raise ShowBusyError("full")

    monkeypatch.setattr("server.app.time.perf_counter_ns", lambda: 120)
    engine = BusyEngine()
    _submit_detected_beat(engine, DetectedBeatTiming(100))

    assert engine.detected_beat_timing.snapshot()["latest"]["outcome"] == "dropped_queue_full"


def test_show_engine_records_processing_and_action_boundaries(data_root, monkeypatch) -> None:
    """A detected beat that changes a cue must retain every observed boundary."""
    engine = ShowEngine(Library.open(data_root, sync_ilda=False), AppConfig())

    class ActionController:
        def on_beat(self, on_action) -> bool:
            on_action()
            return True

    engine._controller = ActionController()
    engine._emit_state = lambda: None
    ticks = iter((150, 180))
    monkeypatch.setattr("server.engine.time.perf_counter_ns", lambda: next(ticks))
    engine._handle(
        ShowCommand(
            kind=CommandKind.BEAT,
            received_ns=120,
            detected_beat_timing=DetectedBeatTiming(100, 120),
        )
    )

    assert engine.detected_beat_timing.snapshot()["latest"] == {
        "detected_beat_published_ns": 100,
        "command_submitted_ns": 120,
        "command_processed_ns": 150,
        "beat_action_ns": 180,
        "publish_to_submit_ns": 20,
        "submit_to_process_ns": 30,
        "publish_to_process_ns": 50,
        "process_to_action_ns": 30,
        "publish_to_action_ns": 80,
        "outcome": "processed",
    }


def test_show_engine_omits_action_timing_when_a_detected_beat_changes_nothing(data_root, monkeypatch) -> None:
    """A beat between cue boundaries must not claim an action timestamp."""
    engine = ShowEngine(Library.open(data_root, sync_ilda=False), AppConfig())

    class IdleController:
        def on_beat(self, on_action) -> bool:
            return False

    engine._controller = IdleController()
    engine._emit_state = lambda: None
    monkeypatch.setattr("server.engine.time.perf_counter_ns", lambda: 150)
    engine._handle(
        ShowCommand(
            kind=CommandKind.BEAT,
            received_ns=120,
            detected_beat_timing=DetectedBeatTiming(100, 120),
        )
    )

    latest = engine.detected_beat_timing.snapshot()["latest"]
    assert latest["command_processed_ns"] == 150
    assert latest["beat_action_ns"] is None
    assert "process_to_action_ns" not in latest


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


def test_resolve_input_device_resolves_unique_name_to_index_and_logs_identity(
    monkeypatch, caplog
) -> None:
    from server.app import _resolve_input_device

    requested = "Microphone (Realtek(R) Audio), Windows WASAPI"

    def query_devices(selector: object, kind: str) -> object:
        assert selector == requested
        assert kind == "input"
        return {"index": 12, "name": "Microphone (Realtek(R) Audio)", "hostapi": 2}

    _install_fake_sounddevice(
        monkeypatch,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": "Windows WASAPI"},
    )

    with caplog.at_level(logging.INFO, logger="server.app"):
        resolved = _resolve_input_device(requested)

    assert resolved == 12
    assert requested in caplog.text
    assert "[12] Microphone (Realtek(R) Audio)" in caplog.text
    assert "Windows WASAPI" in caplog.text


def test_resolve_input_device_rejects_blank_without_using_default(monkeypatch) -> None:
    from server.app import _resolve_input_device

    monkeypatch.setattr(
        "server.app._default_input_device_selector",
        lambda: (_ for _ in ()).throw(AssertionError("default must not be used")),
    )

    assert _resolve_input_device("") is None
    assert _resolve_input_device("   ") is None


def test_resolve_input_device_uses_host_default_when_unset(monkeypatch) -> None:
    from server.app import _resolve_input_device

    monkeypatch.setattr("server.app._default_input_device_selector", lambda: 4)

    def query_devices(selector: object, kind: str) -> object:
        assert selector == 4
        assert kind == "input"
        return {"index": 4, "name": "Default microphone", "hostapi": 1}

    _install_fake_sounddevice(
        monkeypatch,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": "MME"},
    )

    assert _resolve_input_device(None) == 4


def test_numeric_string_selector_is_not_treated_as_device_index(monkeypatch, caplog) -> None:
    from server.app import _resolve_input_device

    monkeypatch.setattr(
        "server.app._default_input_device_selector",
        lambda: (_ for _ in ()).throw(AssertionError("default must not be used")),
    )

    def query_devices(selector: object, kind: str) -> object:
        assert selector == "12"
        assert kind == "input"
        raise ValueError("No input device matching '12'")

    _install_fake_sounddevice(
        monkeypatch,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": "unused"},
    )

    with caplog.at_level(logging.ERROR, logger="server.app"):
        resolved = _resolve_input_device("12")

    assert resolved is None
    assert "explicit audio input selector '12' could not be resolved" in caplog.text


def test_ambiguous_explicit_selector_fails_closed_without_building_audio_source(
    data_root, monkeypatch, caplog
) -> None:
    from server.app import create_app

    monkeypatch.setattr(
        "server.app._default_input_device_selector",
        lambda: (_ for _ in ()).throw(AssertionError("default must not be used")),
    )

    def query_devices(selector: object, kind: str) -> object:
        assert selector == "Microphone (Realtek(R) Audio)"
        assert kind == "input"
        raise ValueError("Multiple input devices found")

    _install_fake_sounddevice(
        monkeypatch,
        query_devices=query_devices,
        query_hostapis=lambda index: {"name": "unused"},
    )

    with caplog.at_level(logging.ERROR, logger="server.app"):
        app = create_app(
            AppConfig(audio=AudioConfig(input_device="Microphone (Realtek(R) Audio)")),
            data_root=data_root,
        )

    assert app.state.audio_source is None
    assert "could not be resolved" in caplog.text


def test_create_app_logs_effective_data_root_and_config_path(data_root, caplog) -> None:
    from server.app import create_app

    with caplog.at_level(logging.INFO, logger="server.app"):
        create_app(AppConfig(), data_root=data_root)

    assert f"application data root: {data_root}" in caplog.text
    assert f"config path: {data_root / 'config.json'}" in caplog.text


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

    monkeypatch.setattr("server.app._default_input_device_selector", lambda: 4)
    _install_fake_sounddevice(
        monkeypatch,
        query_devices=lambda selector, kind: {
            "index": 4,
            "name": "Default microphone",
            "hostapi": 1,
        },
        query_hostapis=lambda index: {"name": "Test host API"},
    )
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

    _install_fake_sounddevice(
        monkeypatch,
        query_devices=lambda selector, kind: {
            "index": 8,
            "name": "Test microphone",
            "hostapi": 1,
        },
        query_hostapis=lambda index: {"name": "Test host API"},
    )
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
