"""Phase 13 T2.SB6c T-A.6c.4 — entry-service candidate_id + pattern_evaluation_id population.

Per plan §G.4 Step 7(d) + §C.5 Layer 3 + OQ-11 + OQ-12 closure:
- Pipeline-origin trade (hyp-recs / watch / aplus) populates candidate_id via
  Path 1 (evaluation_run_id filter) when _latest_complete_evaluation_run_id
  returns a matching value.
- Pattern_evaluation_id populated from server-derived value passed through
  EntryRequest (NOT operator-submitted hidden input verbatim; route handler
  re-derives + 5-tier-validates before threading to record_entry).
- Manual_off_pipeline trade persists candidate_id=NULL + pattern_evaluation_id=NULL.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Candidate, EvaluationRun, PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.data.repos.trades import get_trade
from swing.trades.entry import EntryRationale, EntryRequest, record_entry
from swing.trades.origin import EntryPath


def _seed_v21(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    return conn


def _seed_pipeline_with_watch_candidate(
    conn, *, ticker: str = "ABC", pattern_class: str = "vcp",
) -> tuple[int, int, int]:
    """Returns (eval_run_id, pipeline_run_id, pattern_evaluation_id)."""
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None,
        run_ts="2026-05-20T09:00:00",
        data_asof_date="2026-05-19",
        action_session_date="2026-05-20",
        finviz_csv_path="data/finviz-inbox/finviz20May2026.csv",
        tickers_evaluated=5,
        aplus_count=0,
        watch_count=1,
        skip_count=0,
        excluded_count=4,
        error_count=0,
        rs_universe_version="rs-v1",
        rs_universe_hash="abc",
    ))
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token, evaluation_run_id)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00',
                'manual', '2026-05-19', '2026-05-20',
                'complete', 't-1', ?)
        """,
        (eval_run_id,),
    )
    pipeline_run_id = int(cur.lastrowid)
    insert_candidates(conn, eval_run_id, [
        Candidate(
            ticker=ticker, bucket="watch", close=120.0, pivot=120.5,
            initial_stop=100.0, adr_pct=4.0, tight_streak=3,
            pullback_pct=10.0, prior_trend_pct=35.0, rs_rank=85,
            rs_return_12w_vs_spy=0.18, rs_method="universe",
            pattern_tag="vcp", notes=None, criteria=(),
            sector="Technology", industry="Semiconductors",
        ),
    ])
    eval_id = evals_repo.insert_evaluation(conn, PatternEvaluation(
        id=None, pipeline_run_id=pipeline_run_id, ticker=ticker,
        pattern_class=pattern_class, detector_version="v1",
        geometric_score=0.55, geometric_score_json='{"criteria":[]}',
        composite_score=0.62,
        structural_evidence_json='{"criteria_pass":{}}',
        feature_distribution_log_json="{}",
        window_start_date="2026-04-01", window_end_date="2026-05-15",
        created_at="2026-05-20T09:01:00",
    ))
    return eval_run_id, pipeline_run_id, eval_id


def _req(
    *, ticker: str = "ABC", entry_path=EntryPath.HYP_RECS_BUTTON,
    candidate_id: int | None = None, pattern_evaluation_id: int | None = None,
) -> EntryRequest:
    return EntryRequest(
        ticker=ticker, entry_date="2026-05-20", entry_price=120.5,
        shares=5, initial_stop=100.0,
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
        rationale=EntryRationale.VCP_BREAKOUT.value,
        event_ts="2026-05-20T09:30:00",
        entry_path=entry_path,
        thesis="bullish on the setup",
        why_now="VCP completed today",
        invalidation_condition="break of 100",
        expected_scenario="20% in 4 weeks",
        premortem_technical="prior pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small",
        event_risk_present=0,
        event_handling="not_applicable",
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm","confident"]',
        market_regime="Bullish",
        catalyst="technical_only",
        manual_entry_confidence="normal",
        candidate_id=candidate_id,
        pattern_evaluation_id=pattern_evaluation_id,
    )


def test_record_entry_populates_candidate_id_for_pipeline_origin(tmp_path):
    """OQ-11: pipeline-origin trade populates candidate_id from candidates lookup."""
    conn = _seed_v21(tmp_path)
    try:
        eval_run_id, pipeline_run_id, eval_id = (
            _seed_pipeline_with_watch_candidate(conn)
        )
        result = record_entry(
            conn, _req(
                entry_path=EntryPath.HYP_RECS_BUTTON,
                pattern_evaluation_id=eval_id,
            ),
            soft_warn=10, hard_cap=20, force=False,
        )
        trade = get_trade(conn, result.trade_id)
    finally:
        conn.close()
    assert trade is not None
    # candidate_id populated from latest complete evaluation run lookup.
    assert trade.candidate_id is not None, (
        "OQ-11: pipeline-origin trade must populate candidate_id"
    )
    # pattern_evaluation_id threaded from request.
    assert trade.pattern_evaluation_id == eval_id


def test_record_entry_persists_null_candidate_id_for_manual_off_pipeline(tmp_path):
    """OQ-11 negative: manual_off_pipeline trade (no candidate row) → candidate_id NULL."""
    conn = _seed_v21(tmp_path)
    try:
        # No pipeline_runs / candidates seeded.
        result = record_entry(
            conn, _req(
                ticker="NEW", entry_path=EntryPath.MANUAL_WEB_FORM,
                candidate_id=None, pattern_evaluation_id=None,
            ),
            soft_warn=10, hard_cap=20, force=False,
        )
        trade = get_trade(conn, result.trade_id)
    finally:
        conn.close()
    assert trade is not None
    assert trade.candidate_id is None
    assert trade.pattern_evaluation_id is None
    assert trade.trade_origin == "manual_off_pipeline"


def test_record_entry_pattern_evaluation_id_threads_through(tmp_path):
    """OQ-12: explicit pattern_evaluation_id on EntryRequest persists verbatim."""
    conn = _seed_v21(tmp_path)
    try:
        eval_run_id, pipeline_run_id, eval_id = (
            _seed_pipeline_with_watch_candidate(conn)
        )
        result = record_entry(
            conn, _req(
                entry_path=EntryPath.HYP_RECS_BUTTON,
                pattern_evaluation_id=eval_id,
            ),
            soft_warn=10, hard_cap=20, force=False,
        )
        trade = get_trade(conn, result.trade_id)
    finally:
        conn.close()
    assert trade is not None
    assert trade.pattern_evaluation_id == eval_id
