"""Phase 12 Sub-bundle C.A — Codex R1 Major #3 regression tests.

Verifies the ``swing/data/repos/schwab_api_calls.py`` repo was extended to
project + populate + write the ``linked_correction_id`` column added by
migration 0019 (T-A.2).

Tests:
  1. insert + read-back with ``linked_correction_id=None`` — default state
     for the vast majority of Schwab API calls (those that do NOT source
     a canonical value for a reconciliation correction).
  2. insert with a populated ``linked_correction_id`` (when caller wires
     it post-correction-creation via the new helper) — read-back surfaces
     the FK.
  3. ``update_call_linked_correction`` helper UPDATEs the column on an
     existing call row + preserves all other columns.
  4. FK ``ON DELETE SET NULL`` — DELETE the parent
     ``reconciliation_corrections`` row + verify ``linked_correction_id``
     becomes NULL on the dependent call row (mirrors the
     ``linked_snapshot_id`` and ``linked_reconciliation_run_id``
     ``ON DELETE SET NULL`` semantics established in migration 0018).

Pre-fix expected (Codex R1 Major #3):
  - Test 2 + Test 3 + Test 4 FAIL because the existing ``_SELECT_COLUMNS``
    + ``_row_to_model`` did not project the new column (reads always
    returned ``linked_correction_id=None`` regardless of actual value).
  - The ``update_call_linked_correction`` helper did not exist.

Post-fix expected: all 4 tests PASS.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.schwab_api_calls import (
    get_call,
    insert_in_flight,
    update_call_linked_correction,
)

# ============================================================================
# Fixtures + seed helpers (kept local to avoid coupling with the v18-named
# fixture in the existing test_schwab_api_calls.py — schema_version is now
# 19 in this branch but the fixture name is preserved for git-blame
# continuity).
# ============================================================================


@pytest.fixture
def v19_conn(tmp_path: Path) -> sqlite3.Connection:
    """Fresh DB walked to EXPECTED_SCHEMA_VERSION (19 in this branch).

    PRAGMA foreign_keys=ON via ensure_schema — required for the FK ON
    DELETE SET NULL test to fire.
    """
    return ensure_schema(tmp_path / "schwab-linked-correction-test.db")


def _seed_pipeline_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO pipeline_runs ("
        "started_ts, trigger, data_asof_date, action_session_date, "
        "state, lease_token"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-15T08:00:00", "manual", "2026-05-14", "2026-05-15",
         "running", "test-token"),
    )
    return int(cur.lastrowid)


def _seed_correction_fk_target(conn: sqlite3.Connection) -> int:
    """Seed reconciliation_runs + reconciliation_discrepancies +
    reconciliation_corrections; return the correction_id PK.

    Mirrors the seed shape used in
    ``tests/data/test_review_log_superseded_by_correction_id_roundtrip.py``.
    """
    ts = "2026-05-15T12:00:00"
    run_cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('tos_csv', ?, 'completed')",
        (ts,),
    )
    run_id = int(run_cur.lastrowid)
    disc_cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, ticker, field_name, "
        "expected_value_json, actual_value_json, "
        "material_to_review, resolution, created_at"
        ") VALUES (?, 'stop_mismatch', 'ABC', 'stop', "
        "'9.00', '8.50', 1, 'unresolved', ?)",
        (run_id, ts),
    )
    disc_id = int(disc_cur.lastrowid)
    corr_cur = conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, "
        "affected_row_id, field_name, pre_correction_value_json, "
        "applied_value_json, applied_at, applied_by, "
        "reconciliation_run_id"
        ") VALUES (?, 'auto_applied', 'fills', 1, 'price', "
        "'{\"price\": 5.00}', '{\"price\": 5.10}', ?, 'auto', ?)",
        (disc_id, ts, run_id),
    )
    return int(corr_cur.lastrowid)


# ============================================================================
# Tests
# ============================================================================


def test_get_call_returns_linked_correction_id_none_by_default(
    v19_conn: sqlite3.Connection,
) -> None:
    """Test 1 — read-back surfaces None for the new column by default.

    Most Schwab API calls do NOT source a canonical value for a
    reconciliation correction. The dataclass default is ``None``; reads
    must round-trip that default.
    """
    conn = v19_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn,
            ts="2026-05-15T12:00:00",
            endpoint="oauth.refresh",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline",
            environment="production",
        )
        conn.commit()

        call = get_call(conn, call_id=call_id)
        assert call is not None
        assert call.linked_correction_id is None, (
            "Default-state Schwab API call must read back "
            "linked_correction_id=None; got "
            f"{call.linked_correction_id!r}. Pre-fix: _SELECT_COLUMNS did "
            "not project the new column at all; the dataclass default "
            "would surface None regardless of actual value — making this "
            "test pass for the wrong reason. Test 2 distinguishes."
        )
    finally:
        conn.close()


def test_get_call_surfaces_populated_linked_correction_id(
    v19_conn: sqlite3.Connection,
) -> None:
    """Test 2 — read-back surfaces an actual populated value.

    DISCRIMINATING test for Codex R1 Major #3: pre-fix _SELECT_COLUMNS
    did NOT include linked_correction_id; reads always returned None
    even when the column was populated in the DB. Post-fix: reads
    surface the actual integer.
    """
    conn = v19_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        correction_id = _seed_correction_fk_target(conn)

        call_id = insert_in_flight(
            conn,
            ts="2026-05-15T12:00:00",
            endpoint="accounts.details",
            pipeline_run_id=pipeline_run_id,
            surface="cli",
            environment="production",
        )
        # Direct UPDATE — pre-helper baseline for Test 3.
        conn.execute(
            "UPDATE schwab_api_calls SET linked_correction_id = ? "
            "WHERE call_id = ?",
            (correction_id, call_id),
        )
        conn.commit()

        call = get_call(conn, call_id=call_id)
        assert call is not None
        assert call.linked_correction_id == correction_id, (
            "Read-back must surface populated linked_correction_id; got "
            f"{call.linked_correction_id!r}, expected {correction_id}. "
            "Pre-fix this assertion failed because _SELECT_COLUMNS did "
            "not project the new column added by migration 0019."
        )
    finally:
        conn.close()


def test_update_call_linked_correction_stamps_value(
    v19_conn: sqlite3.Connection,
) -> None:
    """Test 3 — the new update_call_linked_correction helper UPDATEs the
    column on an existing call row + preserves all other columns.

    Mirrors update_call_linked_snapshot test shape verbatim.
    """
    conn = v19_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        correction_id = _seed_correction_fk_target(conn)

        call_id = insert_in_flight(
            conn,
            ts="2026-05-15T12:00:00",
            endpoint="marketdata.quotes",
            pipeline_run_id=pipeline_run_id,
            surface="cli",
            environment="production",
        )
        # Mark this call as having sourced a canonical value for the
        # correction. Use the new helper (the thing under test).
        update_call_linked_correction(
            conn, call_id=call_id, correction_id=correction_id,
        )
        conn.commit()

        row = conn.execute(
            "SELECT call_id, ts, endpoint, status, surface, environment, "
            "linked_correction_id, linked_snapshot_id, "
            "linked_reconciliation_run_id "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == call_id
        assert row[1] == "2026-05-15T12:00:00"  # ts preserved
        assert row[2] == "marketdata.quotes"  # endpoint preserved
        assert row[3] == "in_flight"  # status preserved
        assert row[4] == "cli"  # surface preserved
        assert row[5] == "production"  # environment preserved
        assert row[6] == correction_id  # linked_correction_id updated
        assert row[7] is None  # linked_snapshot_id unchanged
        assert row[8] is None  # linked_reconciliation_run_id unchanged
    finally:
        conn.close()


def test_fk_on_delete_set_null_for_linked_correction(
    v19_conn: sqlite3.Connection,
) -> None:
    """Test 4 — DELETE parent reconciliation_corrections row + assert
    linked_correction_id flips to NULL on the dependent call row.

    Mirrors migration 0019 line 200-201:
        ALTER TABLE schwab_api_calls
            ADD COLUMN linked_correction_id INTEGER
                REFERENCES reconciliation_corrections(correction_id)
                ON DELETE SET NULL;

    Requires PRAGMA foreign_keys=ON (set by ensure_schema fixture).
    """
    conn = v19_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        correction_id = _seed_correction_fk_target(conn)

        call_id = insert_in_flight(
            conn,
            ts="2026-05-15T12:00:00",
            endpoint="accounts.transactions.list",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline",
            environment="production",
        )
        update_call_linked_correction(
            conn, call_id=call_id, correction_id=correction_id,
        )
        conn.commit()

        # Sanity: linked_correction_id is set before the parent DELETE.
        call_pre = get_call(conn, call_id=call_id)
        assert call_pre is not None
        assert call_pre.linked_correction_id == correction_id

        # Delete the parent correction row; FK ON DELETE SET NULL should
        # null the dependent column without cascade-deleting the call.
        conn.execute(
            "DELETE FROM reconciliation_corrections WHERE correction_id = ?",
            (correction_id,),
        )
        conn.commit()

        call_post = get_call(conn, call_id=call_id)
        assert call_post is not None, (
            "FK violation — call row was cascade-deleted instead of "
            "having its linked_correction_id set NULL. Migration 0019 "
            "specified ON DELETE SET NULL; verify the column ALTER "
            "preserved the FK action."
        )
        assert call_post.linked_correction_id is None, (
            "FK ON DELETE SET NULL did not fire — linked_correction_id "
            f"is {call_post.linked_correction_id!r}, expected None. "
            "Verify PRAGMA foreign_keys=ON and migration 0019's "
            "ALTER TABLE preserved the REFERENCES ... ON DELETE SET NULL "
            "clause."
        )
    finally:
        conn.close()
