"""SQLite connection + migrations + schema-version gate."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

# pipeline_pattern_classifications + trade chart_pattern columns (migrations 0009 + 0010)
# chart_targets source taxonomy expansion (migration 0011)
# sector + industry columns on candidates + trades (migration 0012)
# post-trade review surface: 10 trade fields + review_log table (migration 0013)
# phase 7 state machine + fills first-class (migration 0014)
# finviz_api_calls table (migration 0015)
# phase 8 daily_management_records table + planned_target_R column (migration 0016)
# phase 9 risk_policy + reconciliation depth (migration 0017): 5 new tables
#   (risk_policy / reconciliation_runs / reconciliation_discrepancies /
#   hypothesis_status_history / account_equity_snapshots) + 2 ALTER ADDs
#   (trades.risk_policy_id_at_lock + review_log.risk_policy_id_at_review_completion)
# phase 11 schwab API integration (migration 0018): schwab_api_calls audit
#   table + 2 ALTER ADDs (account_equity_snapshots.schwab_account_hash +
#   reconciliation_runs.schwab_api_call_id). Migration opens with explicit
#   BEGIN; / COMMIT; per Codex R1 Critical #1 (executescript implicit COMMIT
#   gotcha) — sets new discipline for all future migrations.
# phase 12 sub-bundle C.A auto-correct reconciliation (migration 0019):
#   reconciliation_corrections audit table (20 cols + 4 indexes) +
#   reconciliation_discrepancies rebuild (widen resolution CHECK 5→9 + new
#   ambiguity_kind column + cross-column CHECK) + ALTER review_log ADD
#   superseded_by_correction_id + ALTER schwab_api_calls ADD linked_correction_id +
#   trade_events rebuild (widen event_type CHECK 6→7 to add
#   'reconciliation_auto_correct'). Atomic BEGIN/COMMIT discipline preserved.
# phase 13 t2.sb1 charts patterns autofill usability (migration 0020):
#   5 new tables (pattern_exemplars + chart_renders + pattern_evaluations +
#   watchlist_close_track_flags + watchlist_close_track_flag_events) +
#   schwab_api_calls rebuild (widen surface CHECK 2 -> 4: add 'trade_entry' +
#   'trade_exit') + fills widening (4 ALTER ADDs: fill_origin DEFAULT
#   'operator_typed' + 3 audit JSON cols) + review_log widening
#   (auto_populated_field_keys_json). Atomic BEGIN/COMMIT discipline
#   preserved. OQ-12 Option E migration-only commit boundary.
# phase 13 t2.sb6c trades backlinks atomic landing (migration 0021):
#   2 NULLable INTEGER FK columns on trades — candidate_id (REFERENCES
#   candidates(id) ON DELETE SET NULL) + pattern_evaluation_id (REFERENCES
#   pattern_evaluations(id) ON DELETE SET NULL) + 2 indexes. Closes T2.SB6b
#   V1 simplifications #4 + #5; enables outcome bucketing per spec §5.10
#   lines 785-790 + line 775. Backfill semantics: NULL for all pre-v21
#   existing rows (OQ-1). Atomic BEGIN/COMMIT discipline preserved.
# phase 14 sub-bundle 3 chart-surface uniformity (migration 0023):
#   atomic rename of the chart_renders.surface old detail token to
#   'ticker_detail' via an id-preserving single-table rebuild. NO new tables,
#   NO column-shape change, NO candlestick change. Atomic BEGIN/COMMIT
#   discipline preserved (gotcha #9).
EXPECTED_SCHEMA_VERSION = 23
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Phase 7 backup gate (spec §12.1): when migrating to schema_version >= 14,
# the runner takes a SQLite-native Connection.backup() snapshot of the source
# DB and verifies it against this table set BEFORE applying any migration.
# Update this set when new tables are added in subsequent phases so the
# integrity check stays meaningful.
PHASE7_EXPECTED_TABLES: set[str] = {
    "trades",
    "exits",
    "trade_events",
    "pipeline_runs",
    "weather_runs",
    "candidates",
    "evaluation_runs",
    "daily_recommendations",
    "watchlist",
    "cash_movements",
    "review_log",
    "schema_version",
}

# Phase 8 backup gate (spec §8.2 + plan §A.5): when migrating from v15 → v16+,
# snapshot the live v15 DB. The expected table set is the ACTUAL post-Phase-7-
# post-Finviz v15 schema (NOT the Phase 7 v13 source set). Phase 7's migration
# 0014 dropped `exits` and added `fills`; migration 0015 (Finviz V1) added
# `finviz_api_calls`. Per Codex R4 Major #1: derive deterministically from the
# Phase 7 set so future maintainers can reason about provenance.
PHASE8_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    (PHASE7_EXPECTED_TABLES - {"exits"}) | {"fills", "finviz_api_calls"}
)

# Phase 9 backup gate (spec §9.3 + plan §A.0): when migrating from v16 → v17+,
# snapshot the live v16 DB. Adds `daily_management_records` to the post-Phase-8
# baseline; derive deterministically from PHASE8 set so provenance stays
# auditable. Filename pattern `swing-pre-phase9-migration-<ISO>.db`.
PHASE9_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE8_PRE_MIGRATION_EXPECTED_TABLES | {"daily_management_records"}
)

# Phase 12 Sub-bundle C backup gate (spec §11.3 + plan §A.12 + plan §B.4):
# when migrating from v18 → v19+, snapshot the live v18 DB. Adds the Phase 9
# tables (risk_policy / reconciliation_runs / reconciliation_discrepancies /
# hypothesis_status_history / account_equity_snapshots) AND the Phase 11
# schwab_api_calls audit table to the post-Phase-9 baseline. Derived
# deterministically from PHASE9 set so provenance stays auditable. Phase 11
# itself did NOT wire a version-specific gate (plan §C.5 LOCK on Sub-bundle B
# of Phase 11; no swing-pre-phase11-*.db backups exist in the wild). Filename
# pattern `swing-pre-phase12-bundle-c-migration-<ISO>.db` per plan §B.4 #1.
PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE9_PRE_MIGRATION_EXPECTED_TABLES
    | {
        "risk_policy",
        "reconciliation_runs",
        "reconciliation_discrepancies",
        "hypothesis_status_history",
        "account_equity_snapshots",
        "schwab_api_calls",
    }
)

# Phase 13 T2.SB1 backup gate (spec §3.5 + plan §B.1): when migrating from
# v19 -> v20+, snapshot the live v19 DB. Adds reconciliation_corrections
# (introduced in migration 0019) to the post-Phase-12-Sub-bundle-C baseline.
# Derived deterministically from PHASE12 set so provenance stays auditable.
# Filename pattern: ``swing-pre-phase13-migration-<ISO>.db`` per plan §B.1 +
# CLAUDE.md migration-runner backup-gate strict-equality gotcha
# (``pre_version == 19`` STRICT EQUALITY, NOT ``<=``).
PHASE13_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES
    | {"reconciliation_corrections"}
)

# Phase 13 T2.SB6c backup gate (spec §A.14 + plan §B.5): when migrating from
# v20 -> v21+, snapshot the live v20 DB. Adds the 5 v20-shipped Phase 13
# tables (pattern_exemplars + chart_renders + pattern_evaluations +
# watchlist_close_track_flags + watchlist_close_track_flag_events) to the
# post-Phase-13-v20 baseline. Derived deterministically from PHASE13 set so
# provenance stays auditable. Filename pattern:
# ``swing-pre-phase13-sb6c-migration-<ISO>.db`` per plan §B.5 + OQ-8 LOCK +
# CLAUDE.md migration-runner backup-gate strict-equality gotcha
# (``pre_version == 20`` STRICT EQUALITY, NOT ``<=``).
PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_PRE_MIGRATION_EXPECTED_TABLES
    | {
        "pattern_exemplars",
        "chart_renders",
        "pattern_evaluations",
        "watchlist_close_track_flags",
        "watchlist_close_track_flag_events",
    }
)

# Phase 14 Sub-bundle 2 backup gate (spec section 2.3 + plan T-2.1): when
# migrating from v21 -> v22+, snapshot the live v21 DB. Migration 0021 added
# only trades columns + indexes -- NO new tables -- so the table set present
# at v21 equals the set present at v20. Derived deterministically from the
# PHASE13_SB6C set so provenance stays auditable. Filename pattern:
# ``swing-pre-phase14-migration-<ISO>.db`` per CLAUDE.md migration-runner
# backup-gate strict-equality gotcha (``pre_version == 21`` STRICT EQUALITY,
# NOT ``<=``).
PHASE14_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 14 Sub-bundle 3 backup gate (plan §G Task T-3.1): when migrating from
# v22 -> v23+, snapshot the live v22 DB. Migration 0023 only renames a
# chart_renders.surface enum value via a single-table rebuild -- NO new tables
# -- so the table set present at v22 equals the set present after Sub-bundle 2
# (which added pattern_detection_events + pattern_forward_observations).
# Derived deterministically from the PHASE14 set so provenance stays auditable.
# Filename pattern ``swing-pre-phase14-sb3-migration-<ISO>.db`` per CLAUDE.md
# migration-runner backup-gate strict-equality gotcha (``pre_version == 22``
# STRICT EQUALITY, NOT ``<=``).
PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE14_PRE_MIGRATION_EXPECTED_TABLES
    | {"pattern_detection_events", "pattern_forward_observations"}
)


class SchemaVersionMismatchError(RuntimeError):
    """Raised when the DB schema version doesn't match what the code expects."""


