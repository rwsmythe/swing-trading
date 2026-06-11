"""Phase 11 T-A.7 — migration 0018 round-trip + atomicity-by-counter-example.

Per plan §C.1 + §C.4 + §C.5 (Schwab API Integration plan, 2026-05-13):

  - schwab_api_calls audit table (14 cols + 4 CHECK enums + 3 FKs ON DELETE SET NULL).
  - 4 indexes (ts; status+ts; pipeline_run_id+ts; surface+ts).
  - 2 ALTER ADD COLUMNs (account_equity_snapshots.schwab_account_hash;
    reconciliation_runs.schwab_api_call_id FK to schwab_api_calls(call_id) ON DELETE SET NULL).
  - UPDATE schema_version SET version = 18.

The migration file MUST open with `BEGIN;` and close with `COMMIT;` per
Codex R1 Critical #1 + CLAUDE.md gotcha "executescript() implicit COMMIT":
the runner-level rollback can only undo partial DDL when the SQL itself
opens an explicit transaction. Two counter-example tests pin the
discipline:

  - Canonical (with BEGIN/COMMIT) + planted fail-mid-sequence → rollback
    succeeds; ``schwab_api_calls`` table does NOT exist post-failure.
  - Canonical-MINUS-BEGIN/COMMIT (autocommit mode) + same planted failure
    → CREATE TABLE persists despite later failure (locks the discipline
    by counter-example).

§C.5 LOCK: No backup gate fires for 17→18 (gate is version-specific;
Phase-9 gate fires only on current==16 AND target>=17). Test plants v17
state + applies 0018 + asserts NO backup file written.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _apply_migration,
    ensure_schema,
    run_migrations,
)

_MIGRATION_0018_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "data"
    / "migrations"
    / "0018_schwab_integration.sql"
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Fresh DB walked through the full migration ladder up to EXPECTED."""
    db_path = tmp_path / "phase11.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — EXPECTED_SCHEMA_VERSION constant + schema_version row
# ============================================================================


def test_expected_schema_version_constant_is_19() -> None:
    # Phase 14 Sub-bundle 3 migration 0023 advanced 22 -> 23.
    assert EXPECTED_SCHEMA_VERSION == 27


