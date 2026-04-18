"""Round-trip test for candidates repo."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import (
    fetch_candidates_for_run,
    insert_candidates,
    insert_evaluation_run,
)


def test_insert_candidate_with_no_criteria_roundtrips(tmp_db: Path):
    """Excluded/error candidates have criteria=(); fetch must not break."""
    conn = ensure_schema(tmp_db)
    run = EvaluationRun(
        id=None,
        run_ts="2026-04-17T21:49:00",
        data_asof_date="2026-04-17",
        action_session_date="2026-04-20",
        finviz_csv_path=None,
        tickers_evaluated=1,
        aplus_count=0,
        watch_count=0,
        skip_count=0,
        excluded_count=1,
        error_count=0,
    )
    run_id = insert_evaluation_run(conn, run)
    insert_candidates(
        conn,
        run_id,
        [
            Candidate(
                ticker="UCO",
                bucket="excluded",
                close=None,
                pivot=None,
                initial_stop=None,
                adr_pct=None,
                tight_streak=None,
                pullback_pct=None,
                prior_trend_pct=None,
                rs_rank=None,
                rs_return_12w_vs_spy=None,
                rs_method="unavailable",
                pattern_tag=None,
                notes="ETF blocklist",
                criteria=(),
            ),
        ],
    )
    fetched = fetch_candidates_for_run(conn, run_id)
    assert len(fetched) == 1
    assert fetched[0].bucket == "excluded"
    assert fetched[0].criteria == ()
    assert fetched[0].notes == "ETF blocklist"
    conn.close()


def test_insert_run_and_candidates_roundtrip(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    run = EvaluationRun(
        id=None,
        run_ts="2026-04-17T21:49:00",
        data_asof_date="2026-04-17",
        action_session_date="2026-04-20",
        finviz_csv_path="data/finviz-inbox/finviz17Apr2026.csv",
        tickers_evaluated=2,
        aplus_count=1,
        watch_count=1,
        skip_count=0,
        excluded_count=0,
        error_count=0,
    )
    run_id = insert_evaluation_run(conn, run)
    assert run_id > 0

    candidates = [
        Candidate(
            ticker="CE",
            bucket="aplus",
            close=68.34,
            pivot=68.65,
            initial_stop=58.77,
            adr_pct=4.66,
            tight_streak=2,
            pullback_pct=22.3,
            prior_trend_pct=304.6,
            rs_rank=82,
            rs_return_12w_vs_spy=0.18,
            rs_method="universe",
            pattern_tag="HTF",
            notes=None,
            criteria=(
                CriterionResult("prior_trend", "vcp", "pass", "304.6%", ">= 25%"),
                CriterionResult("TT1_above_150_200", "trend_template", "pass", "close > 150MA, 200MA", ""),
            ),
        ),
        Candidate(
            ticker="UNIT",
            bucket="watch",
            close=11.06,
            pivot=11.19,
            initial_stop=9.66,
            adr_pct=4.95,
            tight_streak=0,
            pullback_pct=18.1,
            prior_trend_pct=45.0,
            rs_rank=55,
            rs_return_12w_vs_spy=0.04,
            rs_method="universe",
            pattern_tag=None,
            notes=None,
            criteria=(
                CriterionResult("tightness", "vcp", "fail", "0 day streak", ">= 2 days"),
            ),
        ),
    ]
    insert_candidates(conn, run_id, candidates)

    fetched = fetch_candidates_for_run(conn, run_id)
    assert len(fetched) == 2
    by_ticker = {c.ticker: c for c in fetched}
    assert by_ticker["CE"].bucket == "aplus"
    assert by_ticker["CE"].rs_method == "universe"
    assert len(by_ticker["CE"].criteria) == 2
    assert by_ticker["UNIT"].bucket == "watch"
    assert by_ticker["UNIT"].criteria[0].result == "fail"
    conn.close()
