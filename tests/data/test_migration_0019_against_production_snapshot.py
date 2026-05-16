"""Phase 12 Sub-bundle C.A T-A.8 — migration 0019 against operator's production DB snapshot.

Per plan §B.8 in
``docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md``:

  Slow-marked regression test that copies the operator's production
  ``~/swing-data/swing.db`` to a tmp path, dynamically snapshots the
  pre-migration row content of `reconciliation_discrepancies` +
  `reconciliation_runs` + `review_log` + `trade_events` + `schwab_api_calls`,
  applies migration 0019, and asserts:

    1. schema_version transitions 18 -> 19.
    2. All snapshotted rows preserved column-by-column against the
       pre-migration snapshot (new columns NULL for preserved rows):
        - `reconciliation_discrepancies.ambiguity_kind`
        - `review_log.superseded_by_correction_id`
        - `schwab_api_calls.linked_correction_id`
    3. Row counts derived from the SNAPSHOT (not hardcoded), so the test
       survives production drift between plan-drafting and integration-merge.

Skip conditions (all `pytest.skip`, never failure):

    - Operator DB file absent (CI without operator snapshot).
    - Operator DB already at schema_version >= 19 (pre-condition v18 not met;
      e.g., production has already migrated past v18).

The test reads a COPY (`shutil.copy`) of the operator's DB; the actual
production file is never opened for write by this test.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import _apply_migration

_MIGRATION_0019_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "data"
    / "migrations"
    / "0019_phase12_bundle_c_auto_correct_reconciliation.sql"
)

# Tables the migration rebuilds (reconciliation_discrepancies + trade_events)
# OR adds a new column to (review_log + schwab_api_calls), PLUS reconciliation_runs
# as an FK-parent left untouched (sanity preservation check).
_SNAPSHOT_TABLES = (
    "reconciliation_discrepancies",
    "reconciliation_runs",
    "review_log",
    "trade_events",
    "schwab_api_calls",
)


def _operator_db_path() -> Path:
    """Resolve operator's production DB path per CLAUDE.md `DB location` invariant."""
    return Path(os.path.expanduser("~/swing-data/swing.db"))


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _select_all_ordered(
    conn: sqlite3.Connection, table: str, columns: list[str]
) -> list[tuple]:
    """SELECT all rows from `table` projecting exactly `columns`, ordered by
    the first column (typically the PK) for stable comparison."""
    col_list = ", ".join(columns)
    order_by = columns[0]
    cur = conn.execute(f"SELECT {col_list} FROM {table} ORDER BY {order_by}")
    return cur.fetchall()


@pytest.mark.slow
def test_migration_0019_against_operator_production_snapshot(tmp_path: Path) -> None:
    """Apply 0019 against a copy of operator's production DB; assert row preservation.

    Pre-condition: operator DB at schema_version == 18 (else skip; not a failure).
    Post-condition: schema_version == 19 + all snapshotted rows preserved
    column-by-column + new nullable columns are NULL for all preserved rows.
    """
    src_db = _operator_db_path()
    if not src_db.exists():
        pytest.skip(f"operator DB snapshot not present at {src_db}")

    # Copy the operator's DB to tmp (NEVER touch the real file).
    dst_db = tmp_path / "production_snapshot.db"
    shutil.copy(src_db, dst_db)

    conn = sqlite3.connect(dst_db)
    try:
        # Verify pre-condition: schema_version == 18.
        cur = conn.execute("SELECT version FROM schema_version")
        pre_version = cur.fetchone()[0]
        if pre_version != 18:
            pytest.skip(
                f"operator DB at schema_version={pre_version}; "
                f"pre-condition v18 not met (test no-op)"
            )

        # Capture pre-migration column lists per table (DYNAMIC — survives any
        # column additions on main between plan-drafting + integration merge).
        pre_columns: dict[str, list[str]] = {
            table: _column_names(conn, table) for table in _SNAPSHOT_TABLES
        }

        # Snapshot pre-migration row content (full column tuples) per table.
        pre_snapshot: dict[str, list[tuple]] = {
            table: _select_all_ordered(conn, table, pre_columns[table])
            for table in _SNAPSHOT_TABLES
        }

        # Apply migration 0019 atomically via the canonical runner.
        _apply_migration(conn, _MIGRATION_0019_PATH)

        # Assert schema_version transitions 18 -> 19.
        cur = conn.execute("SELECT version FROM schema_version")
        post_version = cur.fetchone()[0]
        assert post_version == 19, (
            f"expected schema_version=19 after applying 0019; got {post_version}"
        )

        # Per-table assertions: row count unchanged + row content preserved for
        # the projection of pre-migration columns (new columns may be present
        # post-migration but are NULL for all preserved rows).
        for table in _SNAPSHOT_TABLES:
            pre_rows = pre_snapshot[table]
            pre_cols = pre_columns[table]

            # SELECT the same column projection from the post-migration table.
            post_rows = _select_all_ordered(conn, table, pre_cols)

            # Row count preserved (dynamic — derived from snapshot, not hardcoded).
            assert len(post_rows) == len(pre_rows), (
                f"{table}: row count changed across migration "
                f"(pre={len(pre_rows)}, post={len(post_rows)})"
            )

            # Column-by-column equality on the pre-migration column projection.
            assert post_rows == pre_rows, (
                f"{table}: row content drift across migration "
                f"on pre-migration column projection"
            )

        # New columns introduced by 0019 must be NULL for all preserved rows.
        # (a) reconciliation_discrepancies.ambiguity_kind
        cur = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE ambiguity_kind IS NOT NULL"
        )
        assert cur.fetchone()[0] == 0, (
            "reconciliation_discrepancies.ambiguity_kind must be NULL for all "
            "preserved rows after 0019 lands"
        )

        # (b) review_log.superseded_by_correction_id
        cur = conn.execute(
            "SELECT COUNT(*) FROM review_log "
            "WHERE superseded_by_correction_id IS NOT NULL"
        )
        assert cur.fetchone()[0] == 0, (
            "review_log.superseded_by_correction_id must be NULL for all "
            "preserved rows after 0019 lands"
        )

        # (c) schwab_api_calls.linked_correction_id
        cur = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls "
            "WHERE linked_correction_id IS NOT NULL"
        )
        assert cur.fetchone()[0] == 0, (
            "schwab_api_calls.linked_correction_id must be NULL for all "
            "preserved rows after 0019 lands"
        )

        # Sanity: the new reconciliation_corrections table exists and is empty.
        cur = conn.execute("SELECT COUNT(*) FROM reconciliation_corrections")
        assert cur.fetchone()[0] == 0, (
            "reconciliation_corrections table must be empty immediately "
            "after 0019 lands"
        )
    finally:
        conn.close()
