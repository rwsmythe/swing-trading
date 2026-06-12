"""Equity / R / shares-remaining pure functions (legacy parity)."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from swing.data.models import CashMovement, Trade
from swing.trades.equity import (
    current_equity,
    r_so_far,
    risk_per_share,
    shares_remaining,
    sizing_equity,
    total_current_risk,
)


# C.13: Local Exit-shape adapter — the equity helpers consume ExitLike duck-
# typed (.trade_id, .shares, .realized_pnl). Mirrors the in-prod _ExitShape
# pattern (C.10) without depending on the soon-to-be-removed shim.
@dataclass(frozen=True)
class Exit:  # noqa: N801 — name preserved for readability of test bodies
    id: int | None
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None
    notes: str | None


def _trade(initial_shares: int = 10) -> Trade:
    return Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=initial_shares, initial_stop=170.0, current_stop=170.0,
        state="entered", watchlist_entry_target=181.0,
        watchlist_initial_stop=170.0, notes=None,
    )


def test_current_equity_starting_only():
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=[]) == 1000.0


def test_current_equity_includes_realized():
    exits = [Exit(id=1, trade_id=1, exit_date="2026-04-20", exit_price=190.0,
                  shares=5, reason="partial", realized_pnl=50.0, r_multiple=0.5, notes=None)]
    assert current_equity(starting_equity=1000.0, exits=exits, cash_movements=[]) == 1050.0


def test_current_equity_includes_cash_movements():
    cm = [
        CashMovement(id=1, date="2026-04-01", kind="deposit", amount=200.0, ref=None, note=None),
        CashMovement(id=2, date="2026-04-15", kind="withdraw", amount=50.0, ref=None, note=None),
    ]
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=cm) == 1150.0


def test_current_equity_excludes_unrealized():
    assert current_equity(starting_equity=1000.0, exits=[], cash_movements=[]) == 1000.0


def test_sizing_equity_uses_floor_when_below():
    assert sizing_equity(real_equity=1200.0, floor=7500.0) == 7500.0


def test_sizing_equity_uses_real_when_above():
    assert sizing_equity(real_equity=10_000.0, floor=7500.0) == 10_000.0


def test_sizing_equity_no_floor():
    assert sizing_equity(real_equity=1200.0, floor=0.0) == 1200.0


def test_shares_remaining():
    exits = [Exit(id=1, trade_id=1, exit_date="2026-04-18", exit_price=185.0,
                  shares=3, reason="trim", realized_pnl=15.0, r_multiple=0.3, notes=None)]
    t = _trade(initial_shares=10)
    assert shares_remaining(t, exits) == 7


def test_risk_per_share():
    t = _trade()
    assert risk_per_share(t) == 10.0


def test_risk_per_share_zero_when_stop_above_entry():
    t = Trade(id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=200.0, current_stop=200.0,
              state="entered", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert risk_per_share(t) == 0.0


def test_r_so_far_at_entry():
    assert r_so_far(_trade(), current_price=180.0) == 0.0


def test_r_so_far_at_2r():
    assert r_so_far(_trade(), current_price=200.0) == 2.0


def test_r_so_far_zero_rps_returns_zero():
    t = Trade(id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=180.0, current_stop=180.0,
              state="entered", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert r_so_far(t, current_price=200.0) == 0.0


# NOTE (Arc 4b Task 2/4): the former test_net_cash_movements_unknown_kind_ignored
# was removed. CashMovement.__post_init__ now rejects unknown kinds at
# construction (migration 0029 widened the CHECK to 5 kinds), and
# net_cash_movements RAISES on an unknown kind (the silent-ignore drift hazard
# is gone). The replacement is test_net_cash_movements_unknown_kind_raises in
# tests/trades/test_equity_five_kind.py (Task 4).


# -----------------------------------------------------------------------------
# total_current_risk — Tranche B-ops spec §2 (Bug 6 open-risk tile).
# -----------------------------------------------------------------------------

def _open_trade(
    trade_id: int, ticker: str, *, entry: float, stop: float,
    initial_shares: int = 10,
) -> Trade:
    return Trade(
        id=trade_id, ticker=ticker, entry_date="2026-04-15",
        entry_price=entry, initial_shares=initial_shares, initial_stop=stop,
        current_stop=stop, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )


def test_total_current_risk_empty_book():
    dollars, contributing, all_above_be = total_current_risk([], [])
    assert dollars == 0.0
    assert contributing == 0
    assert all_above_be is False


def test_total_current_risk_single_position_below_entry():
    # entry 100, stop 95, 10 sh → $50 at risk.
    trade = _open_trade(1, "AAPL", entry=100.0, stop=95.0, initial_shares=10)
    dollars, contributing, all_above_be = total_current_risk([trade], [])
    assert dollars == pytest.approx(50.0)
    assert contributing == 1
    assert all_above_be is False


def test_total_current_risk_stop_at_entry_contributes_zero():
    # Stop exactly at entry → locked-in flat → $0 (not negative).
    trade = _open_trade(1, "AAPL", entry=100.0, stop=100.0, initial_shares=10)
    dollars, contributing, all_above_be = total_current_risk([trade], [])
    assert dollars == 0.0
    assert contributing == 0
    assert all_above_be is True


def test_total_current_risk_stop_above_entry_contributes_zero():
    # Trailed past breakeven → locked-in profit → $0, not negative.
    trade = _open_trade(1, "AAPL", entry=100.0, stop=110.0, initial_shares=10)
    dollars, contributing, all_above_be = total_current_risk([trade], [])
    assert dollars == 0.0
    assert contributing == 0
    assert all_above_be is True


def test_total_current_risk_respects_partial_exits():
    # entry 100, stop 90, 10 sh originally, partial exit of 6 → 4 sh remaining × $10 = $40.
    trade = _open_trade(1, "AAPL", entry=100.0, stop=90.0, initial_shares=10)
    exits = [
        Exit(
            id=1, trade_id=1, exit_date="2026-04-20", exit_price=108.0,
            shares=6, reason="partial", realized_pnl=48.0, r_multiple=0.8, notes=None,
        )
    ]
    dollars, contributing, all_above_be = total_current_risk([trade], exits)
    assert dollars == pytest.approx(40.0)
    assert contributing == 1
    assert all_above_be is False


def test_total_current_risk_sums_multiple_positions():
    # A: entry 100, stop 95, 10 sh → $50 at risk.
    # B: entry 50, stop 48, 20 sh → $40 at risk.
    # C: entry 200, stop 210 (above entry) → $0.
    trades = [
        _open_trade(1, "AAA", entry=100.0, stop=95.0, initial_shares=10),
        _open_trade(2, "BBB", entry=50.0, stop=48.0, initial_shares=20),
        _open_trade(3, "CCC", entry=200.0, stop=210.0, initial_shares=5),
    ]
    dollars, contributing, all_above_be = total_current_risk(trades, [])
    assert dollars == pytest.approx(90.0)
    assert contributing == 2
    assert all_above_be is False


def test_total_current_risk_all_above_breakeven_flag_set_only_when_nonempty():
    # Two trades, both stops trailed past entry → $0 total, all_above_be True.
    trades = [
        _open_trade(1, "AAA", entry=100.0, stop=102.0, initial_shares=10),
        _open_trade(2, "BBB", entry=50.0, stop=55.0, initial_shares=20),
    ]
    dollars, contributing, all_above_be = total_current_risk(trades, [])
    assert dollars == 0.0
    assert contributing == 0
    assert all_above_be is True
