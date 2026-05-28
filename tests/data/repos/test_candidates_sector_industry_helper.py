"""Discriminating tests for ``get_latest_sector_industry_per_ticker``
(Phase 14 Sub-bundle 1 V2.G3 backfill helper).

Per CLAUDE.md cumulative gotcha #17 (Expansion #2 refinement) + forward-binding
lesson #1 -- signature contract pinned via inspect.signature.

Tests cover spec section 4.3 + 4.5 discriminating-example walkthroughs.
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from swing.data.db import ensure_schema
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import (
    CandidateSectorIndustryRecord,
    get_latest_sector_industry_per_ticker,
    insert_candidates,
    insert_evaluation_run,
)


def _build_candidate_fixture(ticker: str) -> dict[str, Any]:
    """Return Candidate kwargs minus ticker/sector/industry. Production-shape
    defaults populated for all required dataclass fields per the
    `Synthetic-fixture-vs-production-emitter shape drift` discipline.
    """
    return {
        "bucket": "watch",
        "close": 25.0,
        "pivot": 26.0,
        "initial_stop": 24.0,
        "adr_pct": 3.5,
        "tight_streak": 5,
        "pullback_pct": 4.0,
        "prior_trend_pct": 40.0,
        "rs_rank": 80,
        "rs_return_12w_vs_spy": 0.15,
        "rs_method": "universe",
        "pattern_tag": None,
        "notes": None,
        "criteria": (),
    }


def _open_conn(tmp_path):
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    return conn


def test_signature_contract_signature_pinned():
    """Lock signature: get_latest_sector_industry_per_ticker(conn, tickers)
    returns dict[str, CandidateSectorIndustryRecord] per spec section 4.3
    + Codex R1.M#6 LOCK (provenance metadata carried via the record)."""
    sig = inspect.signature(get_latest_sector_industry_per_ticker)
    params = list(sig.parameters.values())
    assert len(params) == 2, f"expected 2 params, got {len(params)}"
    assert params[0].name == "conn"
    assert params[1].name == "tickers"
    hints = get_type_hints(get_latest_sector_industry_per_ticker)
    # Sequence[str] tickers; dict[str, CandidateSectorIndustryRecord] return
    # (Codex R1.M#6 LOCK -- provenance metadata carried so the V2.G3 dry-run
    # table can cite source_candidate_id + source_evaluation_run_id).
    assert hints["return"] == dict[str, CandidateSectorIndustryRecord]


def test_empty_input_returns_empty_dict_without_sql(tmp_path):
    """Empty tickers list short-circuits per CLAUDE.md gotcha #20."""
    conn = _open_conn(tmp_path)
    try:
        result = get_latest_sector_industry_per_ticker(conn, [])
        assert result == {}
    finally:
        conn.close()


def test_happy_path_single_ticker_returns_non_empty_pair(tmp_path):
    """VSAT in candidates with non-empty Sector + Industry; helper
    returns the non-empty pair (spec section 4.5 example #1)."""
    conn = _open_conn(tmp_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26", action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [Candidate(
                ticker="VSAT",
                sector="Technology",
                industry="Communications Equipment",
                **_build_candidate_fixture("VSAT"),
            )])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        # Provenance present (Codex R1.M#6 LOCK).
        assert result["VSAT"].candidate_id is not None
        assert result["VSAT"].evaluation_run_id == run_id
    finally:
        conn.close()


def test_multi_ticker_mixed_qualifying_returns_per_ticker_results(tmp_path):
    """Plant VSAT (qualifies); DHA (no candidates row); assert VSAT pair
    returned + DHA maps to ('', '') (spec section 4.5 example #3 + #4)."""
    conn = _open_conn(tmp_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26", action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(ticker="VSAT", sector="Technology",
                          industry="Communications Equipment",
                          **_build_candidate_fixture("VSAT")),
            ])
        result = get_latest_sector_industry_per_ticker(
            conn, ["VSAT", "DHA"],
        )
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        assert result["VSAT"].evaluation_run_id == run_id
        # DHA is the no-match sentinel: empty strings + None provenance
        # (Codex R1.M#6 LOCK).
        assert result["DHA"].sector == ""
        assert result["DHA"].industry == ""
        assert result["DHA"].candidate_id is None
        assert result["DHA"].evaluation_run_id is None
    finally:
        conn.close()


def test_partial_empty_candidate_row_excluded_from_qualifying_pool(tmp_path):
    """Candidate row with sector='Tech', industry='' must NOT qualify
    (AND-empty filter per spec section 4.3 R2.M3 LOCK)."""
    conn = _open_conn(tmp_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26", action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(ticker="VSAT", sector="Technology", industry="",
                          **_build_candidate_fixture("VSAT")),
            ])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        # VSAT's only candidates row has industry=''; helper excludes
        # via AND-empty WHERE clause + ticker maps to the no-match
        # sentinel (empty strings + None provenance per Codex R1.M#6).
        assert result["VSAT"].sector == ""
        assert result["VSAT"].industry == ""
        assert result["VSAT"].candidate_id is None
        assert result["VSAT"].evaluation_run_id is None
    finally:
        conn.close()


def test_ordering_most_recent_evaluation_run_id_wins(tmp_path):
    """Plant 2 candidates rows for VSAT across different evaluation_run_ids;
    helper returns the row with the HIGHER evaluation_run_id (most-recent
    per spec section 4.3 SQL ORDER BY)."""
    conn = _open_conn(tmp_path)
    try:
        with conn:
            # First (older) run.
            old_run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-20T20:00:00",
                data_asof_date="2026-05-19", action_session_date="2026-05-20",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, old_run_id, [
                Candidate(ticker="VSAT", sector="OldSector",
                          industry="OldIndustry",
                          **_build_candidate_fixture("VSAT")),
            ])
            # Second (newer) run.
            new_run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26", action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, new_run_id, [
                Candidate(ticker="VSAT", sector="NewSector",
                          industry="NewIndustry",
                          **_build_candidate_fixture("VSAT")),
            ])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "NewSector"
        assert result["VSAT"].industry == "NewIndustry"
        # Provenance points at the NEWER run (Codex R1.M#6 LOCK).
        assert result["VSAT"].evaluation_run_id == new_run_id
    finally:
        conn.close()


def test_historical_only_candidates_row_picked_when_no_recent(tmp_path):
    """Plant ONLY an older candidates row for VSAT; helper picks it
    (spec section 4.5 example #2 -- VSAT historical post-rotation)."""
    conn = _open_conn(tmp_path)
    try:
        with conn:
            old_run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-01T20:00:00",
                data_asof_date="2026-04-30", action_session_date="2026-05-01",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, old_run_id, [
                Candidate(ticker="VSAT", sector="Technology",
                          industry="Communications Equipment",
                          **_build_candidate_fixture("VSAT")),
            ])
        # No newer run for VSAT (rotated out of finviz screen).
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        # Provenance still cites the historical run (Codex R1.M#6).
        assert result["VSAT"].evaluation_run_id == old_run_id
    finally:
        conn.close()


def test_helper_module_source_is_ascii_only():
    """Per gotcha #32 + spec section 15.2 ASCII discipline scope:
    swing/data/repos/candidates.py + this test module ASCII-only."""
    from pathlib import Path

    import swing.data.repos.candidates as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    src.encode("ascii")  # raises UnicodeEncodeError on any non-ASCII
    test_src = Path(__file__).read_text(encoding="utf-8")
    test_src.encode("ascii")
