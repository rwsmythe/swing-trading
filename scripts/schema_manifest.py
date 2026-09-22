"""D51 -- the schema-manifest comparator. Stdlib only.

Nothing in this repo asserts that the DDL objects a migration PROMISES
(indexes, triggers, CHECKs) are actually PRESENT at HEAD -- each migration
test checks only its own objects at its own version. A table rebuild (the
SQLite ALTER-limited DROP+CREATE idiom -- 21-B did one, 22-B's Demand A
rebuilds `trades`) that forgets to re-create an index or a trigger fails
OPEN and the suite stays green. This script reads `sqlite_master`, hashes
each object's normalized DDL text, and compares the result against a
committed one-line-per-object fixture (`tests/data/schema_manifest_head.tsv`)
so a dropped or silently-weakened object shows up as a diff line instead of
as silence.

WHAT IS READ: every `sqlite_master` row EXCEPT `sqlite_sequence` and
`sqlite_stat*` -- so `sqlite_autoindex_*` rows (the only trace in
`sqlite_master` of a UNIQUE/PRIMARY KEY constraint) ARE included. A rebuild
that drops a UNIQUE drops one of these and nothing else would show it.

WHAT IS HASHED: the `sql` column's text with whitespace runs collapsed to a
single space and stripped, sha256 hex-encoded. `sql IS NULL` (autoindexes
carry no `sql`) hashes the empty string. Nothing else is normalized -- case,
quoting, and comments inside a statement are all part of the DDL as written,
so a rebuild that re-types a statement differently shows as CHANGED. That is
deliberate: a fixture update is a decision the diff should show, not noise
this script suppresses.

READ-ONLY POSTURE (the gotcha this script is built to respect): NEVER open a
backup or a live DB through a path that reaches `ensure_schema`/`connect` --
both auto-migrate or refuse a version mismatch by design, and either would
corrupt a recovery artifact or crash on an incrementally-migrated live DB.
`--db` opens the target with plain `sqlite3` as a URI in `mode=ro` and never
imports `swing.data.db`. A `mode=ro` open still RECREATES `-shm`/`-wal`
sidecars beside the target file (a documented SQLite behavior, not a bug in
this script) -- this is not "cleaned up" afterward; the sidecars are SQLite's
own artifacts of a WAL-mode file being opened at all, not evidence this
script wrote to the target. `--db` never writes a database row or a schema
change to the target under any circumstance.

Usage:
    python scripts/schema_manifest.py --write            # migrate an EMPTY DB in a
                                                          #   tempdir at HEAD, overwrite
                                                          #   the fixture
    python scripts/schema_manifest.py --check            # same migrate, compare to the
                                                          #   fixture, print the diff,
                                                          #   exit 1 if not clean
    python scripts/schema_manifest.py --db <path>        # READ-ONLY: open <path> with
                                                          #   sqlite3 URI mode=ro, compare
                                                          #   to the fixture, print the
                                                          #   diff + the DB's
                                                          #   schema_version, exit 1 if
                                                          #   not clean
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from swing.data.db import ensure_schema  # noqa: E402

_DEFAULT_FIXTURE = _REPO_ROOT / "tests" / "data" / "schema_manifest_head.tsv"
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, order=True)
class ManifestRow:
    type: str
    name: str
    tbl_name: str
    sql_sha256: str


@dataclass(frozen=True)
class ManifestDiff:
    missing: frozenset[tuple[str, str]]
    unexpected: frozenset[tuple[str, str]]
    changed: frozenset[tuple[str, str]]
    # (type, name) -> tbl_name, for render()'s "<type> <name> (<tbl_name>)"
    # lines. Populated by compare(); not part of the diff's identity, so it
    # is excluded from equality/hash via `compare=False`.
    tbl_name_by_key: dict[tuple[str, str], str]

    @property
    def is_clean(self) -> bool:
        return not (self.missing or self.unexpected or self.changed)

    def render(self) -> str:
        lines: list[str] = []
        if self.is_clean:
            lines.append("schema manifest: clean (no missing/unexpected/changed objects)")
        else:
            for label, keys in (
                ("missing", self.missing),
                ("unexpected", self.unexpected),
                ("changed", self.changed),
            ):
                if not keys:
                    continue
                lines.append(f"{label}:")
                for type_, name in sorted(keys):
                    tbl_name = self.tbl_name_by_key.get((type_, name), "")
                    lines.append(f"  {type_} {name} ({tbl_name})")
        lines.append(
            "Regenerate with: python scripts/schema_manifest.py --write"
        )
        return "\n".join(lines)


def _normalize_sql(sql: str | None) -> str:
    if sql is None:
        return ""
    return _WHITESPACE_RE.sub(" ", sql).strip()


def _sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_manifest(conn: sqlite3.Connection) -> list[ManifestRow]:
    """Every `sqlite_master` row except `sqlite_sequence` and `sqlite_stat*`
    (so `sqlite_autoindex_*` rows ARE included), sorted by (type, name)."""
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name != 'sqlite_sequence' AND name NOT LIKE 'sqlite_stat%' "
        "ORDER BY type, name"
    ).fetchall()
    return [
        ManifestRow(
            type=type_, name=name, tbl_name=tbl_name,
            sql_sha256=_sha256_of(_normalize_sql(sql)),
        )
        for type_, name, tbl_name, sql in rows
    ]


def compare(expected: list[ManifestRow], actual: list[ManifestRow]) -> ManifestDiff:
    expected_by_key = {(r.type, r.name): r for r in expected}
    actual_by_key = {(r.type, r.name): r for r in actual}
    expected_keys = set(expected_by_key)
    actual_keys = set(actual_by_key)

    missing = frozenset(expected_keys - actual_keys)
    unexpected = frozenset(actual_keys - expected_keys)
    changed = frozenset(
        key
        for key in expected_keys & actual_keys
        if expected_by_key[key].tbl_name != actual_by_key[key].tbl_name
        or expected_by_key[key].sql_sha256 != actual_by_key[key].sql_sha256
    )

    tbl_name_by_key: dict[tuple[str, str], str] = {}
    for key in missing:
        tbl_name_by_key[key] = expected_by_key[key].tbl_name
    for key in unexpected:
        tbl_name_by_key[key] = actual_by_key[key].tbl_name
    for key in changed:
        tbl_name_by_key[key] = actual_by_key[key].tbl_name

    return ManifestDiff(
        missing=missing, unexpected=unexpected, changed=changed,
        tbl_name_by_key=tbl_name_by_key,
    )


def write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    lines = [
        "# schema_manifest_head.tsv -- generated by scripts/schema_manifest.py "
        "--write. One line per sqlite_master object (autoindexes included), "
        "tab-separated: type\tname\ttbl_name\tsql_sha256. Sorted by (type, name).",
    ]
    for row in sorted(rows, key=lambda r: (r.type, r.name)):
        lines.append(f"{row.type}\t{row.name}\t{row.tbl_name}\t{row.sql_sha256}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        type_, name, tbl_name, sql_sha256 = line.split("\t")
        rows.append(ManifestRow(type=type_, name=name, tbl_name=tbl_name,
                                 sql_sha256=sql_sha256))
    return sorted(rows, key=lambda r: (r.type, r.name))


def _head_manifest() -> list[ManifestRow]:
    """Migrates an EMPTY DB in a tempdir to HEAD and reads its manifest.
    Never touches the repo, the live DB, or any path outside the tempdir."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "head.db"
        conn = ensure_schema(db_path)
        try:
            return read_manifest(conn)
        finally:
            conn.close()


