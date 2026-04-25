"""Production-DB read tests for the Finviz-pool analysis fetcher.

Uses an in-memory schema-applied SQLite DB seeded with a tiny set of
``evaluation_runs`` rows; finviz_csv_path resolution against a tmp
inbox directory. No real production data needed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research.finviz_pool_analysis.fetcher import (
    QualifyingRun,
    SkippedRun,
    fetch_run_candidates_with_criteria,
    list_qualifying_evaluation_runs,
)
from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run


@pytest.fixture
def schema_db(tmp_path) -> Path:
    db_path = tmp_path / "fpa.db"
    conn = ensure_schema(db_path)
    conn.close()
    return db_path


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _insert_run(
    conn: sqlite3.Connection,
    *,
    run_ts: str,
    finviz_csv_path: str | None,
    action_session: str = "2026-04-21",
    data_asof: str = "2026-04-20",
) -> int:
    return insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts=run_ts,
            data_asof_date=data_asof,
            action_session_date=action_session,
            finviz_csv_path=finviz_csv_path,
            tickers_evaluated=0,
            aplus_count=0,
            watch_count=0,
            skip_count=0,
            excluded_count=0,
            error_count=0,
        ),
    )


def _make_inbox(tmp_path: Path, *, top: list[str] = (), rejected: list[str] = ()) -> Path:
    inbox = tmp_path / "finviz-inbox"
    (inbox / "rejected").mkdir(parents=True)
    for name in top:
        (inbox / name).write_text("ignored\n")
    for name in rejected:
        (inbox / "rejected" / name).write_text("ignored\n")
    return inbox


def test_qualifying_run_resolves_top_level_csv(schema_db, tmp_path):
    inbox = _make_inbox(tmp_path, top=["finviz20Apr2026.csv"])
    with _conn(schema_db) as conn:
        rid = _insert_run(
            conn, run_ts="2026-04-20T15:00", finviz_csv_path="data/finviz-inbox/finviz20Apr2026.csv"
        )
    with _conn(schema_db) as conn:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, inbox)
    assert len(qualifying) == 1 and len(skipped) == 0
    assert qualifying[0].run_id == rid
    assert qualifying[0].finviz_csv_basename == "finviz20Apr2026.csv"
    assert qualifying[0].resolved_location == "inbox"


def test_qualifying_run_resolves_rejected_subdir(schema_db, tmp_path):
    inbox = _make_inbox(tmp_path, rejected=["finviz20Apr2026.csv"])
    with _conn(schema_db) as conn:
        _insert_run(
            conn, run_ts="2026-04-20T15:00", finviz_csv_path="data/finviz-inbox/finviz20Apr2026.csv"
        )
    with _conn(schema_db) as conn:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, inbox)
    assert len(qualifying) == 1 and len(skipped) == 0
    assert qualifying[0].resolved_location == "rejected"


def test_skipped_run_csv_missing(schema_db, tmp_path):
    inbox = _make_inbox(tmp_path)  # empty
    with _conn(schema_db) as conn:
        rid = _insert_run(
            conn, run_ts="2026-04-20T15:00", finviz_csv_path="data/finviz-inbox/finviz16Apr2026.csv"
        )
    with _conn(schema_db) as conn:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, inbox)
    assert len(qualifying) == 0 and len(skipped) == 1
    assert skipped[0].run_id == rid
    assert skipped[0].reason == "csv_missing"
    assert skipped[0].finviz_csv_basename == "finviz16Apr2026.csv"


def test_skipped_run_csv_path_null(schema_db, tmp_path):
    inbox = _make_inbox(tmp_path)
    with _conn(schema_db) as conn:
        _insert_run(conn, run_ts="2026-04-20T15:00", finviz_csv_path=None)
    with _conn(schema_db) as conn:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, inbox)
    assert len(qualifying) == 0 and len(skipped) == 1
    assert skipped[0].reason == "csv_path_null"


def test_basename_extraction_handles_windows_absolute_path(schema_db, tmp_path):
    """Production stores Drive-absolute Windows paths with backslashes;
    Path(...).name does NOT split on '\\' under POSIX. The fetcher must
    extract basename correctly regardless of platform."""
    inbox = _make_inbox(tmp_path, top=["finviz23Apr2026.csv"])
    win_path = r"C:\Users\rwsmy\My Drive\Swing Trading\data\finviz-inbox\finviz23Apr2026.csv"
    with _conn(schema_db) as conn:
        _insert_run(conn, run_ts="2026-04-23T20:00", finviz_csv_path=win_path)
    with _conn(schema_db) as conn:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, inbox)
    assert len(qualifying) == 1
    assert qualifying[0].finviz_csv_basename == "finviz23Apr2026.csv"


def test_qualifying_runs_ordered_by_run_id(schema_db, tmp_path):
    inbox = _make_inbox(tmp_path, top=["a.csv", "b.csv"])
    with _conn(schema_db) as conn:
        rid_a = _insert_run(
            conn, run_ts="2026-04-20T08:00", finviz_csv_path="data/finviz-inbox/a.csv"
        )
        rid_b = _insert_run(
            conn, run_ts="2026-04-20T20:00", finviz_csv_path="data/finviz-inbox/b.csv"
        )
    with _conn(schema_db) as conn:
        qualifying, _ = list_qualifying_evaluation_runs(conn, inbox)
    assert [r.run_id for r in qualifying] == [rid_a, rid_b]


def test_fetch_run_candidates_returns_candidates_with_criteria(schema_db, tmp_path):
    crits = (
        CriterionResult("TT1_above_150_200", "trend_template", "pass"),
        CriterionResult("risk_feasibility", "risk", "fail"),
    )
    cand = Candidate(
        ticker="ABCD",
        bucket="skip",
        close=10.0,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=crits,
    )
    with _conn(schema_db) as conn:
        rid = _insert_run(
            conn, run_ts="2026-04-20T15:00", finviz_csv_path="data/finviz-inbox/x.csv"
        )
        insert_candidates(conn, rid, [cand])
    with _conn(schema_db) as conn:
        rows = fetch_run_candidates_with_criteria(conn, rid)
    assert len(rows) == 1
    assert rows[0].ticker == "ABCD"
    assert {c.criterion_name for c in rows[0].criteria} == {
        "TT1_above_150_200",
        "risk_feasibility",
    }
