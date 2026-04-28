"""Task 7 — chart-step wall-time monitoring + log-capture tests.

Instruments `_step_charts` with a wall-time timer that brackets all chart-step
work (from entry through last fenced write). WARNING fires at >60s; ERROR fires
at >120s; the two are mutually exclusive via if/elif. Tests drive the timer
past thresholds DETERMINISTICALLY by patching `swing.pipeline.runner.time.monotonic`;
assertions are on log records (`caplog`), NOT on real timing.

Spec: docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md §A
Plan: docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md Task 7
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.data.models import (
    Candidate,
    CriterionResult,
    EvaluationRun,
    WatchlistEntry,
)
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.pipeline import (
    list_chart_targets,
    set_evaluation_run_id,
)
from swing.pipeline.lease import acquire_lease
from swing.pipeline.runner import _step_charts


# ---------------------------------------------------------------------------
# Shared helpers (mirror _StepChartsCtx pattern from test_runner_chart_targets)
# ---------------------------------------------------------------------------

def _ohlcv(closes=None, end="2026-04-15"):
    import pandas as pd
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _make_aplus_candidate(ticker: str, *, pivot: float, initial_stop: float) -> Candidate:
    tt_criteria = tuple(
        CriterionResult(
            criterion_name=f"TT{i}", layer="trend_template", result="pass",
        )
        for i in range(1, 9)
    )
    vcp_criteria = (
        CriterionResult(criterion_name="vcp_prior_trend", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_pullback", layer="vcp", result="pass"),
        CriterionResult(criterion_name="vcp_tightness", layer="vcp", result="pass"),
    )
    return Candidate(
        ticker=ticker, bucket="aplus",
        close=pivot * 0.99, pivot=pivot, initial_stop=initial_stop,
        adr_pct=4.5, tight_streak=3, pullback_pct=10.0, prior_trend_pct=30.0,
        rs_rank=85, rs_return_12w_vs_spy=0.15, rs_method="universe",
        pattern_tag=None, notes=None,
        criteria=tt_criteria + vcp_criteria,
    )


def _seed_watchlist_row(
    conn: sqlite3.Connection, *, ticker: str,
    entry_target: float | None, last_close: float | None,
    initial_stop_target: float | None = None,
) -> None:
    entry = WatchlistEntry(
        ticker=ticker, added_date="2026-04-15",
        last_qualified_date="2026-04-15", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-15",
        entry_target=entry_target,
        initial_stop_target=initial_stop_target,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=None, missing_criteria=None, notes=None,
    )
    from swing.data.repos.watchlist import upsert_watchlist_entry
    with conn:
        upsert_watchlist_entry(conn, entry)


class _StubFetcher:
    """Returns ample bars for any ticker so _step_charts doesn't fetcher_fail."""
    def get(self, ticker, lookback_days, *, as_of_date=None):
        return _ohlcv()


def _make_walltime_ctx(tmp_path: Path, *, candidates=None):
    """Build the minimal DB state for a direct `_step_charts` invocation.

    Seeds one A+ candidate (TSTT) with valid pivot/stop so pipeline_chart_targets
    will be non-empty after the call (needed for test #4's status assertions).
    """
    cfg = _make_cfg(tmp_path)
    data_asof = "2026-04-15"
    action_session = "2026-04-16"
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date=data_asof, action_session_date=action_session,
    )
    if candidates is None:
        candidates = [_make_aplus_candidate("TSTT", pivot=110.0, initial_stop=100.0)]

    conn = connect(cfg.paths.db_path)
    try:
        with lease.fenced_write() as wconn:
            run = EvaluationRun(
                id=None, run_ts="2026-04-15T21:00:00",
                data_asof_date=data_asof, action_session_date=action_session,
                finviz_csv_path=None,
                tickers_evaluated=len(candidates),
                aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
                watch_count=sum(1 for c in candidates if c.bucket == "watch"),
                skip_count=0, excluded_count=0, error_count=0,
                rs_universe_version=None, rs_universe_hash=None,
            )
            eval_run_id = insert_evaluation_run(wconn, run)
            if candidates:
                insert_candidates(wconn, eval_run_id, candidates)
            set_evaluation_run_id(
                wconn, pipeline_run_id=lease.run_id,
                evaluation_run_id=eval_run_id,
            )
    finally:
        conn.close()

    return cfg, lease, eval_run_id, data_asof, _StubFetcher()


def _patch_monotonic(monkeypatch, seq: list[float]) -> None:
    """Patch `swing.pipeline.runner.time.monotonic` to return the next value
    from `seq` on each call. Requires the production code to use a
    MODULE-LEVEL `import time` (NOT function-local) so the attribute lookup
    `swing.pipeline.runner.time` resolves to a patchable object.
    """
    it = iter(seq)
    monkeypatch.setattr(
        "swing.pipeline.runner.time.monotonic", lambda: next(it),
    )


