"""Task 1 -- the fixture builders themselves are pinned against real shapes.

A fixture that drifts from the emitter is the synthetic-fixture-vs-production
gotcha family, and every downstream Demand-C test rests on these builders. So
the builders are asserted against the REAL roster constants and the REAL
label builder rather than against their own spelling.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.evaluation.scoring import (
    EXPECTED_TT_CRITERIA,
    EXPECTED_VCP_CRITERIA,
)
from swing.recommendations.hypothesis import _descriptive_label
from tests.trades._cohort_provenance_fixtures import (
    CADL_ACTION_SESSION,
    CADL_DATA_ASOF,
    CADL_F,
    CADL_FILL_DATETIME,
    CADL_LABEL,
    CADL_RUN_TS_LOCAL,
    CLEAN_APLUS_LABEL,
    H1_NAME,
    TT_CRITERIA,
    VCP_CRITERIA,
    build_cadl_case,
    rebase_status_history_recorded_at,
)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def test_criterion_rosters_match_the_real_evaluator_constants() -> None:
    """The fixture roster IS the evaluator's roster, not a copy that rots."""
    assert set(TT_CRITERIA) == set(EXPECTED_TT_CRITERIA)
    assert set(VCP_CRITERIA) == set(EXPECTED_VCP_CRITERIA)


def test_cadl_case_reproduces_the_live_row_shapes(
    conn: sqlite3.Connection,
) -> None:
    ids = build_cadl_case(conn)
    run = conn.execute(
        "SELECT run_ts, data_asof_date, action_session_date "
        "FROM evaluation_runs WHERE id = ?",
        (ids["evaluation_run_id"],),
    ).fetchone()
    # The two anchors DIFFER on the live case -- an equal pair would make the
    # section 3.2 discriminator vacuous.
    assert run == (CADL_RUN_TS_LOCAL, CADL_DATA_ASOF, CADL_ACTION_SESSION)
    assert run[1] != run[2]

    cand = conn.execute(
        "SELECT ticker, bucket FROM candidates WHERE id = ?",
        (ids["candidate_id"],),
    ).fetchone()
    assert cand == ("CADL", "aplus")

    non_pass = conn.execute(
        "SELECT criterion_name, result FROM candidate_criteria "
        "WHERE candidate_id = ? AND result <> 'pass'",
        (ids["candidate_id"],),
    ).fetchall()
    assert non_pass == [("TT8_rs_rank", "na")]
    total = conn.execute(
        "SELECT COUNT(*) FROM candidate_criteria WHERE candidate_id = ?",
        (ids["candidate_id"],),
    ).fetchone()[0]
    assert total == 18  # 8 TT + 9 VCP + 1 risk

    dr = conn.execute(
        "SELECT recommendation, evaluation_run_id, action_session_date "
        "FROM daily_recommendations WHERE id = ?",
        (ids["daily_recommendation_id"],),
    ).fetchone()
    assert dr == ("today_decision", ids["evaluation_run_id"],
                  CADL_ACTION_SESSION)

    fill = conn.execute(
        "SELECT fill_datetime, action FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()
    assert fill == (CADL_FILL_DATETIME, "entry")
    assert CADL_FILL_DATETIME[:10] == CADL_F

    trade = conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin, state "
        "FROM trades WHERE id = ?",
        (ids["trade_id"],),
    ).fetchone()
    assert trade == (None, None, "manual_off_pipeline", "entered")


def test_seeded_candidate_yields_the_faithful_derived_label(
    conn: sqlite3.Connection,
) -> None:
    """The fixture's criteria produce the RD-ruled suffix string, and a
    clean-criteria variant produces the sibling string -- so the suffix is a
    function of the record rather than a constant."""
    ids = build_cadl_case(conn)
    [cand] = [
        c for c in fetch_candidates_for_run(conn, ids["evaluation_run_id"])
    ]
    assert _descriptive_label(cand, H1_NAME) == CADL_LABEL

    clean = build_cadl_case(conn, non_pass={}, ticker="VSTS")
    [clean_cand] = [
        c for c in fetch_candidates_for_run(conn, clean["evaluation_run_id"])
    ]
    assert _descriptive_label(clean_cand, H1_NAME) == CLEAN_APLUS_LABEL


def test_rebase_makes_the_seeded_history_contemporaneous(
    conn: sqlite3.Connection,
) -> None:
    """Migration 0017 stamps `recorded_at` at APPLY time, which post-dates
    every fixture run_ts; the rebase helper is what makes an interval
    admissible, and its absence is what a retrospective-refusal test needs."""
    before = conn.execute(
        "SELECT recorded_at FROM hypothesis_status_history WHERE history_id=1",
    ).fetchone()[0]
    assert before > CADL_RUN_TS_LOCAL  # today's stamp, i.e. retrospective
    rebase_status_history_recorded_at(conn)
    after = conn.execute(
        "SELECT recorded_at FROM hypothesis_status_history WHERE history_id=1",
    ).fetchone()[0]
    assert after == "2026-04-25T00:00:00.000"
    assert after < CADL_RUN_TS_LOCAL


def test_pipeline_window_carries_the_live_local_clock_gap(
    conn: sqlite3.Connection,
) -> None:
    ids = build_cadl_case(conn)
    started, finished, state = conn.execute(
        "SELECT started_ts, finished_ts, state FROM pipeline_runs WHERE id = ?",
        (ids["pipeline_run_id"],),
    ).fetchone()
    assert state == "complete"
    assert started == "2026-08-10T17:30:00"
    assert finished == "2026-08-10T17:44:45"
    # 14m19s between run_ts and finished_ts -- the real CADL uncertainty
    # window the as-of status rule closes over.
    assert CADL_RUN_TS_LOCAL == "2026-08-10T17:30:26"
