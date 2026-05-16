"""Phase 12 Sub-bundle C T-A.6 — ReviewLog.superseded_by_correction_id row deserializer.

Per plan §B.6: mirror of T-A.5 for `ReviewLog` — the `_row_to_review_log`
deserializer at `swing/data/repos/review_log.py` must read the new column
added at T-A.1 (migration 0019 ALTER `review_log ADD COLUMN
superseded_by_correction_id`) and populate the dataclass field added at
T-A.2.

Column layout (verified via PRAGMA table_info post-migration):
  rows 0-20: migration 0013 original 21 columns.
  row 21:    risk_policy_id_at_review_completion (ALTER migration 0017).
             NOT consumed by the current ReviewLog dataclass — this column
             stays at the SQL layer only.
  row 22:    superseded_by_correction_id (ALTER migration 0019).
             NEW field added to ReviewLog dataclass at T-A.2.

Tests:
  1. Plant a review_log row with superseded_by_correction_id pointing at a
     real reconciliation_corrections.correction_id; read via get(); verify
     dataclass field populated with that FK value.
  2. Back-compat: plant a normal review_log row with the new column
     defaulting to NULL; read back; verify superseded_by_correction_id is
     None.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.repos.review_log import get


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase12_T_A6.db"
    return ensure_schema(db_path)


def _insert_review_log_row(
    conn: sqlite3.Connection,
    *,
    review_type: str = "daily",
    period_start: str = "2026-05-14",
    period_end: str = "2026-05-14",
    superseded_by_correction_id: int | None = None,
) -> int:
    """Plant a minimal review_log row via raw SQL.

    Uses positional INSERT to stay independent of the production write
    paths (complete_review_atomic) which do not yet take
    superseded_by_correction_id as a kwarg in V1.
    """
    cur = conn.execute(
        """
        INSERT INTO review_log (
            review_type, period_start, period_end, scheduled_date,
            completed_date, skipped, duration_minutes, n_trades_reviewed,
            total_mistake_cost_R, total_lucky_violation_R,
            primary_lesson, next_period_focus, created_at,
            superseded_by_correction_id
        ) VALUES (?, ?, ?, ?, NULL, 0, NULL, 0, 0.0, 0.0,
                  NULL, NULL, ?, ?)
        """,
        (
            review_type, period_start, period_end, period_end,
            now_ms(), superseded_by_correction_id,
        ),
    )
    conn.commit()
    return cur.lastrowid


def _seed_correction_fk_target(conn: sqlite3.Connection) -> int:
    """Plant a reconciliation_corrections row so an FK reference is valid.

    Requires: a reconciliation_runs row + a reconciliation_discrepancies
    row to satisfy the corrections-table FK chain.
    """
    cur_run = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES ('tos_csv', ?, 'completed')
        """,
        (now_ms(),),
    )
    run_id = cur_run.lastrowid
    cur_disc = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, ticker, field_name,
            expected_value_json, actual_value_json,
            material_to_review, resolution, created_at
        ) VALUES (?, 'stop_mismatch', 'ABC', 'stop',
                  '9.00', '8.50', 1, 'unresolved', ?)
        """,
        (run_id, now_ms()),
    )
    disc_id = cur_disc.lastrowid
    cur_corr = conn.execute(
        """
        INSERT INTO reconciliation_corrections (
            discrepancy_id, correction_action, affected_table,
            affected_row_id, field_name, pre_correction_value_json,
            applied_value_json, applied_at, applied_by,
            reconciliation_run_id
        ) VALUES (?, 'auto_applied', 'fills', 1, 'price',
                  '{"price": 5.00}', '{"price": 5.10}', ?, 'auto', ?)
        """,
        (disc_id, now_ms(), run_id),
    )
    conn.commit()
    return cur_corr.lastrowid


# ============================================================================
# §1 — discriminating test: superseded_by_correction_id populated
# ============================================================================


def test_get_review_log_populates_superseded_by_correction_id_field(
    conn: sqlite3.Connection,
) -> None:
    correction_id = _seed_correction_fk_target(conn)
    review_id = _insert_review_log_row(
        conn,
        period_start="2026-05-14",
        period_end="2026-05-14",
        superseded_by_correction_id=correction_id,
    )

    rl = get(conn, review_id)
    assert rl is not None
    assert rl.superseded_by_correction_id == correction_id


# ============================================================================
# §2 — back-compat: default NULL
# ============================================================================


def test_get_review_log_default_superseded_by_correction_id_is_none(
    conn: sqlite3.Connection,
) -> None:
    review_id = _insert_review_log_row(
        conn,
        period_start="2026-05-15",
        period_end="2026-05-15",
        superseded_by_correction_id=None,
    )

    rl = get(conn, review_id)
    assert rl is not None
    assert rl.superseded_by_correction_id is None
