"""Equity / R / shares-remaining pure functions (legacy parity)."""
from __future__ import annotations

import pytest

from swing.data.models import CashMovement, Exit, Trade
from swing.trades.equity import (
    current_equity, sizing_equity, shares_remaining,
    risk_per_share, r_so_far, net_cash_movements,
)


def _trade(initial_shares: int = 10) -> Trade:
    return Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=initial_shares, initial_stop=170.0, current_stop=170.0,
        status="open", watchlist_entry_target=181.0,
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
              status="open", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert risk_per_share(t) == 0.0


def test_r_so_far_at_entry():
    assert r_so_far(_trade(), current_price=180.0) == 0.0


def test_r_so_far_at_2r():
    assert r_so_far(_trade(), current_price=200.0) == 2.0


def test_r_so_far_zero_rps_returns_zero():
    t = Trade(id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=180.0, current_stop=180.0,
              status="open", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert r_so_far(t, current_price=200.0) == 0.0


def test_net_cash_movements_unknown_kind_ignored():
    cm = [
        CashMovement(id=1, date="2026-04-01", kind="deposit", amount=100.0, ref=None, note=None),
        CashMovement(id=2, date="2026-04-02", kind="weird", amount=50.0, ref=None, note=None),
    ]
    assert net_cash_movements(cm) == 100.0
