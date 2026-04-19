"""Trade form VMs — entry/exit/stop."""
from __future__ import annotations

from datetime import datetime

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_entry_form_vm_shape(seeded_db, monkeypatch):
    """Entry form VM populated with ticker, prefilled price/stop, suggested shares."""
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.trades import build_entry_form_vm, TradeEntryFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=None,
    )
    assert isinstance(vm, TradeEntryFormVM)
    assert vm.ticker == "AAPL"
    assert vm.entry_price == 180.95
    assert vm.initial_stop == 170.0  # from watchlist
    assert vm.watchlist_entry_target == 181.0
    assert vm.soft_warn_threshold == cfg.position_limits.soft_warn_open
    assert vm.hard_cap == cfg.position_limits.hard_cap_open
    # suggested_shares: depends on equity/risk/stop distance — just assert >= 0.
    assert vm.suggested_shares >= 0
