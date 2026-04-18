"""Daily recommendations repo: upsert + get_for_session."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import DailyRecommendation, EvaluationRun
from swing.data.repos.candidates import insert_evaluation_run
from swing.data.repos.recommendations import upsert_recommendation, list_for_session


def _seed_run(conn) -> int:
    er = EvaluationRun(
        id=None, run_ts="2026-04-15T21:49:00",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        finviz_csv_path="x.csv", tickers_evaluated=1,
        aplus_count=1, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0,
        rs_universe_version="2026-04-17-1", rs_universe_hash="abcd",
    )
    with conn:
        return insert_evaluation_run(conn, er)


def _rec(eval_id: int, ticker: str = "NVDA", reco: str = "today_decision") -> DailyRecommendation:
    return DailyRecommendation(
        id=None, evaluation_run_id=eval_id, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", ticker=ticker,
        recommendation=reco, action_text=f"Buy-stop $850 \u00b7 2 sh",
        entry_target=850.0, stop_target=820.0, shares=2,
        risk_dollars=60.0, risk_pct=0.5, rationale="VCP coil",
    )


def test_upsert_and_list(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        eid = _seed_run(conn)
        with conn:
            upsert_recommendation(conn, _rec(eid, "NVDA"))
            upsert_recommendation(conn, _rec(eid, "AAPL"))

        rows = list_for_session(conn, "2026-04-16")
        assert {r.ticker for r in rows} == {"NVDA", "AAPL"}
    finally:
        conn.close()


def test_upsert_replaces_on_conflict(tmp_path: Path):
    """Re-running pipeline for same session must update in place, not duplicate."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        eid = _seed_run(conn)
        with conn:
            upsert_recommendation(conn, _rec(eid))

        # Update entry_target - same key triple
        updated = DailyRecommendation(
            id=None, evaluation_run_id=eid, data_asof_date="2026-04-15",
            action_session_date="2026-04-16", ticker="NVDA",
            recommendation="today_decision", action_text="Buy-stop $852 \u00b7 2 sh",
            entry_target=852.0, stop_target=820.0, shares=2,
            risk_dollars=64.0, risk_pct=0.53, rationale="updated pivot",
        )
        with conn:
            upsert_recommendation(conn, updated)

        rows = list_for_session(conn, "2026-04-16")
        assert len(rows) == 1
        assert rows[0].entry_target == 852.0
        assert "852" in rows[0].action_text
    finally:
        conn.close()
