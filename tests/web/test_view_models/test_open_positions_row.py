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


def test_build_open_positions_row_single_row(seeded_db, monkeypatch):
    """build_open_positions_row does one get_many + one list_exits_for_trade
    + one advisories compute; returns OpenPositionsRowVM."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=182.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.trade.ticker == "AAPL"
    assert vm.price_snapshot is not None
    assert vm.price_snapshot.price == 182.0
    assert vm.remaining_shares == 10  # no exits seeded
    assert isinstance(vm.advisories, tuple)


def test_build_open_positions_row_reduces_remaining_shares_for_prior_exits(seeded_db, monkeypatch):
    """After a prior partial exit, remaining_shares = initial - sum(exits.shares)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_trade_with_event, insert_exit_with_event, list_open_trades,
    )
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
            trade = list_open_trades(conn)[0]
            insert_exit_with_event(
                conn,
                Exit(id=None, trade_id=trade.id, exit_date="2026-04-17",
                     exit_price=185.0, shares=3, reason="partial",
                     realized_pnl=15.0, r_multiple=1.5, notes=None),
                event_ts="2026-04-17T10:00:00", rationale="locking in 1.5R partial",
            )
            trade = list_open_trades(conn)[0]  # refresh
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=188.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.remaining_shares == 7   # 10 - 3


def test_build_open_positions_row_plumbs_ohlcv_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4: build_open_positions_row receives ohlcv_cache and plumbs
    sma10/20/50 + previous_close into AdvisoryContext."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    from swing.web.view_models.open_positions_row import build_open_positions_row
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.data.models import Trade

    cfg, _ = test_cfg
    trade = Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        status="open", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = build_open_positions_row(
            trade=trade, cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache,
            executor=ex,
        )

    rules = {a.rule for a in vm.advisories}
    assert "exit_below_50ma" in rules
