"""Behavioral flags: caution-market, losers-held-too-long, cutting-winners-short."""
from __future__ import annotations

from swing.data.models import Exit, Trade, WeatherRun
from swing.journal.flags import compute_flags, BehavioralFlag


def _trade(tid: int, ticker: str, entry_date: str, exit_date: str,
           pnl: float = 0.0, r: float = 0.0) -> tuple[Trade, Exit]:
    t = Trade(id=tid, ticker=ticker, entry_date=entry_date,
              entry_price=100.0, initial_shares=10, initial_stop=95.0,
              current_stop=95.0, status="closed", state="closed",
              watchlist_entry_target=None, watchlist_initial_stop=None, notes=None)
    e = Exit(id=tid, trade_id=tid, exit_date=exit_date, exit_price=100.0 + pnl/10,
             shares=10, reason="target", realized_pnl=pnl, r_multiple=r, notes=None)
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
