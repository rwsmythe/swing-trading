"""Repo for the pipeline_step_timings child table (Arc-1 spec §5.5).

(run_id, step_name) is NOT unique: finviz_fetch yields two rows. Consumers MUST
sum duration_ms grouped by step_name -- step_durations_by_name does this so no
caller hand-rolls (and forgets) the aggregation.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class StepTiming:
    ordinal: int
    step_name: str
    started_ts: str
    finished_ts: str
    duration_ms: int


def _row_to_step_timing(row: tuple) -> StepTiming:
    # connect() sets NO row_factory -> rows are tuples; positional access matches
    # the existing repo convention (swing/data/repos/pipeline.py uses row[N]).
    # Column order matches the SELECT in list_step_timings.
    return StepTiming(
        ordinal=row[0],
        step_name=row[1],
        started_ts=row[2],
        finished_ts=row[3],
        duration_ms=row[4],
    )


def insert_step_timings(
    conn: sqlite3.Connection, run_id: int, timings: Sequence[StepTiming],
) -> None:
    """Batch insert. ON CONFLICT(run_id, ordinal) DO NOTHING keeps the table
    append-only against a re-flush by a separate Lease/process for the same run."""
    conn.executemany(
        "INSERT INTO pipeline_step_timings "
        "(run_id, ordinal, step_name, started_ts, finished_ts, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, ordinal) DO NOTHING",
        [
            (run_id, t.ordinal, t.step_name, t.started_ts, t.finished_ts, t.duration_ms)
            for t in timings
        ],
    )


def list_step_timings(conn: sqlite3.Connection, run_id: int) -> list[StepTiming]:
    """Raw per-ordinal rows, chronological. Preserves the two finviz_fetch rows
    for forensic ordering. ORDER BY ordinal ASC is explicit (SQLite does not
    guarantee row order otherwise)."""
    cur = conn.execute(
        "SELECT ordinal, step_name, started_ts, finished_ts, duration_ms "
        "FROM pipeline_step_timings WHERE run_id = ? ORDER BY ordinal ASC",
        (run_id,),
    )
    return [_row_to_step_timing(r) for r in cur.fetchall()]


def step_durations_by_name(conn: sqlite3.Connection, run_id: int) -> dict[str, int]:
    """SUM(duration_ms) GROUP BY step_name, ordered by first appearance. The
    mandatory aggregator -- do NOT assume one row per step_name."""
    cur = conn.execute(
        "SELECT step_name, SUM(duration_ms) AS total_ms "
        "FROM pipeline_step_timings WHERE run_id = ? "
        "GROUP BY step_name ORDER BY MIN(ordinal) ASC",
        (run_id,),
    )
    # Tuple rows (no row_factory): step_name=r[0], total_ms=r[1].
    return {r[0]: int(r[1]) for r in cur.fetchall()}
