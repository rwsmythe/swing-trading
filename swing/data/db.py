"""SQLite connection + migrations + schema-version gate."""
from __future__ import annotations

import sqlite3
from pathlib import Path

EXPECTED_SCHEMA_VERSION = 10  # chart-pattern persistence (pipeline_pattern_classifications + trade chart_pattern columns)
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class SchemaVersionMismatch(RuntimeError):
    """Raised when the DB schema version doesn't match what the code expects."""


class DuplicateOpenTradesError(RuntimeError):
    """Migration 0004 cannot apply while duplicate status='open' rows exist.

    Adversarial review Batch 3 Round 2 Major: CREATE UNIQUE INDEX would fail
    with a generic SQLite error, leaving users stuck at v3 with no forward path.
    Preflight detects the duplicates and surfaces them with actionable guidance.
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
        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        for mig in migration_files:
            try:
                version = int(mig.stem.split("_", 1)[0])
            except ValueError:
                continue
            if current < version <= EXPECTED_SCHEMA_VERSION:
                if version == 4:
                    _preflight_migration_0004(conn)
                _apply_migration(conn, mig)

        if _current_version(conn) != EXPECTED_SCHEMA_VERSION:
            raise RuntimeError("Migration ran but schema_version did not reach expected value.")
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