def _stub_render(monkeypatch):
    """Patch render_chart to write a stub PNG and return the path."""
    def fake_render(*, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png-stub")
        return output_path
    monkeypatch.setattr("swing.pipeline.runner.render_chart", fake_render)


# ---------------------------------------------------------------------------
# Test 1 — WARNING at 65s (soft budget)
# ---------------------------------------------------------------------------

def test_step_charts_logs_warning_when_walltime_above_soft_budget(
    tmp_path: Path, monkeypatch, caplog
):
    """_patch_monotonic([0.0, 65.0]) → elapsed=65s.

    Assert exactly 1 WARNING log record with substring 'soft budget'.
    Assert the measured value 65 (or 65.0) appears in the message.
    """
    cfg, lease, eval_run_id, data_asof, fetcher = _make_walltime_ctx(tmp_path)
    _patch_monotonic(monkeypatch, [0.0, 65.0])
    _stub_render(monkeypatch)

    import logging
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        _step_charts(
            cfg=cfg, lease=lease, eval_run_id=eval_run_id,
            data_asof=data_asof, fetcher=fetcher,
        )

    warn_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "soft budget" in r.message
    ]
    assert len(warn_records) == 1, (
        f"expected exactly 1 WARNING with 'soft budget', got {len(warn_records)}: "
        f"{[r.message for r in warn_records]}"
    )
    msg = warn_records[0].message
    assert "65" in msg, (
        f"measured elapsed value (65 or 65.0) not found in WARNING message: {msg!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — ERROR at 130s (hard budget) + ZERO WARNING records
# ---------------------------------------------------------------------------

def test_step_charts_logs_error_when_walltime_above_hard_budget(
    tmp_path: Path, monkeypatch, caplog
):
    """_patch_monotonic([0.0, 130.0]) → elapsed=130s.

    Assert exactly 1 ERROR log record with substring 'hard budget'.
    Assert ZERO WARNING records (mutual exclusion via if/elif).
    """
    cfg, lease, eval_run_id, data_asof, fetcher = _make_walltime_ctx(tmp_path)
    _patch_monotonic(monkeypatch, [0.0, 130.0])
    _stub_render(monkeypatch)

    import logging
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        _step_charts(
            cfg=cfg, lease=lease, eval_run_id=eval_run_id,
            data_asof=data_asof, fetcher=fetcher,
        )

    error_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR and "hard budget" in r.message
    ]
    assert len(error_records) == 1, (
        f"expected exactly 1 ERROR with 'hard budget', got {len(error_records)}: "
        f"{[r.message for r in error_records]}"
    )
    assert "130" in error_records[0].message, (
        f"measured elapsed value (130 or 130.0) not found in ERROR message: "
        f"{error_records[0].message!r}"
    )

    # Mutual exclusion: if/elif means ERROR fires, WARNING must NOT.
    warn_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "budget" in r.message
    ]
    assert len(warn_records) == 0, (
        f"expected ZERO WARNING budget records when ERROR fires (if/elif), "
        f"got {len(warn_records)}: {[r.message for r in warn_records]}"
    )


# ---------------------------------------------------------------------------
# Test 3 — No log at 30s (under soft budget)
# ---------------------------------------------------------------------------

def test_step_charts_no_log_when_walltime_under_soft_budget(
    tmp_path: Path, monkeypatch, caplog
):
    """_patch_monotonic([0.0, 30.0]) → elapsed=30s.

    Assert ZERO chart-step wall-time log records (verified-empirically pin
    for healthy runs under the 60s soft budget threshold).
    """
    cfg, lease, eval_run_id, data_asof, fetcher = _make_walltime_ctx(tmp_path)
    _patch_monotonic(monkeypatch, [0.0, 30.0])
    _stub_render(monkeypatch)

    import logging
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        _step_charts(
            cfg=cfg, lease=lease, eval_run_id=eval_run_id,
            data_asof=data_asof, fetcher=fetcher,
        )

    budget_records = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "budget" in r.message
    ]
    assert len(budget_records) == 0, (
        f"expected ZERO budget log records at 30s elapsed, "
        f"got {len(budget_records)}: {[r.message for r in budget_records]}"
    )


# ---------------------------------------------------------------------------
# Test 4 — pipeline_chart_targets.chart_status unchanged on overrun
# ---------------------------------------------------------------------------

def test_step_charts_pipeline_runs_charts_status_unchanged_on_overrun(
    tmp_path: Path, monkeypatch, caplog
):
    """_patch_monotonic([0.0, 130.0]) → elapsed=130s (hard budget overrun).

    After _step_charts completes, query pipeline_chart_targets.chart_status
    rows; assert all values are in {'ok', 'fetcher_failed', 'too_few_bars'}
    (NOT 'failed'). Spec §A: pipeline continues normally on overrun — the
    wall-time log is advisory only, not a failure signal.
    """
    cfg, lease, eval_run_id, data_asof, fetcher = _make_walltime_ctx(tmp_path)
    _patch_monotonic(monkeypatch, [0.0, 130.0])
    _stub_render(monkeypatch)

    import logging
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        _step_charts(
            cfg=cfg, lease=lease, eval_run_id=eval_run_id,
            data_asof=data_asof, fetcher=fetcher,
        )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT chart_status FROM pipeline_chart_targets WHERE pipeline_run_id = ?",
            (lease.run_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) > 0, (
        "pipeline_chart_targets must have at least one row after _step_charts "
        "with a seeded A+ candidate (TSTT)"
    )
    allowed = {"ok", "fetcher_failed", "too_few_bars"}
    bad = [row[0] for row in rows if row[0] not in allowed]
    assert bad == [], (
        f"chart_status values outside allowed set {allowed} found after overrun: "
        f"{bad}. Pipeline must continue normally on wall-time overrun."
    )
