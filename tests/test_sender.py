from __future__ import annotations

import threading
import time
from typing import List

from models.Active_DMX_Channels import UNIVERSE_SIZE
from runtime.active import UniverseState
from runtime.sender import NullTransport, SenderThread

# Generous enough for a loaded CI box; the sender is expected to react in microseconds.
WAIT_S = 2.0


class CountingTransport:
    """Records every frame it is handed, and how many were sent."""

    def __init__(self) -> None:
        self.frames: List[List[int]] = []
        self.closed = False

    @property
    def name(self) -> str:
        return "counting"

    def send(self, channels: List[int]) -> None:
        self.frames.append(list(channels))

    def close(self) -> None:
        self.closed = True


def _wait_for(predicate, timeout_s: float = WAIT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return False


def _run_sender(universe: UniverseState, transport):
    stop = threading.Event()
    sender = SenderThread(universe, transport, stop=stop)
    sender.start()
    return sender


def test_publish_raises_the_dirty_flag_and_counts_frames() -> None:
    universe = UniverseState()

    universe.publish()

    assert universe.dirty.is_set()
    assert universe.publish_count() == 1


def test_two_universe_states_do_not_share_dirty_or_count() -> None:
    first = UniverseState()
    second = UniverseState()
    first.publish()

    assert first.dirty.is_set()
    assert not second.dirty.is_set()
    assert first.publish_count() == 1
    assert second.publish_count() == 0


def test_replace_skips_publish_when_unchanged() -> None:
    universe = UniverseState()
    universe.replace([1] * UNIVERSE_SIZE)
    assert universe.publish_count() == 1
    universe.replace([1] * UNIVERSE_SIZE)
    assert universe.publish_count() == 1


def test_replace_clamps_and_pads_to_universe_size() -> None:
    universe = UniverseState()
    universe.replace([-3, 300, 12])

    snap = universe.snapshot()
    assert snap[0:3] == [0, 255, 12]
    assert len(snap) == UNIVERSE_SIZE
    assert universe.dirty.is_set()


def test_sender_sends_on_change() -> None:
    universe = UniverseState()
    transport = CountingTransport()
    sender = _run_sender(universe, transport)
    try:
        universe.replace([7] * UNIVERSE_SIZE)

        assert _wait_for(lambda: len(transport.frames) >= 1)
        assert transport.frames[0][0] == 7
    finally:
        sender.stop()


def test_sender_is_idle_until_something_changes() -> None:
    transport = CountingTransport()
    sender = _run_sender(UniverseState(), transport)
    try:
        time.sleep(0.1)
        assert transport.frames == []
    finally:
        sender.stop()


def test_change_callback_fires_on_send() -> None:
    universe = UniverseState()
    transport = CountingTransport()
    changes: List[int] = []
    stop = threading.Event()
    sender = SenderThread(
        universe,
        transport,
        stop=stop,
        on_change_sent=lambda: changes.append(1),
    )
    sender.start()
    try:
        time.sleep(0.05)
        assert transport.frames == []
        assert changes == []

        universe.publish()
        assert _wait_for(lambda: len(transport.frames) >= 1)
        assert _wait_for(lambda: len(changes) >= 1)
    finally:
        sender.stop()


def test_stop_ends_the_thread() -> None:
    sender = _run_sender(UniverseState(), CountingTransport())
    assert sender.running

    sender.stop()

    assert not sender.running


def test_null_transport_counts_frames_without_a_socket() -> None:
    transport = NullTransport()

    transport.send([1, 2, 3])
    transport.send([4, 5, 6])

    assert transport.send_count == 2
    assert transport.last_channels == [4, 5, 6]
    assert transport.name == "null"


def test_sender_snapshots_under_the_owned_universe() -> None:
    """A sender does not read a module-global buffer — only the universe it was given."""
    live = UniverseState()
    other = UniverseState()
    transport = CountingTransport()
    sender = _run_sender(live, transport)
    try:
        other.replace([9] * UNIVERSE_SIZE)
        time.sleep(0.05)
        assert transport.frames == []

        live.replace([4] * UNIVERSE_SIZE)
        assert _wait_for(lambda: len(transport.frames) >= 1)
        assert transport.frames[0][0] == 4
    finally:
        sender.stop()
