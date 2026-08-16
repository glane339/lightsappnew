"""
The thread that puts the universe on the wire, and the transports it can use.

``SenderThread`` owns the wake loop and knows nothing about packets; a transport owns
the wire and knows nothing about beats. ``NullTransport`` remains the default so a fresh
install emits nothing, and ``E131Transport`` is opted into from config once the rig is
wired (D-013).
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, List, Optional, Protocol, Sequence, Tuple

from models.Active_DMX_Channels import UNIVERSE_SIZE, Active_DMX_Channels
from runtime.active import dmx_dirty
from runtime.e131 import (
    DEFAULT_SOURCE_NAME,
    OPTION_STREAM_TERMINATED,
    SACN_PORT,
    SequenceCounter,
    build_data_packet,
    cid_from_source_name,
    multicast_host,
)
from storage.config import DMXConfig

logger = logging.getLogger(__name__)

# A managed switch on the same subnet is one hop away, so multicast never needs to leave
# the local segment. Raising this would leak show traffic onto the rest of the network.
MULTICAST_TTL = 1

# Send failures repeat at the keepalive rate, so every one of them must not reach the
# log. The first is always reported; after that only every so often.
_FAILURE_LOG_INTERVAL = 500


class DmxTransport(Protocol):
    def send(self, channels: List[int]) -> None: ...

    def close(self) -> None: ...


class NullTransport:
    """
    Counts frames and keeps the last one, but opens no socket.

    The default, and the thing the latency harness measures against — a send that does
    nothing still proves the wake path.
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


def _open_udp_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


class E131Transport:
    """
    Frames the universe as sACN and sends it over UDP.

    The socket is opened on the first send rather than in ``__init__`` so that a bad
    address or a NIC that is not up yet degrades to a logged failure instead of stopping
    the server from starting. For the same reason no send path raises: the rig going
    quiet is bad, but the show thread dying is worse.
    """

    def __init__(
        self,
        *,
        universe: int,
        host: str,
        port: int = SACN_PORT,
        priority: int = 100,
        source_name: str = DEFAULT_SOURCE_NAME,
        multicast: bool = False,
        bind_address: Optional[str] = None,
        socket_factory: Callable[[], socket.socket] = _open_udp_socket,
    ) -> None:
        self._universe = universe
        self._priority = priority
        self._source_name = source_name
        self._cid = cid_from_source_name(source_name)
        self._multicast = multicast
        self._bind_address = bind_address
        self._socket_factory = socket_factory

        # In multicast the group is derived from the universe, so a configured host would
        # be silently ignored; deriving it here makes the destination explicit either way.
        destination_host = multicast_host(universe) if multicast else host
        self._destination: Tuple[str, int] = (destination_host, port)

        self._sequence = SequenceCounter()
        self._socket: Optional[socket.socket] = None
        self._closed = False
        self._socket_error_logged = False

        self.send_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0

    @property
    def name(self) -> str:
        return "e131"

    @property
    def destination(self) -> Tuple[str, int]:
        return self._destination

    def send(self, channels: List[int]) -> None:
        self._send_frame(channels)

    def close(self) -> None:
        """
        Blackout, terminate the stream, then release the socket.

        Two frames rather than one: the zeros are what a receiver that ignores
        Stream_Terminated acts on, and the terminated flag is what tells a receiver that
        honours it to stop waiting for this source instead of holding for its timeout.
        """
        if self._closed:
            return
        self._closed = True

        sock = self._socket
        if sock is None:
            return
        try:
            blackout = [0] * UNIVERSE_SIZE
            self._send_frame(blackout, allow_closed=True)
            self._send_frame(blackout, options=OPTION_STREAM_TERMINATED, allow_closed=True)
        finally:
            try:
                sock.close()
            except OSError as exc:
                logger.warning("closing the sACN socket failed: %s", exc)
            self._socket = None

    def _send_frame(
        self,
        channels: Sequence[int],
        *,
        options: int = 0,
        allow_closed: bool = False,
    ) -> None:
        sock = self._socket if allow_closed else self._ensure_socket()
        if sock is None:
            return

        packet = build_data_packet(
            cid=self._cid,
            source_name=self._source_name,
            universe=self._universe,
            priority=self._priority,
            sequence=self._sequence.next(self._universe),
            channels=channels,
            options=options,
        )
        try:
            sock.sendto(packet, self._destination)
        except OSError as exc:
            self._record_failure(exc)
        else:
            self.send_count += 1
            self.consecutive_failures = 0

    def _ensure_socket(self) -> Optional[socket.socket]:
        if self._closed:
            return None
        if self._socket is not None:
            return self._socket

        try:
            sock = self._socket_factory()
            if self._bind_address:
                sock.bind((self._bind_address, 0))
            if self._multicast:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
                if self._bind_address:
                    sock.setsockopt(
                        socket.IPPROTO_IP,
                        socket.IP_MULTICAST_IF,
                        socket.inet_aton(self._bind_address),
                    )
        except OSError as exc:
            if not self._socket_error_logged:
                logger.error(
                    "could not open the sACN socket for %s:%d (bind %s): %s",
                    self._destination[0],
                    self._destination[1],
                    self._bind_address or "any",
                    exc,
                )
                self._socket_error_logged = True
            return None

        logger.info(
            "sACN transport ready: universe %d %s to %s:%d, priority %d, source %r",
            self._universe,
            "multicast" if self._multicast else "unicast",
            self._destination[0],
            self._destination[1],
            self._priority,
            self._source_name,
        )
        self._socket = sock
        self._socket_error_logged = False
        return sock

    def _record_failure(self, exc: OSError) -> None:
        self.failure_count += 1
        self.consecutive_failures += 1
        if self.consecutive_failures == 1 or self.consecutive_failures % _FAILURE_LOG_INTERVAL == 0:
            logger.warning(
                "sACN send to %s:%d failed (%d in a row): %s",
                self._destination[0],
                self._destination[1],
                self.consecutive_failures,
                exc,
            )


def build_transport(dmx: DMXConfig) -> DmxTransport:
    """Pick a transport from config. Anything but an explicit ``e131`` stays silent."""
    if dmx.transport != "e131":
        return NullTransport()
    return E131Transport(
        universe=dmx.universe,
        host=dmx.host,
        port=dmx.port,
        priority=dmx.priority,
        source_name=dmx.source_name,
        multicast=dmx.mode == "multicast",
        bind_address=dmx.bind_address,
    )


class SenderThread:
    """
    Send-on-change with a keepalive floor.

    ``dmx_dirty.wait`` returns the moment a look changes. The timeout re-sends an
    unchanged universe so a receiver that missed a packet recovers, and so a box that
    blacks out when packets stop keeps holding the current look.
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
        self.send_errors = 0

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

            # A transport is contracted not to raise, but this thread dying would freeze
            # the rig with no error anywhere, so the contract is not trusted.
            try:
                self._transport.send(self._channels.channels)
            except Exception:
                self.send_errors += 1
                logger.exception("sender survived a transport failure")

            # Fired even when the send failed: the commands waiting behind this frame
            # still need answering, and leaving them queued would grow without bound.
            if changed and self._on_change_sent is not None:
                self._on_change_sent()
