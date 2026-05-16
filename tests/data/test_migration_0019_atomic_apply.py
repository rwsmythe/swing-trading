"""Phase 12 Sub-bundle C.A T-A.1 — migration 0019 atomic apply + atomicity discipline.

Per plan §B.1 + §A.1 + §A.10 (auto-correct reconciliation plan, 2026-05-15):

  - reconciliation_corrections audit table (20 cols + 4 indexes; spec §3.1
    header says 19 but enumerated rows are 20 — plan §B.1 acceptance #3
    LOCKS 20; banked as V2.1 §VII.F amendment candidate §I.16).
  - reconciliation_discrepancies rebuild (widen resolution CHECK 5 → 9
    values + add new nullable `ambiguity_kind` column with 7-value CHECK
    enum + bidirectional cross-column CHECK pairing).
  - 5 indexes on reconciliation_discrepancies (4 preserved + 1 new partial
    index for tier-2 pending-ambiguity rows).
  - review_log gains nullable `superseded_by_correction_id` (FK to
    reconciliation_corrections(correction_id) ON DELETE SET NULL).
  - schwab_api_calls gains nullable `linked_correction_id` (FK to
    reconciliation_corrections(correction_id) ON DELETE SET NULL).
  - trade_events rebuild widens `event_type` CHECK 6 → 7 values
    (+ 'reconciliation_auto_correct'); preserves rows + index.
  - UPDATE schema_version SET version = 19. MUST be the FINAL statement
    before COMMIT per Phase 9 §A.0 R1 Critical #1 precedent.

The migration file MUST open with `BEGIN;` and close with `COMMIT;` per
Codex R1 Critical #1 + CLAUDE.md gotcha "executescript() implicit COMMIT".
Counter-example tests mirror the 0018 precedent (test_migration_0018.py
§8) and lock the BEGIN/COMMIT discipline by demonstrating that
canonical-MINUS-BEGIN/COMMIT autocommit-mode scripts persist partial DDL
despite mid-script failure.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    _apply_migration,
    ensure_schema,
    run_migrations,
)

_MIGRATION_0019_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "data"
    / "migrations"
    / "0019_phase12_bundle_c_auto_correct_reconciliation.sql"
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Fresh DB walked through the full migration ladder up to EXPECTED."""
    db_path = tmp_path / "phase12_bundle_c_a.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — EXPECTED_SCHEMA_VERSION constant + schema_version row
# ============================================================================


def test_expected_schema_version_constant_is_19() -> None:
    assert EXPECTED_SCHEMA_VERSION == 19


def test_schema_version_row_is_19(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == 19


# ============================================================================
# §2 — Per plan §B.1 Step 1: applies-against-v18-baseline binding test.
# ============================================================================


def test_migration_0019_applies_against_v18_baseline(tmp_path: Path) -> None:
    """Plan §B.1 Step 1 canonical pin — sub-bundle C deltas land at v19."""
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        post = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
        assert post == 19

        # Tables/columns expected by Sub-bundle C exist:
        schema = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "reconciliation_corrections" in schema

        # ambiguity_kind column on reconciliation_discrepancies:
        cols = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(reconciliation_discrepancies)"
            )
        ]
        assert "ambiguity_kind" in cols

        # superseded_by_correction_id on review_log:
        cols_rl = [
            row[1]
            for row in conn.execute("PRAGMA table_info(review_log)")
        ]
        assert "superseded_by_correction_id" in cols_rl

        # linked_correction_id on schwab_api_calls:
        cols_api = [
            row[1]
            for row in conn.execute("PRAGMA table_info(schwab_api_calls)")
        ]
        assert "linked_correction_id" in cols_api
    finally:
        conn.close()


# ============================================================================
# §3 — BEGIN/COMMIT markers (defense-in-depth grep against future edits)
# ============================================================================


def test_migration_0019_sql_begins_with_begin_marker() -> None:
    """First non-comment-non-blank line is 'BEGIN;' (atomicity discipline)."""
    sql_text = _MIGRATION_0019_PATH.read_text(encoding="utf-8")
    lines = [
        ln.rstrip()
        for ln in sql_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("--")
    ]
    assert lines, "migration file is empty after stripping comments+blanks"
    assert lines[0] == "BEGIN;", (
        f"expected first non-comment line to be 'BEGIN;'; got {lines[0]!r}"
    )