class DuplicateOpenTradesError(RuntimeError):
    """Migration 0004 cannot apply while duplicate active-trade rows exist.

    Migration 0004 enforces the one-open-per-ticker invariant via a partial
    unique index. Pre-Phase-7 the index was keyed on ``status='open'``;
    Phase 7 re-keys it to ``state IN ('entered','managing','partial_exited')``
    once migration 0014 lands. The runtime preflight below still queries the
    legacy ``status='open'`` column because Migration 0004 fires DURING the
    0001 -> 0014 migration walk and the ``state`` column does not yet exist
    when this preflight runs. Helper-body rewrite (plan §2.1 line 165) is
    deferred to a later Sub-A task that owns the runtime call-site rewrite;
    in practice the preflight only fires once on a fresh-seed migration walk
    starting at v3 or earlier, and existing DBs already past v4 never hit it.
    """


class MigrationBackupRequiredException(RuntimeError):  # noqa: N818  -- name fixed by Phase 7 spec §12.1
    """Raised when pre-migration backup creation or verification fails.

    Migration runner refuses to apply schema changes; source DB unchanged.
    Per spec §12.1: SQLite-native Connection.backup() is the ONLY accepted
    snapshot path; size threshold is advisory; PRAGMA integrity_check must
    return exactly 'ok' and the expected table set must be present.
    """


