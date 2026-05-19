"""Phase 13 T1.SB0 — wiring discriminating test for ``_step_charts``.

Plan §G.0 T-T1.SB0.3 acceptance: ``_step_charts`` no longer invokes the legacy
``PriceFetcher.get`` path; it invokes ``OhlcvCache.get_or_fetch`` instead.

Discriminator: pass a stub that exposes ONLY ``get_or_fetch`` (NOT ``get``).
Pre-implementation: ``_step_charts`` calls ``fetcher.get(...)`` → AttributeError.
Post-implementation: ``_step_charts`` calls ``ohlcv_cache.get_or_fetch(...)`` →
test passes + spy records the expected callsites.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pandas as pd

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.data.repos.pipeline import set_evaluation_run_id
from swing.pipeline.lease import acquire_lease
from swing.pipeline.runner import _step_charts
from tests.cli.test_cli_eval import _minimal_config


def _make_cfg(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _make_aplus_candidate(ticker: str, *, pivot: float, initial_stop: float) -> Candidate:
    """Mirrors ``tests/pipeline/test_runner_chart_targets.py``'s helper —
    bucket=aplus + 8/8 TT passes + 3/3 VCP passes so flag tags compute fully.
    """
    tt = tuple(
        CriterionResult(criterion_name=f"TT{i}", layer="trend_template", result="pass")
        for i in range(1, 9)
    )
    vcp = (
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
        criteria=tt + vcp,
    )


def _ohlcv(n: int = 200) -> pd.DataFrame:
    """Deterministic OHLCV DataFrame (capitalized columns + DatetimeIndex)."""
    idx = pd.bdate_range(end="2026-04-30", periods=n)
    closes = [100.0 + i * 0.05 for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.05 for c in closes],
            "High": [c + 0.30 for c in closes],
            "Low": [c - 0.30 for c in closes],
            "Close": closes,
            "Volume": [1_000_000 + i for i in range(n)],
        },
        index=idx,
    )


class _OhlcvCacheSpy:
    """Stub exposing ONLY ``get_or_fetch`` — pre-implementation ``_step_charts``
    would call ``.get(...)`` and AttributeError. Post-implementation it calls
    ``.get_or_fetch(ticker=..., window_days=...)`` and the spy records every
    invocation.
    """

    def __init__(self, returns: pd.DataFrame):
        self._returns = returns
        self.calls: list[tuple[str, int]] = []

    def get_or_fetch(self, *, ticker: str, window_days: int):
        self.calls.append((ticker, window_days))
        return self._returns


def _seed_eval_with_aplus_candidates(cfg, lease, tickers_with_pivots):
    """Insert one evaluation_runs + N candidates (bucket=aplus) inside the
    lease's fenced write. Returns the new evaluation_run_id."""
    data_asof = "2026-04-15"
    action_session = "2026-04-16"
    cands = [
        _make_aplus_candidate(t, pivot=p, initial_stop=p * 0.9)
        for (t, p) in tickers_with_pivots
    ]
    with lease.fenced_write() as conn:
        run = EvaluationRun(
            id=None, run_ts="2026-04-15T21:00:00",
            data_asof_date=data_asof, action_session_date=action_session,
            finviz_csv_path=None,
            tickers_evaluated=len(cands),
            aplus_count=len(cands),
            watch_count=0, skip_count=0, excluded_count=0, error_count=0,
            rs_universe_version=None, rs_universe_hash=None,
        )
        eval_run_id = insert_evaluation_run(conn, run)
        if cands:
            insert_candidates(conn, eval_run_id, cands)
        set_evaluation_run_id(
            conn, pipeline_run_id=lease.run_id, evaluation_run_id=eval_run_id,
        )
    return eval_run_id, data_asof


def _stub_render(monkeypatch):
    """Stub ``render_chart`` so the step doesn't actually render PNG."""
    def fake_render(*, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png-stub")
        return output_path
    monkeypatch.setattr("swing.pipeline.runner.render_chart", fake_render)


def test_step_charts_calls_ohlcv_cache_get_or_fetch_not_legacy_fetcher_get(
    tmp_path: Path, monkeypatch,
):
    """Plan §G.0 T-T1.SB0.3 acceptance: ``_step_charts`` invokes
    ``OhlcvCache.get_or_fetch`` (NOT ``PriceFetcher.get``).

    Spy stub exposes ONLY ``get_or_fetch``; pre-implementation ``_step_charts``
    calls ``.get(...)`` → AttributeError → test fails. Post-implementation
    spy records two callsites (one per A+ candidate).
    """
    cfg = _make_cfg(tmp_path)
    cfg = replace(cfg, pipeline=replace(cfg.pipeline, chart_top_n_watch=5))
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    eval_run_id, data_asof = _seed_eval_with_aplus_candidates(
        cfg, lease, [("APLA", 110.0), ("APLB", 120.0)],
    )
    spy = _OhlcvCacheSpy(returns=_ohlcv(200))
    _stub_render(monkeypatch)

    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id, data_asof=data_asof,
        ohlcv_cache=spy,
    )

    assert len(spy.calls) == 2, f"unexpected callcount: {spy.calls}"
    tickers_called = sorted(t for (t, _w) in spy.calls)
    assert tickers_called == ["APLA", "APLB"], (
        f"unexpected tickers: {tickers_called}"
    )
    # Preserves existing lookback semantics (line 1323 used lookback_days=200).
    windows = sorted({w for (_t, w) in spy.calls})
    assert windows == [200], (
        f"window_days drift — expected 200 to preserve legacy chart window: {windows}"
    )


def test_step_charts_handles_get_or_fetch_value_error_as_fetcher_failed(
    tmp_path: Path, monkeypatch,
):
    """Plan §G.0 T-T1.SB0.3 acceptance + recon §1 invariant: when
    ``get_or_fetch`` raises ``ValueError``, ``_step_charts`` catches it +
    records ``chart_status='fetcher_failed'``. Preserves the existing per-
    ticker exception-handling semantics from the legacy fetcher.get path.
    """
    cfg = _make_cfg(tmp_path)
    cfg = replace(cfg, pipeline=replace(cfg.pipeline, chart_top_n_watch=5))
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    eval_run_id, data_asof = _seed_eval_with_aplus_candidates(
        cfg, lease, [("DELT", 50.0)],
    )

    class _RaisingStub:
        def get_or_fetch(self, *, ticker, window_days):
            raise ValueError(f"No data for {ticker}")

    _stub_render(monkeypatch)
    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id, data_asof=data_asof,
        ohlcv_cache=_RaisingStub(),
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = list(conn.execute(
            """SELECT ticker, chart_status FROM pipeline_chart_targets
               WHERE pipeline_run_id = ?""",
            (lease.run_id,),
        ))
    finally:
        conn.close()
    assert rows == [("DELT", "fetcher_failed")], f"got rows={rows}"
