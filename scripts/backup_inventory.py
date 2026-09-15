"""Read-only inventory of swing-data backup images (D32 / F4). Stdlib only.

Scans, NON-recursively:
  * ``<root>/swing-pre-*.db``            -- pre-migration gate images beside the DB
  * ``<backups>/*.db``                   -- CLI copies, weekly backups, gate images
  * ``<backups>/pre-images/*.db``        -- gate images after the F4(a) move

For every file it prints location, class, size, mtime, the schema version read
as ``SELECT version FROM schema_version`` (``unknown`` when the table is absent;
``PRAGMA user_version`` reads 0 on this project's DBs and is never used), the
sha256 of the bytes, and -- for each CLI copy -- the gate image(s) with the SAME
sha256 (its byte-identical twin), or ``none``.

Classes, by NAME only:
  gate-image    ``swing-pre-*``
  cli-copy      ``swing-YYYYMMDDTHHMMSS.db``   (swing/cli.py db-migrate)
  weekly-backup ``swing-YYYYWW.db``            (swing/data/backup.py _WEEKLY_BACKUP_RE)
  unclassified  anything else -- PRINTED with its path, never skipped

THIS SCRIPT WRITES NOTHING AND MOVES NOTHING. Each DB is opened with plain
``sqlite3`` as ``file:...?mode=ro&immutable=1``. ``immutable=1`` is load-bearing,
not belt: every image written by ``Connection.backup()`` from a WAL-mode source
carries the WAL header, and a plain ``mode=ro`` open of such a file CREATES
``-shm``/``-wal`` sidecars beside it (measured 2026-09-14). A ``-wal`` sidecar
already present is reported (``wal_sidecar=present``) because an immutable read
does not see its contents. ``swing``'s own ``connect``/``ensure_schema`` are
never imported (they would migrate a recovery artifact).

Usage:
    python scripts/backup_inventory.py [--root DIR] [--backups-dir DIR]
Defaults: root = ~/swing-data ; backups-dir = <root>/backups
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_CLI_COPY_RE = re.compile(r"^swing-\d{8}T\d{6}\.db$")
_WEEKLY_RE = re.compile(r"^swing-\d{6}\.db$")
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Entry:
    location: str
    cls: str
    path: Path
    size: int
    mtime: str
    version: str
    sha256: str
    wal_sidecar: bool


def classify(name: str) -> str:
    if name.startswith("swing-pre-"):
        return "gate-image"
    if _CLI_COPY_RE.match(name):
        return "cli-copy"
    if _WEEKLY_RE.match(name):
        return "weekly-backup"
    return "unclassified"


def read_schema_version(path: Path) -> str:
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        return f"error:{type(exc).__name__}:{exc}"
    try:
        has = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if has is None:
            return "unknown"
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return "unknown" if row is None else str(int(row[0]))
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return f"error:{type(exc).__name__}:{exc}"
    finally:
        conn.close()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _scan(location: str, directory: Path, pattern: str) -> list[Entry]:
    if not directory.is_dir():
        return []
    out = []
    for p in sorted(directory.glob(pattern)):
        if not p.is_file():
            continue
        st = p.stat()
        out.append(Entry(
            location=location,
            cls=classify(p.name),
            path=p,
            size=st.st_size,
            mtime=datetime.fromtimestamp(st.st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            version=read_schema_version(p),
            sha256=sha256_of(p),
            wal_sidecar=Path(str(p) + "-wal").exists(),
        ))
    return out


def inventory(root: Path, backups_dir: Path) -> list[Entry]:
    return (
        _scan("root", root, "swing-pre-*.db")
        + _scan("backups", backups_dir, "*.db")
        + _scan("pre-images", backups_dir / "pre-images", "*.db")
    )


def render(entries: list[Entry], root: Path, backups_dir: Path) -> str:
    gate_by_hash: dict[str, list[Path]] = {}
    for e in entries:
        if e.cls == "gate-image":
            gate_by_hash.setdefault(e.sha256, []).append(e.path)
    lines = [
        "# backup_inventory (read-only)",
        f"# root={root}",
        f"# backups_dir={backups_dir}",
        "location\tclass\tsize_bytes\tmtime_utc\tschema_version\tsha256\twal_sidecar\ttwin\tpath",
    ]
    for e in entries:
        if e.cls == "cli-copy":
            twins = gate_by_hash.get(e.sha256, [])
            twin = ";".join(str(t) for t in twins) if twins else "none"
        else:
            twin = "-"
        lines.append("\t".join([
            e.location, e.cls, str(e.size), e.mtime, e.version, e.sha256,
            "present" if e.wal_sidecar else "absent", twin, str(e.path),
        ]))
    lines.append("# summary")
    keys = sorted({(e.location, e.cls) for e in entries})
    for loc, cls in keys:
        group = [e for e in entries if (e.location, e.cls) == (loc, cls)]
        lines.append(
            f"# {loc}\t{cls}\tcount={len(group)}\tbytes={sum(e.size for e in group)}")
    cli = [e for e in entries if e.cls == "cli-copy"]
    twinned = [e for e in cli if e.sha256 in gate_by_hash]
    lines.append(
        f"# cli-copy with a byte-identical gate twin: {len(twinned)} of {len(cli)} "
        f"({sum(e.size for e in twinned)} bytes)")
    lines.append(
        f"# unclassified: {sum(1 for e in entries if e.cls == 'unclassified')}")
    lines.append(f"# total: {len(entries)} files, {sum(e.size for e in entries)} bytes")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "swing-data")
    ap.add_argument("--backups-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    root = args.root
    backups_dir = args.backups_dir if args.backups_dir is not None else root / "backups"
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2
    text = render(inventory(root, backups_dir), root, backups_dir)
    sys.stdout.write(text.encode("ascii", "backslashreplace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