def _apply_migration(conn: sqlite3.Connection, sql_path: Path) -> None:
    """Apply a migration SQL script atomically; rollback on any failure.

    sqlite3.Connection.executescript() leaves the in-script transaction open
    if a statement fails mid-script — without explicit rollback, a caller that
    catches the exception can later commit() the partial state and persist a
    half-applied migration. Phase 7's 0014 migration is large + invasive
    (table rebuilds, FK cascade, multi-step backfill); a half-applied state
    would leave the production DB at an undefined version with no clean
    forward path. Wrap execution in try/except to guarantee rollback on
    failure; re-raise so run_migrations() abort behavior is preserved.

    Hotfix 2026-05-05 (Sub-C integration layer; Sub-A territory exception
    authorized per chained-branch posture): toggle foreign_keys=OFF before
    executescript + restore prior value after. Migration 0014's step 10
    (CREATE-COPY-DROP-RENAME on trades) triggers ON DELETE CASCADE on
    fills.trade_id + trade_events.trade_id when foreign_keys=ON, wiping
    the just-populated fills table (5 rows) AND the audit-log trade_events
    (11 rows in production) during the table rebuild. Sub-A T10 test passed
    because the test fixture's connection had foreign_keys=OFF (sqlite3's
    default for fresh connections); production has foreign_keys=ON
    (db.ensure_schema sets it explicitly). Per SQLite docs §11.2, table-
    rebuild migrations should disable foreign_keys for the duration. Apply
    the fix at the runner level so all current + future migrations inherit
    the discipline.

    PRAGMA foreign_keys is a no-op inside an active transaction. The PRAGMA
    must be set when no transaction is open; sqlite3.Connection.executescript
    issues an implicit COMMIT before running its script, so the connection
    is in autocommit mode at the moment of the PRAGMA call.
    """
    sql = sql_path.read_text(encoding="utf-8")
    prior_fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(
            "PRAGMA foreign_keys=ON" if prior_fk else "PRAGMA foreign_keys=OFF"
        )