def test_migration_0019_sql_ends_with_commit_marker() -> None:
    """Last non-comment-non-blank line is 'COMMIT;' (atomicity discipline)."""
    sql_text = _MIGRATION_0019_PATH.read_text(encoding="utf-8")
    lines = [
        ln.rstrip()
        for ln in sql_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("--")
    ]
    assert lines, "migration file is empty after stripping comments+blanks"
    assert lines[-1] == "COMMIT;", (
        f"expected last non-comment line to be 'COMMIT;'; got {lines[-1]!r}"
    )


def test_migration_0019_schema_version_update_is_last_statement() -> None:
    """UPDATE schema_version SET version = 19 must be the final pre-COMMIT
    statement per Phase 9 §A.0 R1 Critical #1 precedent (acceptance #13).
    """
    sql_text = _MIGRATION_0019_PATH.read_text(encoding="utf-8")
    lines = [
        ln.rstrip()
        for ln in sql_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("--")
    ]
    # last line is COMMIT;, second-to-last must be the version bump.
    assert lines[-1] == "COMMIT;"
    assert lines[-2] == "UPDATE schema_version SET version = 19;", (
        f"expected version bump immediately before COMMIT; got {lines[-2]!r}"
    )


# ============================================================================
# §4 — Atomicity discipline: BEGIN/COMMIT counter-example tests.
#     Mirror of migration 0018 §8 pattern (test_migration_0018.py:413-504).
# ============================================================================

_CANONICAL_HEAD = """\
BEGIN;

CREATE TABLE reconciliation_corrections (
    correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discrepancy_id INTEGER NOT NULL,
    correction_action TEXT NOT NULL,
    affected_table TEXT NOT NULL,
    affected_row_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    pre_correction_value_json TEXT NOT NULL,
    applied_value_json TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    reconciliation_run_id INTEGER NOT NULL
);
"""

# Deliberate mid-sequence failure: bad INDEX on nonexistent table.
_FAILING_TAIL = """\
CREATE INDEX ix_bad ON nonexistent_table(col);

UPDATE schema_version SET version = 19;

COMMIT;
"""


def test_canonical_with_begin_rolls_back_partial_state(tmp_path: Path) -> None:
    """Plant canonical 0019-shaped fixture WITH BEGIN/COMMIT + planted failure.

    With explicit BEGIN, the runner's conn.rollback() undoes the CREATE TABLE.
    Post-failure: schema_version still 18, reconciliation_corrections absent,
    conn.in_transaction == False.
    """
    db_path = tmp_path / "v18.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18)
    conn.commit()
    assert _read_version(conn) == 18

    bad_sql_path = tmp_path / "bad_0019_with_begin.sql"
    bad_sql_path.write_text(_CANONICAL_HEAD + "\n" + _FAILING_TAIL)

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Post-failure invariants:
    assert _read_version(conn) == 18
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='reconciliation_corrections'"
    ).fetchone()
    assert table_row is None, (
        "explicit BEGIN should have rolled back CREATE TABLE"
    )
    assert conn.in_transaction is False
    conn.close()


def test_canonical_minus_begin_does_not_roll_back(tmp_path: Path) -> None:
    """Plant 0019-shaped fixture WITHOUT BEGIN/COMMIT (autocommit).

    Counter-example: in autocommit mode the CREATE TABLE persists despite
    later failure — locks the BEGIN-discipline contract by counter-example
    (mirrors 0018 precedent).
    """
    db_path = tmp_path / "v18_no_begin.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18)
    conn.commit()
    assert _read_version(conn) == 18

    no_begin_head = _CANONICAL_HEAD.replace("BEGIN;\n\n", "", 1)
    no_commit_tail = _FAILING_TAIL.replace("COMMIT;\n", "", 1)
    bad_sql_path = tmp_path / "bad_0019_no_begin.sql"
    bad_sql_path.write_text(no_begin_head + "\n" + no_commit_tail)

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Counter-example invariant: CREATE TABLE persisted despite later failure.
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='reconciliation_corrections'"
    ).fetchone()
    assert table_row is not None, (
        "without BEGIN, CREATE TABLE should persist in autocommit mode; "
        "if this assert fires the canonical-with-BEGIN test no longer "
        "documents the discipline by counter-example."
    )
    # schema_version still 18 because the UPDATE was after the failure.
    assert _read_version(conn) == 18
    conn.close()


# ============================================================================
# Helpers
# ============================================================================


def _read_version(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT version FROM schema_version").fetchone()[0]
