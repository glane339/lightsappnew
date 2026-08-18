"""
The measurement half of the latency requirement.

Samples span scene selection (command received on the server) through ``DmxTransport.send``
returning — the path the operator page and self-test measure. The ring buffer is
preallocated and the hot call is one index write, so recording a sample cannot itself
become a source of jitter.
"""

from __future__ import annotations

import threading
from typing import Dict, List

# p99 ceiling for scene selection → sender, in microseconds (13 ms).
LATENCY_BUDGET_US = 13_000

# Holds a full acceptance run (1000 activations) with room to spare, so a self-test never
# overwrites its own samples.
DEFAULT_CAPACITY = 8192


def percentile_ns(sorted_ns: List[int], fraction: float) -> int:
    """Linear-interpolated percentile over a sorted sample list."""
    if not sorted_ns:
        return 0
    if len(sorted_ns) == 1:
        return sorted_ns[0]
    rank = (len(sorted_ns) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(sorted_ns) - 1)
    weight = rank - low
    return int(round(sorted_ns[low] * (1.0 - weight) + sorted_ns[high] * weight))


class LatencyTracker:
    """
    Fixed-size ring of click-to-packet samples, in nanoseconds.

    ``record`` runs on the sender thread and ``snapshot`` on the event loop, so the ring
    is lock-guarded; the lock is never held across anything but a few index writes.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._samples = [0] * capacity
        self._next = 0
        self._count = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def record(self, elapsed_ns: int) -> None:
        with self._lock:
            self._samples[self._next] = elapsed_ns
            self._next = (self._next + 1) % self._capacity
            if self._count < self._capacity:
                self._count += 1

    def clear(self) -> None:
        with self._lock:
            self._next = 0
            self._count = 0

    def snapshot(self) -> Dict[str, int]:
        """
        Percentiles in microseconds — nanoseconds are noise at this scale.

        The samples are copied under the lock and sorted outside it. Sorting while holding
        it would put an O(n log n) stretch between the sender thread and its ``record``
        call, so merely reading the latency would be enough to inflate it.
        """
        with self._lock:
            count = self._count
            raw = self._samples[:count] if count < self._capacity else list(self._samples)

        values = sorted(raw)
        if not values:
            return {"count": 0, "p50_us": 0, "p95_us": 0, "p99_us": 0, "max_us": 0}

        return {
            "count": count,
            "p50_us": percentile_ns(values, 0.50) // 1000,
            "p95_us": percentile_ns(values, 0.95) // 1000,
            "p99_us": percentile_ns(values, 0.99) // 1000,
            "max_us": values[-1] // 1000,
        }

    def summary(self) -> Dict[str, int]:
        """The two numbers worth putting on the operator page."""
        snapshot = self.snapshot()
        return {
            "count": snapshot["count"],
            "p50_us": snapshot["p50_us"],
            "p99_us": snapshot["p99_us"],
        }
