"""Phase 13 T2.SB1 T-A.1.1b — pattern_evaluations repo CRUD discriminating tests.

Per plan §G.1 T-A.1.1b Step 1: 3 discriminating tests covering
(a) insert_row roundtrips through SQL; (b) get_by_id returns inserted row;
(c) list_* paginates correctly. Caller-tx contract verified.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as repo


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb1_repo_evaluations.db"
    return ensure_schema(db_path)


@pytest.fixture
def pipeline_run_id(conn: sqlite3.Connection) -> int:
    """Seed a pipeline_runs row for FK references."""
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2024-02-02T00:00:00.000', 'manual', '2024-02-01', "
            "'2024-02-02', 'complete', 'tok')"
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _make_eval(pipeline_run_id: int, **overrides: object) -> PatternEvaluation:
    base = {
        "id": None,
        "pipeline_run_id": pipeline_run_id,
        "ticker": "ABC",
        "pattern_class": "vcp",
        "detector_version": "vcp-v1.0",
        "geometric_score": 0.8,
        "geometric_score_json": "{\"score\": 0.8}",
        "composite_score": 0.8,
        "structural_evidence_json": "{}",
        "feature_distribution_log_json": "{}",
        "window_start_date": "2024-01-01",
        "window_end_date": "2024-02-01",
        "created_at": "2024-02-02T00:00:00.000",
    }
    base.update(overrides)
    return PatternEvaluation(**base)


def test_insert_pattern_evaluation_roundtrips_through_sql(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """insert_evaluation persists; SELECT post-INSERT returns matching values."""
    ev = _make_eval(pipeline_run_id, ticker="XYZ", composite_score=0.95)
    with conn:
        ev_id = repo.insert_evaluation(conn, ev)
    row = conn.execute(
        "SELECT ticker, pattern_class, geometric_score, composite_score "
        "FROM pattern_evaluations WHERE id = ?",
        (ev_id,),
    ).fetchone()
    assert row == ("XYZ", "vcp", 0.8, 0.95)


def test_get_pattern_evaluation_by_id_returns_inserted_row(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """get_evaluation_by_id reconstructs the dataclass; None on missing."""
    ev = _make_eval(pipeline_run_id, ticker="MMM", pattern_class="flat_base")
    with conn:
        ev_id = repo.insert_evaluation(conn, ev)

    fetched = repo.get_evaluation_by_id(conn, ev_id)
    assert fetched is not None
    assert fetched.ticker == "MMM"
    assert fetched.pattern_class == "flat_base"
    assert fetched.pipeline_run_id == pipeline_run_id

    assert repo.get_evaluation_by_id(conn, 999_999) is None


def test_list_pattern_evaluations_paginates_correctly(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """list_evaluations + per-column filters + limit/offset pagination."""
    with conn:
        for i, pclass in enumerate(
            ["vcp", "flat_base", "vcp", "cup_with_handle", "vcp"]
        ):
            ev = _make_eval(
                pipeline_run_id, ticker=f"T{i}", pattern_class=pclass,
            )
            repo.insert_evaluation(conn, ev)

    # No filter: all 5.
    all_rows = repo.list_evaluations(conn)
    assert len(all_rows) == 5

    # ticker filter.
    t0_rows = repo.list_evaluations(conn, ticker="T0")
    assert len(t0_rows) == 1

    # pattern_class filter.
    vcp_rows = repo.list_evaluations(conn, pattern_class="vcp")
    assert len(vcp_rows) == 3

    # pipeline_run_id filter.
    run_rows = repo.list_evaluations(conn, pipeline_run_id=pipeline_run_id)
    assert len(run_rows) == 5

    # Pagination.
    first_two = repo.list_evaluations(conn, limit=2, offset=0)
    assert len(first_two) == 2
    next_two = repo.list_evaluations(conn, limit=2, offset=2)
    assert next_two[0].id > first_two[1].id


def test_repo_does_not_commit_within_function(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Caller-tx contract: rollback undoes insert."""
    ev = _make_eval(pipeline_run_id, ticker="ROLLED_BACK")
    conn.execute("BEGIN")
    repo.insert_evaluation(conn, ev)
    conn.rollback()
    assert repo.list_evaluations(conn, ticker="ROLLED_BACK") == []
