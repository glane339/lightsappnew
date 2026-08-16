"""
The show, running on its own thread.

One thread owns ``SceneController`` outright and reads commands off a queue, which is
why nothing here takes a lock: there is only ever one mutator. The event loop stays on
I/O, the sender thread stays on the wake path, and LEDfx — the one output that can block
for seconds — is pushed onto a worker where a slow response costs the strips and nothing
else.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

from ledfx.client import LedFxClientProtocol
from ledfx.service import build_ledfx_stack
from runtime.active import publish_count
from runtime.outputs import AsyncCueOutput, DmxOutput, WledOutput
from runtime.scene_controller import SceneController
from runtime.sender import DmxTransport, SenderThread, build_transport
from server.commands import CommandKind, ShowCommand, ShowEvent, ShowState
from server.latency import LatencyTracker
from storage.config import AppConfig
from storage.json_store import StorageError
from storage.library import Library

logger = logging.getLogger(__name__)

# Deep enough to absorb a burst of taps, shallow enough that a backlog is a loud failure
# rather than silently growing latency.
COMMAND_QUEUE_MAX = 64

# One slot: the WLED worker only ever needs the newest cue.
WLED_QUEUE_MAX = 1

# How long a drained thread waits before re-checking the stop flag.
_POLL_S = 0.1

THREAD_PRIORITY_ABOVE_NORMAL = 1


class ShowBusyError(RuntimeError):
    """The show thread is not keeping up with commands."""


def _raise_current_thread_priority() -> None:
    """Nudge the calling thread above normal on Windows; a no-op elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetCurrentThread()
        ctypes.windll.kernel32.SetThreadPriority(handle, THREAD_PRIORITY_ABOVE_NORMAL)
    except Exception as exc:  # pragma: no cover - priority is an optimisation, not a need
        logger.debug("could not raise thread priority: %s", exc)


