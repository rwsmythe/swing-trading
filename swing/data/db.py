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
EXPECTED_SCHEMA_VERSION = 14
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


class SchemaVersionMismatch(RuntimeError):
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
    sql = sql_path.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


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
    if target_version < 14 or current_version >= 14:
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
        raise SchemaVersionMismatch(
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
        raise SchemaVersionMismatch(
            f"DB not found at {db_path}. Run: swing db-migrate"
        )
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    current = _current_version(conn)
    if current != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatch(
            f"DB schema version {current}, code expects {EXPECTED_SCHEMA_VERSION}. "
            "Run: swing db-migrate"
        )
    return conn
