import sqlite3
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.data.backup import do_backup


def test_backup_under_wal_with_open_writer_passes_integrity(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    # An open writer connection (simulating a live pipeline writer).
    writer = open_connection(db, busy_timeout_ms=30000)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, surface, environment, status) "
        "VALUES ('2026-06-06T00:00:00Z','marketdata.pricehistory','pipeline','production','in_flight')"
    )
    writer.commit()
    dest_dir = tmp_path / "backups"
    try:
        final = do_backup(db, dest_dir)
        chk = sqlite3.connect(final)
        try:
            assert chk.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            chk.close()
    finally:
        writer.close()


def test_backup_source_still_fail_closed_on_missing_db(tmp_path):
    # mode=rw must refuse a missing source (NOT create it) -- preserved after
    # routing through open_connection.
    missing = tmp_path / "nope.db"
    with pytest.raises(sqlite3.OperationalError):
        do_backup(missing, tmp_path / "backups")
    assert not missing.exists()
