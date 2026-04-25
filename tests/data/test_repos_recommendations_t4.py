"""Tranche C T4: list_for_session accepts evaluation_run_id filter (Bug 7).

The dashboard's today_decisions panel previously read by action_session_date
alone, allowing a standalone `swing eval` run within the same session to
poison the result. After T4, the dashboard binds today_decisions to the
pipeline's own eval (via pipeline_runs.evaluation_run_id), eliminating the
mixed-anchor bug structurally. The repo function must support both modes:
new code passes the FK; legacy callers still use the date-only filter.
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import DailyRecommendation, EvaluationRun
from swing.data.repos.candidates import insert_evaluation_run
from swing.data.repos.recommendations import list_for_session, upsert_recommendation


def _seed_run(conn, *, run_ts: str, action_session: str = "2026-04-16") -> int:
    er = EvaluationRun(
        id=None, run_ts=run_ts,
        data_asof_date="2026-04-15", action_session_date=action_session,
        finviz_csv_path="x.csv", tickers_evaluated=1,
        aplus_count=1, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0,
        rs_universe_version="2026-04-17-1", rs_universe_hash="abcd",
    )
    with conn:
        return insert_evaluation_run(conn, er)


def _rec(
    eval_id: int, *, ticker: str, reco: str = "today_decision",
    action_session: str = "2026-04-16",
) -> DailyRecommendation:
    return DailyRecommendation(
        id=None, evaluation_run_id=eval_id, data_asof_date="2026-04-15",
        action_session_date=action_session, ticker=ticker,
        recommendation=reco, action_text=f"Buy-stop $100",
        entry_target=100.0, stop_target=95.0, shares=1,
        risk_dollars=5.0, risk_pct=0.5, rationale="vcp",
    )


def test_list_for_session_without_eval_filter_preserves_legacy_behavior(
    tmp_path: Path,
):
    """No evaluation_run_id arg → existing date-only filter, both evals'
    recs returned (the pre-T4 mixed-anchor failure mode, retained for
    legacy callers and for the legacy NULL-FK fallback path)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        e1 = _seed_run(conn, run_ts="2026-04-15T21:00:00")
        e2 = _seed_run(conn, run_ts="2026-04-15T22:00:00")
        with conn:
            upsert_recommendation(conn, _rec(e1, ticker="AAPL"))
            upsert_recommendation(conn, _rec(e2, ticker="NVDA"))
        rows = list_for_session(conn, "2026-04-16")
        # Both evals' recs are present (UNIQUE constraint allows because
        # ticker differs). Date-only filter returns the union.
        assert {r.ticker for r in rows} == {"AAPL", "NVDA"}
    finally:
        conn.close()


def test_list_for_session_with_eval_filter_scopes_to_that_eval_only(
    tmp_path: Path,
):
    """Bug 7 fix: when evaluation_run_id is passed, only that eval's recs
    are returned, regardless of what other evals wrote for the same session."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        e1 = _seed_run(conn, run_ts="2026-04-15T21:00:00")
        e2 = _seed_run(conn, run_ts="2026-04-15T22:00:00")
        with conn:
            upsert_recommendation(conn, _rec(e1, ticker="AAPL"))
            upsert_recommendation(conn, _rec(e2, ticker="NVDA"))
        rows = list_for_session(conn, "2026-04-16", evaluation_run_id=e1)
        assert {r.ticker for r in rows} == {"AAPL"}
        rows = list_for_session(conn, "2026-04-16", evaluation_run_id=e2)
        assert {r.ticker for r in rows} == {"NVDA"}
    finally:
        conn.close()


def test_list_for_session_eval_filter_empty_when_no_matching_recs(
    tmp_path: Path,
):
    """Defensive: filtering by an eval id that has no recs in the session
    returns an empty list rather than raising."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        e1 = _seed_run(conn, run_ts="2026-04-15T21:00:00")
        e2 = _seed_run(conn, run_ts="2026-04-15T22:00:00")
        with conn:
            upsert_recommendation(conn, _rec(e1, ticker="AAPL"))
        # e2 has no recs.
        rows = list_for_session(conn, "2026-04-16", evaluation_run_id=e2)
        assert rows == []
    finally:
        conn.close()


def test_list_for_session_eval_filter_does_not_leak_other_session(
    tmp_path: Path,
):
    """Eval filter + session filter are AND-ed: a rec from e1 written for
    session B doesn't leak into a query for session A even when e1 matches."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        e1 = _seed_run(
            conn, run_ts="2026-04-15T21:00:00", action_session="2026-04-16",
        )
        with conn:
            upsert_recommendation(
                conn, _rec(e1, ticker="AAPL", action_session="2026-04-17"),
            )
        rows = list_for_session(conn, "2026-04-16", evaluation_run_id=e1)
        assert rows == []
        rows2 = list_for_session(conn, "2026-04-17", evaluation_run_id=e1)
        assert {r.ticker for r in rows2} == {"AAPL"}
    finally:
        conn.close()
