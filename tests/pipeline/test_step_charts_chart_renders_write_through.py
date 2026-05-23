"""Phase 13 T2.SB6c task T-A.6c.2 §1.5.1 amendment — pipeline-side chart_renders
write-through tests for `_step_charts`.

Per plan §G.2 step 1b (6-8 tests):

  - 4 surface-population tests (watchlist_row / hyprec_detail / position_detail
    / market_weather) — exactly 1 chart_renders row exists per active ticker
    per surface with the correct cache key shape.
  - 1 F6 transient-empty-bytes defense test — renderer returns b""; ChartRender
    construction raises; per-ticker loop catches + warns + continues.
  - 1 DELETE-then-INSERT idempotency test — second `_step_charts` invocation
    replaces the prior row (1 row per cache key, not duplicated).
  - 1 multi-surface sanity test — all 4 surfaces populated for a ticker that
    appears in multiple input sets.

Per L7 + L8 + L17 + L18 LOCK: substrate API FROZEN; `refresh_chart_render` +
`get_cached_chart_svg` + `render_*_svg` invoked verbatim.

Per Codex R2 MAJOR #4 closure: `market_weather` cache row MUST be keyed on
`cfg.rs.benchmark_ticker` (NOT `"^GSPC"` or any other hardcoded value); the
dashboard reader at T2.SB6b consults the same key.
"""
from __future__ import annotations

import pandas as pd
import pytest

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.chart_renders import (
    get_cached_chart_svg,
    list_chart_renders,
)
from swing.data.repos.trades import insert_trade_with_event
from swing.data.repos.watchlist import upsert_watchlist_entry


# ---------------------------------------------------------------------------
# Fixtures: a minimal pipeline-run substrate for `_step_charts` to write into.
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline_db(tmp_path):
    """Apply schema + create a `pipeline_runs` row in state='running' so
    `lease.fenced_write` succeeds. Returns (cfg, run_id, eval_run_id).
    """
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
            # Evaluation run + completed pipeline run.
            cur = conn.execute(
                """
                INSERT INTO evaluation_runs
                    (run_ts, data_asof_date, action_session_date,
                     finviz_csv_path, tickers_evaluated, aplus_count,
                     watch_count, skip_count, excluded_count, error_count)
                VALUES ('2026-05-22T09:00:00', '2026-05-21', '2026-05-22',
                        NULL, 1, 1, 0, 0, 0, 0)
                """
            )
            eval_run_id = int(cur.lastrowid)
            cur = conn.execute(
                """
                INSERT INTO pipeline_runs
                    (started_ts, trigger, data_asof_date,
                     action_session_date, state, lease_token,
                     evaluation_run_id)
                VALUES ('2026-05-22T08:00:00', 'manual', '2026-05-21',
                        '2026-05-22', 'running', 't-step', ?)
                """,
                (eval_run_id,),
            )
            run_id = int(cur.lastrowid)
    finally:
        conn.close()
    return cfg, run_id, eval_run_id


def _make_bars(periods: int = 60) -> pd.DataFrame:
    """Synthesize a minimal OHLCV DataFrame the renderers accept."""
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
    """Duck-typed OhlcvCache stub matching `get_or_fetch(ticker, window_days)`."""

    def __init__(self, frames: dict[str, pd.DataFrame] | None = None,
                 fail_tickers: set[str] | None = None):
        self._frames = frames or {}
        self._fail = fail_tickers or set()

    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        if ticker in self._fail:
            raise RuntimeError(f"stub fetch fail for {ticker}")
        return self._frames.get(ticker, _make_bars())


def _seed_watchlist_row(conn, *, ticker: str) -> None:
    from swing.data.models import WatchlistEntry
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


def _seed_aplus_candidate(conn, *, eval_run_id: int, ticker: str) -> None:
    conn.execute(
        """
        INSERT INTO candidates
            (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
             adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
             rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
             sector, industry)
        VALUES (?, ?, 'aplus', 100.0, 100.0, 95.0, 2.0, 5,
                NULL, NULL, NULL, NULL, 'fallback_spy', NULL, NULL,
                'Technology', 'Software-Application')
        """,
        (eval_run_id, ticker),
    )


def _seed_open_trade(conn, *, ticker: str = "POS") -> int:
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


