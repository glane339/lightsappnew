"""
Process-wide settings that protect the latency headroom.

None of this makes the fast path faster; it stops the interpreter and the OS from
occasionally making it slower. Applied by the entry point rather than the app factory,
because every one of these is global and tests should not inherit them.
"""

from __future__ import annotations

import gc
import logging
import sys

logger = logging.getLogger(__name__)

# The default 5 ms is half the budget: a CPU-bound stretch on the event loop can hold the
# GIL that long and stall the show thread.
SWITCH_INTERVAL_S = 0.001

# Collection is the other source of multi-millisecond pauses, and the shape of the fix is
# not "collect less often". A gen0 pass scans only the young objects, so its cost tracks
# the threshold — pushing gen0 into the tens of thousands buys fewer pauses at the price
# of much longer ones, which is the wrong trade when p99 is the target. Gen0 stays small,
# while the generation multipliers go up to make the expensive full passes rare. The real
# win is gc.freeze(), which takes every startup object out of the scan for good.
GEN0_THRESHOLD = 2_000
GEN1_RATIO = 50
GEN2_RATIO = 50

WINDOWS_TIMER_PERIOD_MS = 1

_timer_period_set = False


def apply() -> None:
    sys.setswitchinterval(SWITCH_INTERVAL_S)
    gc.collect()
    gc.freeze()
    gc.set_threshold(GEN0_THRESHOLD, GEN1_RATIO, GEN2_RATIO)
    _begin_windows_timer_period()
    logger.info(
        "latency tuning applied: switchinterval=%.4fs, gc thresholds=%s",
        SWITCH_INTERVAL_S,
        gc.get_threshold(),
    )


def release() -> None:
    """Undo what has to be undone; the rest dies with the process."""
    global _timer_period_set
    if _timer_period_set and sys.platform == "win32":
        import ctypes

        ctypes.windll.winmm.timeEndPeriod(WINDOWS_TIMER_PERIOD_MS)
        _timer_period_set = False


def _begin_windows_timer_period() -> None:
    """
    Ask Windows for a 1 ms scheduler tick.

    Without it a keepalive wait can overshoot by the default ~15 ms tick, which is the
    whole budget spent on nothing.
    """
    global _timer_period_set
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.winmm.timeBeginPeriod(WINDOWS_TIMER_PERIOD_MS)
        _timer_period_set = True
    except Exception as exc:  # pragma: no cover - tuning is best effort
        logger.warning("could not set Windows timer period: %s", exc)
