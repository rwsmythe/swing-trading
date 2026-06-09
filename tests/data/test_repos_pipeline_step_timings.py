# tests/data/test_repos_pipeline_step_timings.py
from __future__ import annotations

from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from swing.data.db import connect, ensure_schema
from swing.data.repos.pipeline_step_timings import (
    StepTiming,
    insert_step_timings,
    list_step_timings,
    step_durations_by_name,
)
from swing.pipeline.lease import acquire_lease


@pytest.fixture
def db_path(tmp_path):
    # ensure_schema migrates to EXPECTED_SCHEMA_VERSION (25).
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


@pytest.fixture
def conn(db_path):
    c = connect(db_path)  # same tmp_path -> same DB file as db_path
    yield c
    c.close()


def _run_id(db_path) -> int:
    """Create a real pipeline_runs row via the production lease path (satisfies all
    NOT-NULL columns: data_asof_date, action_session_date, lease_token, ...)."""
    lease = acquire_lease(
        db_path=db_path, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )
    return lease.run_id


def test_round_trip_preserves_order(conn, db_path):
    rid = _run_id(db_path)
    rows = [
        StepTiming(0, "finviz_fetch", "2026-06-09T00:00:00", "2026-06-09T00:00:01", 500),
        StepTiming(1, "weather", "2026-06-09T00:00:01", "2026-06-09T00:00:01", 200),
        StepTiming(2, "finviz_fetch", "2026-06-09T00:00:01", "2026-06-09T00:00:01", 30),
    ]
    with conn:
        insert_step_timings(conn, rid, rows)
    back = list_step_timings(conn, rid)
    assert [r.ordinal for r in back] == [0, 1, 2]
    assert back == rows


def test_durations_by_name_sums_repeated_step(conn, db_path):
    rid = _run_id(db_path)
    with conn:
        insert_step_timings(conn, rid, [
            StepTiming(0, "finviz_fetch", "t", "t", 500),
            StepTiming(1, "weather", "t", "t", 200),
            StepTiming(2, "finviz_fetch", "t", "t", 30),
        ])
    totals = step_durations_by_name(conn, rid)
    # CORRECT (SUM GROUP BY): finviz_fetch = 500 + 30 = 530.
    # NAIVE (one-row-per-name / last-wins): finviz_fetch = 30.  530 != 30 distinguishes.
    assert totals["finviz_fetch"] == 530
    assert totals["weather"] == 200
    assert list(totals) == ["finviz_fetch", "weather"]  # chronological by MIN(ordinal)


def test_idempotent_reinsert_on_conflict(conn, db_path):
    rid = _run_id(db_path)
    rows = [StepTiming(0, "evaluate", "t", "t", 10)]
    with conn:
        insert_step_timings(conn, rid, rows)
    with conn:
        insert_step_timings(conn, rid, rows)  # ON CONFLICT(run_id, ordinal) DO NOTHING
    assert len(list_step_timings(conn, rid)) == 1
