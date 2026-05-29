"""T-2.5 tests: _advance_status status machine (Step 2) + _step_pattern_observe
integration (Step 6). Fixtures imported from conftest_temporal."""
import pytest

from swing.pipeline.runner import _advance_status

# Shared temporal-log fixtures (plan section L.4).
from tests.pipeline.conftest_temporal import (  # noqa: F401
    _StubOhlcvCache,
    _build_bars,
    _cfg,
    _FakeLease,
    _plant_detection,
    _stub_window,
    tmp_db_v22,
)


class _Det:
    """Minimal detection stub carrying the anchors the status machine reads."""
    def __init__(self, pivot=10.0, invalidation=8.0):
        import json
        self.pattern_class = "vcp"
        self.data_asof_date = "2026-05-28"
        self.structural_anchors_json = json.dumps(
            {"evidence": {"pivot_price": pivot, "base_top_price": pivot,
                          "contractions": [{"low": invalidation}]}})


def _bar(high, low, close, open_=None):
    return {"open": open_ or close, "high": high, "low": low,
            "close": close, "volume": 1_000_000}


def test_pending_stays_pending_within_window():
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


def test_pending_to_triggered_open_on_pivot_breakout():
    status, ev = _advance_status(
        _Det(pivot=10.0), prev=None, bar=_bar(10.5, 9.8, 10.2),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev == "entry_fired"


def test_pending_to_invalidated_on_structural_break():
    status, ev = _advance_status(
        _Det(invalidation=8.0), prev=None, bar=_bar(8.2, 7.5, 7.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_pending_to_expired_at_window_threshold():
    # AT threshold (30) without trigger -> expired (>= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "time_exit"


def test_pending_below_window_threshold_not_expired():
    # Under threshold (29) -> still pending (distinguishes >= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=29, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


class _PrevOpen:
    status = "triggered_open"


def test_triggered_open_to_expired_at_horizon():
    # AT pending+post_trigger (90) -> horizon reached.
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=90, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "observation_horizon_reached"


def test_triggered_open_stays_open_within_horizon():
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=50, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev is None


# --- Same-bar conflict precedence (Codex chain #2 Major #1 + #3) ---

def test_same_bar_breakout_and_invalidation_resolves_to_invalidated():
    # high 10.5 >= pivot 10.0 (intraday breakout) AND close 7.5 < invalidation
    # 8.0 (confirmed shape break) -> INVALIDATION WINS (failed breakout).
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None,
        bar=_bar(10.5, 7.4, 7.5),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_breakout_at_max_pending_boundary_fires_not_expires():
    # high >= pivot exactly at sessions == max_pending -> trigger wins over expiry.
    status, ev = _advance_status(
        _Det(pivot=10.0), prev=None, bar=_bar(10.5, 9.8, 10.2),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev == "entry_fired"


def test_invalidation_at_max_pending_boundary_wins_over_expiry():
    status, ev = _advance_status(
        _Det(invalidation=8.0), prev=None, bar=_bar(8.2, 7.5, 7.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_non_triggering_bar_at_max_pending_expires():
    # neither breakout nor invalidation at the boundary -> expired.
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "time_exit"


def test_near_miss_breakout_stays_pending():
    # high 9.9 < pivot 10.0 -> NOT a breakout (distinguishes the >= predicate).
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None, bar=_bar(9.9, 9.0, 9.5),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


def test_terminal_prev_status_raises():
    # Defensive guard (Major #4): a terminal prev status must never reach here.
    class _PrevTerminal:
        status = "invalidated"
    with pytest.raises(ValueError, match="terminal prev status"):
        _advance_status(_Det(), prev=_PrevTerminal(), bar=_bar(9.0, 8.5, 8.8),
                        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
