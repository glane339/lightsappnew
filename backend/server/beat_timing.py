"""Software-path timing for automatically detected beats only."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional


_HISTORY_SIZE = 32


@dataclass(frozen=True)
class DetectedBeatTiming:
    """Monotonic boundaries for one detected beat through the Lights App runtime."""

    detected_beat_published_ns: int
    command_submitted_ns: Optional[int] = None
    command_processed_ns: Optional[int] = None
    beat_action_ns: Optional[int] = None


class DetectedBeatTimingTracker:
    """Keep a bounded, thread-safe record of detected-beat software timing."""

    def __init__(self, capacity: int = _HISTORY_SIZE) -> None:
        self._capacity = capacity
        self._records: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._dropped = 0
        self._lock = threading.Lock()

    def record(self, timing: DetectedBeatTiming) -> None:
        payload = self._payload(timing, outcome="processed")
        with self._lock:
            self._records.append(payload)

    def record_drop(self, timing: DetectedBeatTiming) -> None:
        payload = self._payload(timing, outcome="dropped_queue_full")
        with self._lock:
            self._records.append(payload)
            self._dropped += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latest = dict(self._records[-1]) if self._records else None
            recorded = len(self._records)
            dropped = self._dropped
        return {
            "measurement": "software_path_only",
            "capacity": self._capacity,
            "recorded": recorded,
            "dropped": dropped,
            "latest": latest,
        }

    @staticmethod
    def _payload(timing: DetectedBeatTiming, *, outcome: str) -> dict[str, Any]:
        if timing.command_submitted_ns is None:
            raise ValueError("detected beat timing must include command submission")
        payload: dict[str, Any] = {
            "detected_beat_published_ns": timing.detected_beat_published_ns,
            "command_submitted_ns": timing.command_submitted_ns,
            "command_processed_ns": timing.command_processed_ns,
            "beat_action_ns": timing.beat_action_ns,
            "publish_to_submit_ns": (
                timing.command_submitted_ns - timing.detected_beat_published_ns
            ),
            "outcome": outcome,
        }
        if timing.command_processed_ns is not None:
            payload["submit_to_process_ns"] = (
                timing.command_processed_ns - timing.command_submitted_ns
            )
            payload["publish_to_process_ns"] = (
                timing.command_processed_ns - timing.detected_beat_published_ns
            )
        if timing.beat_action_ns is not None and timing.command_processed_ns is not None:
            payload["process_to_action_ns"] = (
                timing.beat_action_ns - timing.command_processed_ns
            )
            payload["publish_to_action_ns"] = (
                timing.beat_action_ns - timing.detected_beat_published_ns
            )
        return payload
