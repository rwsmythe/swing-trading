"""Read-only inventory of swing-data backup images (D32 / F4). Stdlib only.

Scans, NON-recursively:
  * ``<root>/swing-pre-*.db``            -- pre-migration gate images beside the DB
  * ``<backups>/*.db``                   -- CLI copies, weekly backups, gate images
  * ``<backups>/pre-images/*.db``        -- gate images after the F4(a) move

For every file it prints location, class, size, mtime, the schema version read
as ``SELECT version FROM schema_version`` (``unknown`` when the table is absent;
``PRAGMA user_version`` reads 0 on this project's DBs and is never used), the
sha256 of the bytes, and -- for each CLI copy -- the gate image(s) with the SAME
sha256 (its byte-identical twin), or ``none``. A twin is a claim that licenses a
delete downstream, so it fails CLOSED: a ``-wal`` or ``-journal`` sidecar beside
EITHER member of the candidate pair (the CLI copy or the gate image) withholds
it (``indeterminate-wal-sidecar`` / ``indeterminate-journal-sidecar``) -- never
a positive twin on a hole in the proof.

A file that raises ``OSError`` on the existence/stat check, the schema-version
read or the hash -- OR whose schema-version read fails WITHOUT raising (a
readable file that is not a valid database) -- does NOT abort the scan and is
never silently skipped: it gets its own row with the exception text in a
dedicated ``error`` column, whatever metadata was ALREADY obtained before the
failure preserved (size, mtime, sidecar flags, and the schema version itself
when only the hash step failed), the hash column ``indeterminate`` when the
hash could not be computed, and the twin column ``indeterminate`` -- a member
that cannot be read cannot be named a positive twin on either side of the
pair, byte-identical bytes notwithstanding. The scan continues; the summary
line counts these rows; the run still exits 0 (an inventory is evidence, not
a gate).

Classes, by NAME only:
  gate-image    ``swing-pre-*``
  cli-copy      ``swing-YYYYMMDDTHHMMSS.db``   (swing/cli.py db-migrate)
  weekly-backup ``swing-YYYYWW.db``            (swing/data/backup.py _WEEKLY_BACKUP_RE)
  unclassified  anything else -- PRINTED with its path, never skipped
  scan-error    a whole DIRECTORY (root/backups/pre-images) that could not
                be examined or listed -- one visible row, path = the
                directory, never a silent empty scan of it (the class-sweep
                fix below).

Every filesystem probe (a directory's existence, its listing, a ``-wal``/
``-journal`` sidecar) distinguishes ABSENT (confirmed not-there) from
UNKNOWN (any other ``OSError`` -- permission denied, a flaky mount, a
symlink loop): a plain pathlib Boolean probe (``exists``/``is_dir``/
``is_file``) cannot make that distinction (it folds every failure into
``False``) and is never used for one here. ``wal_sidecar``/
``journal_sidecar`` are each one of ``present``/``absent``/``unknown``;
UNKNOWN withholds a positive twin exactly like ``present`` does. The
``journal_sidecar`` column is appended AFTER ``error`` so every earlier
column index is stable across this addition.

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
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from stat import S_ISDIR, S_ISREG

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
    wal_sidecar: str  # "present" | "absent" | "unknown"
    journal_sidecar: str  # "present" | "absent" | "unknown"
    error: str | None = None


def _probe(path: Path) -> tuple[str, os.stat_result | None]:
    """The class fix (Reviewer B's Expansion-#13 sweep, SS-1..SS-5): every
    Boolean filesystem probe this script used to call -- ``Path.exists()``,
    ``Path.is_dir()``, ``Path.is_file()`` with the default
    ``follow_symlinks=True`` -- resolves on THIS Windows/Python build to a
    native ``os.path._path_isdir``/``_path_isfile``/``_path_exists`` builtin
    (verified: ``os.path.isdir is genericpath.isdir`` is ``False``) that
    does NOT call the patchable ``os.stat`` at all and folds EVERY failure
    (not-found, permission-denied, an unreadable mount, anything) into a
    bare ``False`` -- the same bypass Reviewer B's B2R-2 measured for
    ``Path.is_file()`` alone, generalised here to every sibling probe.
    ``os.stat`` is the one primitive under this ``Path.stat()`` already
    calls directly (proven by B3's existing per-file guard), so routing
    every existence/type check through IT, instead of through a Boolean
    Path method, is what makes the ABSENT/UNKNOWN distinction both real and
    testable. Returns ("absent", None) for a confirmed not-there path
    (``FileNotFoundError``/``NotADirectoryError`` -- a missing path or a
    path component that is a file, not a directory), ("unknown", None) for
    any OTHER ``OSError`` (permission denied, I/O failure, anything this
    script cannot diagnose), or ("present", the stat result) otherwise."""
    try:
        st = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return "absent", None
    except OSError:
        return "unknown", None
    return "present", st


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


def _directory_error_entry(location: str, directory: Path, reason: str) -> Entry:
    """SS-1/SS-2: a directory-level probe/listing failure is a VISIBLE row,
    never a silent empty scan and never a crash of the other locations --
    the same "scan continues, evidence not a gate" posture B3 already gives
    per-file failures, generalised one level up. One row per unreachable
    directory; never rows for files that could not even be enumerated."""
    return Entry(
        location=location, cls="scan-error", path=directory, size=0,
        mtime="unknown", version="unknown", sha256="indeterminate",
        wal_sidecar="unknown", journal_sidecar="unknown",
        error=f"error:DirectoryUnreadable:{reason}",
    )


def _scan(location: str, directory: Path, pattern: str) -> list[Entry]:
    """SS-1 (the directory-existence check) + SS-2 (the listing itself).

    ``directory.is_dir()`` swallows every ``OSError`` into ``False`` with
    no ABSENT/UNKNOWN discrimination (see ``_probe``'s docstring) -- a
    directory that genuinely exists but cannot be examined (permission
    denied, a flaky mount) previously read IDENTICALLY to one that was
    never created, and every file inside it vanished with no trace.
    ``directory.glob(pattern)`` is worse: its internal ``os.scandir()`` call
    is not wrapped in any try/except anywhere in the stdlib glob machinery,
    so a directory that STATS fine but cannot be LISTED previously
    propagated an uncaught ``OSError`` out of this function and crashed the
    WHOLE inventory, every location, not just this one. Both now degrade to
    one visible ``scan-error`` row (never a positive claim, never silence).
    """
    state, st = _probe(directory)
    if state == "absent":
        return []
    if state == "unknown":
        return [_directory_error_entry(location, directory, "could not determine "
                                        "whether this directory exists")]
    if not S_ISDIR(st.st_mode):
        return []
    try:
        paths = sorted(directory.glob(pattern))
    except OSError as exc:
        return [_directory_error_entry(location, directory, f"{type(exc).__name__}:{exc}")]
    out = []
    for p in paths:
        entry = _scan_one(location, p)
        if entry is not None:
            out.append(entry)
    return out


def _scan_one(location: str, p: Path) -> Entry | None:
    """Per-file isolation (Reviewer B, B3 + the B2 re-read's B2R-1/B2R-2).

    EVERY fallible step -- the existence/stat check included -- runs inside
    the guard below, so an inaccessible or vanished matched path yields its
    own error row instead of vanishing with NO row at all (a bare
    ``Path.is_file()`` call BEFORE the guard swallows ``OSError`` internally
    and returns False, dropping the candidate silently -- B2R-2) or aborting
    the whole scan (B3). Whatever was obtained before a failure is KEPT, not
    zeroed (B2R-3): a hash-step failure after a successful stat/version read
    still shows the real size, mtime, sidecar flags and schema version, with
    only the hash and the derived twin state going indeterminate.

    A schema-version read that fails WITHOUT raising (``read_schema_version``
    catches ``sqlite3.Error``/``ValueError``/``TypeError`` internally and
    returns an ``error:...`` string) is ALSO treated as this file's error
    (B2R-1): byte identity between two unreadable/corrupt files does not
    prove they are the same recoverable database, so a member in that state
    must never be named a positive twin either.

    Returns ``None`` ONLY for a confirmed non-regular-file match (e.g. a
    directory the glob pattern happened to match) -- never on a failure to
    determine that.
    """
    size = 0
    mtime = "unknown"
    wal_sidecar = "unknown"
    journal_sidecar = "unknown"
    version: str | None = None
    sha256: str | None = None
    error: str | None = None
    try:
        st = p.stat()
        if not S_ISREG(st.st_mode):
            return None
        size = st.st_size
        mtime = datetime.fromtimestamp(st.st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        wal_sidecar = _probe(Path(str(p) + "-wal"))[0]
        journal_sidecar = _probe(Path(str(p) + "-journal"))[0]
        version = read_schema_version(p)
        sha256 = sha256_of(p)
    except OSError as exc:
        error = f"error:{type(exc).__name__}:{exc}"

    if error is None and version is not None and version.startswith("error:"):
        error = version

    return Entry(
        location=location,
        cls=classify(p.name),
        path=p,
        size=size,
        mtime=mtime,
        version=version if version is not None else (error or "unknown"),
        sha256=sha256 if sha256 is not None else "indeterminate",
        wal_sidecar=wal_sidecar,
        journal_sidecar=journal_sidecar,
        error=error,
    )


def inventory(root: Path, backups_dir: Path) -> list[Entry]:
    return (
        _scan("root", root, "swing-pre-*.db")
        + _scan("backups", backups_dir, "*.db")
        + _scan("pre-images", backups_dir / "pre-images", "*.db")
    )


def _sidecar_reason(e: Entry) -> str | None:
    """None = clean; else the specific hole that withholds a positive twin.

    SS-3/SS-4: an UNKNOWN sidecar probe (a real OSError the -wal/-journal
    check could not resolve, never a confirmed absence) withholds the twin
    the SAME as a confirmed-present sidecar -- the fail-closed rule already
    ruled for B2/B3 extends to "we could not tell" as much as "it is
    there"."""
    if e.wal_sidecar == "present":
        return "indeterminate-wal-sidecar"
    if e.wal_sidecar == "unknown":
        return "indeterminate-wal-unknown"
    if e.journal_sidecar == "present":
        return "indeterminate-journal-sidecar"
    if e.journal_sidecar == "unknown":
        return "indeterminate-journal-unknown"
    return None


_TWIN_SENTINELS = frozenset({
    "none",
    "indeterminate",
    "indeterminate-wal-sidecar",
    "indeterminate-journal-sidecar",
    "indeterminate-wal-unknown",
    "indeterminate-journal-unknown",
})


def _is_positive_twin(twin_value: str) -> bool:
    """Reviewer B, B2R-4 (minor): EXACT sentinel membership, never a string
    prefix test. A twin value that legitimately STARTS WITH the same text as
    a sentinel (e.g. a matched gate path under a directory literally named
    ``indeterminate-something``) is a real positive twin, not a tainted one
    -- only exact equality to a sentinel withholds it."""
    return twin_value not in _TWIN_SENTINELS


def render(entries: list[Entry], root: Path, backups_dir: Path) -> str:
    # A twin is a claim that licenses a delete downstream, so it fails CLOSED:
    # a -wal OR -journal sidecar beside EITHER member of the candidate pair
    # withholds it -- an immutable read and a main-file hash cannot see a
    # sidecar's pending/committed pages, so two equal main files are NOT
    # proven equal databases when either side carries one. An unreadable file
    # (error row) can never be claimed as, or matched to, a twin either.
    gate_matches_by_hash: dict[str, list[tuple[Path, str | None]]] = {}
    for e in entries:
        if e.cls == "gate-image" and e.error is None:
            gate_matches_by_hash.setdefault(e.sha256, []).append((e.path, _sidecar_reason(e)))

    twin_by_path: dict[Path, str] = {}
    for e in entries:
        if e.error is not None:
            twin_by_path[e.path] = "indeterminate"
        elif e.cls != "cli-copy":
            twin_by_path[e.path] = "-"
        else:
            reason = _sidecar_reason(e)
            if reason is not None:
                twin_by_path[e.path] = reason
            else:
                matches = gate_matches_by_hash.get(e.sha256, [])
                clean = [p for p, r in matches if r is None]
                tainted = [r for _, r in matches if r is not None]
                if clean:
                    twin_by_path[e.path] = ";".join(str(p) for p in clean)
                elif tainted:
                    twin_by_path[e.path] = tainted[0]
                else:
                    twin_by_path[e.path] = "none"

    lines = [
        "# backup_inventory (read-only)",
        f"# root={root}",
        f"# backups_dir={backups_dir}",
        # B3R-2: journal_sidecar is APPENDED after error -- every existing
        # column index (path at [8], error at [9]) stays stable.
        "location\tclass\tsize_bytes\tmtime_utc\tschema_version\tsha256\twal_sidecar\ttwin\t"
        "path\terror\tjournal_sidecar",
    ]
    for e in entries:
        lines.append("\t".join([
            e.location, e.cls, str(e.size), e.mtime, e.version, e.sha256,
            e.wal_sidecar, twin_by_path[e.path], str(e.path),
            e.error if e.error is not None else "-",
            e.journal_sidecar,
        ]))
    lines.append("# summary")
    keys = sorted({(e.location, e.cls) for e in entries})
    for loc, cls in keys:
        group = [e for e in entries if (e.location, e.cls) == (loc, cls)]
        lines.append(
            f"# {loc}\t{cls}\tcount={len(group)}\tbytes={sum(e.size for e in group)}")
    cli = [e for e in entries if e.cls == "cli-copy"]
    twinned = [e for e in cli if _is_positive_twin(twin_by_path[e.path])]
    lines.append(
        f"# cli-copy with a byte-identical gate twin: {len(twinned)} of {len(cli)} "
        f"({sum(e.size for e in twinned)} bytes)")
    lines.append(
        f"# unclassified: {sum(1 for e in entries if e.cls == 'unclassified')}")
    lines.append(
        f"# errors: {sum(1 for e in entries if e.error is not None)}")
    lines.append(f"# total: {len(entries)} files, {sum(e.size for e in entries)} bytes")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "swing-data")
    ap.add_argument("--backups-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    root = args.root
    backups_dir = args.backups_dir if args.backups_dir is not None else root / "backups"
    # SS-5: distinguish a root that is genuinely ABSENT from one that
    # EXISTS but could not be checked (permission denied, an I/O failure)
    # -- root.is_dir() folded both into the same "not found" message.
    state, st = _probe(root)
    if state == "absent" or (state == "present" and not S_ISDIR(st.st_mode)):
        sys.stderr.write(_ascii(f"root not found: {root}\n"))
        return 2
    if state == "unknown":
        sys.stderr.write(_ascii(f"root exists but could not be checked: {root}\n"))
        return 2
    text = render(inventory(root, backups_dir), root, backups_dir)
    sys.stdout.write(_ascii(text))
    return 0


def _ascii(text: str) -> str:
    """Every byte this script prints is ASCII (a cp1252 console crashes on the rest)."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


if __name__ == "__main__":
    raise SystemExit(main())
