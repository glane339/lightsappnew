from __future__ import annotations

import threading
import time
from typing import List

import pytest

from models.Active_DMX_Channels import UNIVERSE_SIZE, Active_DMX_Channels
from runtime.active import dmx_dirty, publish, publish_count
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


@pytest.fixture
def clean_dirty_flag():
    dmx_dirty.clear()
    yield
    dmx_dirty.clear()


def _wait_for(predicate, timeout_s: float = WAIT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return False


def _run_sender(channels, transport, keepalive_s: float = 60.0):
    """Start a sender on a long keepalive, so any send is change-driven."""
    stop = threading.Event()
    sender = SenderThread(channels, transport, keepalive_s=keepalive_s, stop=stop)
    sender.start()
    return sender


def test_publish_raises_the_dirty_flag_and_counts_frames(clean_dirty_flag) -> None:
    before = publish_count()

    publish()

    assert dmx_dirty.is_set()
    assert publish_count() == before + 1


def test_sender_sends_on_change_without_waiting_for_the_keepalive(clean_dirty_flag) -> None:
    channels = Active_DMX_Channels()
    transport = CountingTransport()
    sender = _run_sender(channels, transport)
    try:
        channels.channels = [7] * UNIVERSE_SIZE
        publish()

        assert _wait_for(lambda: len(transport.frames) >= 1)
        assert transport.frames[0][0] == 7
    finally:
        sender.stop()


def test_sender_is_idle_until_something_changes(clean_dirty_flag) -> None:
    transport = CountingTransport()
    sender = _run_sender(Active_DMX_Channels(), transport)
    try:
        time.sleep(0.1)
        # No publish, and the keepalive is a minute out, so nothing should have gone.
        assert transport.frames == []
    finally:
        sender.stop()


def test_keepalive_resends_an_unchanged_universe(clean_dirty_flag) -> None:
    transport = CountingTransport()
    sender = _run_sender(Active_DMX_Channels(), transport, keepalive_s=0.02)
    try:
        assert _wait_for(lambda: len(transport.frames) >= 3)
    finally:
        sender.stop()


def test_change_callback_fires_only_for_changes(clean_dirty_flag) -> None:
    channels = Active_DMX_Channels()
    transport = CountingTransport()
    changes: List[int] = []
    stop = threading.Event()
    sender = SenderThread(
        channels,
        transport,
        keepalive_s=0.02,
        stop=stop,
        on_change_sent=lambda: changes.append(1),
    )
    sender.start()
    try:
        # Let several keepalive frames go out before anything changes.
        assert _wait_for(lambda: len(transport.frames) >= 3)
        assert changes == []

        publish()
        assert _wait_for(lambda: len(changes) >= 1)
    finally:
        sender.stop()


def test_stop_ends_the_thread(clean_dirty_flag) -> None:
    sender = _run_sender(Active_DMX_Channels(), CountingTransport())
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


def test_keepalive_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SenderThread(
            Active_DMX_Channels(),
            NullTransport(),
            keepalive_s=0,
            stop=threading.Event(),
        )