def _preflight_migration_0004(conn: sqlite3.Connection) -> None:
    """Reject migration 0004 if the trades table already has duplicate open rows."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
    )
    if cur.fetchone() is None:
        return
    rows = conn.execute(
        "SELECT ticker, COUNT(*) AS n FROM trades WHERE status='open' "
        "GROUP BY ticker HAVING n > 1 ORDER BY ticker"
    ).fetchall()
    if not rows:
        return
    details = ", ".join(f"{t} ({n} open)" for t, n in rows)
    raise DuplicateOpenTradesError(
        "Cannot apply migration 0004 (one-open-trade-per-ticker invariant): "
        f"duplicate open trades exist for: {details}. "
        "Inspect with: SELECT id, ticker, entry_date, entry_price, status FROM trades "
        "WHERE status='open' ORDER BY ticker, entry_date; "
        "Resolve the duplicates via the journal so the audit trail stays intact: "
        "for a legitimate exit, close the trade through `swing trade exit` "
        "(records an `exits` row and a `trade_events` row in one transaction); "
        "for an erroneous INSERT (no real fill ever occurred), keep the row "
        "and mark it closed with a correction note in a SINGLE transaction: "
        "(1) UPDATE trades SET status='closed' WHERE id=?; (2) INSERT INTO "
        "trade_events (trade_id, ts, event_type, payload_json) VALUES (?, ?, "
        "'note', json_object('correction','erroneous duplicate open — closed "
        "to resolve one-open-per-ticker invariant')). Both statements inside "
        "BEGIN/COMMIT. Never flip `trades.status` without the paired note "
        "event — the CHECK constraint only allows event_type in "
        "('entry','stop_adjust','note','exit','flag'), and deleting the bad "
        "row won't work either because `trade_events.trade_id` cascades on "
        "delete and would drop any audit note you try to attach."
    )


def _current_version(conn: sqlite3.Connection) -> int:
    """Return DB's schema_version, or 0 if no schema_version table exists."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        return 0
    cur = conn.execute("SELECT version FROM schema_version")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _create_pre_migration_backup(
    src_path: Path, *, dest_dir: Path | None = None
) -> Path:
    """Create a SQLite-native consistent-snapshot backup of ``src_path``.

    Uses ``sqlite3.Connection.backup()`` (transactional, consistent under live
    writers). ``shutil.copy2()`` is NOT acceptable per spec §12.1 — a
    filesystem-level copy of a live SQLite DB can yield a torn snapshot.
    """
    if dest_dir is None:
        dest_dir = src_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase7-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _verify_backup_integrity(
    backup_path: Path, *, expected_tables: set[str]
) -> None:
    """Run 4 binding integrity checks per spec §12.1; raise on any failure.

    Checks (each independent + separately tested):
      1. File exists at ``backup_path``.
      2. File is non-empty (size > 0). Size threshold relative to source is
         advisory only — VACUUM INTO can legitimately compact, so do NOT use
         a percentage-of-source heuristic as a hard gate.
      3. ``PRAGMA integrity_check`` returns exactly 'ok' (page-level
         corruption, broken indices, FK issues all surface here).
      4. ``sqlite_master`` contains ``expected_tables``.
    """
    if not backup_path.exists():
        raise MigrationBackupRequiredException(
            f"backup file missing: {backup_path}"
        )
    if backup_path.stat().st_size == 0:
        raise MigrationBackupRequiredException(
            f"backup file empty: {backup_path}"
        )
    conn = sqlite3.connect(backup_path)
    try:
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise MigrationBackupRequiredException(
                f"PRAGMA integrity_check failed on backup: {exc}"
            ) from exc
        if result is None or result[0] != "ok":
            raise MigrationBackupRequiredException(
                f"PRAGMA integrity_check failed on backup: {result}"
            )
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        actual_tables = {r[0] for r in rows}
        missing = expected_tables - actual_tables
        if missing:
            raise MigrationBackupRequiredException(
                f"backup missing expected table(s): {sorted(missing)}"
            )
    finally:
        conn.close()


