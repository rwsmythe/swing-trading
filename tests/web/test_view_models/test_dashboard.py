"""build_dashboard produces a correctly-shaped VM from seeded state."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from swing.data.db import connect
from swing.data.repos.trades import insert_trade_with_event
from swing.data.models import Trade


def _seed_for_dashboard(cfg) -> None:
    """Seed one pipeline run, one evaluation run, one open trade, one weather, one watchlist row."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Weather
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES (?, ?, 'SPY', 'Bullish', 450.0, 'ok')""",
                ("2026-04-17T21:49:00", "2026-04-17"),
            )
            # Evaluation + candidate
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 2, 1, 1, 0, 0, 0, 'v1', 'deadbeef')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot, initial_stop, rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id,),
            )
            # Daily recommendation for today's action session
            conn.execute(
                """INSERT INTO daily_recommendations
                   (evaluation_run_id, data_asof_date, action_session_date,
                    ticker, recommendation, action_text)
                   VALUES (?, '2026-04-17', '2026-04-20', 'AAPL', 'today_decision',
                           'Buy-stop limit $181.00 · 5 sh · $55 risk')""",
                (eval_id,),
            )
            # Open trade
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="AAPL", entry_date="2026-04-15",
                    entry_price=180.0, initial_shares=5, initial_stop=170.0,
                    current_stop=170.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
            # Pipeline run
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 'done-token')""",
            )
    finally:
        conn.close()


def test_build_dashboard_shape(seeded_db, monkeypatch):
    from swing.web.view_models.dashboard import DashboardVM, build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert isinstance(vm, DashboardVM)
    assert vm.session_date != ""
    assert len(vm.open_trades) == 1
    assert vm.open_trades[0].ticker == "AAPL"
    assert "AAPL" in vm.open_trade_last_prices
    assert vm.open_trade_last_prices["AAPL"].price == 182.0
    assert 1 in vm.open_trade_advisories   # keyed by trade_id
    assert vm.price_source_degraded is False


def _seed_open_trade_direct(cfg, *, ticker: str, entry_price: float, shares: int) -> int:
    """Helper: insert an open trade via the repo, returning its id. Avoids
    coupling this test to any specific CLI command name."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=entry_price, initial_shares=shares,
                initial_stop=entry_price * 0.95, current_stop=entry_price * 0.95,
                status="open", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            return insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()


def test_build_dashboard_plumbs_ohlcv_bundle_into_advisory_context(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4: when ohlcv_cache returns a bundle with SMAs + previous_close,
    those values must appear in the AdvisoryContext inputs for each open trade."""
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.view_models import dashboard as dm
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    # Patch the ohlcv_cache to return a canned bundle.
    # NB: monkeypatching a CLASS METHOD — the first arg is `self`, so the
    # fake MUST accept it (Codex R1 Major 4 correction).
    def fake_bundles(self, tickers, *, deadline_seconds, executor):
        return {t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                                previous_close=190.0, fetched_at=0.0)
                for t in tickers}

    monkeypatch.setattr(OhlcvCache, "get_many_bundles", fake_bundles)
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    # Patch PriceCache.get_many to return a canned live price.
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = dm.build_dashboard(
            cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache, executor=ex,
        )

    # The open-positions row for AAPL should show SMA50 exit advisory
    # (previous_close 190 < sma50 195).
    assert len(vm.open_trades) == 1
    advisories = vm.open_trade_advisories[vm.open_trades[0].id]
    rules = {a.rule for a in advisories}
    assert "exit_below_50ma" in rules
    assert vm.ohlcv_source_degraded is False


def test_build_dashboard_reflects_ohlcv_degraded_flag(test_cfg, seeded_db, monkeypatch):
    """Spec §3.4: DashboardVM.ohlcv_source_degraded is True when the cache is."""
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.view_models import dashboard as dm
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache

    cfg, _ = test_cfg

    monkeypatch.setattr(OhlcvCache, "get_many_bundles",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: True)
    monkeypatch.setattr(PriceCache, "get_many",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = dm.build_dashboard(
            cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache, executor=ex,
        )
    assert vm.ohlcv_source_degraded is True
