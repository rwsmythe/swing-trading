"""Phase 13 T-T4.SB.3 (Item 5; OQ-5.1 R4 LOCK) — chart_renders cache prune helper.

Operator-locked manual prune CLI for `chart_renders` rows older than a
threshold (in days). The cache is otherwise unbounded by design (V1
default behavior); operator invokes this CLI when monitoring shows
unbounded growth (e.g., post-multi-month JIT accumulation).

V2 candidate (banked per return report): automated time-based eviction
on pipeline-end or per-row TTL column.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone


def prune_chart_renders_older_than(
    conn: sqlite3.Connection, *, older_than_days: int,
) -> int:
    """DELETE `chart_renders` rows with ``rendered_at`` older than
    `older_than_days` calendar days before now (UTC).

    Caller-tx contract: NO ``conn.commit()`` in the helper; the caller
    owns the transaction boundary (mirrors repo pattern at
    ``swing/data/repos/chart_renders.py``).

    Returns the number of rows deleted.
    """
    if older_than_days < 0:
        raise ValueError(
            f"older_than_days must be non-negative; got {older_than_days!r}"
        )
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = conn.execute(
        "DELETE FROM chart_renders WHERE rendered_at < ?",
        (cutoff_iso,),
    )
    return int(cur.rowcount)
