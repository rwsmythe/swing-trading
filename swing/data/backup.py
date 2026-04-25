"""Weekly DB backup helper.

The first pipeline run of each ISO calendar week produces a snapshot at
`<dest_dir>/swing-{YYYY}{WW:02d}.db` and prunes older snapshots beyond the
configured retention. Manual triggering is exposed via `swing db-backup`.

Design notes:
  * SQLite runs in WAL mode (PRAGMA journal_mode=WAL on first open). A naive
    byte-level copy of the .db file alone can miss data still in the .db-wal
    sidecar or capture a torn read mid-checkpoint. We use sqlite3's online
    backup API (`Connection.backup`) which produces a single self-contained
    file regardless of WAL state and is safe under concurrent writers.
  * Atomic-replace pattern: copy into a temp file inside `dest_dir` (same
    filesystem) then `os.replace` to the final name. Putting the temp file in
    the destination directory avoids `OSError: Invalid cross-device link` on
    Windows when `$TMP` lives on a different volume than the destination
    (CLAUDE.md gotcha).
  * Pruning: only filenames matching the strict `swing-YYYYWW.db` pattern are
    eligible for deletion — manual operator snapshots and the migrate-style
    timestamp backups (`swing-YYYYMMDDTHHMMSS.db`) are left alone.
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

# Strict ISO-week filename: swing-{YYYY}{WW:02d}.db. Six digits, no separators.
_WEEKLY_BACKUP_RE = re.compile(r"^swing-\d{6}\.db$")


def compute_backup_destination(now: datetime, dest_dir: Path) -> Path:
    """Return the canonical backup path for the ISO calendar week of `now`."""
    iso = now.isocalendar()
    return dest_dir / f"swing-{iso.year:04d}{iso.week:02d}.db"


def should_backup(dest_dir: Path, now: datetime) -> bool:
    """True iff no backup file exists for the ISO calendar week of `now`."""
    target = compute_backup_destination(now, dest_dir)
    return not target.exists()


def do_backup(db_path: Path, dest_dir: Path, *, now: datetime | None = None) -> Path:
    """Snapshot `db_path` to `dest_dir/swing-{YYYY}{WW:02d}.db`.

    Atomic via temp-in-dest + os.replace. Uses sqlite3's online backup API so
    the result is consistent even if other connections hold WAL writes.
    """
    if now is None:
        now = datetime.now()
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_path = compute_backup_destination(now, dest_dir)

    # Temp file on the same filesystem as the destination (Windows os.replace
    # cannot cross volumes). delete=False because we need to write+close before
    # opening as a sqlite3 destination connection on Windows.
    fd, tmp_str = tempfile.mkstemp(prefix=".backup-", suffix=".db.tmp", dir=str(dest_dir))
    os.close(fd)
    tmp_path = Path(tmp_str)
    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp_path)
        src.backup(dst)
    except BaseException:
        # Clean up the partial temp file on any failure (including Ctrl-C).
        try:
            if dst is not None:
                dst.close()
        finally:
            try:
                if src is not None:
                    src.close()
            finally:
                tmp_path.unlink(missing_ok=True)
        raise
    else:
        dst.close()
        src.close()

    os.replace(tmp_path, final_path)
    return final_path


def prune_old_backups(dest_dir: Path, keep: int) -> list[Path]:
    """Delete weekly backups beyond the `keep` most recent. Returns deleted paths.

    Only files matching `swing-YYYYWW.db` are candidates. Sort is by filename
    descending; ISO YYYY-then-WW is monotonic within a year and across years.
    """
    if not dest_dir.exists():
        return []
    weekly = sorted(
        (p for p in dest_dir.glob("swing-*.db") if _WEEKLY_BACKUP_RE.match(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    to_delete = weekly[keep:]
    deleted: list[Path] = []
    for p in to_delete:
        p.unlink()
        deleted.append(p)
    return deleted
