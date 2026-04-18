"""SQLite connection + migrations + schema-version gate."""
from __future__ import annotations

import sqlite3
from pathlib import Path

EXPECTED_SCHEMA_VERSION = 4  # partial unique index on trades(ticker) WHERE status='open'
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class SchemaVersionMismatch(RuntimeError):
    """Raised when the DB schema version doesn't match what the code expects."""


def _apply_migration(conn: sqlite3.Connection, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


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

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for mig in migration_files:
        try:
            version = int(mig.stem.split("_", 1)[0])
        except ValueError:
            continue
        if current < version <= EXPECTED_SCHEMA_VERSION:
            _apply_migration(conn, mig)

    if _current_version(conn) != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise RuntimeError("Migration ran but schema_version did not reach expected value.")
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
