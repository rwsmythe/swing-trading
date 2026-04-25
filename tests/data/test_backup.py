"""Weekly DB backup helper — atomic copy + ISO-week naming + retention."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from swing.data.backup import (
    compute_backup_destination,
    do_backup,
    prune_old_backups,
    should_backup,
)


def _make_seeded_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t(x INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(50)])
        conn.commit()
    finally:
        conn.close()


def test_compute_backup_destination_uses_iso_year_and_week():
    """ISO 2026 week 17 → swing-202617.db. Format: swing-{YYYY}{WW:02d}.db."""
    dest_dir = Path("/tmp/backups")
    # 2026-04-25 is Saturday of ISO week 17, 2026.
    dt = datetime(2026, 4, 25, 12, 0, 0)
    p = compute_backup_destination(dt, dest_dir)
    assert p == dest_dir / "swing-202617.db"


def test_compute_backup_destination_iso_year_can_differ_from_calendar_year():
    """ISO year boundary: 2025-12-29 (Mon) is in ISO 2026 week 1 — verify."""
    dt = datetime(2025, 12, 29, 12, 0, 0)
    p = compute_backup_destination(dt, Path("/tmp"))
    # Python's isocalendar(): year=2026, week=1.
    iso = dt.isocalendar()
    assert (iso.year, iso.week) == (2026, 1)
    assert p.name == "swing-202601.db"


def test_should_backup_true_when_dest_missing(tmp_path: Path):
    """No dest_dir → no backup yet → should_backup returns True."""
    dest = tmp_path / "no-such-dir"
    assert should_backup(dest, datetime(2026, 4, 25)) is True


def test_should_backup_false_when_current_week_backup_exists(tmp_path: Path):
    """Current ISO-week backup file present → should_backup returns False."""
    dest = tmp_path / "backups"
    dest.mkdir()
    (dest / "swing-202617.db").write_bytes(b"placeholder")
    assert should_backup(dest, datetime(2026, 4, 25)) is False


def test_should_backup_true_when_only_other_weeks_present(tmp_path: Path):
    """Older-week backup files don't satisfy the current-week check."""
    dest = tmp_path / "backups"
    dest.mkdir()
    (dest / "swing-202616.db").write_bytes(b"old")
    (dest / "swing-202615.db").write_bytes(b"older")
    assert should_backup(dest, datetime(2026, 4, 25)) is True


def test_do_backup_creates_destination_directory(tmp_path: Path):
    """do_backup must create dest_dir if missing — first-run UX."""
    src = tmp_path / "swing.db"
    _make_seeded_db(src)
    dest = tmp_path / "fresh-backups"
    out = do_backup(src, dest, now=datetime(2026, 4, 25))
    assert out.exists()
    assert out.parent == dest


def test_do_backup_produces_readable_sqlite_copy(tmp_path: Path):
    """The backup file must be a valid SQLite DB with the source rows intact."""
    src = tmp_path / "swing.db"
    _make_seeded_db(src)
    dest = tmp_path / "backups"
    out = do_backup(src, dest, now=datetime(2026, 4, 25))
    conn = sqlite3.connect(out)
    try:
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        assert n == 50
    finally:
        conn.close()


def test_do_backup_filename_matches_iso_week(tmp_path: Path):
    """do_backup writes to swing-{YYYY}{WW:02d}.db, no other files."""
    src = tmp_path / "swing.db"
    _make_seeded_db(src)
    dest = tmp_path / "backups"
    out = do_backup(src, dest, now=datetime(2026, 4, 25))
    assert out.name == "swing-202617.db"
    # No leftover temp files.
    assert sorted(p.name for p in dest.iterdir()) == ["swing-202617.db"]


