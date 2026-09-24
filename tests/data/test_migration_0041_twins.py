"""22-I T6-T12 -- the (c) twins: plan section 4.2.

Every probe is a (version, verdict) pair on the SAME seeded world: at v40 the
statement is EXPOSED (it succeeds, or only an engine constraint refuses it);
at v41 `trg_<abbr>_immutable` refuses it -- or, for an ADMITTED transition,
it succeeds at both.

    C1  UPDATE each I column                          exposed / immutable
    C2  UPDATE each M column                          OK / OK
    C3  W: NULL -> value . value -> other . value -> NULL   OK / OK . immutable . immutable
    C4a F REACHABLE / DELETABLE: the parent delete (FKs ON)   OK / OK (child FK NULL)
    C4b F -> NULL with the parent PRESENT             exposed / immutable
    C4c F -> NULL together with an I column (parent gone)     exposed / immutable
    C4d F NULL -> value                               exposed / immutable
    C4e F DEAD-BY-PARENT-GUARD: the clause pin (FK OFF, the parent's
        no_delete dropped by the seam, the parent deleted, then F -> NULL)   OK / OK
    C5  D risk_policy.is_active 1 -> 0 . 0 -> 1        OK / OK . immutable
    C6  no_delete                                     exposed / no_delete
    C7  A1-A6/A8 of section 4.1 (in test_migration_0041_triples.py)
    C8  THE COMPARATOR (RD binding (ii); CLAUDE.md #11): the spec's classes
        partition PRAGMA table_info; the stored trigger names NEW.<c> for
        every non-M column and NO M column; every I column appears as
        `NEW.c IS OLD.c`; every F clause names its parent and parent PK.

dmr (T11) and review_log (T12) carry bespoke clause tests in their own
modules; C1/C2/C6/C8 hold for them here too.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests._22i_guard_seam import guards_dropped
from tests.data._22i_guard_spec import DEAD, DELETABLE, REACHABLE, SPEC, FCol
from tests.data._22i_seed import (
    different_value,
    fresh_row,
    insert_copy_sql,
    is_engine_refusal,
    migrated,
    open_plain,
    outcome,
    row_of,
    where_pk,
)

# The (c) twin tables whose triggers have landed (the list grows per task).
TWIN_TABLES: tuple[str, ...] = (
    "reconciliation_runs", "reconciliation_discrepancies",
    "reconciliation_corrections", "schwab_api_calls", "yfinance_calls",
    "account_equity_snapshots",
)
PAIR = pytest.mark.parametrize("version", [40, 41])

# The row an F probe runs on, where it is not the first seeded row.
F_SUBJECT: dict[tuple[str, str], dict[str, Any]] = {
    ("reconciliation_discrepancies", "trade_id"): {"discrepancy_id": 2},
    ("schwab_api_calls", "pipeline_run_id"): {"call_id": 2},
    ("yfinance_calls", "pipeline_run_id"): {"call_id": 2},
}
# The parent row each F subject points at, and the PRODUCTION (or probe)
# statement that deletes it.
PARENT_DELETE: dict[tuple[str, str], tuple[str, tuple]] = {
    # REACHABLE: split_into_partials' literal statement
    # (swing/trades/reconciliation_auto_correct.py:3226)
    ("reconciliation_discrepancies", "fill_id"):
        ("DELETE FROM fills WHERE fill_id = ?", (41,)),
    # DELETABLE-NO-PRODUCTION-DELETER: probe deletes of parents seeded without
    # guarded CASCADE children
    ("reconciliation_discrepancies", "trade_id"):
        ("DELETE FROM trades WHERE id = ?", (21,)),
    ("reconciliation_discrepancies", "cash_movement_id"):
        ("DELETE FROM cash_movements WHERE id = ?", (1,)),
    ("schwab_api_calls", "pipeline_run_id"):
        ("DELETE FROM pipeline_runs WHERE id = ?", (2,)),
    ("yfinance_calls", "pipeline_run_id"):
        ("DELETE FROM pipeline_runs WHERE id = ?", (2,)),
}


def _world(tmp_path: Path, version: int):
    return migrated(tmp_path, version, world=True)


def _twin(table: str) -> str:
    return f"trg_{SPEC[table].abbr}_immutable"


def _check(verdict: str, version: int, trigger: str) -> None:
    if version == 40:
        assert verdict == "OK" or is_engine_refusal(verdict), verdict
    else:
        assert verdict == f"TRIGGER:{trigger}", verdict


def _subject(table: str, col: str | None = None) -> dict[str, Any] | None:
    return F_SUBJECT.get((table, col)) if col else None


def _update(c, table: str, sets: dict[str, Any], pk: dict | None = None,
            setup=()) -> str:
    w, p = where_pk(table, pk)
    clause = ", ".join(f"{k} = ?" for k in sets)
    return outcome(c, f"UPDATE {table} SET {clause} WHERE {w}",
                   (*sets.values(), *p), setup=setup)


def _cases(attr: str):
    for table in TWIN_TABLES:
        for col in getattr(SPEC[table], attr):
            yield pytest.param(table, col, id=f"{table}.{col}")


def _f_cases(states=(REACHABLE, DELETABLE, DEAD)):
    for table in TWIN_TABLES:
        for f in SPEC[table].F:
            if f.state in states:
                yield pytest.param(table, f, id=f"{table}.{f.col}")


# ---------------------------------------------------------------------------
# C1 / C2 / C3 / C5 / C6
# ---------------------------------------------------------------------------
@PAIR
@pytest.mark.parametrize("table,col", list(_cases("I")))
def test_c1_each_immutable_column(tmp_path: Path, table: str, col: str,
                                  version: int) -> None:
    c = _world(tmp_path, version)
    try:
        v = different_value(c, table, col, row_of(c, table)[col])
        verdict = _update(c, table, {col: v})
    finally:
        c.close()
    _check(verdict, version, _twin(table))


@PAIR
@pytest.mark.parametrize("table,col", list(_cases("M")))
def test_c2_each_mutable_column(tmp_path: Path, table: str, col: str,
                                version: int) -> None:
    c = _world(tmp_path, version)
    try:
        v = different_value(c, table, col, row_of(c, table)[col])
        verdict = _update(c, table, {col: v})
    finally:
        c.close()
    assert verdict == "OK", verdict


# W columns: the value a NULL -> value transition writes, and the OTHER value.
W_VALUES: dict[tuple[str, str], tuple[Any, Any]] = {
    ("reconciliation_corrections", "correction_set_id"): (1, 2),
    ("reconciliation_corrections", "superseded_by_correction_id"): (2, 1),
    ("risk_policy", "effective_to"): ("2026-09-01T00:00:00", "2026-09-02T00:00:00"),
    ("risk_policy", "superseded_by_policy_id"): (1, 2),
    ("hypothesis_status_history", "effective_to"): ("2026-09-01T00:00:00.000",
                                                    "2026-09-02T00:00:00.000"),
}


@PAIR
@pytest.mark.parametrize("step", ["null_to_value", "value_to_other", "value_to_null"])
@pytest.mark.parametrize("table,col", list(_cases("W")))
def test_c3_write_once(tmp_path: Path, table: str, col: str, step: str,
                       version: int) -> None:
    c = _world(tmp_path, version)
    try:
        first, other = W_VALUES[(table, col)]
        assert row_of(c, table)[col] is None
        w, p = where_pk(table)
        set_first = (f"UPDATE {table} SET {col} = ? WHERE {w}", (first, *p))
        if step == "null_to_value":
            verdict = _update(c, table, {col: first})
        elif step == "value_to_other":
            verdict = _update(c, table, {col: other}, setup=[set_first])
        else:
            verdict = _update(c, table, {col: None}, setup=[set_first])
    finally:
        c.close()
    if step == "null_to_value":
        assert verdict == "OK", verdict
    else:
        _check(verdict, version, _twin(table))


@PAIR
@pytest.mark.parametrize("table", TWIN_TABLES)
def test_c6_no_delete(tmp_path: Path, table: str, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        w, p = where_pk(table)
        verdict = outcome(c, f"DELETE FROM {table} WHERE {w}", p)
    finally:
        c.close()
    _check(verdict, version, f"trg_{SPEC[table].abbr}_no_delete")


# ---------------------------------------------------------------------------
# C4 -- the a17 F columns (CHARC a17 + the parent-gone clause; three states)
# ---------------------------------------------------------------------------
def _fk_read(table: str, col: str, pk: dict | None):
    w, p = where_pk(table, pk)
    return lambda k: k.execute(f"SELECT {col} FROM {table} WHERE {w}", p).fetchone()


@PAIR
@pytest.mark.parametrize("table,f", list(_f_cases((REACHABLE, DELETABLE))))
def test_c4a_the_parent_delete_is_admitted(tmp_path: Path, table: str, f: FCol,
                                           version: int) -> None:
    """REACHABLE: the production parent delete. DELETABLE-NO-PRODUCTION-DELETER:
    a PROBE delete ("probe delete, no production deleter") of a parent seeded
    without guarded CASCADE children. FKs ON: the SET NULL action's UPDATE is
    the one the twin must admit."""
    c = _world(tmp_path, version)
    pk = _subject(table, f.col)
    try:
        assert _fk_read(table, f.col, pk)(c) != (None,)
        sql, params = PARENT_DELETE[(table, f.col)]
        verdict, seen = outcome(c, sql, params, post=_fk_read(table, f.col, pk))
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (None,))


@PAIR
@pytest.mark.parametrize("table,f", list(_f_cases()))
def test_c4b_fk_to_null_with_the_parent_present(tmp_path: Path, table: str, f: FCol,
                                                version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = _update(c, table, {f.col: None}, _subject(table, f.col))
    finally:
        c.close()
    _check(verdict, version, _twin(table))


def _parent_gone(c, f: FCol, value) -> list:
    return [(f"DELETE FROM {f.parent} WHERE {f.ppk} = ?", (value,))]


def _parent_guard(f: FCol) -> tuple[str, ...]:
    parent = SPEC.get(f.parent)
    return (f"trg_{parent.abbr}_no_delete",) if parent is not None else ()


@PAIR
@pytest.mark.parametrize("table,f", list(_f_cases()))
def test_c4c_fk_to_null_with_an_immutable_column(tmp_path: Path, table: str,
                                                 f: FCol, version: int) -> None:
    """The parent GONE (deleted with FKs OFF, no cascade): the FK half alone is
    admitted (the control); together with an I column it aborts."""
    c0 = _world(tmp_path, version)
    db = Path(c0.execute("PRAGMA database_list").fetchone()[2])
    c0.close()
    c = open_plain(db, fk=False)
    pk = _subject(table, f.col)
    try:
        value = _fk_read(table, f.col, pk)(c)[0]
        icol = next(x for x in SPEC[table].I if x not in SPEC[table].pk)
        iv = different_value(c, table, icol, row_of(c, table, pk)[icol])
        gone = _parent_gone(c, f, value)
        with guards_dropped(c, *_parent_guard(f)):  # clause pin: parent delete
            control = _update(c, table, {f.col: None}, pk, setup=gone)
            verdict = _update(c, table, {f.col: None, icol: iv}, pk, setup=gone)
    finally:
        c.close()
    assert control == "OK", control
    _check(verdict, version, _twin(table))


@PAIR
@pytest.mark.parametrize("table,f", list(_f_cases()))
def test_c4d_fk_null_to_value(tmp_path: Path, table: str, f: FCol,
                              version: int) -> None:
    """A fresh row appended with the FK NULL, then the FK written."""
    c = _world(tmp_path, version)
    try:
        spec = SPEC[table]
        row = fresh_row(c, table) if spec.conflict_keys else _fresh_pk_row(c, table)
        value = _fk_read(table, f.col, _subject(table, f.col))(c)[0]
        row[f.col] = None
        new_pk = 900
        row[spec.pk[0]] = new_pk
        verdict = _update(c, table, {f.col: value}, {spec.pk[0]: new_pk},
                          setup=[insert_copy_sql(c, table, row)])
    finally:
        c.close()
    _check(verdict, version, _twin(table))


def _fresh_pk_row(c, table: str) -> dict:
    row = row_of(c, table)
    del row[SPEC[table].pk[0]]
    return row


@PAIR
@pytest.mark.parametrize("table,f", list(_f_cases((DEAD,))))
def test_c4e_dead_by_parent_guard_clause_pin(tmp_path: Path, table: str, f: FCol,
                                             version: int) -> None:
    """The clause's own pin, labelled: the parent delete is REFUSED in
    production by its own no_delete (DEAD-BY-PARENT-GUARD, AL-9); on this test
    DB it is dropped by the seam, the parent deleted with FKs OFF, and the
    child's FK -> NULL is admitted -- the clause stays executable."""
    c0 = _world(tmp_path, version)
    db = Path(c0.execute("PRAGMA database_list").fetchone()[2])
    c0.close()
    c = open_plain(db, fk=False)
    pk = _subject(table, f.col)
    try:
        value = _fk_read(table, f.col, pk)(c)[0]
        with guards_dropped(c, *_parent_guard(f)):  # clause pin, no production path
            verdict = _update(c, table, {f.col: None}, pk,
                              setup=_parent_gone(c, f, value))
    finally:
        c.close()
    assert verdict == "OK", verdict


