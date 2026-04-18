"""Journal stats — share-weighted R, win rate, expectancy, streak."""
from __future__ import annotations

import pytest

from swing.data.models import Exit, Trade
from swing.journal.stats import (
    JournalStats, compute_stats, period_filter, _trade_closed_date,
)


def _trade(tid: int, ticker: str, entry: float = 100.0, stop: float = 95.0,
           shares: int = 10, status: str = "closed") -> Trade:
    return Trade(
        id=tid, ticker=ticker, entry_date="2026-04-15", entry_price=entry,
        initial_shares=shares, initial_stop=stop, current_stop=stop,
        status=status, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


def _exit(tid: int, *, exit_date: str, price: float, shares: int,
          rps: float, reason: str = "target") -> Exit:
    pnl = shares * (price - 100.0)
    r = (price - 100.0) / rps if rps > 0 else 0.0
    return Exit(id=None, trade_id=tid, exit_date=exit_date, exit_price=price,
                shares=shares, reason=reason, realized_pnl=pnl,
                r_multiple=r, notes=None)


def test_empty_returns_zeros():
    s = compute_stats(trades=[], exits=[], cash_movements=[])
    assert s.n_trades == 0
    assert s.win_rate == 0.0
    assert s.expectancy_r == 0.0
    assert s.current_streak == 0


def test_single_winner():
    t = _trade(1, "AAPL")
    e = _exit(1, exit_date="2026-04-20", price=110.0, shares=10, rps=5.0)
    s = compute_stats(trades=[t], exits=[e], cash_movements=[])
    assert s.n_trades == 1
    assert s.win_rate == 1.0
    assert s.avg_win_r == 2.0
    assert s.avg_loss_r == 0.0
    assert s.total_r == 2.0
    assert s.current_streak_kind == "W"


def test_share_weighted_r_for_partials():
    t = _trade(1, "AAPL", shares=10)
    e1 = _exit(1, exit_date="2026-04-18", price=105.0, shares=5, rps=5.0)
    e2 = _exit(1, exit_date="2026-04-22", price=115.0, shares=5, rps=5.0)
    s = compute_stats(trades=[t], exits=[e1, e2], cash_movements=[])
    assert s.n_trades == 1
    assert s.total_r == pytest.approx(2.0)


def test_loser_trade():
    t = _trade(1, "AAPL")
    e = _exit(1, exit_date="2026-04-20", price=95.0, shares=10, rps=5.0,
              reason="stop-hit")
    s = compute_stats(trades=[t], exits=[e], cash_movements=[])
    assert s.win_rate == 0.0
    assert s.avg_loss_r == -1.0
    assert s.current_streak_kind == "L"


def test_streak_walks_back():
    trades = [_trade(i, f"T{i}") for i in (1, 2, 3)]
    exits = [
        _exit(1, exit_date="2026-04-10", price=95.0, shares=10, rps=5.0),
        _exit(2, exit_date="2026-04-12", price=105.0, shares=10, rps=5.0),
        _exit(3, exit_date="2026-04-15", price=110.0, shares=10, rps=5.0),
    ]
    s = compute_stats(trades=trades, exits=exits, cash_movements=[])
    assert s.current_streak == 2
    assert s.current_streak_kind == "W"


def test_period_filter_week():
    trades = [_trade(1, "OLD"), _trade(2, "NEW")]
    exits = [
        _exit(1, exit_date="2026-03-01", price=110.0, shares=10, rps=5.0),
        _exit(2, exit_date="2026-04-12", price=110.0, shares=10, rps=5.0),
    ]
    today = "2026-04-15"
    week_trades = period_filter(trades, exits, period="week", today=today)
    assert {t.ticker for t in week_trades} == {"NEW"}


def test_expectancy_r():
    trades = [_trade(i, f"T{i}") for i in (1, 2, 3, 4)]
    exits = [
        _exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0),
        _exit(2, exit_date="2026-04-11", price=110.0, shares=10, rps=5.0),
        _exit(3, exit_date="2026-04-12", price=110.0, shares=10, rps=5.0),
        _exit(4, exit_date="2026-04-13", price=95.0,  shares=10, rps=5.0),
    ]
    s = compute_stats(trades=trades, exits=exits, cash_movements=[])
    assert s.expectancy_r == pytest.approx(1.25)
