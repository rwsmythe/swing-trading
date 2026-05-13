"""Phase 10 Sub-bundle A T-A.5 — rolling-N window helper tests."""
from __future__ import annotations

import math

import pytest

from swing.metrics.rolling import rolling_mean_series, rolling_window_samples


# ---------------------------------------------------------------------------
# rolling_window_samples
# ---------------------------------------------------------------------------

def test_rolling_window_basic():
    """Plan §D Task A.5 acceptance: samples=[1,2,3,4,5], window_size=3
    → growing-then-sliding windows."""
    windows = rolling_window_samples(
        samples=[1, 2, 3, 4, 5], window_size=3,
    )
    assert windows == [[1], [1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]]


def test_rolling_window_window_larger_than_samples():
    """When window_size > len(samples), no window ever fills."""
    windows = rolling_window_samples(
        samples=[1, 2], window_size=10,
    )
    assert windows == [[1], [1, 2]]


def test_rolling_window_empty_samples():
    assert rolling_window_samples(samples=[], window_size=3) == []


def test_rolling_window_step_param():
    """step=2 emits every other position only."""
    windows = rolling_window_samples(
        samples=[1, 2, 3, 4, 5], window_size=3, step=2,
    )
    assert windows == [[1], [1, 2, 3], [3, 4, 5]]


def test_rolling_window_rejects_invalid_window_size():
    with pytest.raises(ValueError, match="window_size must be > 0"):
        rolling_window_samples(samples=[1, 2, 3], window_size=0)


def test_rolling_window_rejects_invalid_step():
    with pytest.raises(ValueError, match="step must be > 0"):
        rolling_window_samples(samples=[1, 2, 3], window_size=3, step=0)


# ---------------------------------------------------------------------------
# rolling_mean_series
# ---------------------------------------------------------------------------

def test_rolling_mean_series_basic():
    """Plan §D Task A.5 acceptance: samples=[1,2,3,4,5], window_size=3
    → [(0,None),(1,None),(2,2.0),(3,3.0),(4,4.0)]."""
    series = rolling_mean_series(
        samples=[1.0, 2.0, 3.0, 4.0, 5.0], window_size=3,
    )
    assert series == [
        (0, None), (1, None), (2, 2.0), (3, 3.0), (4, 4.0),
    ]


def test_rolling_mean_empty():
    assert rolling_mean_series(samples=[], window_size=3) == []


def test_rolling_mean_window_larger_than_samples():
    """Plan §D Task A.5 acceptance: samples=[1,2], window_size=10
    → [(0,None),(1,None)] (effective_n always <3)."""
    series = rolling_mean_series(samples=[1.0, 2.0], window_size=10)
    assert series == [(0, None), (1, None)]


def test_rolling_mean_at_exactly_min_n_floor():
    """Window size 3 + samples [10,20,30] → (2, 20.0) at the last position
    (boundary of the min-n floor)."""
    series = rolling_mean_series(samples=[10.0, 20.0, 30.0], window_size=3)
    assert series == [(0, None), (1, None), (2, 20.0)]


def test_rolling_mean_window_size_2_renders_none_throughout():
    """When window_size=2, every window has at most 2 samples — below
    the min-n-for-mean floor of 3 — so the series is all-None.

    This is the discriminating case for the spec §5.4 R3 M2 decoupling:
    operational floor (3) is independent of the render-layer effective_n
    floor (5). A future caller asking for a window_size=2 rolling-mean
    gets None throughout (no noise-dominated 2-sample means surface)."""
    series = rolling_mean_series(samples=[1.0, 2.0, 3.0, 4.0, 5.0], window_size=2)
    assert all(v is None for (_, v) in series)


def test_rolling_mean_rejects_invalid_window_size():
    with pytest.raises(ValueError, match="window_size must be > 0"):
        rolling_mean_series(samples=[1.0, 2.0, 3.0], window_size=0)


def test_rolling_mean_values_correct_when_window_full():
    """Verify exact means when window slides past the start."""
    series = rolling_mean_series(
        samples=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0], window_size=3,
    )
    # i=0,1 → None; i=2 → mean(10,20,30)=20; i=3 → mean(20,30,40)=30;
    # i=4 → mean(30,40,50)=40; i=5 → mean(40,50,60)=50.
    expected = [(0, None), (1, None), (2, 20.0), (3, 30.0), (4, 40.0), (5, 50.0)]
    for (got_i, got_v), (exp_i, exp_v) in zip(series, expected, strict=True):
        assert got_i == exp_i
        if exp_v is None:
            assert got_v is None
        else:
            assert math.isclose(got_v, exp_v, abs_tol=1e-9)
