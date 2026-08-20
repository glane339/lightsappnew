from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass

from audio.audio_engine_source import AudioEngineBeatSource


@dataclass(frozen=True)
class FakeBeat:
    timestamp_seconds: float


@dataclass(frozen=True)
class FakeResult:
    bpm: float | None
    beat_events: tuple[FakeBeat, ...]


class FakeSource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _wait_for(predicate: object, timeout_s: float = 1.0) -> bool:
    assert callable(predicate)
    return threading.Event().wait(0) if False else _poll(predicate, timeout_s)


def _poll(predicate: object, timeout_s: float) -> bool:
    assert callable(predicate)
    deadline = threading.Event()
    for _ in range(int(timeout_s * 100)):
        if predicate():
            return True
        deadline.wait(0.01)
    return bool(predicate())


def test_adapter_tracks_bpm_count_and_event_order() -> None:
    source = FakeSource()
    results = (
        FakeResult(120.0, (FakeBeat(1.0), FakeBeat(1.5))),
        FakeResult(124.0, (FakeBeat(2.0),)),
    )

    def runner(_source: object, _engine: object) -> Iterator[FakeResult]:
        yield from results

    adapter = AudioEngineBeatSource(source, object(), runner=runner)
    received: list[int] = []
    adapter.subscribe(lambda: received.append(adapter.beat_count))

    adapter.start()
    assert _wait_for(lambda: adapter.beat_count == 3)
    adapter.stop()

    assert adapter.bpm == 124.0
    assert received == [1, 2, 3]
    assert source.closed is True
    assert adapter.health()["capture"] == "off"


def test_adapter_catches_worker_failures_and_stop_is_idempotent() -> None:
    source = FakeSource()

    def runner(_source: object, _engine: object) -> Iterator[FakeResult]:
        raise RuntimeError("capture failed")
        yield  # pragma: no cover

    adapter = AudioEngineBeatSource(source, object(), runner=runner)

    adapter.start()
    assert _wait_for(lambda: not adapter.running)
    assert adapter.health()["capture"] == "dead"
    adapter.stop()
    adapter.stop()

    assert source.closed is True
    assert adapter.health()["capture"] == "dead"


def test_adapter_reports_silent_when_frames_have_no_beats() -> None:
    source = FakeSource()
    hold = threading.Event()

    def runner(_source: object, _engine: object) -> Iterator[FakeResult]:
        yield FakeResult(None, ())
        hold.wait()

    adapter = AudioEngineBeatSource(source, object(), runner=runner)
    adapter.start()
    try:
        assert _wait_for(lambda: adapter.health()["capture"] == "silent")
        assert adapter.health()["running"] is True
    finally:
        hold.set()
        adapter.stop()
