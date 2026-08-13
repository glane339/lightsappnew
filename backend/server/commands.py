"""
What crosses the boundary between the event loop and the show thread.

The command queue is the only way into the show, which is what lets the show thread own
``SceneController`` without a lock. A beat detector (WS-9) becomes another producer here
rather than another caller of the controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CommandKind(str, Enum):
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    BLACKOUT = "blackout"
    BEAT = "beat"


@dataclass(frozen=True)
class ShowCommand:
    """
    One operator action, stamped when it arrived.

    ``received_ns`` is taken at the edge — the moment the WebSocket frame or HTTP body
    was read — so the latency ledger measures the whole software path rather than the
    part after the queue.
    """

    kind: CommandKind
    received_ns: int
    scene_id: Optional[str] = None
    ack_id: Optional[str] = None


@dataclass(frozen=True)
class ShowState:
    active_scene_id: Optional[str]
    is_active: bool
    sensitivity: Optional[float]


@dataclass(frozen=True)
class ShowEvent:
    """Anything the show thread pushes back to connected clients."""

    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