def test_do_backup_overwrites_same_week_via_atomic_replace(tmp_path: Path):
    """Two calls in the same week → second call replaces the first atomically."""
    src = tmp_path / "swing.db"
    _make_seeded_db(src)
    dest = tmp_path / "backups"
    do_backup(src, dest, now=datetime(2026, 4, 25))

    # Mutate the source so the second backup has different bytes.
    conn = sqlite3.connect(src)
    try:
        conn.execute("INSERT INTO t VALUES (999)")
        conn.commit()
    finally:
        conn.close()

    out2 = do_backup(src, dest, now=datetime(2026, 4, 25))
    conn = sqlite3.connect(out2)
    try:
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        assert n == 51
    finally:
        conn.close()
    # Still exactly one backup file for the week, no temp leftovers.
    assert sorted(p.name for p in dest.iterdir()) == ["swing-202617.db"]


def test_prune_old_backups_keeps_latest_n(tmp_path: Path):
    """prune_old_backups(keep=12) deletes everything beyond the 12 latest by name."""
    dest = tmp_path / "backups"
    dest.mkdir()
    # 15 weeks of backups, weeks 1..15 in 2026.
    for w in range(1, 16):
        (dest / f"swing-2026{w:02d}.db").write_bytes(b"x")
    deleted = prune_old_backups(dest, keep=12)
    remaining = sorted(p.name for p in dest.glob("swing-*.db"))
    assert len(remaining) == 12
    # Latest 12 → weeks 4..15.
    assert remaining[0] == "swing-202604.db"
    assert remaining[-1] == "swing-202615.db"
    assert sorted(p.name for p in deleted) == [
        "swing-202601.db", "swing-202602.db", "swing-202603.db",
    ]


def test_prune_old_backups_no_op_when_under_keep(tmp_path: Path):
    """Fewer than `keep` backups → nothing deleted."""
    dest = tmp_path / "backups"
    dest.mkdir()
    for w in range(10, 13):
        (dest / f"swing-2026{w:02d}.db").write_bytes(b"x")
    deleted = prune_old_backups(dest, keep=12)
    assert deleted == []
    assert len(list(dest.glob("swing-*.db"))) == 3


def test_prune_old_backups_ignores_unrelated_files(tmp_path: Path):
    """Non-weekly-pattern files (db-migrate timestamp backups, manual notes) are
    never deleted, even though they match the loose `swing-*.db` glob."""
    dest = tmp_path / "backups"
    dest.mkdir()
    # 13 weekly backups so pruning would remove 1 ⇒ test that ONLY a weekly is
    # the deletion target, not the migrate-style timestamp files.
    for w in range(1, 14):
        (dest / f"swing-2026{w:02d}.db").write_bytes(b"x")
    # db-migrate format: swing-{ts}.db where ts is YYYYMMDDTHHMMSS.
    (dest / "swing-20260425T120000.db").write_bytes(b"manual")
    (dest / "operator-snapshot.db").write_bytes(b"manual")

    deleted = prune_old_backups(dest, keep=12)
    deleted_names = sorted(p.name for p in deleted)
    assert deleted_names == ["swing-202601.db"]
    # Manual snapshots untouched.
    assert (dest / "swing-20260425T120000.db").exists()
    assert (dest / "operator-snapshot.db").exists()


def test_prune_old_backups_handles_missing_dir(tmp_path: Path):
    """Dest dir missing → no error, returns []."""
    dest = tmp_path / "no-such-dir"
    assert prune_old_backups(dest, keep=12) == []


def test_do_backup_under_concurrent_writes_does_not_corrupt(tmp_path: Path):
    """sqlite3 Connection.backup is the contract — verify a backup taken while a
    second connection has an open write transaction still produces a queryable
    SQLite file. This documents the design choice (use sqlite3 backup API, not
    raw shutil.copyfileobj) for WAL-mode safety."""
    src = tmp_path / "swing.db"
    _make_seeded_db(src)

    holder = sqlite3.connect(src)
    try:
        # Begin an open write transaction; do not commit until after backup.
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO t VALUES (1234)")
        # Backup should still produce a consistent file (without the uncommitted
        # row, which is by-design).
        dest = tmp_path / "backups"
        out = do_backup(src, dest, now=datetime(2026, 4, 25))
        holder.commit()
    finally:
        holder.close()

    conn = sqlite3.connect(out)
    try:
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        # The uncommitted row was excluded; the 50 originals are present.
        assert n == 50
    finally:
        conn.close()
