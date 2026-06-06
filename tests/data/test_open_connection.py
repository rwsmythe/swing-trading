import sqlite3
import pytest
from pathlib import Path
from swing.data.db import open_connection, DEFAULT_BUSY_TIMEOUT_MS, ensure_schema


def test_default_busy_timeout_constant():
    assert DEFAULT_BUSY_TIMEOUT_MS == 30000


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()  # creates a migrated WAL DB
    return db


def test_open_connection_applies_default_busy_timeout(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_open_connection_keyword_override(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=1234)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 1234
    finally:
        conn.close()


def test_open_connection_no_wal_reaffirm_by_default_but_db_stays_wal(tmp_path):
    # reaffirm_wal=False must NOT issue PRAGMA journal_mode=WAL, yet the DB is
    # already persistently WAL from ensure_schema -> journal_mode reads 'wal'.
    db = _make_db(tmp_path)
    conn = open_connection(db, reaffirm_wal=False)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_open_connection_reaffirm_wal_sets_wal(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, reaffirm_wal=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_open_connection_uri_mode_rw_is_fail_closed(tmp_path):
    # mode=rw must REFUSE to create a missing DB (fail-closed); default rwc
    # would fabricate one. Proves uri=True forwarding preserves backup semantics.
    missing = tmp_path / "does-not-exist.db"
    uri = "file:" + missing.as_posix() + "?mode=rw"
    with pytest.raises(sqlite3.OperationalError):
        open_connection(uri, uri=True)
    assert not missing.exists()  # not fabricated


def test_open_connection_check_same_thread_false_allowed(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, check_same_thread=False)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        conn.close()
