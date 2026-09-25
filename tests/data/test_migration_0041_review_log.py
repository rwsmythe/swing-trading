"""22-I T12 -- review_log: the service twin FIRST, then the F-I3 writer, then the
triggers (plan section 3 T12; authorize-then-abort, harness section 5.1: a
trigger never ships ahead of its service check).

    T12a  complete_review_atomic refuses an ALREADY-completed row with the typed
          ReviewAlreadyCompletedError (RD S3-F3 (A); CHARC's scope ruling), and
          the CLI wraps it to click.ClickException("Review already completed")
          -- the web's 409 detail text (routes/trades.py:3766-3770) verbatim.
    T12b  trg_rl_no_replace + trg_rl_no_delete, and the F-I3 writer
          adjustment (CHARC S3-F4 (i)): insert_pre_create pre-filters with
          WHERE NOT EXISTS, so its idempotent no-op never reaches the barrier;
          the IntegrityError matcher is retained VERBATIM as the belt ((ii)
          refused: no trigger-name matching).
    T12c  trg_rl_immutable (RD S3-F3 (A); plan section 1.3): the seven I
          columns are frozen always; the S aggregates + completed_date + the
          completion text are frozen once OLD.completed_date IS NOT NULL (the
          pre-completion row stays writable); risk_policy_id_at_review_completion
          is F-shaped while frozen (a17, DEAD-BY-PARENT-GUARD);
          superseded_by_correction_id is M (reconciliation_auto_correct.py:2404
          overwrites it unconditionally). C1/C2/C4/C6/C8 run in
          test_migration_0041_twins.py.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.review_log import (
    ReviewAlreadyCompletedError,
    complete_review_atomic,
    insert_pre_create,
)
from tests.data._22i_guard_spec import SPEC
from tests.data._22i_seed import TS, different_value, migrated, outcome, row_of

PAIR = pytest.mark.parametrize("version", [40, 41])


def _all_columns(conn: sqlite3.Connection, review_id: int) -> tuple:
    return conn.execute("SELECT * FROM review_log WHERE review_id = ?",
                        (review_id,)).fetchone()


@pytest.fixture
def completed(tmp_path: Path):
    conn = ensure_schema(tmp_path / "rl.db")
    with conn:
        rid = insert_pre_create(conn, review_type="daily", period_start="2026-04-30",
                                period_end="2026-04-30", scheduled_date="2026-05-01")
    complete_review_atomic(conn, review_id=rid, completed_date="2026-05-02",
                           duration_minutes=10, primary_lesson="first lesson",
                           next_period_focus="first focus")
    yield conn, rid
    conn.close()


def test_complete_review_atomic_refuses_completed_row(completed) -> None:
    conn, rid = completed
    before = _all_columns(conn, rid)
    assert len(before) == 24
    assert before[5] == "2026-05-02"  # completed_date
    with pytest.raises(ReviewAlreadyCompletedError, match="Review already completed"):
        complete_review_atomic(conn, review_id=rid, completed_date="2026-06-01",
                               duration_minutes=99, primary_lesson="second lesson",
                               next_period_focus="second focus")
    assert _all_columns(conn, rid) == before
    assert not conn.in_transaction  # the existing except rolled back


def test_review_already_completed_error_is_a_value_error() -> None:
    """The type the CLI boundary catches; a ValueError subclass so a caller
    written against the service's existing ValueError contract still sees it."""
    assert issubclass(ReviewAlreadyCompletedError, ValueError)


# ---------------------------------------------------------------------------
# T12b -- the F-I3 writer contract (CHARC S3-F4 (i) wording) + the barrier pair
# ---------------------------------------------------------------------------
_PERIOD = dict(review_type="weekly", period_start="2026-08-03",
               period_end="2026-08-09", scheduled_date="2026-08-10")


def _count(c: sqlite3.Connection) -> int:
    return c.execute("SELECT count(*) FROM review_log").fetchone()[0]