def _read_only_manifest(db_path: Path) -> tuple[list[ManifestRow], str]:
    """Opens `db_path` READ-ONLY via a `mode=ro` sqlite3 URI -- never
    `ensure_schema`/`connect` (both would auto-migrate or refuse a version
    mismatch). Returns (manifest, schema_version_display)."""
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = read_manifest(conn)
        version_row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if version_row is None:
            version = "unknown"
        else:
            v = conn.execute("SELECT version FROM schema_version").fetchone()
            version = "unknown" if v is None else str(v[0])
        return rows, version
    finally:
        conn.close()


def _ascii(text: str) -> str:
    """Every byte this script prints is ASCII (a cp1252 console crashes on the rest)."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true",
                        help="migrate an empty DB at HEAD, overwrite the fixture")
    group.add_argument("--check", action="store_true",
                        help="migrate an empty DB at HEAD, compare to the fixture")
    group.add_argument("--db", type=Path, default=None,
                        help="READ-ONLY: compare a live DB's manifest to the fixture")
    ap.add_argument("--fixture", type=Path, default=_DEFAULT_FIXTURE,
                     help="fixture path (default: tests/data/schema_manifest_head.tsv)")
    args = ap.parse_args(argv)

    if args.write:
        rows = _head_manifest()
        write_manifest(args.fixture, rows)
        sys.stdout.write(_ascii(f"wrote {len(rows)} objects to {args.fixture}\n"))
        return 0

    if args.check:
        actual = _head_manifest()
        expected = load_manifest(args.fixture)
        diff = compare(expected, actual)
        sys.stdout.write(_ascii(diff.render() + "\n"))
        return 0 if diff.is_clean else 1

    # --db
    actual, version = _read_only_manifest(args.db)
    expected = load_manifest(args.fixture)
    diff = compare(expected, actual)
    sys.stdout.write(_ascii(f"schema_version {version}\n"))
    sys.stdout.write(_ascii(diff.render() + "\n"))
    return 0 if diff.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
