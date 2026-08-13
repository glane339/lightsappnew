from __future__ import annotations

import pytest

from server.latency import LatencyTracker, percentile_ns


def test_empty_tracker_reports_zeroes() -> None:
    snapshot = LatencyTracker().snapshot()

    assert snapshot == {"count": 0, "p50_us": 0, "p95_us": 0, "p99_us": 0, "max_us": 0}


def test_percentiles_are_reported_in_microseconds() -> None:
    tracker = LatencyTracker(capacity=16)
    for ms in range(1, 11):
        tracker.record(ms * 1_000_000)

    snapshot = tracker.snapshot()

    assert snapshot["count"] == 10
    assert snapshot["max_us"] == 10_000
    assert 5_000 <= snapshot["p50_us"] <= 6_000
    assert snapshot["p99_us"] >= snapshot["p50_us"]


def test_the_ring_keeps_only_the_most_recent_samples() -> None:
    tracker = LatencyTracker(capacity=4)
    for value in (100, 200, 300, 400, 500, 600):
        tracker.record(value * 1000)

    snapshot = tracker.snapshot()

    # The first two samples were overwritten, so the max is from the surviving window.
    assert snapshot["count"] == 4
    assert snapshot["max_us"] == 600


def test_clear_drops_the_window() -> None:
    tracker = LatencyTracker(capacity=8)
    tracker.record(1_000_000)

    tracker.clear()

    assert tracker.snapshot()["count"] == 0


def test_summary_is_the_two_numbers_the_page_shows() -> None:
    tracker = LatencyTracker()
    tracker.record(2_000_000)

    assert set(tracker.summary()) == {"count", "p50_us", "p99_us"}


def test_percentile_of_a_single_sample_is_that_sample() -> None:
    assert percentile_ns([42], 0.99) == 42


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        LatencyTracker(capacity=0)
