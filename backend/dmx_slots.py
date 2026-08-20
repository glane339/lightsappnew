"""DMX512 slot bounds. Shared by the runtime model, the on-disk record, and the wire."""

from __future__ import annotations

from typing import Iterable, List


def require_dmx_slots(values: Iterable[object]) -> List[int]:
    """Reject anything that is not an int in 0–255. Bools are not slots."""
    slots: List[int] = []
    for index, value in enumerate(values):
        if type(value) is not int or value < 0 or value > 255:
            raise ValueError(
                f"channel {index + 1} is {value!r}; DMX values are integers 0-255"
            )
        slots.append(value)
    return slots


def clamp_dmx_slot(value: object) -> int:
    """Last line of defence at the universe write: never let an out-of-range value hit the wire."""
    if type(value) is bool or not isinstance(value, (int, float)):
        try:
            value = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0
    number = int(value)
    if number < 0:
        return 0
    if number > 255:
        return 255
    return number


def clamp_dmx_slots(values: Iterable[object]) -> List[int]:
    return [clamp_dmx_slot(value) for value in values]