def _resolve_main_db_path(conn: sqlite3.Connection) -> Path | None:
    """Return the filesystem path of the connection's main DB, or None for memory."""
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        # row format: (seq, name, file)
        if row[1] == "main":
            file_str = row[2] or ""
            if not file_str:
                return None
            return Path(file_str)
    return None


def _phase7_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Enforce the spec §12.1 backup-before-migrate gate for target_version >= 14.

    Fires BEFORE the migration loop. If backup creation or verification
    raises (OSError on unwritable dest, sqlite3.Error on bad I/O, etc.),
    re-raise as ``MigrationBackupRequiredException`` so callers refuse to
    migrate; the source DB is unmodified.
    """
    # Gate fires only when current_version == 13 (the only state with real
    # production data to back up; fresh installs (current=0) and mid-walk
    # states from v3-seeded tests don't need backup — the migration walk
    # passes through v13→v14 within the same run_migrations call and the
    # intermediate v13 state is transient).
    if (
        target_version < 14
        or current_version >= 14
        or current_version < 13
    ):
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        # In-memory DBs cannot be migrated to v14+ via this gate; spec §12.1
        # presumes a file-backed DB. Surface as the gate-required exception
        # rather than silently proceeding.
        raise MigrationBackupRequiredException(
            "pre-Phase-7 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_migration_backup(src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=PHASE7_EXPECTED_TABLES
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-7 backup failed: {exc}"
        ) from exc


def _create_pre_phase8_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 8 mirror of _create_pre_migration_backup with phase8 filename prefix.

    Per spec §8.2 + plan §A.5: backup file pattern
    ``swing-pre-phase8-migration-<ISO>.db``. SQLite-native Connection.backup()
    is the only acceptable snapshot mechanism (consistent under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase8-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase9_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 9 mirror of _create_pre_migration_backup with phase9 filename prefix.

    Per spec §9.3 + plan §A.0: backup file pattern
    ``swing-pre-phase9-migration-<ISO>.db``. SQLite-native Connection.backup()
    is the only acceptable snapshot mechanism (consistent under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase9-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase12_bundle_c_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 12 Sub-bundle C mirror with phase12-bundle-c filename prefix.

    Per plan §B.4 #1 + spec §11.3: backup file pattern
    ``swing-pre-phase12-bundle-c-migration-<ISO>.db``. SQLite-native
    Connection.backup() is the only acceptable snapshot mechanism (consistent
    under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase12-bundle-c-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase13_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 13 T2.SB1 mirror with phase13 filename prefix.

    Per plan §B.1 + spec §3.5: backup file pattern
    ``swing-pre-phase13-migration-<ISO>.db``. SQLite-native
    Connection.backup() is the only acceptable snapshot mechanism (consistent
    under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase13-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase13_sb6c_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 13 T2.SB6c mirror with sb6c filename prefix (OQ-8 LOCK).

    Per plan §B.5: backup file pattern
    ``swing-pre-phase13-sb6c-migration-<ISO>.db``. SQLite-native
    Connection.backup() is the only acceptable snapshot mechanism (consistent
    under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = (
        dest_dir / f"swing-pre-phase13-sb6c-migration-{timestamp}.db"
    )
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase14_sb3_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 14 Sub-bundle 3 mirror with phase14-sb3 filename prefix.

    SQLite-native Connection.backup() snapshot before the 0023 migration.
    Backup file pattern ``swing-pre-phase14-sb3-migration-<ISO>.db``.
    SQLite-native Connection.backup() is the only acceptable snapshot
    mechanism (consistent under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = (
        dest_dir / f"swing-pre-phase14-sb3-migration-{timestamp}.db"
    )
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _create_pre_phase14_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Phase 14 Sub-bundle 2 mirror with phase14 filename prefix.

    SQLite-native Connection.backup() snapshot before the 0022 migration.
    Backup file pattern ``swing-pre-phase14-migration-<ISO>.db``. Temp file
    created in dest_dir (os.replace same-filesystem gotcha). SQLite-native
    Connection.backup() is the only acceptable snapshot mechanism (consistent
    under live writers).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = (
        dest_dir / f"swing-pre-phase14-migration-{timestamp}.db"
    )
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _phase8_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 8 spec §8.2 backup-before-migrate gate (plan §A.5 + §1.0 Step 3).

    Fires only when ``current_version == 15 AND target_version >= 16`` —
    i.e., a real production v15 DB about to receive Phase 8's migration 0016.
    Mutually exclusive with ``_phase7_backup_gate`` by construction
    (current_version == 13 vs 15); both gates can coexist without conflict.
    Filename: ``swing-pre-phase8-migration-<ISO>.db`` (NOT phase7 prefix).
    """
    if target_version < 16 or current_version != 15:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-8 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase8_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE8_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-8 backup failed: {exc}"
        ) from exc


