from pathlib import Path
from swing.data.db import connect, ensure_schema


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_connect_applies_30s_busy_timeout(tmp_path):
    # ARITHMETIC (feedback_regression_test_arithmetic): pre-fix connect() used
    # sqlite3.connect(db_path) with no busy_timeout -> Python's default
    # timeout=5.0 surfaces as PRAGMA busy_timeout == 5000. Post-fix it is 30000.
    # Asserting == 30000 (which 5000 fails) is the genuine discriminator.
    db = _make_db(tmp_path)
    conn = connect(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        conn.close()


def test_connect_journal_mode_is_wal_regression_pin(tmp_path):
    # journal_mode reads 'wal' BOTH pre- and post-fix (persistent). This is a
    # regression PIN, not the discriminator.
    db = _make_db(tmp_path)
    conn = connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_connect_busy_timeout_keyword_override(tmp_path):
    db = _make_db(tmp_path)
    conn = connect(db, busy_timeout_ms=7777)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 7777
    finally:
        conn.close()


def test_ensure_schema_applies_busy_timeout_and_wal(tmp_path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