@PAIR
def test_insert_pre_create_contract(tmp_path: Path, version: int) -> None:
    """On the migrated schema with the row already present, insert_pre_create
    returns None, raises nothing, and the row count is unchanged; on an absent
    row it returns the new id. The contract does not move with the repair: it
    holds at v40 (the UNIQUE belt) and at v41 (the pre-filter, before the
    barrier)."""
    c = migrated(tmp_path, version)
    try:
        new_id = insert_pre_create(c, **_PERIOD)
        assert isinstance(new_id, int) and new_id >= 1
        n = _count(c)
        assert insert_pre_create(c, **_PERIOD) is None
        assert _count(c) == n
        other = insert_pre_create(c, **dict(_PERIOD, period_end="2026-08-16"))
        assert isinstance(other, int) and other != new_id
        assert _count(c) == n + 1
    finally:
        c.close()


def test_insert_pre_create_other_integrity_errors_still_raise(tmp_path: Path) -> None:
    """The belt is retained verbatim: a non-UNIQUE IntegrityError (a CHECK on
    review_type) still re-raises."""
    c = migrated(tmp_path, 41)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert_pre_create(c, **dict(_PERIOD, review_type="hourly"))
    finally:
        c.close()


def _rl_world(tmp_path: Path, version: int) -> sqlite3.Connection:
    return migrated(tmp_path, version, world=True)


@PAIR
@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE"])
def test_rl_no_replace_on_the_cadence_key(tmp_path: Path, verb: str,
                                          version: int) -> None:
    c = _rl_world(tmp_path, version)
    try:
        verdict = outcome(
            c, f"{verb} INTO review_log (review_type, period_start, period_end, "
               "scheduled_date, primary_lesson) VALUES ('weekly', '2026-08-03', "
               "'2026-08-09', '2026-08-10', 'rewritten')")
    finally:
        c.close()
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == "TRIGGER:trg_rl_no_replace", verdict


@PAIR
def test_rl_no_delete(tmp_path: Path, version: int) -> None:
    c = _rl_world(tmp_path, version)
    try:
        verdict = outcome(c, "DELETE FROM review_log WHERE review_id = 1")
    finally:
        c.close()
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == "TRIGGER:trg_rl_no_delete", verdict


# ---------------------------------------------------------------------------
# T12c -- the state-frozen twin
# ---------------------------------------------------------------------------
TWIN = "TRIGGER:trg_rl_immutable"
PENDING, COMPLETED = {"review_id": 1}, {"review_id": 2}


def _set(c: sqlite3.Connection, col: str, pk: dict) -> str:
    v = different_value(c, "review_log", col, row_of(c, "review_log", pk)[col])
    return outcome(c, f"UPDATE review_log SET {col} = ? WHERE review_id = ?",
                   (v, pk["review_id"]))


@PAIR
@pytest.mark.parametrize("col", SPEC["review_log"].S)
def test_rl_s_column_on_a_completed_row_aborts(tmp_path: Path, col: str,
                                               version: int) -> None:
    c = _rl_world(tmp_path, version)
    try:
        verdict = _set(c, col, COMPLETED)
    finally:
        c.close()
    assert verdict == ("OK" if version == 40 else TWIN), verdict


@PAIR
@pytest.mark.parametrize("col", SPEC["review_log"].S)
def test_rl_s_column_on_an_uncompleted_row_admitted(tmp_path: Path, col: str,
                                                    version: int) -> None:
    c = _rl_world(tmp_path, version)
    try:
        verdict = _set(c, col, PENDING)
    finally:
        c.close()
    assert verdict == "OK", verdict


@PAIR
@pytest.mark.parametrize("col", SPEC["review_log"].I)
def test_rl_i_column_on_a_completed_row_aborts(tmp_path: Path, col: str,
                                               version: int) -> None:
    """C1 runs the I set on the PENDING row (twins module); this is its
    completed-row twin -- I is frozen in BOTH states."""
    c = _rl_world(tmp_path, version)
    try:
        verdict = _set(c, col, COMPLETED)
    finally:
        c.close()
    if version == 40:
        assert verdict == "OK" or verdict.startswith("CONSTRAINT:"), verdict
    else:
        assert verdict == TWIN, verdict