def _run_step_charts(*, cfg, run_id, eval_run_id, ohlcv_cache):
    """Acquire the lease for the seeded pipeline_run + invoke `_step_charts`.

    Returns nothing — the side-effect is `chart_renders` rows written.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_charts
    lease = Lease(
        db_path=cfg.paths.db_path, run_id=run_id, token="t-step",
    )
    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id,
        data_asof="2026-05-21", ohlcv_cache=ohlcv_cache,
    )


# ===========================================================================
# Surface-population tests (4) — one per surface.
# ===========================================================================


def test_step_charts_writes_through_chart_renders_for_watchlist_row_surface(
    pipeline_db,
):
    """§1.5.1 — `_step_charts` writes a chart_renders row per watchlist
    ticker with surface='watchlist_row' + pipeline_run_id non-NULL."""
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_row(conn, ticker="WCH1")
    finally:
        conn.close()
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        svg = get_cached_chart_svg(
            conn, ticker="WCH1", surface="watchlist_row",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    assert svg is not None
    assert svg.startswith(b"<")  # raw SVG bytes


def test_step_charts_does_not_pregen_hyprec_detail_surface_post_t_t4_sb_3(
    pipeline_db,
):
    """Phase 13 T-T4.SB.3 (OQ-5.3 LOCK): `_step_charts` no longer pre-gens
    the `hyprec_detail` surface — it is now JIT-rendered on dashboard
    expand (see ``build_hyp_recs_expanded`` JIT fallback +
    ``swing/web/chart_jit.py``). This test pins the new contract; the
    pre-T-T4.SB.3 ASSERT NOT NULL form is deliberately inverted."""
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_aplus_candidate(conn, eval_run_id=eval_run_id, ticker="HYP1")
    finally:
        conn.close()
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        svg = get_cached_chart_svg(
            conn, ticker="HYP1", surface="hyprec_detail",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    assert svg is None, (
        "_step_charts must NOT pre-gen hyprec_detail (OQ-5.3 LOCK); "
        "JIT-render on /hyp-recs/{ticker}/expand instead."
    )


def test_step_charts_writes_through_chart_renders_for_position_detail_surface(
    pipeline_db,
):
    """§1.5.1 — open trade tickers get a `position_detail` cache row with
    `pipeline_run_id IS NULL` (run-agnostic per v20 §3.2 LOCK)."""
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_open_trade(conn, ticker="POS1")
    finally:
        conn.close()
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        svg = get_cached_chart_svg(
            conn, ticker="POS1", surface="position_detail",
            pipeline_run_id=None,  # run-agnostic
        )
    finally:
        conn.close()
    assert svg is not None


def test_step_charts_writes_through_chart_renders_for_market_weather_surface(
    pipeline_db,
):
    """§1.5.1 + Codex R2 MAJOR #4 closure — market_weather is keyed on
    `cfg.rs.benchmark_ticker` (NOT a hardcoded value); dashboard reader at
    T2.SB6b consults the same key + must round-trip."""
    cfg, run_id, eval_run_id = pipeline_db
    benchmark = cfg.rs.benchmark_ticker
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        svg = get_cached_chart_svg(
            conn, ticker=benchmark, surface="market_weather",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    assert svg is not None, (
        "Codex R2 MAJOR #4 regression: market_weather row must be keyed on "
        f"cfg.rs.benchmark_ticker={benchmark!r}; dashboard reader cannot "
        "see rows keyed on any other ticker."
    )


# ===========================================================================
# F6 transient-empty defense test (1).
# ===========================================================================


def test_step_charts_handles_transient_empty_chart_bytes_gracefully(
    pipeline_db, monkeypatch, caplog,
):
    """§1.5.1 + T2.SB6a R1 MAJOR #2 LOCK — a renderer returning b"" raises
    `ValueError` at ChartRender construction; the pipeline step MUST catch
    + WARN-log + continue (per-ticker isolation). Pre-existing cache rows
    must be preserved verbatim."""
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_row(conn, ticker="WGOOD")
            _seed_watchlist_row(conn, ticker="WEMPTY")
    finally:
        conn.close()

    # Patch the watchlist thumbnail renderer to return empty for WEMPTY.
    real_renderer = None
    from swing.web import charts as charts_mod
    real_renderer = charts_mod.render_watchlist_thumbnail_svg

    def _maybe_empty(*, ticker, bars, ma_lines):
        if ticker == "WEMPTY":
            return b""
        return real_renderer(ticker=ticker, bars=bars, ma_lines=ma_lines)

    # Patch the symbol the runner imports.
    monkeypatch.setattr(
        "swing.pipeline.runner.render_watchlist_thumbnail_svg",
        _maybe_empty,
    )

    caplog.set_level("WARNING")
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    # Good ticker's row landed.
    conn = connect(cfg.paths.db_path)
    try:
        svg_good = get_cached_chart_svg(
            conn, ticker="WGOOD", surface="watchlist_row",
            pipeline_run_id=run_id,
        )
        svg_empty = get_cached_chart_svg(
            conn, ticker="WEMPTY", surface="watchlist_row",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    assert svg_good is not None
    assert svg_empty is None, (
        "F6 LOCK: empty render bytes must NOT persist (ChartRender "
        "construction barrier rejects + step catches + continues)"
    )
    # WARN-log fired.
    assert any(
        "F6" in r.message or "transient" in r.message.lower()
        for r in caplog.records
    ), (
        "F6 LOCK: empty-bytes rejection must emit a WARN log line"
    )


# ===========================================================================
# DELETE-then-INSERT idempotency test (1).
# ===========================================================================


def test_step_charts_chart_renders_write_through_is_idempotent(pipeline_db):
    """§1.5.1 — invoking `_step_charts` twice with identical input replaces
    (does NOT duplicate) the cache row for the same (ticker, surface,
    pipeline_run_id) tuple. DELETE-then-INSERT atomic refresh per L18.

    The pipeline-level UNIQUE on pipeline_chart_targets means the test
    clears that table between invocations to isolate the write-through
    behavior under test (the cache row's DELETE-then-INSERT idempotency).
    """
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_row(conn, ticker="IDEM")
    finally:
        conn.close()
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        first = list_chart_renders(
            conn, ticker="IDEM", surface="watchlist_row",
            pipeline_run_id=run_id,
        )
        # Clear pipeline_chart_targets + pipeline_pattern_classifications
        # so the second invocation doesn't trip their UNIQUE constraints
        # (unrelated to the cache-row idempotency under test).
        with conn:
            conn.execute(
                "DELETE FROM pipeline_chart_targets WHERE pipeline_run_id = ?",
                (run_id,),
            )
            conn.execute(
                "DELETE FROM pipeline_pattern_classifications "
                "WHERE pipeline_run_id = ?",
                (run_id,),
            )
    finally:
        conn.close()
    assert len(first) == 1
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        second = list_chart_renders(
            conn, ticker="IDEM", surface="watchlist_row",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    # Still exactly 1 row per cache key (DELETE-then-INSERT, not duplicated).
    assert len(second) == 1
    # The row's id was re-issued (autoincrement) — DELETE-then-INSERT.
    assert second[0].id != first[0].id


# ===========================================================================
# Multi-ticker / multi-surface sanity (1).
# ===========================================================================


def test_step_charts_populates_three_pregen_surfaces_in_one_run(pipeline_db):
    """§1.5.1 amended by Phase 13 T-T4.SB.3 OQ-5.3 LOCK: `_step_charts`
    pre-gens THREE surfaces (market_weather + watchlist_row +
    position_detail). The fourth surface (hyprec_detail) is now JIT-only
    via the dashboard expand path. See
    ``test_step_charts_does_not_pregen_hyprec_detail_surface_post_t_t4_sb_3``.
    """
    cfg, run_id, eval_run_id = pipeline_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_aplus_candidate(conn, eval_run_id=eval_run_id, ticker="MTA")
            _seed_watchlist_row(conn, ticker="MTW")
            _seed_open_trade(conn, ticker="MTP")
    finally:
        conn.close()
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    conn = connect(cfg.paths.db_path)
    try:
        # market_weather (cfg.rs.benchmark_ticker).
        assert get_cached_chart_svg(
            conn, ticker=cfg.rs.benchmark_ticker,
            surface="market_weather", pipeline_run_id=run_id,
        ) is not None
        # watchlist_row.
        assert get_cached_chart_svg(
            conn, ticker="MTW", surface="watchlist_row",
            pipeline_run_id=run_id,
        ) is not None
        # hyprec_detail — NO LONGER PRE-GENNED per OQ-5.3 LOCK.
        assert get_cached_chart_svg(
            conn, ticker="MTA", surface="hyprec_detail",
            pipeline_run_id=run_id,
        ) is None
        # position_detail (pipeline_run_id IS NULL).
        assert get_cached_chart_svg(
            conn, ticker="MTP", surface="position_detail",
            pipeline_run_id=None,
        ) is not None
    finally:
        conn.close()