def _phase9_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 9 spec §9.3 backup-before-migrate gate (plan §A.0).

    Fires only when ``current_version == 16 AND target_version >= 17`` —
    i.e., a real production v16 DB about to receive Phase 9's migration 0017.
    Mutually exclusive with ``_phase7_backup_gate`` and ``_phase8_backup_gate``
    by construction (current_version == 13 vs 15 vs 16); all three gates can
    coexist without conflict. Filename: ``swing-pre-phase9-migration-<ISO>.db``
    (NOT phase7 / phase8 prefix).
    """
    if target_version < 17 or current_version != 16:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-9 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase9_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE9_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-9 backup failed: {exc}"
        ) from exc


def _phase12_bundle_c_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 12 Sub-bundle C backup-before-migrate gate (plan §B.4 + §A.12).

    Fires only when ``current_version == 18 AND target_version >= 19`` —
    i.e., a real production v18 DB about to receive Phase 12 Sub-bundle C's
    migration 0019. Mutually exclusive with the Phase 7/8/9 gates by
    construction (current_version == 13 vs 15 vs 16 vs 18). Filename:
    ``swing-pre-phase12-bundle-c-migration-<ISO>.db`` (NOT phase7/8/9 prefix).

    Phase 11 (v17 → v18) did NOT wire a version-specific gate per plan
    §C.5 LOCK on Phase 11 Sub-bundle B's migration 0018 ship; this gate
    closes the v18 → v19 transition specifically.

    INTENTIONAL NARROWNESS (ACCEPT-WITH-RATIONALE, Codex R1 Major #1):
    Multi-step migrations from a pre-v18 baseline (e.g., v15 → v19, v17 →
    v19) BYPASS this gate by design — the predicate ``current_version != 18``
    is evaluated ONCE at ``run_migrations`` entry, not before each individual
    schema-jump migration. A DB at v17 advancing to v19 sees the gate
    evaluated with ``current_version=17`` (returns early); the migration
    loop then walks 17→18→19 internally with no further gate evaluation.
    This matches ``_phase9_backup_gate`` precedent verbatim (equality
    predicate ``current_version != 16`` at run_migrations entry; multi-step
    walks from pre-v16 likewise bypass).

    Production operators on v18 (the current state at integration-merge
    time, per CLAUDE.md Phase 11 ship entry) fire the gate on next
    ``swing db-migrate``. Operators who skipped a phase (extremely uncommon
    in this project's history — phase ships are integration-merged
    sequentially) should run a manual one-off backup via Python
    ``sqlite3.Connection.backup()`` (the same SQLite-native mechanism the
    in-tree gates use; matches spec §12.1 binding posture and avoids
    relying on the ``sqlite3`` CLI being installed on PATH).

    Forward-binding note (V2 hardening candidate): firing the gate before
    each individual schema-jump migration (per-version backups instead of
    per-target backups) is a candidate banked at plan §I for V2 dispatch.
    The current per-target design is preserved because:
      (a) the only real-world scenario where it matters is a deliberately
          long-skipped operator state, which has never occurred in the
          project's history;
      (b) per-version backups would generate N intermediate snapshots that
          mostly duplicate each other on a single ``db-migrate`` invocation,
          consuming disk space proportional to the version-jump distance;
      (c) the alternative — a single backup at the FIRST in-flight version
          rather than at the target version — would also work but would
          require a non-trivial refactor of the four phase-specific gates
          into a unified version-aware backup-once helper.
    """
    if target_version < 19 or current_version != 18:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-12-Sub-bundle-C backup gate requires a file-backed "
            "source DB; in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase12_bundle_c_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-12-Sub-bundle-C backup failed: {exc}"
        ) from exc


