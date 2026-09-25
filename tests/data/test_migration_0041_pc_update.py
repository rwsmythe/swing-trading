"""22-I T2 -- F-I2: `trg_provenance_corrections_append_only_update` rebuilt with
its COALESCE wrap (CHARC F-I2, binding; plan section 1.4).

The v40 trigger's WHEN is `NOT ( ... AND NEW.c = OLD.c ... )`. When the
legitimate FK-null branch is TRUE and a `=`-compared column goes NULL in the
SAME statement, `NULL = x` is NULL, the whole WHEN is NULL, and SQLite does
not fire the trigger: it FAILS OPEN, and only the column's NOT NULL refuses
(census section 2: 30 of 30 columns x 2 live rows). The rebuild is the stored
v40 text with exactly two substitutions -- `FOR EACH ROW WHEN NOT (` ->
`FOR EACH ROW WHEN NOT COALESCE((`, and the closing `\\n)\\nBEGIN` ->
`\\n), 0)\\nBEGIN` -- so the same statements now FIRE the trigger.

Every discriminator is a (version, verdict) pair: v40 exposed, v41 guarded.
The world is trade 25's real emitter row (``tests/_tier2_world_22a2``).
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import open_connection, run_migrations
from tests._22i_guard_seam import guards_dropped
from tests._tier2_world_22a2 import (
    T25_FILL_ID,
    _seed_rows,
    base_last_word_payload,
    insert_payload,
    pinned_migration_clock,
)
from tests.data._22i_seed import open_plain, outcome

TRIGGER = "trg_provenance_corrections_append_only_update"
OPEN = "FOR EACH ROW WHEN NOT ("
OPEN_WRAPPED = "FOR EACH ROW WHEN NOT COALESCE(("
CLOSE = "\n)\nBEGIN"
CLOSE_WRAPPED = "\n), 0)\nBEGIN"

_WORLDS: dict[int, Path] = {}


def _world(tmp_path: Path, version: int) -> Path:
    """Trade 25's rows on a DB at ``version`` plus its correction row (the
    PRODUCTION service's row, planted RAW; the citation trigger admits it --
    the same world the service wrote it in). Built once per process and
    version, then COPIED into ``tmp_path`` per test."""
    if version not in _WORLDS:
        import tempfile

        root = Path(tempfile.mkdtemp(prefix=f"22i-pc-w{version}-"))
        payload = base_last_word_payload(root)
        path = root / "swing.db"
        conn = open_connection(path)
        try:
            with pinned_migration_clock():
                run_migrations(conn, target_version=version, backup_dir=root / "bak")
            _seed_rows(conn, with_envelope_reading=True)
            insert_payload(conn, payload)
            conn.commit()
        finally:
            conn.close()
        _WORLDS[version] = path
    dst = tmp_path / f"pc-w{version}.db"
    shutil.copyfile(_WORLDS[version], dst)
    return dst


def _stored(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                        "AND name = ?", (TRIGGER,)).fetchone()[0]


def _wrap(sql: str) -> str:
    assert sql.count(OPEN) == 1 and sql.count(CLOSE) == 1
    return sql.replace(OPEN, OPEN_WRAPPED).replace(CLOSE, CLOSE_WRAPPED)


def _unwrap(sql: str) -> str:
    assert sql.count(OPEN_WRAPPED) == 1 and sql.count(CLOSE_WRAPPED) == 1
    return sql.replace(OPEN_WRAPPED, OPEN).replace(CLOSE_WRAPPED, CLOSE)


def _eq_columns(v40_sql: str) -> list[str]:
    """The `=`-compared columns of the STORED v40 text, minus the PK (a PK ->
    NULL is refused by the engine, `datatype mismatch`, before any trigger)."""
    cols = re.findall(r"NEW\.(\w+) = OLD\.\1\b", v40_sql)
    return [c for c in cols if c != "provenance_correction_id"]


def _v40(tmp_path: Path) -> str:
    from tests.data._22i_seed import migrated

    c = migrated(tmp_path, 40, name="v40-text.db")
    try:
        return _stored(c)
    finally:
        c.close()


def _eq_cols_static() -> list[str]:
    """Collection-time roster: read the v39/v40 source text (0039:704) the
    stored trigger is created from."""
    from swing.data import db as db_mod

    text = (Path(db_mod.__file__).resolve().parent / "migrations"
            / "0039_provenance_corrections_tier2.sql").read_text(encoding="utf-8")
    start = text.index(f"CREATE TRIGGER {TRIGGER}")
    return _eq_columns(text[start:text.index("END;", start)])


EQ_COLS = _eq_cols_static()
PAIR = pytest.mark.parametrize("version,expect", [(40, "exposed"), (41, "guarded")])


def test_the_roster_is_the_thirty_census_columns() -> None:
    assert len(EQ_COLS) == 30 == len(set(EQ_COLS))


def test_rebuilt_text_is_the_v40_text_plus_the_wrap(tmp_path: Path) -> None:
    from tests.data._22i_seed import migrated

    v40 = _v40(tmp_path)
    c = migrated(tmp_path, 41, name="v41-text.db")
    try:
        v41 = _stored(c)
    finally:
        c.close()
    assert v41 == _wrap(v40)
    assert _unwrap(v41) == v40
    assert len(v40) == 4140 and len(v41) == 4153  # the ledger S3-4 measurement


def _conn(path: Path, *, fk: bool) -> sqlite3.Connection:
    return open_plain(path, fk=fk)


def _pc_id(c: sqlite3.Connection) -> int:
    return c.execute("SELECT provenance_correction_id FROM provenance_corrections"
                     ).fetchone()[0]


@PAIR
@pytest.mark.parametrize("col", EQ_COLS)
def test_fk_null_branch_plus_column_null_fires(tmp_path: Path, col: str,
                                               version: int, expect: str) -> None:
    """The FK-null branch made TRUE (fill deleted with FKs OFF, the census
    probe (ii)) plus `col` -> NULL in the same statement."""
    c = _conn(_world(tmp_path, version), fk=False)
    try:
        verdict = outcome(
            c, f"UPDATE provenance_corrections SET entry_fill_id = NULL, {col} = NULL "
               "WHERE provenance_correction_id = ?", (_pc_id(c),),
            setup=[("DELETE FROM fills WHERE fill_id = ?", (T25_FILL_ID,))])
    finally:
        c.close()
    if expect == "exposed":
        assert verdict == "CONSTRAINT:NOT NULL"  # the trigger is SILENT
    else:
        assert verdict == f"TRIGGER:{TRIGGER}"


@PAIR
def test_risk_policy_branch_plus_null_fires(tmp_path: Path, version: int,
                                            expect: str) -> None:
    """The risk-policy FK-null branch made TRUE plus a column -> NULL. The
    parent delete is a CLAUSE PIN: from T10 `trg_rp_no_delete` refuses it in
    production (AL-9), so it runs under the seam; at v40 the name is absent."""
    c = _conn(_world(tmp_path, version), fk=False)
    try:
        policy = c.execute("SELECT risk_policy_id_at_correction FROM "
                           "provenance_corrections").fetchone()[0]
        assert policy is not None
        # clause pin, parent delete refused in production
        with guards_dropped(c, "trg_rp_no_delete"):
            verdict = outcome(
                c, "UPDATE provenance_corrections SET risk_policy_id_at_correction = NULL, "
                   "correction_reason = NULL WHERE provenance_correction_id = ?",
                (_pc_id(c),),
                setup=[("DELETE FROM risk_policy WHERE policy_id = ?", (policy,))])
    finally:
        c.close()
    if expect == "exposed":
        assert verdict == "CONSTRAINT:NOT NULL"
    else:
        assert verdict == f"TRIGGER:{TRIGGER}"


def test_split_into_partials_fill_delete_admitted(tmp_path: Path) -> None:
    """The production control (`split_into_partials`' `DELETE FROM fills`, FKs
    ON, cascade SET NULL) stays ADMITTED under the rebuilt trigger."""
    c = _conn(_world(tmp_path, 41), fk=True)
    try:
        verdict, seen = outcome(
            c, "DELETE FROM fills WHERE fill_id = ?", (T25_FILL_ID,),
            post=lambda k: k.execute("SELECT entry_fill_id FROM provenance_corrections"
                                     ).fetchone())
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (None,))


def test_risk_policy_delete_null_admitted(tmp_path: Path) -> None:
    """The risk-policy FK-null branch through the engine's own SET NULL (FKs
    ON): the parent delete itself is a clause pin (seam), the cascade UPDATE
    the trigger sees is admitted."""
    c = _conn(_world(tmp_path, 41), fk=True)
    try:
        policy = c.execute("SELECT risk_policy_id_at_correction FROM "
                           "provenance_corrections").fetchone()[0]
        # clause pin, parent delete refused in production
        with guards_dropped(c, "trg_rp_no_delete"):
            verdict, seen = outcome(
                c, "DELETE FROM risk_policy WHERE policy_id = ?", (policy,),
                post=lambda k: k.execute(
                    "SELECT risk_policy_id_at_correction FROM provenance_corrections"
                ).fetchone())
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (None,))


@pytest.mark.parametrize("col", EQ_COLS)
def test_plain_update_still_fires(tmp_path: Path, col: str) -> None:
    c = _conn(_world(tmp_path, 41), fk=True)
    try:
        verdict = outcome(
            c, f"UPDATE provenance_corrections SET {col} = 'x-22i' "
               "WHERE provenance_correction_id = ?", (_pc_id(c),))
    finally:
        c.close()
    assert verdict == f"TRIGGER:{TRIGGER}"
