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
    with conn:
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
    with conn:
        run_id = insert_evaluation_run(conn, run)
        assert run_id > 0
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


def test_candidate_sector_industry_roundtrip(tmp_db):
    """A Candidate with sector + industry inserted via insert_candidates is
    fetched back with both fields populated AS-IS. Distinct values
    ("Healthcare" / "Biotechnology") chosen to discriminate against any
    test fixture default that might mask a passthrough bug."""
    conn = ensure_schema(tmp_db)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-04-28T00:00:00",
                data_asof_date="2026-04-25", action_session_date="2026-04-28",
                finviz_csv_path=None,
                tickers_evaluated=1, aplus_count=0, watch_count=1,
                skip_count=0, excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="ZZZA", bucket="watch",
                    close=100.0, pivot=105.0, initial_stop=95.0,
                    adr_pct=2.0, tight_streak=5, pullback_pct=None,
                    prior_trend_pct=None, rs_rank=None,
                    rs_return_12w_vs_spy=None, rs_method="fallback_spy",
                    pattern_tag=None, notes=None,
                    criteria=(),
                    sector="Healthcare", industry="Biotechnology",
                ),
            ])
        rows = fetch_candidates_for_run(conn, run_id)
        assert len(rows) == 1
        assert rows[0].ticker == "ZZZA"
        assert rows[0].sector == "Healthcare"
        assert rows[0].industry == "Biotechnology"
    finally:
        conn.close()


def test_candidate_default_sector_industry_empty(tmp_path):
    """A Candidate constructed without explicit sector/industry uses empty
    strings as defaults — preserves call sites that don't carry these fields."""
    from swing.data.models import Candidate
    c = Candidate(
        ticker="DFLT", bucket="watch",
        close=None, pivot=None, initial_stop=None,
        adr_pct=None, tight_streak=None, pullback_pct=None,
        prior_trend_pct=None, rs_rank=None,
        rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes=None, criteria=(),
    )
    assert c.sector == ""
    assert c.industry == ""
