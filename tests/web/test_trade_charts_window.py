"""Phase 14 SB4 Slice 0 Task 0.2: _trade_window_bars trade-window archive slice.

Covers: lower-bound slice + entry-coverage; archive-predates-entry -> None
(#29 entry-must-be-visible); F6 empty -> None.
"""
from datetime import date

import pandas as pd

import swing.web.trade_charts as tc


def _archive(idx_dates):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in idx_dates])
    return pd.DataFrame(
        {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 100},
        index=idx)


def test_window_slices_lower_bound_and_covers_entry(monkeypatch, cfg_fixture):
    days = pd.date_range("2026-01-01", "2026-03-31", freq="D")

    # read_or_fetch_archive returns rows <= end_date (production semantics);
    # the helper relies on that upper-bound slice and only computes the lower
    # bound locally.
    def _fake(ticker, *, end_date, **k):
        df = _archive(days)
        return df[df.index.date <= end_date]

    monkeypatch.setattr(tc, "read_or_fetch_archive", _fake)
    out = tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture)
    assert out is not None
    assert out.index.min().date() <= date(2026, 2, 1)   # entry covered
    assert out.index.max().date() <= date(2026, 3, 2)   # exit + 10d
    # lower-bound slice computed locally: window_start = entry - 30d
    assert out.index.min().date() >= date(2026, 1, 2)


def test_window_none_when_archive_predates_entry(monkeypatch, cfg_fixture):
    days = pd.date_range("2026-02-15", "2026-03-31", freq="D")  # starts after entry
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: _archive(days))
    assert tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture) is None


def test_window_none_on_empty_archive(monkeypatch, cfg_fixture):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture) is None
