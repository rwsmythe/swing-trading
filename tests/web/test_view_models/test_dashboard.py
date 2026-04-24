"""build_dashboard produces a correctly-shaped VM from seeded state."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
                           'Buy-stop $181.00 · 5 sh · $55 risk')""",
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


def test_build_dashboard_skips_ohlcv_fetch_when_no_open_trades(
    seeded_db, monkeypatch,
):
    """OHLCV advisories only apply to open trades. When there are zero open
    trades, the dashboard MUST NOT call `ohlcv_cache.get_many_bundles` —
    otherwise yfinance is burned on watchlist tickers that never consume the
    SMA data, and the breaker trips on first load."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.ohlcv_cache import OhlcvCache
    from datetime import datetime

    cfg, _ = seeded_db
    # Don't seed open trades — just weather + watchlist so the dashboard
    # has something to render.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES (?, ?, 'SPY', 'Bullish', 450.0, 'ok')""",
                ("2026-04-17T21:49:00", "2026-04-17"),
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    call_count = {"n": 0}
    def tracking(self, tickers, *, deadline_seconds, executor):
        call_count["n"] += 1
        return {}
    monkeypatch.setattr(OhlcvCache, "get_many_bundles", tracking)
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    ohlcv_cache = OhlcvCache(cfg)
    build_dashboard(cfg=cfg, cache=cache, executor=None, ohlcv_cache=ohlcv_cache)

    assert call_count["n"] == 0, (
        "OHLCV fetch should be skipped when there are no open trades"
    )


