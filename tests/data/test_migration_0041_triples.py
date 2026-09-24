"""22-I T3/T4/T13 -- the (a) triples and the (c) barrier pairs: plan section 4.1.

Each probe is a (version, verdict) pair on the SAME seeded world: at v40 the
statement is EXPOSED (it succeeds, or only an engine constraint refuses it),
at v41 the named 0041 trigger refuses it.

    A1 ordinary append, pk omitted                    OK / OK
    A2 INSERT OR REPLACE / REPLACE on each conflict key  exposed / no_replace
    A3 INSERT OR IGNORE / ON CONFLICT DO NOTHING      exposed / no_replace (the priced cost)
    A4 plain INSERT, explicit conflicting PK          UNIQUE / no_replace
    A5 INSERT OR REPLACE, explicit conflicting PK     exposed / no_replace
    A6 DELETE                                         exposed / no_delete
    A7 UPDATE <col>, every column                     exposed / no_update (blanket tables)
    A8 explicit -1 PK insert                          OK / OK (AL-1, pinned)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.data._22i_guard_spec import SPEC
from tests.data._22i_seed import (
    conflict_rows,
    different_value,
    fresh_row,
    insert_copy_sql,
    is_engine_refusal,
    migrated,
    outcome,
    row_of,
    where_pk,
)

BLANKET = ("pattern_forward_observations", "candidate_criteria", "trade_events",
           "finviz_api_calls", "pattern_evaluations", "evaluation_runs")
# Tables whose BARRIER PAIR (no_replace + no_delete) the A2-A6 probes cover.
BARRIER_TABLES = (*BLANKET, "pattern_detection_events",
                  "reconciliation_runs", "reconciliation_discrepancies",
                  "reconciliation_corrections", "schwab_api_calls", "yfinance_calls")
PAIR = pytest.mark.parametrize("version", [40, 41])


def _world(tmp_path: Path, version: int):
    return migrated(tmp_path, version, world=True)


def _check(verdict: str, version: int, trigger: str) -> None:
    if version == 40:
        assert verdict == "OK" or is_engine_refusal(verdict), verdict
    else:
        assert verdict == f"TRIGGER:{trigger}", verdict


@PAIR
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a1_ordinary_append_succeeds(tmp_path: Path, table: str, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        assert outcome(c, *insert_copy_sql(c, table, fresh_row(c, table))) == "OK"
    finally:
        c.close()


@PAIR
@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a2_replace_on_each_conflict_key(tmp_path: Path, table: str, verb: str,
                                         version: int) -> None:
    c = _world(tmp_path, version)
    try:
        for _label, row in conflict_rows(c, table):
            verdict = outcome(c, *insert_copy_sql(c, table, row, verb=verb))
            _check(verdict, version, f"trg_{SPEC[table].abbr}_no_replace")
    finally:
        c.close()


@PAIR
@pytest.mark.parametrize("form", ["INSERT OR IGNORE", "ON CONFLICT DO NOTHING"])
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a3_ignore_and_do_nothing_are_refused(tmp_path: Path, table: str, form: str,
                                              version: int) -> None:
    """The priced cost, pinned: a BEFORE INSERT trigger cannot see the conflict
    algorithm, so the idempotent forms abort too (a writer pre-filters)."""
    c = _world(tmp_path, version)
    try:
        for _label, row in conflict_rows(c, table):
            if form == "INSERT OR IGNORE":
                sql, params = insert_copy_sql(c, table, row, verb="INSERT OR IGNORE")
            else:
                sql, params = insert_copy_sql(c, table, row)
                sql += " ON CONFLICT DO NOTHING"
            verdict = outcome(c, sql, params)
            if version == 40:
                assert verdict == "OK", verdict  # a silent no-op
            else:
                assert verdict == f"TRIGGER:trg_{SPEC[table].abbr}_no_replace"
    finally:
        c.close()


def _explicit_pk_row(c, table: str) -> dict:
    row = row_of(c, table)
    col = next(x for x in SPEC[table].all_columns() if x not in SPEC[table].pk)
    row[col] = different_value(c, table, col, row[col])
    return row


@PAIR
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a4_plain_insert_with_an_explicit_conflicting_pk(tmp_path: Path, table: str,
                                                         version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *insert_copy_sql(c, table, _explicit_pk_row(c, table)))
    finally:
        c.close()
    if version == 40:
        assert verdict == "CONSTRAINT:UNIQUE", verdict
    else:
        assert verdict == f"TRIGGER:trg_{SPEC[table].abbr}_no_replace"


@PAIR
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a5_insert_or_replace_with_an_explicit_conflicting_pk(
        tmp_path: Path, table: str, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *insert_copy_sql(c, table, _explicit_pk_row(c, table),
                                              verb="INSERT OR REPLACE"))
    finally:
        c.close()
    _check(verdict, version, f"trg_{SPEC[table].abbr}_no_replace")


@PAIR
@pytest.mark.parametrize("table", BARRIER_TABLES)
def test_a6_delete(tmp_path: Path, table: str, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        w, p = where_pk(table)
        verdict = outcome(c, f"DELETE FROM {table} WHERE {w}", p)
    finally:
        c.close()
    _check(verdict, version, f"trg_{SPEC[table].abbr}_no_delete")


def _a7_cases():
    for table in BLANKET:
        for col in SPEC[table].all_columns():
            yield pytest.param(table, col, id=f"{table}.{col}")


@PAIR
@pytest.mark.parametrize("table,col", list(_a7_cases()))
def test_a7_update_of_every_column(tmp_path: Path, table: str, col: str,
                                   version: int) -> None:
    c = _world(tmp_path, version)
    try:
        row = row_of(c, table)
        w, p = where_pk(table)
        verdict = outcome(c, f"UPDATE {table} SET {col} = ? WHERE {w}",
                          (different_value(c, table, col, row[col]), *p))
    finally:
        c.close()
    _check(verdict, version, f"trg_{SPEC[table].abbr}_no_update")


@PAIR
@pytest.mark.parametrize(
    "table", [t for t in BARRIER_TABLES if SPEC[t].integer_pk])
def test_a8_explicit_minus_one_pk_is_the_declared_residual(
        tmp_path: Path, table: str, version: int) -> None:
    """AL-1: no CHECK (pk > 0) is added (a rebuild); an explicit -1 passes the
    `NEW.pk != -1` clause. Pinned so a later CHECK is a visible change."""
    c = _world(tmp_path, version)
    try:
        row = fresh_row(c, table)
        row[SPEC[table].pk[0]] = -1
        assert outcome(c, *insert_copy_sql(c, table, row)) == "OK"
    finally:
        c.close()
