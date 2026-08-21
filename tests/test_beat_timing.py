from __future__ import annotations

from server.beat_timing import DetectedBeatTiming, DetectedBeatTimingTracker


def test_tracker_serializes_complete_detected_beat_timing_and_deltas() -> None:
    """Removing a boundary or calculating from the wrong one must fail this test."""
    tracker = DetectedBeatTimingTracker()
    tracker.record(
        DetectedBeatTiming(
            detected_beat_published_ns=100,
            command_submitted_ns=120,
            command_processed_ns=150,
            beat_action_ns=180,
        )
    )

    assert tracker.snapshot() == {
        "measurement": "software_path_only",
        "capacity": 32,
        "recorded": 1,
        "dropped": 0,
        "latest": {
            "detected_beat_published_ns": 100,
            "command_submitted_ns": 120,
            "command_processed_ns": 150,
            "beat_action_ns": 180,
            "publish_to_submit_ns": 20,
            "submit_to_process_ns": 30,
            "publish_to_process_ns": 50,
            "process_to_action_ns": 30,
            "publish_to_action_ns": 80,
            "outcome": "processed",
        },
    }


def test_tracker_omits_action_deltas_when_a_beat_does_not_change_a_cue() -> None:
    """An idle beat must not pretend to have reached an output action."""
    tracker = DetectedBeatTimingTracker()
    tracker.record(
        DetectedBeatTiming(
            detected_beat_published_ns=100,
            command_submitted_ns=120,
            command_processed_ns=150,
        )
    )

    latest = tracker.snapshot()["latest"]
    assert latest["beat_action_ns"] is None
    assert latest["publish_to_submit_ns"] == 20
    assert latest["submit_to_process_ns"] == 30
    assert latest["publish_to_process_ns"] == 50
    assert "process_to_action_ns" not in latest
    assert "publish_to_action_ns" not in latest


def test_tracker_records_queue_full_drop_without_processing_timestamps() -> None:
    """A full show queue must remain visible without inventing processing timing."""
    tracker = DetectedBeatTimingTracker()
    tracker.record_drop(DetectedBeatTiming(detected_beat_published_ns=100, command_submitted_ns=120))

    snapshot = tracker.snapshot()
    assert snapshot["recorded"] == 1
    assert snapshot["dropped"] == 1
    assert snapshot["latest"] == {
        "detected_beat_published_ns": 100,
        "command_submitted_ns": 120,
        "command_processed_ns": None,
        "beat_action_ns": None,
        "publish_to_submit_ns": 20,
        "outcome": "dropped_queue_full",
    }


def test_tracker_evicts_old_records_without_waiting_for_a_snapshot() -> None:
    """An unpolled runtime must never retain more than the fixed diagnostic ring."""
    tracker = DetectedBeatTimingTracker()

    for index in range(40):
        tracker.record(
            DetectedBeatTiming(
                detected_beat_published_ns=index * 10,
                command_submitted_ns=index * 10 + 1,
            )
        )

    assert len(tracker._records) == 32
    assert [record["detected_beat_published_ns"] for record in tracker._records] == list(
        range(80, 400, 10)
    )
    snapshot = tracker.snapshot()
    assert snapshot["recorded"] == 32
    assert snapshot["dropped"] == 0
    assert snapshot["latest"]["detected_beat_published_ns"] == 390
