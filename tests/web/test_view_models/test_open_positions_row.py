"""OpenPositionsRowVM assembly — pure helper, no I/O."""
from __future__ import annotations

from datetime import datetime

from swing.data.models import Trade
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


def _mk_trade(id_=42, ticker="AAPL", stop=170.0) -> Trade:
    return Trade(
        id=id_, ticker=ticker, entry_date="2026-04-15",
        entry_price=180.0, initial_shares=5, initial_stop=170.0,
        current_stop=stop, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )


def test_vm_pure_assembly_with_snapshot_and_advisories():
    from swing.web.view_models.open_positions_row import (
        _open_positions_row_vm, OpenPositionsRowVM,
    )
    trade = _mk_trade()
    snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    advs = (AdvisorySuggestionVM(rule="breakeven", message="move stop to entry"),)
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=snap, remaining_shares=5, advisories=advs,
    )
    assert isinstance(vm, OpenPositionsRowVM)
    assert vm.trade is trade
    assert vm.price_snapshot is snap
    assert vm.remaining_shares == 5
    assert vm.advisories == advs


def test_vm_pure_assembly_with_no_snapshot_and_no_advisories():
    from swing.web.view_models.open_positions_row import _open_positions_row_vm
    trade = _mk_trade()
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=None, remaining_shares=3, advisories=(),
    )
    assert vm.price_snapshot is None
    assert vm.advisories == ()
    assert vm.remaining_shares == 3
