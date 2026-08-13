"""
The thread that would put the universe on the wire.

Symbolic on purpose: a transport protocol, a null implementation, and a wake loop.
Nothing here opens a socket or builds a packet. A real E1.31 transport drops in later
as one class behind ``DmxTransport`` once the universe box is verified (D-013, D-017).
"""

from __future__ import annotations

import threading
from typing import Callable, List, Optional, Protocol

from models.Active_DMX_Channels import Active_DMX_Channels
from runtime.active import dmx_dirty


class DmxTransport(Protocol):
    def send(self, channels: List[int]) -> None: ...

    def close(self) -> None: ...


class NullTransport:
    """
    Counts frames and keeps the last one, but opens no socket.

    The default until the universe box is verified, and the thing the latency harness
    measures against — a send that does nothing still proves the wake path.
    """

    def __init__(self) -> None:
        self.send_count = 0
        self.last_channels: Optional[List[int]] = None

    @property
    def name(self) -> str:
        return "null"

    def send(self, channels: List[int]) -> None:
        self.send_count += 1
        self.last_channels = channels

    def close(self) -> None:
        return None


class SenderThread:
    """
    Send-on-change with a keepalive floor.

    ``dmx_dirty.wait`` returns the moment a look changes. The timeout re-sends an
    unchanged universe so a future receiver that missed a packet can recover. Today
    both paths call ``NullTransport.send``.
    """

    def __init__(
        self,
        channels: Active_DMX_Channels,
        transport: DmxTransport,
        *,
        keepalive_s: float,
        stop: threading.Event,
        on_change_sent: Optional[Callable[[], None]] = None,
    ) -> None:
        if keepalive_s <= 0:
            raise ValueError("keepalive_s must be positive")
        self._channels = channels
        self._transport = transport
        self._keepalive_s = keepalive_s
        self._stop = stop
        self._on_change_sent = on_change_sent
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._thread = threading.Thread(target=self._run, name="dmx-sender", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        dmx_dirty.set()  # break the wait rather than letting it run out the keepalive
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_s)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            changed = dmx_dirty.wait(timeout=self._keepalive_s)
            if self._stop.is_set():
                break

            # Cleared before the buffer is read, so a look that lands during the send
            # leaves the flag set and is picked up on the next pass instead of being
            # swallowed.
            dmx_dirty.clear()
            self._transport.send(self._channels.channels)

            if changed and self._on_change_sent is not None:
                self._on_change_sent()