# ---------------------------------------------------------------------------
# C8 -- THE COMPARATOR
# ---------------------------------------------------------------------------
def _stored(c, name: str) -> str:
    row = c.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                    "AND name = ?", (name,)).fetchone()
    assert row is not None, f"{name} is not installed"
    return row[0]


@pytest.mark.parametrize("table", TWIN_TABLES)
def test_c8_the_comparator(tmp_path: Path, table: str) -> None:
    spec = SPEC[table]
    c = migrated(tmp_path, 41)
    try:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
        sql = _stored(c, spec.update_trigger)
    finally:
        c.close()
    # (1) the classes PARTITION the table's columns
    declared = spec.all_columns()
    assert len(declared) == len(set(declared)), "a column in two classes"
    assert sorted(declared) == sorted(cols), (
        f"unknown: {sorted(set(declared) - set(cols))}; "
        f"undecided: {sorted(set(cols) - set(declared))}")
    body = sql.split("RAISE(ABORT", 1)[0]
    # (2) NEW.<c> for every non-M column, for NO M column
    for col in cols:
        named = re.search(rf"\bNEW\.{col}\b", body) is not None
        assert named == (col not in spec.M), (col, named)
    # (3) the I form
    for col in spec.I:
        assert f"NEW.{col} IS OLD.{col}" in body, col
    # (4) every F clause names its parent and parent PK
    for f in spec.F:
        assert (f"NOT EXISTS (SELECT 1 FROM {f.parent} WHERE {f.ppk} = OLD.{f.col})"
                in body), f.col
