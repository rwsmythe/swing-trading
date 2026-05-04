"""Journal stats — share-weighted R, win rate, expectancy, streak."""
from __future__ import annotations

import pytest

from swing.data.models import Exit, Trade
from swing.journal.stats import (
    HypothesisBucket, JournalStats, compute_hypothesis_breakdown, compute_stats,
    period_filter, _trade_closed_date,
)


def _trade(tid: int, ticker: str, entry: float = 100.0, stop: float = 95.0,
           shares: int = 10, status: str = "closed",
           state: str | None = None,
           hypothesis_label: str | None = None) -> Trade:
    # State derives from status default unless overridden so callers passing
    # only status="open" (open-trade exclusion test on line 128) still get the
    # right state mapping per Phase 7 plan §3 (open→entered, closed→closed).
    if state is None:
        state = "entered" if status == "open" else "closed"
    return Trade(
        id=tid, ticker=ticker, entry_date="2026-04-15", entry_price=entry,
        initial_shares=shares, initial_stop=stop, current_stop=stop,
        status=status, state=state, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        hypothesis_label=hypothesis_label,
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


# --- Hypothesis breakdown -----------------------------------------------------

def test_hypothesis_breakdown_empty_returns_empty_list():
    """No closed trades → no buckets (CLI suppresses the section entirely)."""
    out = compute_hypothesis_breakdown(trades=[], exits=[])
    assert out == []


def test_hypothesis_breakdown_no_label_only():
    """All trades unlabeled → single (no label) bucket. Open trades excluded
    (their P&L is unrealized; same closed-trades-only frame as compute_stats)."""
    trades = [
        _trade(1, "AAA"),
        _trade(2, "BBB"),
        _trade(3, "CCC", status="open", state="entered"),  # open — must NOT appear
    ]
    exits = [
        _exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0),  # +$100
        _exit(2, exit_date="2026-04-11", price=95.0,  shares=10, rps=5.0),  # -$50
    ]
    out = compute_hypothesis_breakdown(trades=trades, exits=exits)
    assert len(out) == 1
    b = out[0]
    assert b.label is None
    assert b.n_trades == 2
    assert b.total_pnl == pytest.approx(50.0)  # 100 - 50
    assert b.win_rate is None  # N < 3 suppresses


def test_hypothesis_breakdown_groups_and_orders_by_count_desc():
    """Labeled groups sorted by trade count DESC; (no label) always first when
    non-empty, regardless of count."""
    trades = [
        _trade(1, "T1", hypothesis_label="alpha"),
        _trade(2, "T2", hypothesis_label="alpha"),
        _trade(3, "T3", hypothesis_label="beta"),
        _trade(4, "T4", hypothesis_label="beta"),
        _trade(5, "T5", hypothesis_label="beta"),
        _trade(6, "T6"),  # (no label)
    ]
    exits = [
        _exit(i, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0)
        for i in range(1, 7)
    ]
    out = compute_hypothesis_breakdown(trades=trades, exits=exits)
    labels = [b.label for b in out]
    # (no label) first, then labeled in count-DESC order: beta(3) > alpha(2).
    assert labels == [None, "beta", "alpha"]


def test_hypothesis_breakdown_win_rate_when_3_or_more():
    """Win rate = fraction of trades with realized P&L > 0; only emitted for
    N >= 3 (small-sample noise suppression per brief §4.5)."""
    trades = [_trade(i, f"T{i}", hypothesis_label="alpha") for i in (1, 2, 3, 4)]
    exits = [
        _exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0),  # win
        _exit(2, exit_date="2026-04-11", price=110.0, shares=10, rps=5.0),  # win
        _exit(3, exit_date="2026-04-12", price=110.0, shares=10, rps=5.0),  # win
        _exit(4, exit_date="2026-04-13", price=95.0,  shares=10, rps=5.0),  # loss
    ]
    out = compute_hypothesis_breakdown(trades=trades, exits=exits)
    assert len(out) == 1
    b = out[0]
    assert b.label == "alpha"
    assert b.n_trades == 4
    assert b.win_rate == pytest.approx(0.75)


def test_hypothesis_breakdown_single_labeled_trade_no_win_rate():
    """N < 3 → win_rate is None; the CLI suppresses the win-rate column."""
    trades = [_trade(1, "T1", hypothesis_label="solo")]
    exits = [_exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0)]
    out = compute_hypothesis_breakdown(trades=trades, exits=exits)
    assert len(out) == 1
    assert out[0].label == "solo"
    assert out[0].n_trades == 1
    assert out[0].win_rate is None


def test_hypothesis_breakdown_zero_pnl_is_neither_win_nor_loss():
    """Win-rate definition: P&L > 0 (strict). A zero-P&L trade is neither.
    Pinned here so renames or rewrites don't drift the win/loss boundary."""
    trades = [_trade(i, f"T{i}", hypothesis_label="x") for i in (1, 2, 3)]
    exits = [
        _exit(1, exit_date="2026-04-10", price=110.0, shares=10, rps=5.0),  # win
        _exit(2, exit_date="2026-04-11", price=100.0, shares=10, rps=5.0),  # 0
        _exit(3, exit_date="2026-04-12", price=95.0,  shares=10, rps=5.0),  # loss
    ]
    out = compute_hypothesis_breakdown(trades=trades, exits=exits)
    assert out[0].n_trades == 3
    assert out[0].win_rate == pytest.approx(1.0 / 3.0)


def test_hypothesis_bucket_is_immutable():
    """Frozen dataclass — defensive against mid-render mutation by callers."""
    b = HypothesisBucket(label="x", n_trades=1, total_pnl=10.0, win_rate=None)
    with pytest.raises(Exception):
        b.n_trades = 99  # type: ignore[misc]
