"""Phase 14 SB4 Slice 4 Task 4.1: render_trade_window_thumbnail_svg.

Small candlestick thumbnail over the trade window:
  coverage      -> <svg bytes
  no-coverage   -> None
  no title      -> thumbnails are unlabeled (no new mathtext surface)
  @_serialized_render -> no deadlock under a held (reentrant) lock.

Reuses the Slice 0 fixtures (closed_single_leg_trade / its_fills /
old_closed_trade / planted_archive) defined in test_trade_charts_render.py;
they are re-declared here so this module is self-contained.
"""
from datetime import date

import pandas as pd
import pytest

import swing.web.charts as charts
import swing.web.trade_charts as tc
from swing.data.models import Fill, Trade


def _archive_for_trade():
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


def test_thumbnail_returns_svg(monkeypatch, cfg_fixture, closed_single_leg_trade,
                               its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    out = tc.render_trade_window_thumbnail_svg(
        trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None and b"<svg" in out


def test_thumbnail_none_on_no_coverage(monkeypatch, cfg_fixture, old_closed_trade,
                                       its_fills):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc.render_trade_window_thumbnail_svg(
        trade=old_closed_trade, fills=its_fills, cfg=cfg_fixture) is None


def test_thumbnail_no_deadlock_under_lock(monkeypatch, cfg_fixture,
        closed_single_leg_trade, its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    with charts._RENDER_LOCK:  # reentrant: render must complete, not block
        out = tc.render_trade_window_thumbnail_svg(
            trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None


def test_thumbnail_open_trade_uses_trailing_window(monkeypatch, cfg_fixture,
                                                   planted_archive):
    """Open trade (no reducing fill) -> exit_date None -> trailing window."""
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    open_trade = Trade(
        id=3, ticker="ABC", entry_date="2024-02-10", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None)
    entry_only = [Fill(fill_id=None, trade_id=3,
                       fill_datetime="2024-02-10T09:30:00", action="entry",
                       quantity=100.0, price=10.0)]
    assert tc._exit_date_for(open_trade, entry_only) is None
    out = tc.render_trade_window_thumbnail_svg(
        trade=open_trade, fills=entry_only, cfg=cfg_fixture)
    assert out is not None and b"<svg" in out