def _phase13_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 13 T2.SB1 backup-before-migrate gate (plan §B.1 + spec §3.5).

    Fires only when ``current_version == 19 AND target_version >= 20`` —
    i.e., a real production v19 DB about to receive Phase 13's migration
    0020. STRICT EQUALITY on pre_version per CLAUDE.md gotcha "Migration
    runner backup-gate equality form: pre_version == (target - 1) strict
    equality, NOT pre_version <= (target - 1)". Multi-step migration walks
    from pre-v19 baselines bypass this gate by design (matches Phase 9 /
    Phase 12 C.A precedent).

    Filename: ``swing-pre-phase13-migration-<ISO>.db`` (NOT
    phase7/8/9/12-bundle-c prefix).
    """
    if target_version < 20 or current_version != 19:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-13 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase13_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE13_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-13 backup failed: {exc}"
        ) from exc


def _phase13_sb6c_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 13 T2.SB6c backup-before-migrate gate (plan §B.5 + spec §A.14).

    Fires only when ``current_version == 20 AND target_version >= 21`` —
    i.e., a real production v20 DB about to receive Phase 13's migration
    0021. STRICT EQUALITY on pre_version per CLAUDE.md gotcha "Migration
    runner backup-gate equality form: pre_version == (target - 1) strict
    equality, NOT pre_version <= (target - 1)" (OQ-3 LOCK). Multi-step
    migration walks from pre-v20 baselines bypass this gate by design
    (matches Phase 9 / Phase 12 C.A / Phase 13 T-A.1.1 precedent).

    Filename: ``swing-pre-phase13-sb6c-migration-<ISO>.db`` (NOT
    phase7/8/9/12-bundle-c/phase13-v20 prefix).
    """
    if target_version < 21 or current_version != 20:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-13-SB6c backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase13_sb6c_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-13-SB6c backup failed: {exc}"
        ) from exc


