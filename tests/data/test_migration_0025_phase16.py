# tests/data/test_migration_0025_phase16.py
from __future__ import annotations

from pathlib import Path

import pytest  # noqa: F401

from swing.data import db as dbmod  # noqa: F401
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    open_connection,
    run_migrations,
    _current_version,
    _phase16_backup_gate,
)


def _migrate_to(db_path: Path, version: int, backup_dir: Path | None = None):
    # open_connection is the canonical opener (busy_timeout + FK + WAL); it creates
    # the file if missing and does NOT enforce a schema-version gate, so it can build
    # a DB at any target version. (connect() also works but reaffirm_wal=True matches
    # ensure_schema's bootstrap; mirror the existing migration tests.)
    conn = open_connection(db_path, reaffirm_wal=True)
    run_migrations(conn, target_version=version, backup_dir=backup_dir)
    return conn


def test_expected_schema_version_is_25():
    assert EXPECTED_SCHEMA_VERSION == 27


def test_migrate_to_25_creates_table(tmp_path):
    db = tmp_path / "swing.db"
    conn = _migrate_to(db, 25)
    assert _current_version(conn) == 25
    # connect() sets NO row_factory -> rows are tuples; PRAGMA table_info columns
    # are (cid, name, type, notnull, dflt_value, pk) -> name is index 1.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_step_timings)")}
    assert cols == {
        "id", "run_id", "ordinal", "step_name",
        "started_ts", "finished_ts", "duration_ms",
    }
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    db = tmp_path / "swing.db"
    _migrate_to(db, 25).close()
    conn = open_connection(db, reaffirm_wal=True)
    run_migrations(conn, target_version=25)  # current >= target -> early return
    assert _current_version(conn) == 25
    conn.close()


def test_backup_gate_fires_strict_on_v24(tmp_path):
    # Each gate call uses its OWN backup_dir so a second-resolution timestamp
    # collision in the filename cannot mask a second backup (count per-dir is 0/1).
    db = tmp_path / "swing.db"
    conn = _migrate_to(db, 24)  # build a real v24 DB (no gate fires at 24)

    def _count(d):
        return len(list(d.glob("swing-pre-phase16-migration-*.db")))

    inert = tmp_path / "b_inert"      # current=25 -> must NOT fire
    fire_25 = tmp_path / "b_25"       # current=24, target=25 -> fires
    fire_26 = tmp_path / "b_26"       # current=24, target=26 -> fires (crossing v25)
    naive_bug = tmp_path / "b_naive"  # current=23, target=25 -> STRICT skips; a <=24 bug fires

    _phase16_backup_gate(conn, current_version=25, target_version=26, backup_dir=inert)
    _phase16_backup_gate(conn, current_version=24, target_version=25, backup_dir=fire_25)
    _phase16_backup_gate(conn, current_version=24, target_version=26, backup_dir=fire_26)
    _phase16_backup_gate(conn, current_version=23, target_version=25, backup_dir=naive_bug)

    assert _count(inert) == 0
    assert _count(fire_25) == 1
    assert _count(fire_26) == 1
    assert _count(naive_bug) == 0  # the discriminator: a `current_version <= 24` bug -> 1 here
    conn.close()


def test_run_migrations_wires_phase16_gate(tmp_path):
    # Proves _phase16_backup_gate is actually WIRED into run_migrations (a direct
    # gate call cannot catch a missing wire). A real v24->v25 walk through the runner
    # must produce a backup; a fresh 0->25 build must NOT (current=0 != 24, strict).
    fresh_backups = tmp_path / "fresh"
    fresh = tmp_path / "fresh.db"
    _migrate_to(fresh, 25, backup_dir=fresh_backups).close()  # 0->25, gate inert
    assert not list(fresh_backups.glob("swing-pre-phase16-migration-*.db"))

    v24_backups = tmp_path / "v24b"
    db = tmp_path / "swing.db"
    _migrate_to(db, 24).close()  # build v24
    conn = open_connection(db, reaffirm_wal=True)
    run_migrations(conn, target_version=25, backup_dir=v24_backups)  # v24->v25 via runner
    assert _current_version(conn) == 25
    assert {r[1] for r in conn.execute("PRAGMA table_info(pipeline_step_timings)")}
    assert len(list(v24_backups.glob("swing-pre-phase16-migration-*.db"))) == 1
    conn.close()

    # v24 -> v26 through the REAL runner: the phase16 gate fires (crossing v25);
    # apply_ceiling = min(26, EXPECTED_SCHEMA_VERSION=26) = 26 now, so the walk
    # applies 0025 then 0026 and reaches 26 (no longer ceiling-clamped at 25 --
    # the ceiling now equals the target). The broad-watch gate is INERT here
    # because the runner evaluates gates once against the ORIGINAL current=24
    # (not 25), so only the phase16 backup is written.
    v26_backups = tmp_path / "v26b"
    db26 = tmp_path / "swing26.db"
    _migrate_to(db26, 24).close()
    conn26 = open_connection(db26, reaffirm_wal=True)
    run_migrations(conn26, target_version=26, backup_dir=v26_backups)
    assert _current_version(conn26) == 26  # ceiling now equals the target (v26)
    assert len(list(v26_backups.glob("swing-pre-phase16-migration-*.db"))) == 1
    # the broad-watch gate is INERT in this v24->v26 walk (gates evaluate against
    # the ORIGINAL current=24, not 25), so it must have written NO backup.
    assert list(v26_backups.glob("swing-pre-broad-watch-baseline-migration-*.db")) == []
    conn26.close()
