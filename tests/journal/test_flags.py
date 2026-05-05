"""Behavioral flags: caution-market, losers-held-too-long, cutting-winners-short."""
from __future__ import annotations

from dataclasses import dataclass

from swing.data.models import Trade, WeatherRun
from swing.journal.flags import compute_flags, BehavioralFlag


# C.13: Local Exit-shape adapter — mirrors the in-prod per-module _ExitShape
# pattern (C.1/C.9/C.10/C.11/C.12). flags.py consumes ExitLike duck-typed:
# (.trade_id, .exit_date, .shares, .r_multiple, .realized_pnl).
@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _trade(tid: int, ticker: str, entry_date: str, exit_date: str,
           pnl: float = 0.0, r: float = 0.0,
           state: str = "closed") -> tuple[Trade, _ExitShape]:
    t = Trade(id=tid, ticker=ticker, entry_date=entry_date,
              entry_price=100.0, initial_shares=10, initial_stop=95.0,
              current_stop=95.0, state=state,
              watchlist_entry_target=None, watchlist_initial_stop=None, notes=None)
    e = _ExitShape(
        trade_id=tid, exit_date=exit_date, exit_price=100.0 + pnl/10,
        shares=10, reason="target", realized_pnl=pnl, r_multiple=r,
    )
    return t, e


def _wr(date: str, status: str) -> WeatherRun:
    return WeatherRun(id=None, run_ts=f"{date}T21:49:00", asof_date=date,
                      ticker="QQQ", status=status, close=480.0,
                      sma10=475.0, sma20=470.0, sma50=460.0,
                      slope20_5bar=0.5, slope10_5bar=0.7, rationale="r")


def test_no_flags_when_clean():
    flags = compute_flags(trades=[], exits=[], weather_runs=[])
    assert flags == []


def test_caution_market_entries_flagged():
    t1, e1 = _trade(1, "AAPL", "2026-04-10", "2026-04-15", pnl=20, r=2)
    t2, e2 = _trade(2, "MSFT", "2026-04-11", "2026-04-16", pnl=-10, r=-1)
    weather = [
        _wr("2026-04-10", "Caution"),
        _wr("2026-04-11", "Bearish"),
    ]
    flags = compute_flags(trades=[t1, t2], exits=[e1, e2], weather_runs=weather)
    assert any(f.code == "caution_market_entries" for f in flags)


def test_losers_held_longer_than_winners_flagged():
    winners = []
    losers = []
    for i in range(3):
        winners.append(_trade(100 + i, f"W{i}", "2026-04-10",
                              "2026-04-13", pnl=20, r=2))
    for i in range(3):
        losers.append(_trade(200 + i, f"L{i}", "2026-04-01",
                             "2026-04-11", pnl=-10, r=-1))
    trades = [t for t, _ in winners + losers]
    exits = [e for _, e in winners + losers]
    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert any(f.code == "losers_held_too_long" for f in flags)


def test_cutting_winners_short_flagged():
    cases = []
    for i in range(4):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15", pnl=5, r=0.5))
    for i in range(4, 6):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15", pnl=20, r=2.0))
    trades = [t for t, _ in cases]
    exits = [e for _, e in cases]
    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert any(f.code == "cutting_winners_short" for f in flags)


def test_caution_market_entries_includes_reviewed_trades():
    """B.9 discriminator: a 'reviewed' (post-review-completed) trade still
    contributes to the caution-market flag. Pre-fix (state == 'closed' only)
    a reviewed Caution-day entry was silently dropped, so the flag
    suppressed when fewer than 2 closed-state entries remained.
    """
    # Two entries on Caution/Bearish days — one closed, one reviewed.
    t1, e1 = _trade(1, "AAPL", "2026-04-10", "2026-04-15", pnl=20, r=2,
                    state="closed")
    t2, e2 = _trade(2, "MSFT", "2026-04-11", "2026-04-16", pnl=-10, r=-1,
                    state="reviewed")
    weather = [
        _wr("2026-04-10", "Caution"),
        _wr("2026-04-11", "Bearish"),
    ]
    flags = compute_flags(trades=[t1, t2], exits=[e1, e2], weather_runs=weather)
    flag = next((f for f in flags if f.code == "caution_market_entries"), None)
    assert flag is not None, (
        "reviewed-state trades must count toward caution-market flag; "
        "pre-fix the predicate dropped them and the flag suppressed below "
        "the >=2 threshold."
    )


def test_cutting_winners_short_includes_reviewed_winners():
    """B.9 discriminator: 'reviewed' winners count toward the
    cutting-winners-short calculation. Pre-fix they were dropped from the
    `winners` list entirely.
    """
    cases = []
    for i in range(3):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15",
                            pnl=5, r=0.5, state="closed"))
    # Add reviewed winners — they MUST count toward the winners pool. With
    # 4 winners and >=50% below +1R, the flag fires.
    for i in range(3, 4):
        cases.append(_trade(i, f"X{i}", "2026-04-10", "2026-04-15",
                            pnl=5, r=0.5, state="reviewed"))
    trades = [t for t, _ in cases]
    exits = [e for _, e in cases]
    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert any(f.code == "cutting_winners_short" for f in flags), (
        "reviewed winners must count toward cutting-winners-short; pre-fix "
        "they were dropped, taking the winner pool below the n>=3 minimum "
        "or skewing the below-1R fraction."
    )


def test_losers_held_too_long_no_division_by_zero_when_winners_all_same_day():
    """All winners closed same-day (0 hold-days) -> avg_w == 0 -> guard returns None.

    Pre-fix: compute_flags raised ZeroDivisionError at the detail-string format
    line (avg_l/avg_w with avg_w=0). Surfaced in production 2026-04-29 when
    operator's smoke-test trades were entered AND closed same-day at profit.

    Discriminating: setup MUST include >=1 winner with 0 hold-days AND >=1
    loser with >0 hold-days. If winners had non-zero hold-days OR no losers
    existed, the bug wouldn't reproduce. Without the guard fix, this test
    raises ZeroDivisionError; with the guard, it returns flags WITHOUT a
    losers_held_too_long flag (the ratio is undefined when avg_w=0).
    """
    winners = [
        _trade(1, "WIN1", "2026-04-29", "2026-04-29", pnl=20, r=2.0),
        _trade(2, "WIN2", "2026-04-29", "2026-04-29", pnl=15, r=1.5),
    ]
    loser = _trade(3, "LOSE", "2026-04-25", "2026-04-29", pnl=-10, r=-1.0)
    trades = [t for t, _ in winners + [loser]]
    exits = [e for _, e in winners + [loser]]

    flags = compute_flags(trades=trades, exits=exits, weather_runs=[])
    assert all(f.code != "losers_held_too_long" for f in flags), (
        "When all winners are same-day (avg_w==0), the losers-held flag "
        "should NOT be emitted because the loser-vs-winner ratio is undefined."
    )