class ShowEngine:
    """
    Owns the show thread, the sender thread, and the LEDfx worker.

    Commands go in through ``submit`` from any thread; state, acks, and errors come back
    out through the asyncio queue handed to ``bind_loop``.
    """

    def __init__(
        self,
        library: Library,
        config: AppConfig,
        *,
        transport: Optional[DmxTransport] = None,
    ) -> None:
        self._library = library
        self._config = config
        self._stop = threading.Event()
        self._commands: "queue.Queue[Optional[ShowCommand]]" = queue.Queue(maxsize=COMMAND_QUEUE_MAX)
        self._wled_cues: "queue.Queue[str]" = queue.Queue(maxsize=WLED_QUEUE_MAX)
        self._latency = LatencyTracker()

        self._transport = transport if transport is not None else build_transport(config.dmx)
        self._ledfx_client, self._ledfx_sync = build_ledfx_stack(library, config.ledfx)

        self._dmx_output = DmxOutput(library)
        self._wled_worker = WledOutput(self._ledfx_client)
        self._controller = SceneController(
            library,
            self._dmx_output,
            AsyncCueOutput(self._wled_cues),
        )

        self._sender = SenderThread(
            self._dmx_output.channels,
            self._transport,
            keepalive_s=1.0 / config.dmx.refresh_hz,
            stop=self._stop,
            on_change_sent=self._on_change_sent,
        )

        # Filled by the show thread before a frame is published, drained by the sender
        # thread once it goes out. A queue rather than a single slot because the sender
        # coalesces: two looks published before it wakes go out as one frame, and both
        # commands still need timing and an ack.
        self._awaiting_send: "queue.SimpleQueue[Tuple[int, Optional[str]]]" = queue.SimpleQueue()

        self._show_thread: Optional[threading.Thread] = None
        self._wled_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._events: Optional["asyncio.Queue[ShowEvent]"] = None

    @property
    def latency(self) -> LatencyTracker:
        return self._latency

    @property
    def transport(self) -> DmxTransport:
        return self._transport

    @property
    def ledfx_client(self) -> LedFxClientProtocol:
        return self._ledfx_client

    @property
    def ledfx_enabled(self) -> bool:
        return self._config.ledfx.enabled

    @property
    def running(self) -> bool:
        return self._show_thread is not None and self._show_thread.is_alive()

    def bind_loop(
        self,
        loop: asyncio.AbstractEventLoop,
        events: "asyncio.Queue[ShowEvent]",
    ) -> None:
        """Point outbound events at the running event loop. Called from the loop."""
        self._loop = loop
        self._events = events

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._sender.start()
        if self._ledfx_sync is not None:
            self._ledfx_sync.start()
            logger.info(
                "LEDfx scene sync started (%s, every %.0fs)",
                self._config.ledfx.base_url,
                self._config.ledfx.scene_refresh_s,
            )
        self._wled_thread = threading.Thread(
            target=self._run_wled_worker, name="wled-worker", daemon=True
        )
        self._wled_thread.start()
        self._show_thread = threading.Thread(target=self._run_show, name="show", daemon=True)
        self._show_thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        try:
            self._commands.put_nowait(None)  # wake the show thread out of its get()
        except queue.Full:
            pass

        if self._ledfx_sync is not None:
            self._ledfx_sync.stop(timeout_s=timeout_s)
        self._sender.stop(timeout_s=timeout_s)

        for thread in (self._show_thread, self._wled_thread):
            if thread is not None:
                thread.join(timeout=timeout_s)
        self._show_thread = None
        self._wled_thread = None

        self._blackout_before_close()
        self._transport.close()
        self._ledfx_client.close()

    def _blackout_before_close(self) -> None:
        """
        Put zeros on the wire while the socket is still open (D-011).

        Sent from this thread rather than published, because the sender is already
        stopped by the time shutdown gets here. The transport repeats the blackout in
        ``close()``; doing it here as well means the rig goes dark even if a transport
        skips that step.
        """
        try:
            self._dmx_output.blackout()
            self._transport.send(self._dmx_output.channels.channels)
        except Exception:  # pragma: no cover - shutdown must not raise
            logger.exception("could not blackout before closing the transport")

    def submit(self, command: ShowCommand) -> None:
        """
        Hand a command to the show thread.

        Raises rather than blocking: a full queue means the show thread is wedged, and
        waiting on the event loop would turn one stall into a stalled server.
        """
        try:
            self._commands.put_nowait(command)
        except queue.Full as exc:
            raise ShowBusyError("show command queue is full") from exc

    def state(self) -> ShowState:
        return ShowState(
            active_scene_id=self._controller.active_scene_id,
            is_active=self._controller.is_active,
            sensitivity=self._controller.sensitivity,
        )

    def sender_health(self) -> Dict[str, Any]:
        destination = getattr(self._transport, "destination", None)
        return {
            "running": self._sender.running,
            "transport": getattr(self._transport, "name", type(self._transport).__name__),
            "frames_sent": getattr(self._transport, "send_count", None),
            "destination": f"{destination[0]}:{destination[1]}" if destination else None,
            "send_failures": getattr(self._transport, "failure_count", None),
        }

    def _run_show(self) -> None:
        _raise_current_thread_priority()
        while not self._stop.is_set():
            try:
                command = self._commands.get(timeout=_POLL_S)
            except queue.Empty:
                continue
            if command is None:
                break
            try:
                self._handle(command)
            except Exception:  # pragma: no cover - last line of defence for the thread
                logger.exception("show thread survived a failure handling %s", command.kind)

    def _handle(self, command: ShowCommand) -> None:
        frames_before = publish_count()
        # Queued before the work, because publishing wakes the sender immediately and it
        # may finish the ack before this method returns.
        self._awaiting_send.put((command.received_ns, command.ack_id))

        # Nothing a command can do may kill this thread: the show thread dying is the
        # whole rig going unresponsive, which is worse than any single bad command.
        try:
            self._dispatch(command)
        except KeyError as exc:
            # Library.get raises KeyError for an id that is not in the collection.
            missing = exc.args[0] if exc.args else "?"
            self._reject(command, f"cannot {command.kind.value}: no record with id {missing!r}")
            return
        except StorageError as exc:
            self._reject(command, str(exc))
            return
        except Exception as exc:  # pragma: no cover - guards against unforeseen failures
            logger.exception("unhandled failure running %s", command.kind.value)
            self._reject(command, f"{type(exc).__name__}: {exc}", warn=False)
            return

        if publish_count() == frames_before:
            # Nothing reached the wire — a deactivate, or a beat mid-cue. There is no
            # packet to time, so acknowledge here instead of leaving the client waiting.
            self._discard_pending(command)

        self._emit_state()

    def _dispatch(self, command: ShowCommand) -> None:
        if command.kind is CommandKind.ACTIVATE:
            if not command.scene_id:
                raise StorageError("activate requires a scene id")
            self._controller.activate(command.scene_id)
        elif command.kind is CommandKind.DEACTIVATE:
            self._controller.deactivate()
        elif command.kind is CommandKind.BLACKOUT:
            # Sequencing is stopped first, or the next beat would light the rig back up
            # and a blackout would not stay black.
            self._controller.deactivate()
            self._dmx_output.blackout()
        elif command.kind is CommandKind.BEAT:
            self._controller.on_beat()
        else:  # pragma: no cover - CommandKind is closed
            raise StorageError(f"unknown command {command.kind!r}")

    def _reject(self, command: ShowCommand, message: str, *, warn: bool = True) -> None:
        """Report a command that did not run. State is unchanged, so none is emitted."""
        self._discard_pending(command, ack=False)
        if warn:
            logger.warning("rejected %s: %s", command.kind.value, message)
        self._emit(ShowEvent("error", {"id": command.ack_id, "message": message}))

    def _discard_pending(self, command: ShowCommand, *, ack: bool = True) -> None:
        """
        Take a command back off the pending-send queue, because no frame is coming.

        Answering the client here keeps every command accounted for: one ack or one
        error per command, whether or not it reached the wire.
        """
        try:
            self._awaiting_send.get_nowait()
        except queue.Empty:
            # The sender got there first, so it has already been timed and answered.
            return
        if ack and command.ack_id is not None:
            self._ack(command.ack_id, (time.perf_counter_ns() - command.received_ns) // 1000)

    def _on_change_sent(self) -> None:
        """
        Runs on the sender thread, right after a changed frame goes out.

        Everything waiting is timed against this one send. A command superseded before
        the frame left is charged the full wait rather than dropped, so the ledger counts
        every command and errs pessimistic.
        """
        sent_ns = time.perf_counter_ns()
        while True:
            try:
                received_ns, ack_id = self._awaiting_send.get_nowait()
            except queue.Empty:
                return
            elapsed_ns = sent_ns - received_ns
            self._latency.record(elapsed_ns)
            if ack_id is not None:
                self._ack(ack_id, elapsed_ns // 1000)

    def _run_wled_worker(self) -> None:
        """
        Drain to the newest cue, then make the blocking call.

        Everything expensive about LEDfx — the HTTP round trip, the 2 s timeout, the
        slug lookup on a cache miss — happens here, off the show thread.
        """
        while not self._stop.is_set():
            try:
                cue = self._wled_cues.get(timeout=_POLL_S)
            except queue.Empty:
                continue
            while True:
                try:
                    cue = self._wled_cues.get_nowait()
                except queue.Empty:
                    break
            self._wled_worker.apply(cue)

    def _emit_state(self) -> None:
        state = self.state()
        self._emit(
            ShowEvent(
                "state",
                {
                    "active_scene_id": state.active_scene_id,
                    "is_active": state.is_active,
                    "sensitivity": state.sensitivity,
                },
            )
        )

    def _ack(self, ack_id: str, latency_us: int) -> None:
        self._emit(ShowEvent("ack", {"id": ack_id, "latency_us": latency_us}))

    def _emit(self, event: ShowEvent) -> None:
        loop = self._loop
        events = self._events
        if loop is None or events is None:
            return

        def deliver() -> None:
            try:
                events.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("dropped %s event: client event queue is full", event.kind)

        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            # Loop closed under us during shutdown; the event has nowhere to go.
            pass
