"""D84 acceptance (i)a -- the END-TO-END discriminator for E1.

A risk-fail A+ name must bucket `aplus` AND latch. The test goes evaluator ->
persist -> latch, because a row seeded straight into the DB latches even
before D84 (`swing/latches/reader.py:_FIRE_SQL` selects on the bucket alone),
so only the EVALUATOR's bucket can discriminate the change.

The TT and VCP criterion functions are monkeypatched to pass, at the names
`swing/evaluation/evaluator.py` resolves (the criterion MODULE attributes). The
risk criterion is NOT patched: the REAL `risk_feasibility.evaluate` runs on an
OHLCV tail shaped to the real KOD geometry (pivot 104.00, stop 29.81; one share
risks $74.19 against the $37.50 budget at the $7,500 floor), so it emits the
real KOD-shaped fail, `0 sh, $0.00 risk`.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

KOD_PIVOT = 104.00
KOD_STOP = 29.81
KOD_CLOSE = 98.46


def _kod_ohlcv(n: int = 260) -> pd.DataFrame:
    idx = pd.bdate_range("2025-10-01", periods=n)
    close = [KOD_CLOSE] * n
    high = [KOD_CLOSE] * n
    low = [KOD_CLOSE] * n
    high[-7] = KOD_PIVOT      # the 20-bar tail's max High is the pivot
    low[-15] = KOD_STOP       # the 20-bar tail's min Low is the stop
    return pd.DataFrame({
        "Open": close, "High": high, "Low": low, "Close": close,
        "Volume": [1_000_000] * n,
    }, index=idx)


def _pass(name: str, layer: str):
    from swing.evaluation.criteria._base import Result

    return Result(name=name, layer=layer, result="pass", value="", rule="")


def _patch_structure_to_pass(monkeypatch):
    from swing.evaluation import evaluator
    from swing.evaluation.scoring import EXPECTED_TT_CRITERIA

    tt = [_pass(n, "trend_template") for n in sorted(EXPECTED_TT_CRITERIA)]
    monkeypatch.setattr(evaluator.trend_template, "evaluate", lambda ctx: list(tt))
    monkeypatch.setattr(
        evaluator.ma_stack_short, "evaluate",
        lambda ctx: (_pass("ma_stack_10_20_50", "vcp"),
                     _pass("ma_short_rising", "vcp")))
    for mod, name in (
        (evaluator.prior_trend, "prior_trend"),
        (evaluator.proximity, "proximity_20ma"),
        (evaluator.adr, "adr"),
        (evaluator.pullback, "pullback"),
        (evaluator.tightness, "tightness"),
        (evaluator.vcp, "vcp_volume_contraction"),
        (evaluator.orderliness, "orderliness"),
    ):
        monkeypatch.setattr(mod, "evaluate", lambda ctx, _n=name: _pass(_n, "vcp"))


def test_acceptance_i_a_risk_fail_A_plus_buckets_aplus_AND_latches(  # noqa: N802
        monkeypatch, sample_config, tmp_path):
    """R-(i)a. Pre-D84 the risk pre-skip buckets this name `skip` and there is
    no latch; post-D84 it is `aplus`, it persists `aplus`, and it latches."""
    from swing.data.db import ensure_schema
    from swing.data.models import EvaluationRun
    from swing.data.repos.candidates import (
        insert_candidates,
        insert_evaluation_run,
    )
    from swing.evaluation.context import (
        BatchContext,
        CandidateContext,
        MarketContext,
    )
    from swing.evaluation.evaluator import evaluate_one
    from swing.latches.reader import build_latch_derivation

    _patch_structure_to_pass(monkeypatch)
    ctx = CandidateContext(
        ticker="KOD", ohlcv=_kod_ohlcv(), config=sample_config,
        batch=BatchContext(
            returns_12w_by_ticker={"KOD": 0.40}, universe_tickers=("KOD",),
            universe_version="t", universe_hash="t", spy_return_12w=0.10),
        market=MarketContext(), current_equity=7500.0)

    candidate = evaluate_one(ctx)

    (risk,) = [c for c in candidate.criteria if c.layer == "risk"]
    assert (risk.criterion_name, risk.result, risk.value) == (
        "risk_feasibility", "fail", "0 sh, $0.00 risk")
    assert (candidate.pivot, candidate.initial_stop) == (KOD_PIVOT, KOD_STOP)
    assert candidate.bucket == "aplus"

    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-10-22T17:30:05",
                data_asof_date="2026-10-22", action_session_date="2026-10-23",
                finviz_csv_path=None, tickers_evaluated=1, aplus_count=1,
                watch_count=0, skip_count=0, excluded_count=0, error_count=0))
            insert_candidates(conn, run_id, [candidate])
        (persisted,) = conn.execute(
            "SELECT bucket FROM candidates WHERE evaluation_run_id = ? "
            "AND ticker = 'KOD'", (run_id,)).fetchone()
        assert persisted == "aplus"

        cache = tmp_path / "prices"
        cache.mkdir()
        cfg = SimpleNamespace(
            paths=SimpleNamespace(prices_cache_dir=cache,
                                  db_path=tmp_path / "t.db"),
            pipeline=SimpleNamespace(observe_max_pending_window_sessions=30),
            trend_template=sample_config.trend_template)
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 10, 23, 12, 0))
        kod = [latch for latch in d.latches if latch.identity.ticker == "KOD"]
        assert len(kod) == 1
        assert kod[0].latched_pivot == KOD_PIVOT
        assert kod[0].latched_initial_stop == KOD_STOP
    finally:
        conn.close()