def test_build_dashboard_ohlcv_fetch_scoped_to_open_trades_only(
    seeded_db, monkeypatch,
):
    """With open trades AND watchlist rows, the OHLCV fetch must include
    ONLY the open-trade tickers. Watchlist tickers don't consume SMA data."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.ohlcv_cache import OhlcvCache
    from datetime import datetime
    from swing.data.db import connect

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)  # AAPL open trade + weather + evaluation

    # Add watchlist rows for two OTHER tickers.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for ticker in ("MSFT", "GOOG"):
                conn.execute(
                    """INSERT INTO watchlist
                       (ticker, added_date, last_qualified_date, status,
                        qualification_count, not_qualified_streak,
                        last_data_asof_date)
                       VALUES (?, '2026-04-15', '2026-04-17', 'watch', 1, 0,
                               '2026-04-17')""",
                    (ticker,),
                )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    fetched_tickers: list[str] = []
    def tracking(self, tickers, *, deadline_seconds, executor):
        fetched_tickers.extend(tickers)
        return {}
    monkeypatch.setattr(OhlcvCache, "get_many_bundles", tracking)
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    ohlcv_cache = OhlcvCache(cfg)
    build_dashboard(cfg=cfg, cache=cache, executor=None, ohlcv_cache=ohlcv_cache)

    assert set(fetched_tickers) == {"AAPL"}, (
        f"OHLCV fetch should be scoped to open trades only; "
        f"got {fetched_tickers}"
    )


def test_build_dashboard_shows_weather_when_asof_precedes_action_session(
    seeded_db, monkeypatch,
):
    """Regression: weather is stored keyed by data_asof_date (e.g. Fri 4/17)
    but dashboard prepares the action_session (e.g. Mon 4/20). The prior
    implementation queried weather by action_session, silently failed, and
    rendered STALE. The fix is to query the latest weather for the ticker
    regardless of asof date (the pipeline is the source of truth for what's
    latest — we don't need to second-guess the date mapping here).
    """
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)   # seeds weather asof='2026-04-17' status='Bullish'

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    # Dashboard's action_session is today-forward; seeded weather asof_date
    # is 2026-04-17. Weather status MUST be "Bullish" from the seeded row,
    # NOT "STALE".
    assert vm.status_strip.weather_status == "Bullish", (
        f"weather regressed to STALE — dashboard failed to find the latest "
        f"weather record. got {vm.status_strip.weather_status!r}"
    )


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


def test_last_pipeline_ts_not_masked_by_inflight_run(seeded_db, monkeypatch):
    """Regression: when a new pipeline run is mid-flight (state='running',
    finished_ts IS NULL), the Status-strip "Last pipeline" tile must continue
    to show the most recent COMPLETED run's finished_ts — not "never".

    Previous implementation ordered by started_ts DESC LIMIT 1, which picked
    up the in-flight row and surfaced its NULL finished_ts, masking the last
    known-good completion and rendering "never" on the dashboard while a new
    run executed.
    """
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)  # seeds one complete run finished at 21:55

    # Insert an in-flight run with a LATER started_ts than the complete one.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    lease_heartbeat_ts, last_step_progress_ts, current_step)
                   VALUES ('2026-04-17T22:00:00', NULL, 'manual',
                           '2026-04-17', '2026-04-20', 'running', 'inflight-tok',
                           '2026-04-17T22:00:05', '2026-04-17T22:00:05', 'evaluate')"""
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    assert vm.status_strip.last_pipeline_ts == "2026-04-17T21:55:00", (
        f"last_pipeline_ts regressed to {vm.status_strip.last_pipeline_ts!r} "
        f"— the in-flight run's NULL finished_ts masked the prior complete run"
    )
    assert vm.status_strip.last_pipeline_state == "running", (
        f"last_pipeline_state should reflect the most-recent-started run's "
        f"state (so operators can see a run is in progress); got "
        f"{vm.status_strip.last_pipeline_state!r}"
    )


# -----------------------------------------------------------------------------
# Open-risk tile — Tranche B-ops spec §2 (Bug 6).
# -----------------------------------------------------------------------------

def test_build_dashboard_status_strip_has_open_risk_fields(seeded_db, monkeypatch):
    """Seeded AAPL open position: entry 180, stop 170, 5 shares → $50 at risk.
    Equity = starting_equity 1200 + 0 realized + 0 cash = $1200.
    open_risk_pct = 50/1200 ≈ 0.04167."""
    from swing.web.view_models.dashboard import build_dashboard
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

    assert vm.status_strip.open_risk_dollars == pytest.approx(50.0)
    assert vm.status_strip.open_risk_pct == pytest.approx(50.0 / 1200.0, rel=1e-6)
    assert vm.status_strip.open_risk_position_count == 1
    assert vm.status_strip.open_risk_all_above_breakeven is False


def test_build_dashboard_status_strip_open_risk_empty_book(seeded_db, monkeypatch):
    """No open trades → $0 / None pct / 0 positions / all_above_be False."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    # Seed weather only; no open trades.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES (?, ?, 'SPY', 'Bullish', 450.0, 'ok')""",
                ("2026-04-17T21:49:00", "2026-04-17"),
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    assert vm.status_strip.open_risk_dollars == 0.0
    # Equity > 0 → pct == 0.0 (not None). None is reserved for equity <= 0.
    assert vm.status_strip.open_risk_pct == 0.0
    assert vm.status_strip.open_risk_position_count == 0
    assert vm.status_strip.open_risk_all_above_breakeven is False


def test_build_dashboard_status_strip_open_risk_pct_none_when_equity_nonpositive(
    seeded_db, monkeypatch,
):
    """Equity ≤ 0 (large drawdown) → percent reads as None so template shows '—'."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)

    # Withdraw more than starting_equity so current_equity goes ≤ 0.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO cash_movements (date, kind, amount)
                   VALUES ('2026-04-16', 'withdraw', 1500.0)""",
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    assert vm.status_strip.open_risk_pct is None
    # Dollars still computed — operator still sees the absolute exposure.
    assert vm.status_strip.open_risk_dollars == pytest.approx(50.0)
    assert vm.status_strip.open_risk_position_count == 1


def test_status_strip_template_renders_open_risk_tile(seeded_db, monkeypatch):
    """End-to-end: GET / renders an Open-risk tile between Account and
    Last-pipeline tiles. Asserts the rendered HTML carries both the dollar
    value and percent, and the tile order matches spec §2."""
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.ohlcv_cache import OhlcvCache
    from datetime import datetime

    cfg, cfg_path = seeded_db
    _seed_for_dashboard(cfg)

    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: fake_snap for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # Tile is present with label and count rationale.
    assert 'id="open-risk-tile"' in body
    assert "Open risk" in body
    # Dollar value ($50) and percent (0.04167 → 4.17%) both rendered.
    assert "$50" in body
    assert "4.17%" in body
    assert "1 position" in body   # singular grammar for count=1
    # Tile order: Account before Open-risk before Last pipeline.
    idx_account = body.index('id="account-tile"')
    idx_open_risk = body.index('id="open-risk-tile"')
    idx_pipeline = body.index('id="pipeline-tile"')
    assert idx_account < idx_open_risk < idx_pipeline, (
        "tile order must be Account → Open risk → Last pipeline"
    )


def test_status_strip_template_all_above_breakeven_shows_position_count(
    seeded_db, monkeypatch,
):
    """Adversarial-review Round 2 Minor 1: end-to-end rendering assertion for
    the all-above-breakeven path. Closes the gap where the VM-level fix was
    tested but the rendered HTML wasn't — a future template regression that
    dropped the position count or the 'all above breakeven' annotation would
    slip through the VM-only test."""
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.ohlcv_cache import OhlcvCache
    from datetime import datetime
    from swing.data.db import connect

    cfg, cfg_path = seeded_db
    _seed_for_dashboard(cfg)
    # Trail the seeded stop above entry so the trade contributes $0.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET current_stop = 185.0 WHERE ticker = 'AAPL'",
            )
    finally:
        conn.close()

    fake_snap = PriceSnapshot(
        ticker="AAPL", price=186.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: fake_snap for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # Scope assertions to the tile HTML to avoid false positives from other
    # areas of the page.
    slice_start = body.index('id="open-risk-tile"')
    slice_end = body.index('id="pipeline-tile"')
    tile_html = body[slice_start:slice_end]
    # $0 at risk, 1 total position, all above breakeven.
    assert "$0" in tile_html
    assert "0.00%" in tile_html
    assert "1 position" in tile_html, (
        f"tile must render the TOTAL open-position count (1), not the "
        f"contributing-count (0). tile html:\n{tile_html}"
    )
    assert "all above breakeven" in tile_html


def test_status_strip_open_risk_count_equals_total_open_positions_when_all_above_be(
    seeded_db, monkeypatch,
):
    """Adversarial-review regression (Round 1 Major 1): spec §2 edge case
    reads "N positions (all above breakeven)" where N is the total open
    position count, NOT the helper's contributing-count. Prior wiring fed
    contributing-count into the VM, which collapsed to 0 when every stop had
    trailed past entry — rendering "0 positions (all above breakeven)" and
    losing the N the operator actually needed to see."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    # Seed weather + one open trade whose stop has trailed ABOVE entry.
    _seed_for_dashboard(cfg)
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Raise current_stop on the seeded AAPL trade to above entry
            # (entry 180 → new stop 185). Now the trade contributes $0 to risk.
            conn.execute(
                "UPDATE trades SET current_stop = 185.0 WHERE ticker = 'AAPL'",
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    assert vm.status_strip.open_risk_dollars == 0.0
    assert vm.status_strip.open_risk_all_above_breakeven is True
    # N must be the full open-position count (1 here), NOT the helper's
    # contributing-count (which would be 0).
    assert vm.status_strip.open_risk_position_count == 1, (
        f"expected N=1 total open position; got "
        f"{vm.status_strip.open_risk_position_count} — likely wired to "
        f"contributing-count, which collapses under all-above-breakeven"
    )


def test_status_strip_template_shows_dash_when_open_risk_pct_none(
    seeded_db, monkeypatch,
):
    """Template shows '—' in the percent slot when open_risk_pct is None."""
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.ohlcv_cache import OhlcvCache
    from datetime import datetime

    cfg, cfg_path = seeded_db
    _seed_for_dashboard(cfg)
    # Push equity negative.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO cash_movements (date, kind, amount)
                   VALUES ('2026-04-16', 'withdraw', 1500.0)""",
            )
    finally:
        conn.close()

    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: fake_snap for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'id="open-risk-tile"' in body
    # Scope the percent-slot dash check to near the Open-risk tile.
    slice_start = body.index('id="open-risk-tile"')
    slice_end = body.index('id="pipeline-tile"')
    tile_html = body[slice_start:slice_end]
    # Percent rendered as '—' because equity ≤ 0.
    assert "—" in tile_html
