"""Phase 13 T-T4.SB.3 (Item 5; OQ-5.3 LOCK) — pre-gen scope reduction tests.

Per plan §B.3 Sub-task 3E: `_step_charts` pre-gen scope reduced from
top-N (`chart_top_n_watch` = 10) to dashboard-top-5 visible-by-default.
The fourth surface (`ticker_detail`) is now JIT-only — pre-gen DROPPED;
JIT-rendered on `/hyp-recs/{ticker}/expand` via the chart_jit helper.

Discriminating fixtures:
- 10 active watchlist tickers + 1 A+ candidate + 1 open trade →
  `_step_charts` writes ≤5 watchlist_row rows + 0 ticker_detail +
  ≥1 market_weather + ≥1 position_detail.
"""
from __future__ import annotations

import pandas as pd
import pytest

from swing.data.db import connect
from swing.data.models import Trade, WatchlistEntry
from swing.data.repos.trades import insert_trade_with_event
from swing.data.repos.watchlist import upsert_watchlist_entry


@pytest.fixture
def pipeline_db(tmp_path):
    """Apply schema + create a `pipeline_runs` row in state='running'."""
    from swing.config import load as load_config
    from swing.data.db import ensure_schema as _ensure
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_config(cfg_path)
    _ensure(cfg.paths.db_path).close()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO evaluation_runs "
                "(run_ts, data_asof_date, action_session_date, "
                "finviz_csv_path, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES ('2026-05-22T09:00:00', '2026-05-21', '2026-05-22', "
                "NULL, 10, 1, 9, 0, 0, 0)"
            )
            eval_run_id = int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO pipeline_runs "
                "(started_ts, trigger, data_asof_date, action_session_date, "
                "state, lease_token, evaluation_run_id) "
                "VALUES ('2026-05-22T08:00:00', 'manual', '2026-05-21', "
                "'2026-05-22', 'running', 't-pregen', ?)",
                (eval_run_id,),
            )
            run_id = int(cur.lastrowid)
    finally:
        conn.close()
    return cfg, run_id, eval_run_id


def _make_bars(periods: int = 60) -> pd.DataFrame:
    closes = [100.0 + i * 0.1 for i in range(periods)]
    idx = pd.bdate_range(start="2026-01-02", periods=periods)
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * periods,
    }, index=idx)


class _StubOhlcvCache:
    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        return _make_bars()


def _seed_watchlist_entry(conn, ticker: str) -> None:
    upsert_watchlist_entry(
        conn,
        WatchlistEntry(
            ticker=ticker, added_date="2026-05-01",
            last_qualified_date="2026-05-21", status="watch",
            qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-05-21",
            entry_target=100.0, initial_stop_target=95.0,
            last_close=100.0, last_pivot=None, last_stop=None,
            last_adr_pct=2.0, missing_criteria=None, notes=None,
        ),
    )


def _seed_aplus(conn, eval_run_id: int, ticker: str) -> None:
    conn.execute(
        "INSERT INTO candidates "
        "(evaluation_run_id, ticker, bucket, close, pivot, initial_stop, "
        " adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        " rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector, industry) "
        "VALUES (?, ?, 'aplus', 100.0, 100.0, 95.0, 2.0, 5, NULL, NULL, "
        "NULL, NULL, 'fallback_spy', NULL, NULL, 'Technology', 'Semis')",
        (eval_run_id, ticker),
    )


def _seed_open_trade(conn, ticker: str) -> int:
    return insert_trade_with_event(
        conn,
        Trade(
            id=None, ticker=ticker,
            entry_date="2026-05-18", entry_price=100.0,
            initial_shares=10, initial_stop=90.0,
            current_stop=90.0, state="entered",
            watchlist_entry_target=None,
            watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-18T09:30:00",
            current_size=10.0,
        ),
        event_ts="2026-05-18T09:30:00",
    )


def _run_step_charts(*, cfg, run_id, eval_run_id):
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_charts
    lease = Lease(
        db_path=cfg.paths.db_path, run_id=run_id, token="t-pregen",
    )
    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id,
        data_asof="2026-05-21", ohlcv_cache=_StubOhlcvCache(),
    )


def test_step_charts_pregen_scope_reduced_to_top5_no_ticker_detail(
    pipeline_db,
):
    """Plan §B.3 Sub-task 3E + OQ-5.3 LOCK: pre-gen writes ONLY
    market_weather + position_detail + watchlist_row (top-5). NOT
    ticker_detail. NOT top-10 watchlist.
    """
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Seed 10 watchlist entries (more than the new top-5 limit).
            for i in range(10):
                _seed_watchlist_entry(conn, f"WCH{i:02d}")
            # Seed 1 A+ candidate (should NOT pre-gen ticker_detail).
            _seed_aplus(conn, eval_run_id, ticker="APX")
            # Seed 1 open trade.
            _seed_open_trade(conn, ticker="POS1")
    finally:
        conn.close()

    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
    )

    conn = connect(cfg.paths.db_path)
    try:
        rows = list(conn.execute(
            "SELECT surface, COUNT(*) FROM chart_renders "
            "GROUP BY surface ORDER BY surface"
        ))
    finally:
        conn.close()
    surface_counts = dict(rows)

    # OQ-5.3 LOCK: ticker_detail dropped from pre-gen.
    assert surface_counts.get("ticker_detail", 0) == 0, (
        "ticker_detail must NOT be pre-genned (OQ-5.3 LOCK); JIT-render "
        "on /hyp-recs/{ticker}/expand instead. Got "
        f"{surface_counts.get('ticker_detail', 0)} rows."
    )
    # market_weather + position_detail still pre-genned.
    assert surface_counts.get("market_weather", 0) >= 1
    assert surface_counts.get("position_detail", 0) >= 1
    # Watchlist limited to top-5 (NOT top-10).
    assert surface_counts.get("watchlist_row", 0) <= 5, (
        "watchlist_row pre-gen capped at top-5 visible-by-default (OQ-5.3 "
        "LOCK); JIT-render positions 6-N at request time. Got "
        f"{surface_counts.get('watchlist_row', 0)} rows."
    )
    # But at least 1 (the test seeded 10 entries so top-5 should fill).
    assert surface_counts.get("watchlist_row", 0) >= 1
