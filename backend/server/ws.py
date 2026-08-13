"""
The hot path: one open socket per operator.

A WebSocket is used for control because the alternative pays TCP and HTTP setup on every
scene change, and the budget has no room for it. Parsing happens before the timestamp is
used for anything, and the command is on the queue within a fraction of a millisecond.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from server.commands import CommandKind, ShowCommand, ShowEvent
from server.engine import ShowBusyError, ShowEngine

logger = logging.getLogger(__name__)

_QUEUED_KINDS = {
    "activate": CommandKind.ACTIVATE,
    "deactivate": CommandKind.DEACTIVATE,
    "blackout": CommandKind.BLACKOUT,
    "beat": CommandKind.BEAT,
}


class ProtocolError(ValueError):
    """The client sent something this server does not accept."""


async def handle_show_socket(
    websocket: WebSocket,
    engine: ShowEngine,
    events: "asyncio.Queue[ShowEvent]",
) -> None:
    await websocket.accept()
    pump = asyncio.create_task(_pump_events(websocket, events))
    try:
        while True:
            raw = await websocket.receive_text()
            # Stamped at the edge so the ledger covers parsing too.
            received_ns = time.perf_counter_ns()
            try:
                _submit(engine, raw, received_ns)
            except ProtocolError as exc:
                await websocket.send_json({"t": "error", "message": str(exc)})
            except ShowBusyError as exc:
                await websocket.send_json({"t": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()


async def _pump_events(websocket: WebSocket, events: "asyncio.Queue[ShowEvent]") -> None:
    """
    Forward show events to this client until cancelled.

    The queue is shared, so with more than one operator page open the events go to
    whichever socket is pumping — fine for the single-operator scope, and the place to
    add fan-out when that changes.
    """
    try:
        while True:
            event = await events.get()
            await websocket.send_json({"t": event.kind, **event.payload})
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - socket died under the pump
        logger.debug("event pump stopped: %s", exc)


def _submit(engine: ShowEngine, raw: str, received_ns: int) -> None:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid json: {exc.msg}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("expected a json object")

    kind = _QUEUED_KINDS.get(message.get("t"))
    if kind is None:
        raise ProtocolError(f"unknown message type {message.get('t')!r}")

    scene_id = None
    if kind is CommandKind.ACTIVATE:
        scene_id = message.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise ProtocolError("activate requires a non-empty string id")

    engine.submit(
        ShowCommand(
            kind=kind,
            received_ns=received_ns,
            scene_id=scene_id,
            ack_id=_ack_id(message),
        )
    )


def _ack_id(message: Dict[str, Any]) -> str:
    """Echo the client's ack tag when it sends one, so it can time its own round trip."""
    ack = message.get("ack")
    if isinstance(ack, str) and ack:
        return ack
    return uuid.uuid4().hex
