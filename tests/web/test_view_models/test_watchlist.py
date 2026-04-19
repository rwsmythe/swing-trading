"""WatchlistVM shape + expand helper."""
from __future__ import annotations

from unittest.mock import MagicMock

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_watchlist_shape(seeded_db, monkeypatch):
    from swing.web.view_models.watchlist import WatchlistVM, build_watchlist
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

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
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.5, asof=datetime.now(),
                                   is_stale=False, source="live")
        })
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_watchlist(cfg=cfg, cache=cache, executor=None)
    assert isinstance(vm, WatchlistVM)
    assert len(vm.rows) == 1
    assert vm.rows[0].ticker == "AAPL"
