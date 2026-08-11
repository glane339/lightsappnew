from __future__ import annotations

import pytest

from runtime.sequencer import CueSequencer


def test_advances_on_the_beat_that_completes_the_count() -> None:
    seq = CueSequencer(["a", "b"], beats=4)

    # The first three beats are silent; the fourth completes the entry.
    assert [seq.on_beat() for _ in range(3)] == [None, None, None]
    assert seq.current == "a"
    assert seq.on_beat() == "b"
    assert seq.current == "b"


def test_every_beat_advances_a_one_beat_list() -> None:
    seq = CueSequencer(["a", "b", "c"], beats=1)

    assert [seq.on_beat() for _ in range(4)] == ["b", "c", "a", "b"]


def test_loops_back_to_the_first_cue() -> None:
    seq = CueSequencer(["a", "b", "c"], beats=2)

    seen = [cue for _ in range(12) if (cue := seq.on_beat()) is not None]
    assert seen == ["b", "c", "a", "b", "c", "a"]
    assert seq.index == 0


def test_single_entry_list_never_reports_a_change() -> None:
    seq = CueSequencer(["only"], beats=2)

    # Nothing to advance to, so the cue is never re-applied and LEDfx is never
    # pointlessly re-told to run the scene it is already running.
    assert [seq.on_beat() for _ in range(6)] == [None] * 6
    assert seq.current == "only"


def test_hold_last_settles_on_the_final_cue() -> None:
    seq = CueSequencer(["a", "b"], beats=1, loop=False)

    assert seq.on_beat() == "b"
    assert seq.holding is True
    assert [seq.on_beat() for _ in range(5)] == [None] * 5
    assert seq.current == "b"


def test_holding_does_not_accumulate_beats() -> None:
    seq = CueSequencer(["a"], beats=3, loop=False)

    for _ in range(10):
        seq.on_beat()
    assert seq.beats_elapsed == 0


def test_reset_returns_to_the_first_cue() -> None:
    seq = CueSequencer(["a", "b", "c"], beats=2)
    seq.on_beat()
    seq.on_beat()
    seq.on_beat()
    assert seq.current == "b"

    assert seq.reset() == "a"
    assert (seq.index, seq.beats_elapsed) == (0, 0)


def test_partial_progress_is_kept_across_cues() -> None:
    seq = CueSequencer(["a", "b"], beats=3)

    seq.on_beat()
    seq.on_beat()
    assert seq.beats_elapsed == 2
    assert seq.on_beat() == "b"
    # The counter restarts for the new entry rather than carrying a remainder.
    assert seq.beats_elapsed == 0


def test_rejects_an_empty_cue_list() -> None:
    with pytest.raises(ValueError, match="at least one entry"):
        CueSequencer([], beats=1)


@pytest.mark.parametrize("beats", [0, -1])
def test_rejects_a_beat_count_below_one(beats: int) -> None:
    with pytest.raises(ValueError, match="beats must be at least 1"):
        CueSequencer(["a"], beats=beats)


def test_entries_are_snapshotted_not_referenced() -> None:
    entries = ["a", "b"]
    seq = CueSequencer(entries, beats=1)

    entries.append("c")
    assert seq.entries == ("a", "b")
