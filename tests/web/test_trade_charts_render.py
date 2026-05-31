"""Phase 14 SB4 Slice 0 Task 0.3: render_trade_window_position_svg.

Coverage -> SVG bytes; no-coverage -> None; @_serialized_render no-deadlock
under a held lock; reopened-ticker correctness (render-direct serves each
trade's own window, no cache collision).
"""
from datetime import date

import pandas as pd
import pytest

import swing.web.charts as charts
import swing.web.trade_charts as tc
from swing.data.models import Fill, Trade


def _archive_for_trade():
    # Window for entry 2024-02-10 .. exit 2024-03-01 is roughly
    # [2024-01-11 .. 2024-03-11]; supply a wide deterministic frame.
    idx = pd.bdate_range(start="2024-01-01", periods=120)
    close = [100.0 + 0.5 * i for i in range(len(idx))]
    return pd.DataFrame(
        {"Open": [c - 0.5 for c in close], "High": [c + 0.8 for c in close],
         "Low": [c - 0.8 for c in close], "Close": close,
         "Volume": [1_000_000 + 10_000 * i for i in range(len(idx))]},
        index=idx)


@pytest.fixture
def closed_single_leg_trade() -> Trade:
    return Trade(
        id=1, ticker="ABC", entry_date="2024-02-10", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None)


@pytest.fixture
def its_fills() -> list[Fill]:
    return [
        Fill(fill_id=None, trade_id=1, fill_datetime="2024-02-10T09:30:00",
             action="entry", quantity=100.0, price=10.0),
        Fill(fill_id=None, trade_id=1, fill_datetime="2024-03-01T15:00:00",
             action="exit", quantity=100.0, price=12.0, reason="manual"),
    ]


@pytest.fixture
def old_closed_trade() -> Trade:
    # Predates the archive depth -> _trade_window_bars returns None.
    return Trade(
        id=2, ticker="OLD", entry_date="2010-01-04", entry_price=5.0,
        initial_shares=50, initial_stop=4.0, current_stop=4.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None)


@pytest.fixture
def planted_archive():
    def _fake(ticker, *, end_date, **k):
        df = _archive_for_trade()
        return df[df.index.date <= end_date]
    return _fake


def test_position_svg_returns_svg_bytes(monkeypatch, cfg_fixture,
                                        closed_single_leg_trade, its_fills,
                                        planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    out = tc.render_trade_window_position_svg(
        trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None and b"<svg" in out


def test_position_svg_none_on_no_coverage(monkeypatch, cfg_fixture,
                                          old_closed_trade, its_fills):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc.render_trade_window_position_svg(
        trade=old_closed_trade, fills=its_fills, cfg=cfg_fixture) is None


def test_position_svg_no_deadlock_under_held_lock(monkeypatch, cfg_fixture,
        closed_single_leg_trade, its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    with charts._RENDER_LOCK:  # reentrant: render must complete, not block
        out = tc.render_trade_window_position_svg(
            trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None


def test_position_svg_reopened_ticker_serves_each_window(
        monkeypatch, cfg_fixture, planted_archive):
    """Render-direct: two trades on the SAME ticker each render their own
    window (no cache collision -- the closed/reopened-position edge case)."""
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    first = Trade(
        id=10, ticker="ABC", entry_date="2024-02-10", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None)
    second = Trade(
        id=11, ticker="ABC", entry_date="2024-04-01", entry_price=20.0,
        initial_shares=50, initial_stop=18.0, current_stop=18.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None)
    fills_first = [
        Fill(fill_id=None, trade_id=10, fill_datetime="2024-02-10T09:30:00",
             action="entry", quantity=100.0, price=10.0),
        Fill(fill_id=None, trade_id=10, fill_datetime="2024-03-01T15:00:00",
             action="exit", quantity=100.0, price=12.0, reason="manual"),
    ]
    fills_second = [
        Fill(fill_id=None, trade_id=11, fill_datetime="2024-04-01T09:30:00",
             action="entry", quantity=50.0, price=20.0),
        Fill(fill_id=None, trade_id=11, fill_datetime="2024-05-01T15:00:00",
             action="exit", quantity=50.0, price=22.0, reason="manual"),
    ]
    out1 = tc.render_trade_window_position_svg(
        trade=first, fills=fills_first, cfg=cfg_fixture)
    out2 = tc.render_trade_window_position_svg(
        trade=second, fills=fills_second, cfg=cfg_fixture)
    assert out1 is not None and out2 is not None
    assert b"<svg" in out1 and b"<svg" in out2


def test_exit_date_for_returns_last_reducing_fill(its_fills):
    t = Trade(id=1, ticker="ABC", entry_date="2024-02-10", entry_price=10.0,
              initial_shares=100, initial_stop=9.0, current_stop=9.0,
              state="closed", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert tc._exit_date_for(t, its_fills) == date(2024, 3, 1)
    # entry-only -> None
    entry_only = [its_fills[0]]
    assert tc._exit_date_for(t, entry_only) is None