def _phase14_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 14 Sub-bundle 2 backup-before-migrate gate.

    Fires only when ``current_version == 21 AND target_version >= 22`` -- a
    real production v21 DB about to receive migration 0022. STRICT EQUALITY
    on pre_version per CLAUDE.md gotcha ``pre_version == (target - 1)`` (NOT
    ``<=``). Multi-step walks from pre-v21 baselines bypass this gate by
    design (matches Phase 9 / 12 C.A / 13 precedent).

    Filename: ``swing-pre-phase14-migration-<ISO>.db``.
    """
    if target_version < 22 or current_version != 21:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-14 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase14_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE14_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-14 backup failed: {exc}"
        ) from exc


def _phase14_sb3_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 14 Sub-bundle 3 backup-before-migrate gate (plan §G Task T-3.1).

    Fires only when ``current_version == 22 AND target_version >= 23`` -- a
    real production v22 DB about to receive migration 0023 (chart_renders
    surface rename). STRICT EQUALITY on pre_version per CLAUDE.md gotcha
    ``pre_version == (target - 1)`` (NOT ``<=``). Multi-step walks from
    pre-v22 baselines bypass this gate by design (matches Phase 9 / 12 C.A /
    13 / 14 SB2 precedent).

    Filename: ``swing-pre-phase14-sb3-migration-<ISO>.db``.
    """
    if target_version < 23 or current_version != 22:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-14-SB3 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase14_sb3_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-14-SB3 backup failed: {exc}"
        ) from exc


def run_migrations(
    conn: sqlite3.Connection,
    *,
    target_version: int = EXPECTED_SCHEMA_VERSION,
    backup_dir: Path | None = None,
) -> None:
    """Apply pending SQL migrations on ``conn`` up to ``target_version``.

    Phase 7 spec §12.1 backup gate: when migrating to ``target_version >= 14``
    from a pre-14 DB, take a SQLite-native ``Connection.backup()`` snapshot
    and verify integrity BEFORE applying any migration. If the backup or
    verification fails, raise ``MigrationBackupRequiredException`` and leave
    the source DB unchanged.

    Note: target_version semantics — this runner only applies migrations
    whose version number is ``<= min(target_version, EXPECTED_SCHEMA_VERSION)``.
    Passing ``target_version=14`` before migration 0014 is registered fires
    the backup gate (correct per spec) but does not actually advance past
    EXPECTED_SCHEMA_VERSION; the gate is "ready" for T2 to land 0014.
    """
    current = _current_version(conn)
    if current >= target_version:
        return

    _phase7_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase8_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase9_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase12_bundle_c_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase13_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase13_sb6c_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase14_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase14_sb3_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )

    apply_ceiling = min(target_version, EXPECTED_SCHEMA_VERSION)
    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for mig in migration_files:
        try:
            version = int(mig.stem.split("_", 1)[0])
        except ValueError:
            continue
        if current < version <= apply_ceiling:
            if version == 4:
                _preflight_migration_0004(conn)
            _apply_migration(conn, mig)

    final_version = _current_version(conn)
    if (
        target_version <= EXPECTED_SCHEMA_VERSION
        and final_version != target_version
    ):
        raise RuntimeError(
            "Migration ran but schema_version did not reach expected value."
        )


def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Create or upgrade the DB schema. Use from the CLI migrate command, NOT from app startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    current = _current_version(conn)
    if current == EXPECTED_SCHEMA_VERSION:
        return conn
    if current > EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatchError(
            f"DB schema version {current} newer than code ({EXPECTED_SCHEMA_VERSION}). "
            "Update the swing package."
        )

    try:
        run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION)
    except Exception:
        conn.close()
        raise
    return conn


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection for normal app use. Raises if schema is not current."""
    if not db_path.exists():
        raise SchemaVersionMismatchError(
            f"DB not found at {db_path}. Run: swing db-migrate"
        )
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    current = _current_version(conn)
    if current != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatchError(
            f"DB schema version {current}, code expects {EXPECTED_SCHEMA_VERSION}. "
            "Run: swing db-migrate"
        )
    return conn
