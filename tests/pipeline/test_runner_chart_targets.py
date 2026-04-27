"""Pipeline runner — Tranche C T2: evaluation_run_id FK + pipeline_chart_targets.

These integration tests exercise the runner end-to-end against the real DB
schema with monkeypatched yfinance. They assert:

- After `_step_evaluate` runs, `pipeline_runs.evaluation_run_id` is populated.
- After `_step_charts` runs, `pipeline_chart_targets` has one row per ticker
  in scope, with `chart_status` reflecting the per-ticker outcome.
- Fetcher exception → `chart_status='fetcher_failed'`.
- `len(df) < MIN_BARS` (rendering returns None) → `chart_status='too_few_bars'`.
- Successful PNG write → `chart_status='ok'`.
- Source field encodes provenance ('aplus' vs 'near_proximity').

Mid-run lease revocation behavior is already covered by
`test_runner_detects_mid_run_lease_revocation` — these tests focus on the
new persistence semantics added by Tranche C.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run, list_chart_targets
from swing.pipeline.runner import run_pipeline_internal


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _csv(inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    )
    csv.write_text(
        cols + "\n"
        "1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n"
        "2,MSFT,T,S,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3.5e9\n",
        encoding="utf-8",
    )
    return csv


def _seed_active_watchlist_entry(
    db_path: Path, *, ticker: str, entry_target: float, last_close: float,
) -> None:
    """Pre-seed a watchlist entry so the chart step's near-by-proximity
    selector picks it up. The pipeline's _step_watchlist may also add or
    requalify rows — this fixture only guarantees one known row exists."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO watchlist
                   (ticker, added_date, last_qualified_date, status,
                    qualification_count, not_qualified_streak,
                    last_data_asof_date, entry_target, initial_stop_target,
                    last_close)
                   VALUES (?, '2026-04-15', '2026-04-15', 'watch', 1, 0,
                           '2026-04-15', ?, NULL, ?)""",
                (ticker, entry_target, last_close),
            )
    finally:
        conn.close()


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def test_step_evaluate_populates_evaluation_run_id(tmp_path: Path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.evaluation_run_id is not None, (
            "pipeline_runs.evaluation_run_id must be populated after "
            "_step_evaluate so the chart-scope resolver can bind structurally"
        )
        # And that FK references a real evaluation_runs row. (We do NOT
        # assert data_asof_date equality with pipeline_runs.data_asof_date —
        # the lease records last_completed_session(now) while the eval
        # records the actual OHLCV max-date, which can legitimately differ
        # in mocked-fetcher tests and in real weekend-edge cases.)
        eval_row = conn.execute(
            "SELECT id FROM evaluation_runs WHERE id = ?",
            (run.evaluation_run_id,),
        ).fetchone()
        assert eval_row is not None
    finally:
        conn.close()


def test_step_charts_writes_chart_targets_with_ok_status(
    tmp_path: Path, monkeypatch,
):
    """Watchlist ticker that gets a PNG written → chart_status='ok',
    source='near_proximity'."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    # Avoid mplfinance dependency in the test env: render_chart returns the
    # path on success, but we monkeypatch it to write a stub PNG so we can
    # test the success branch without mplfinance installed. Phase 3 added a
    # `pattern_overlay` kwarg the runner now passes through; accept and
    # discard.
    def fake_render(
        *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"stub-png")
        return output_path

    monkeypatch.setattr("swing.pipeline.runner.render_chart", fake_render)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        assert len(targets) > 0, (
            "chart step must persist at least one pipeline_chart_targets row "
            "when the watchlist near-by-proximity set is non-empty"
        )
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "ok"
        assert aapl.source == "near_proximity"
    finally:
        conn.close()


def test_step_charts_records_fetcher_failed(tmp_path: Path, monkeypatch):
    """Fetcher raising for a chart-step ticker → chart_status='fetcher_failed'.

    The eval step uses lookback_days∈{120,180,365,400}; the chart step uses
    200. We branch on lookback_days so eval still completes but the chart
    fetch raises for AAPL.
    """
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    def selective_fetcher(self, ticker, lookback_days, *, as_of_date=None):
        if lookback_days == 200 and ticker == "AAPL":
            raise RuntimeError("simulated yfinance outage for chart fetch")
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", selective_fetcher)
    monkeypatch.setattr(
        "swing.pipeline.runner.render_chart",
        lambda *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None: (
            output_path.parent.mkdir(parents=True, exist_ok=True)
            or output_path.write_bytes(b"stub")
            or output_path
        ),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "fetcher_failed", (
            f"expected fetcher_failed for AAPL, got {aapl.chart_status!r}"
        )
    finally:
        conn.close()


def test_step_charts_records_too_few_bars(tmp_path: Path, monkeypatch):
    """render_chart returns None when len(df) < MIN_BARS → chart_status='too_few_bars'."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    def short_render(
        *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None,
    ):
        # Simulate the MIN_BARS short-circuit for AAPL specifically.
        if ticker == "AAPL":
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"stub")
        return output_path

    monkeypatch.setattr("swing.pipeline.runner.render_chart", short_render)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl = next(t for t in targets if t.ticker == "AAPL")
        assert aapl.chart_status == "too_few_bars"
    finally:
        conn.close()


def test_step_charts_dedupes_aplus_then_near_proximity(
    tmp_path: Path, monkeypatch,
):
    """If a ticker is both A+ and on the watchlist, only one chart_targets
    row is written; provenance prefers A+ (the chart's primary justification).
    Validates the runner's dedupe policy that protects the (run_id, ticker)
    UNIQUE constraint."""
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    # Seed AAPL on the watchlist; the fetcher returns long OHLCV so the
    # evaluator may also bucket AAPL as A+. Either way, dedupe must keep one
    # row only.
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL",
        entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.render_chart",
        lambda *, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None: (
            output_path.parent.mkdir(parents=True, exist_ok=True)
            or output_path.write_bytes(b"stub")
            or output_path
        ),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        targets = list_chart_targets(conn, pipeline_run_id=result.run_id)
        aapl_rows = [t for t in targets if t.ticker == "AAPL"]
        assert len(aapl_rows) == 1, (
            f"dedupe must collapse aplus + near_proximity for the same ticker, "
            f"got {len(aapl_rows)} rows for AAPL"
        )
        # If AAPL was A+, source must be 'aplus' (preferred); otherwise
        # near_proximity. Either is fine — assert it's a valid value.
        assert aapl_rows[0].source in ("aplus", "near_proximity")
    finally:
        conn.close()