@PAIR
def test_rl_rp_stamp_on_an_uncompleted_row_admitted(tmp_path: Path, version: int) -> None:
    """F is F-shaped only while frozen: a pending row's stamp moves freely."""
    c = _rl_world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE review_log SET risk_policy_id_at_review_completion "
                             "= 1 WHERE review_id = 1")
    finally:
        c.close()
    assert verdict == "OK", verdict


@PAIR
def test_rl_supersede_2404_on_a_completed_row_admitted(tmp_path: Path,
                                                       version: int) -> None:
    """The literal :2404 statement via _supersede_review_log_for_trade_close,
    on a completed review whose period brackets trade 20's close (fill 44,
    2026-08-11): NULL -> value, then value -> other (the unconditional
    overwrite) -- both admitted."""
    from swing.trades.reconciliation_auto_correct import (
        _supersede_review_log_for_trade_close,
    )

    c = _rl_world(tmp_path, version)
    bracket = ("INSERT INTO review_log (review_id, review_type, period_start, "
               "period_end, scheduled_date, completed_date, duration_minutes, "
               "primary_lesson, next_period_focus, created_at) VALUES "
               "(3, 'weekly', '2026-08-10', '2026-08-16', '2026-08-17', "
               "'2026-08-17', 20, 'l', 'f', ?)", (TS,))
    try:
        def both(k):
            _supersede_review_log_for_trade_close(k, trade_id=20, new_correction_id=1)
            _supersede_review_log_for_trade_close(k, trade_id=20, new_correction_id=2)
        verdict, seen = outcome(
            c, both, setup=[bracket],
            post=lambda k: k.execute("SELECT superseded_by_correction_id FROM "
                                     "review_log WHERE review_id = 3").fetchone())
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (2,))


def test_complete_review_atomic_on_an_uncompleted_row_admitted_at_41(
        tmp_path: Path) -> None:
    c = _rl_world(tmp_path, 41)
    try:
        complete_review_atomic(c, review_id=1, completed_date="2026-08-10",
                               duration_minutes=15, primary_lesson="lesson",
                               next_period_focus="focus")
        row = row_of(c, "review_log", PENDING)
    finally:
        c.close()
    assert row["completed_date"] == "2026-08-10"
    assert row["primary_lesson"] == "lesson"
    assert row["risk_policy_id_at_review_completion"] == 1


# ---------------------------------------------------------------------------
# section 4.4 -- the service-twin closure (authorize-then-abort)
# ---------------------------------------------------------------------------
def test_rl_trigger_refusal_unreachable_through_service(tmp_path: Path) -> None:
    """The one trg_rl_immutable refusal a PRODUCTION path can reach is a
    re-completion (complete_review_atomic -- the CLI and the web both route
    through it; the :2404 supersede writes only the M column). The service
    refuses it FIRST with the typed error, and no UPDATE of review_log is
    ever issued -- so the trigger's refusal is unreachable through the
    service (harness section 5.1: the trigger's predicate set is a subset of
    the service's admission predicates)."""
    c = _rl_world(tmp_path, 41)
    statements: list[str] = []
    c.set_trace_callback(statements.append)
    try:
        with pytest.raises(ReviewAlreadyCompletedError) as info:
            complete_review_atomic(c, review_id=2, completed_date="2026-09-01",
                                   duration_minutes=5, primary_lesson="again",
                                   next_period_focus="again")
    finally:
        c.set_trace_callback(None)
        c.close()
    assert not isinstance(info.value, sqlite3.IntegrityError)
    assert type(info.value) is ReviewAlreadyCompletedError
    assert not [s for s in statements if "UPDATE review_log" in " ".join(s.split())]
    assert any("FROM review_log" in s for s in statements)  # the SELECT-first ran
