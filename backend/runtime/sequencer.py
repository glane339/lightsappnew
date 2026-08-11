"""
Beat-driven cue sequencing.

A pure state machine: its only input is ``on_beat()`` and its only output is which cue
to show. It holds no library reference, performs no I/O, and knows nothing about DMX or
LEDfx, which is what makes a show's timing testable without audio or hardware.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple


class CueSequencer:
    """
    Walks one cue list, advancing every ``beats`` beats.

    ``entries`` is a snapshot taken at activation, not a live view of the library, so
    editing a cue list cannot disturb a running show. Advancing happens *on* the beat
    that completes an entry's count, not the one after it.
    """

    def __init__(self, entries: Sequence[str], beats: int, loop: bool = True) -> None:
        if not entries:
            raise ValueError("a cue sequencer needs at least one entry")
        if beats < 1:
            raise ValueError(f"beats must be at least 1, got {beats}")

        self.entries: Tuple[str, ...] = tuple(entries)
        self.beats = beats
        self.loop = loop
        self.index = 0
        self.beats_elapsed = 0

    @property
    def current(self) -> str:
        """The cue that should be showing right now."""
        return self.entries[self.index]

    @property
    def holding(self) -> bool:
        """True once a non-looping list has settled on its final cue."""
        return not self.loop and self.index == len(self.entries) - 1

    def on_beat(self) -> Optional[str]:
        """
        Register one beat. Returns the new cue id if the cue changed, otherwise None.

        None means "nothing to do" — either the current entry has beats left to run, or
        the list has nowhere else to go. Callers apply output only on a real change, so
        a one-entry list never re-sends the same cue.
        """
        if self.holding:
            return None

        self.beats_elapsed += 1
        if self.beats_elapsed < self.beats:
            return None

        self.beats_elapsed = 0
        last = len(self.entries) - 1
        next_index = 0 if self.index >= last else self.index + 1
        if next_index == self.index:
            return None

        self.index = next_index
        return self.current

    def reset(self) -> str:
        """Return to the first cue with a cleared beat count, and report that cue."""
        self.index = 0
        self.beats_elapsed = 0
        return self.current