def test_schema_version_row_is_19(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == 27


# ============================================================================
# §2 — schwab_api_calls table existence + columns
# ============================================================================


_SCHWAB_CALLS_EXPECTED_COLS: frozenset[str] = frozenset({
    "call_id",
    "ts",
    "endpoint",
    "http_status",
    "response_time_ms",
    "rate_limit_remaining",
    "signature_hash",
    "status",
    "error_message",
    "linked_snapshot_id",
    "linked_reconciliation_run_id",
    "pipeline_run_id",
    "surface",
    "environment",
    # Phase 12 Sub-bundle C.A migration 0019 added `linked_correction_id`
    # via ALTER ADD COLUMN; nullable FK to reconciliation_corrections.
    "linked_correction_id",
})


def test_schwab_api_calls_table_exists_with_15_columns(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(schwab_api_calls)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _SCHWAB_CALLS_EXPECTED_COLS, (
        f"column drift; missing {_SCHWAB_CALLS_EXPECTED_COLS - cols}; "
        f"extra {cols - _SCHWAB_CALLS_EXPECTED_COLS}"
    )
    assert len(cols) == 15


# ============================================================================
# §3 — schwab_api_calls FK constraints (3 outgoing + 1 reciprocal)
# ============================================================================


def _valid_call_kwargs(**overrides: object) -> dict[str, object]:
    """Return a baseline INSERT-arg dict for schwab_api_calls; override per test."""
    base: dict[str, object] = {
        "ts": "2026-05-14T10:00:00.000",
        "endpoint": "accounts.linked",
        "http_status": 200,
        "response_time_ms": 120,
        "rate_limit_remaining": 100,
        "signature_hash": "abc123",
        "status": "success",
        "error_message": None,
        "linked_snapshot_id": None,
        "linked_reconciliation_run_id": None,
        "pipeline_run_id": None,
        "surface": "pipeline",
        "environment": "production",
    }
    base.update(overrides)
    return base


def _insert_call(conn: sqlite3.Connection, **overrides: object) -> int:
    kw = _valid_call_kwargs(**overrides)
    keys = list(kw.keys())
    placeholders = ", ".join("?" for _ in keys)
    conn.execute(
        f"INSERT INTO schwab_api_calls ({', '.join(keys)}) VALUES ({placeholders})",
        tuple(kw[k] for k in keys),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_schwab_api_calls_fk_linked_snapshot_rejects_unknown(
    conn: sqlite3.Connection,
) -> None:
    """FK linked_snapshot_id → account_equity_snapshots(snapshot_id) is enforced."""
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insert_call(conn, linked_snapshot_id=999)


def test_schwab_api_calls_fk_linked_reconciliation_run_rejects_unknown(
    conn: sqlite3.Connection,
) -> None:
    """FK linked_reconciliation_run_id → reconciliation_runs(run_id) is enforced."""
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insert_call(conn, linked_reconciliation_run_id=999)


def test_schwab_api_calls_fk_pipeline_run_rejects_unknown(
    conn: sqlite3.Connection,
) -> None:
    """FK pipeline_run_id → pipeline_runs(run_id) is enforced."""
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insert_call(conn, pipeline_run_id=999)


def test_schwab_api_calls_fks_accept_null(conn: sqlite3.Connection) -> None:
    """All 3 linked FK columns accept NULL (pre-link / unlinked rows)."""
    conn.execute("PRAGMA foreign_keys = ON")
    call_id = _insert_call(conn)  # all 3 linked_* default to None
    assert call_id >= 1


def test_reconciliation_runs_schwab_api_call_id_fk_set_null_on_audit_delete(
    conn: sqlite3.Connection,
) -> None:
    """Reciprocal FK reconciliation_runs.schwab_api_call_id → schwab_api_calls(call_id)
    ON DELETE SET NULL — deleting an audit row nulls the back-pointer."""
    conn.execute("PRAGMA foreign_keys = ON")
    call_id = _insert_call(conn)
    conn.execute(
        "INSERT INTO reconciliation_runs ("
        "source, started_ts, state, schwab_api_call_id"
        ") VALUES ('schwab_api', '2026-05-14T10:00:00.000', 'completed', ?)",
        (call_id,),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Before delete: FK pointer populated.
    pre = conn.execute(
        "SELECT schwab_api_call_id FROM reconciliation_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert pre[0] == call_id

    # Delete the audit row; reconciliation_run survives with NULL pointer.
    conn.execute("DELETE FROM schwab_api_calls WHERE call_id = ?", (call_id,))
    post = conn.execute(
        "SELECT schwab_api_call_id FROM reconciliation_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert post[0] is None


# ============================================================================
# §4 — CHECK enum constraints
# ============================================================================


_VALID_STATUSES = (
    "in_flight",
    "success",
    "error",
    "auth_failed",
    "rate_limited",
    "concurrent_refresh",
)


def test_schwab_api_calls_status_check_enum_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_call(conn, status="foobar")


@pytest.mark.parametrize("status", _VALID_STATUSES)
def test_schwab_api_calls_status_check_enum_accepts_valid(
    conn: sqlite3.Connection, status: str
) -> None:
    _insert_call(conn, status=status)
    n = conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls WHERE status = ?", (status,)
    ).fetchone()[0]
    assert n == 1


def test_schwab_api_calls_surface_check_enum_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    """V1 enum excludes 'web_page_render' (reserved for V2)."""
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_call(conn, surface="web_page_render")


@pytest.mark.parametrize("surface", ("pipeline", "cli"))
def test_schwab_api_calls_surface_check_enum_accepts_valid(
    conn: sqlite3.Connection, surface: str
) -> None:
    _insert_call(conn, surface=surface)


def test_schwab_api_calls_environment_check_enum_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_call(conn, environment="dev")


@pytest.mark.parametrize("environment", ("sandbox", "production"))
def test_schwab_api_calls_environment_check_enum_accepts_valid(
    conn: sqlite3.Connection, environment: str
) -> None:
    _insert_call(conn, environment=environment)


_VALID_ENDPOINTS = (
    "oauth.code_exchange",
    "oauth.refresh",
    "oauth.revoke",
    "accounts.linked",
    "accounts.details",
    "accounts.orders.list",
    "accounts.transactions.list",
    "marketdata.quotes",
    "marketdata.pricehistory",
)


def test_schwab_api_calls_endpoint_check_enum_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_call(conn, endpoint="foo.bar")


@pytest.mark.parametrize("endpoint", _VALID_ENDPOINTS)
def test_schwab_api_calls_endpoint_check_enum_accepts_valid(
    conn: sqlite3.Connection, endpoint: str
) -> None:
    _insert_call(conn, endpoint=endpoint)


# ============================================================================
# §5 — Indexes present
# ============================================================================


def test_schwab_api_calls_indexes_present(conn: sqlite3.Connection) -> None:
    """4 explicit indexes from §C.1; ignore sqlite_autoindex_* for PK."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='schwab_api_calls' AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "ix_schwab_api_calls_ts",
        "ix_schwab_api_calls_status_ts",
        "ix_schwab_api_calls_pipeline_run_id_ts",
        "ix_schwab_api_calls_surface_ts",
    }
    assert names == expected, (
        f"index drift; missing {expected - names}; extra {names - expected}"
    )


# ============================================================================
# §6 — ALTER ADD COLUMNs — NULL-permissible + reciprocal FK populated test
# ============================================================================


def test_account_equity_snapshots_schwab_account_hash_column_exists(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(account_equity_snapshots)")
    cols = {r[1] for r in cur.fetchall()}
    assert "schwab_account_hash" in cols


def test_account_equity_snapshots_legacy_insert_has_null_schwab_account_hash(
    conn: sqlite3.Connection,
) -> None:
    """ALTER ADD COLUMN landed as NULLABLE; legacy INSERT leaves it NULL."""
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
        ") VALUES ('2026-05-13', 1000.0, 'manual', "
        "'2026-05-13T16:00:00.000', 'operator')"
    )
    row = conn.execute(
        "SELECT schwab_account_hash FROM account_equity_snapshots "
        "WHERE snapshot_date = '2026-05-13' AND source = 'manual'"
    ).fetchone()
    assert row[0] is None


def test_reconciliation_runs_schwab_api_call_id_column_exists(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(reconciliation_runs)")
    cols = {r[1] for r in cur.fetchall()}
    assert "schwab_api_call_id" in cols


def test_reconciliation_runs_legacy_insert_has_null_schwab_api_call_id(
    conn: sqlite3.Connection,
) -> None:
    """ALTER ADD COLUMN landed as NULLABLE; legacy INSERT leaves it NULL."""
    conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('tos_csv', '2026-05-14T10:00:00.000', 'completed')"
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute(
        "SELECT schwab_api_call_id FROM reconciliation_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] is None


# ============================================================================
# §7 — BEGIN/COMMIT markers (defense-in-depth grep against future edits)
# ============================================================================


def test_migration_0018_sql_begins_with_begin_marker() -> None:
    """First non-comment-non-blank line is 'BEGIN;' (atomicity discipline)."""
    sql_text = _MIGRATION_0018_PATH.read_text(encoding="utf-8")
    lines = [
        ln.rstrip()
        for ln in sql_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("--")
    ]
    assert lines, "migration file is empty after stripping comments+blanks"
    assert lines[0] == "BEGIN;", (
        f"expected first non-comment line to be 'BEGIN;'; got {lines[0]!r}"
    )


def test_migration_0018_sql_ends_with_commit_marker() -> None:
    """Last non-comment-non-blank line is 'COMMIT;' (atomicity discipline)."""
    sql_text = _MIGRATION_0018_PATH.read_text(encoding="utf-8")
    lines = [
        ln.rstrip()
        for ln in sql_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("--")
    ]
    assert lines, "migration file is empty after stripping comments+blanks"
    assert lines[-1] == "COMMIT;", (
        f"expected last non-comment line to be 'COMMIT;'; got {lines[-1]!r}"
    )


# ============================================================================
# §8 — Atomicity discipline: BEGIN/COMMIT counter-example tests (§C.4)
# ============================================================================


_CANONICAL_HEAD = """\
BEGIN;

CREATE TABLE schwab_api_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL,
    surface TEXT NOT NULL,
    environment TEXT NOT NULL
);
"""

# Deliberate failure: bad INDEX on nonexistent table; mid-sequence, after
# the CREATE TABLE succeeds.
_FAILING_TAIL = """\
CREATE INDEX ix_bad ON nonexistent_table(col);

UPDATE schema_version SET version = 18;

COMMIT;
"""


def test_canonical_with_begin_rolls_back_partial_state(tmp_path: Path) -> None:
    """Plant canonical 0018-shaped fixture WITH BEGIN/COMMIT + planted failure.

    Per plan §C.4: with explicit BEGIN, the runner's conn.rollback() undoes
    the CREATE TABLE. Post-failure: schema_version still 17, schwab_api_calls
    absent, conn.in_transaction == False.
    """
    db_path = tmp_path / "v17.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17)
    conn.commit()
    assert _read_version(conn) == 17

    bad_sql_path = tmp_path / "bad_0018_with_begin.sql"
    bad_sql_path.write_text(_CANONICAL_HEAD + "\n" + _FAILING_TAIL)

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Post-failure invariants:
    assert _read_version(conn) == 17
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='schwab_api_calls'"
    ).fetchone()
    assert table_row is None, "explicit BEGIN should have rolled back CREATE TABLE"
    assert conn.in_transaction is False
    conn.close()


def test_canonical_minus_begin_does_not_roll_back(tmp_path: Path) -> None:
    """Plant 0018-shaped fixture WITHOUT BEGIN/COMMIT (autocommit).

    Per plan §C.4 counter-example: in autocommit mode the CREATE TABLE
    persists despite the later failure — locks the BEGIN-discipline
    contract by counter-example.
    """
    db_path = tmp_path / "v17_no_begin.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17)
    conn.commit()
    assert _read_version(conn) == 17

    # Strip the leading "BEGIN;\n\n" from the canonical head + trailing
    # "COMMIT;\n" from the failing tail — i.e., autocommit-mode script.
    no_begin_head = _CANONICAL_HEAD.replace("BEGIN;\n\n", "", 1)
    no_commit_tail = _FAILING_TAIL.replace("COMMIT;\n", "", 1)
    bad_sql_path = tmp_path / "bad_0018_no_begin.sql"
    bad_sql_path.write_text(no_begin_head + "\n" + no_commit_tail)

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Counter-example invariant: CREATE TABLE persisted despite later failure.
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='schwab_api_calls'"
    ).fetchone()
    assert table_row is not None, (
        "without BEGIN, CREATE TABLE should persist in autocommit mode; "
        "if this assert fires the canonical-with-BEGIN test no longer "
        "documents the discipline by counter-example."
    )
    # schema_version still 17 because the UPDATE was after the failure.
    assert _read_version(conn) == 17
    conn.close()


# ============================================================================
# §9 — Backup gate does NOT fire for 17→18 (§C.5 LOCK)
# ============================================================================


def test_no_backup_gate_fires_for_v17_to_v18(tmp_path: Path) -> None:
    """Per plan §C.5: NO version-specific backup gate is wired for 17→18.

    Plants v17 + applies real 0018 + asserts (a) NO
    MigrationBackupRequiredException raised AND (b) NO backup file written
    to backup_dir matching any of the 3 wired-gate filename prefixes.
    """
    db_path = tmp_path / "v17_no_backup.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version_via_path(db_path) == 17

    # Reopen and walk v17 → v18; MUST NOT raise + MUST NOT write backup file.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=18, backup_dir=backup_dir)
    except MigrationBackupRequiredException as exc:  # pragma: no cover
        pytest.fail(
            f"plan §C.5 LOCK: no backup gate wired for 17→18 but one fired: {exc}"
        )
    conn.commit()
    conn.close()

    assert _read_version_via_path(db_path) == 18

    # No backup file under any known gate prefix:
    leftover = list(backup_dir.glob("swing-pre-phase*-migration-*.db"))
    assert leftover == [], (
        f"unexpected backup file(s) written under §C.5 LOCK: {leftover}"
    )


# ============================================================================
# Helpers
# ============================================================================


def _read_version(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT version FROM schema_version").fetchone()[0]


def _read_version_via_path(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
