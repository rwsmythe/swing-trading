"""The 22-A ``candidates`` barrier-lift helper, tested -- the gap in the arc's
own tooling.

WHY THIS FILE EXISTS.  ``tests/_candidates_barrier_helper.py`` states its
guarantee in PROSE and nothing pinned it: *"a helper that dropped and did not
restore -- or restored an approximation -- would silently disarm structural
admission for every later assertion sharing the connection."*  Five test
modules depend on that sentence.  It is exactly the class this arc keeps
finding, sitting in the arc's own instruments, so it is pinned here.

**THE ASSERTIONS ARE SHOWN TO HAVE TEETH.**  A body comparison that is never
exercised against a WRONG body is the existence check wearing better clothes
(CHARC, 2026-08-24, on review 22A-R9-01) -- so a negative control below plants
a SAME-NAME NO-OP restore and asserts both the byte comparison and the
production integrity reader REJECT it.  Without that control every assertion
here would pass against a helper that restored nothing but the names.

**THE READER IS THE JUDGE, NOT A SECOND COMPARATOR.**  The load-bearing
consequence of a bad restore is that ``barrier_installed`` -- the function rung
9 actually calls -- stops certifying the barrier.  So the round-trip is
asserted THROUGH that reader, not only against a snapshot of ``sqlite_master``
taken by this test.  A test comparing sqlite_master to itself would agree with
any restore the reader rejects.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.repos.candidates_immutability_epoch import (
    BARRIER_TRIGGER_NAMES,
    barrier_installed,
    freeze_tier_for_candidate,
)
from tests._candidates_barrier_helper import (
    CANDIDATES_BARRIER_TRIGGERS,
    candidates_barrier_lifted,
)
from tests._latch_link_fixtures_22a import seed_fire

HELPER_SOURCE = (
    Path(__file__).resolve().parents[1] / "_candidates_barrier_helper.py"
)


@pytest.fixture()
def conn(tmp_path: Path):
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


@pytest.fixture()
def fire(conn) -> int:
    """One A+ candidate to mutate.  INSERT is permitted by the barrier; only
    UPDATE, DELETE and a CONFLICTING insert are not."""
    candidate_id = seed_fire(conn)
    conn.commit()
    return candidate_id


def _trigger_sql(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """``{name: (tbl_name, sql)}`` for the three barrier triggers, RAW.

    Raw, not normalized: the helper's claim is a VERBATIM replay, and comparing
    normalized text would accept a whitespace-reformatted restore that the
    claim does not permit (the reader would too, deliberately -- but the helper
    promises more than the reader requires and that surplus is what is pinned).
    """
    placeholders = ",".join("?" * len(CANDIDATES_BARRIER_TRIGGERS))
    return {
        name: (tbl_name, sql)
        for name, tbl_name, sql in conn.execute(
            f"SELECT name, tbl_name, sql FROM sqlite_master "
            f"WHERE type = 'trigger' AND name IN ({placeholders})",
            CANDIDATES_BARRIER_TRIGGERS,
        )
    }


def _update_aborts(conn: sqlite3.Connection, candidate_id: int) -> bool:
    try:
        conn.execute(
            "UPDATE candidates SET pivot = 99.99 WHERE id = ?", (candidate_id,))
    except sqlite3.IntegrityError:
        return True
    conn.rollback()
    return False


# ---------------------------------------------------------------------------
# The three states: armed before, lifted inside, armed after
# ---------------------------------------------------------------------------
def test_the_barrier_is_armed_before_the_helper_is_used(conn, fire) -> None:
    """The precondition, asserted rather than assumed.  If the barrier were not
    armed to begin with, every "restored" assertion below would be vacuous."""
    assert _update_aborts(conn, fire)
    assert barrier_installed(conn) is True


def test_update_delete_and_a_conflicting_insert_all_work_inside_the_block(
        conn, fire) -> None:
    """All THREE triggers are lifted, not just the two CHARC's requirement was
    written against.  ``trg_candidates_no_replace`` closes the MEASURED
    ``INSERT OR REPLACE`` bypass, so a helper lifting only two would leave a
    fixture unable to plant the very shape it needs."""
    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET pivot = 99.99 WHERE id = ?", (fire,))
        assert conn.execute(
            "SELECT pivot FROM candidates WHERE id = ?", (fire,)
        ).fetchone()[0] == 99.99
        conn.execute(
            "INSERT OR REPLACE INTO candidates (id, evaluation_run_id, ticker, "
            "bucket, close, pivot, initial_stop, rs_method) "
            "VALUES (?, (SELECT evaluation_run_id FROM candidates WHERE id = ?), "
            "'FTRE', 'aplus', 1.0, 2.0, 1.0, 'universe')",
            (fire, fire))
        conn.execute("DELETE FROM candidates WHERE id = ?", (fire,))
        assert conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE id = ?", (fire,)
        ).fetchone()[0] == 0
    conn.commit()


def test_every_trigger_body_is_BYTE_identical_after_the_round_trip(
        conn, fire) -> None:
    """The helper reads the bodies out of ``sqlite_master`` and replays them
    verbatim, so it can never drift from the migration -- it never spells a
    trigger body of its own.  Byte equality, name set, and ``tbl_name``."""
    before = _trigger_sql(conn)
    assert set(before) == set(CANDIDATES_BARRIER_TRIGGERS)

    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET pivot = 12.5 WHERE id = ?", (fire,))
    conn.commit()

    assert _trigger_sql(conn) == before


def test_the_barrier_is_armed_again_after_the_block(conn, fire) -> None:
    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET pivot = 12.5 WHERE id = ?", (fire,))
    conn.commit()
    assert _update_aborts(conn, fire)


def test_the_production_integrity_reader_still_certifies_the_barrier(
        conn, fire) -> None:
    """THE guarantee, asserted through the function rung 9 actually calls.

    ``freeze_tier_for_candidate`` returns ``(tier, barrier_installed)``, and an
    approximate restore turns the second element ``False`` for every later
    assertion sharing this connection -- structural admission silently disarmed,
    which is precisely the failure the helper's docstring names.
    """
    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET pivot = 12.5 WHERE id = ?", (fire,))
    conn.commit()

    assert barrier_installed(conn) is True
    _tier, installed = freeze_tier_for_candidate(conn, fire)
    assert installed is True


# ---------------------------------------------------------------------------
# The negative control -- the assertions above have teeth
# ---------------------------------------------------------------------------
def test_a_same_name_NOOP_restore_is_CAUGHT_by_both_checks(conn, fire) -> None:
    """The discriminator.  Drop the real barrier and re-create a same-name
    NO-OP on the same table -- the shape a name-counting check blesses.

    Both instruments must reject it: the byte comparison this file uses, and
    ``barrier_installed``, which is the one production consults.  If this test
    passed, every "restored" assertion above would be certifying nothing.
    """
    before = _trigger_sql(conn)
    conn.execute("DROP TRIGGER trg_candidates_no_update")
    conn.execute(
        "CREATE TRIGGER trg_candidates_no_update BEFORE UPDATE ON candidates "
        "BEGIN SELECT 1; END")
    conn.commit()

    assert set(_trigger_sql(conn)) == set(before)      # the NAMES still match
    assert _trigger_sql(conn) != before                # the BODIES do not
    assert barrier_installed(conn) is False
    assert _update_aborts(conn, fire) is False


# ---------------------------------------------------------------------------
# The exception path
# ---------------------------------------------------------------------------
def test_the_exception_path_restores_the_barrier_and_re_raises(
        conn, fire) -> None:
    """A ``finally`` restore, pinned.  A helper restoring only on the success
    path leaves the barrier down for the REST of the session after any failing
    assertion inside the block -- and a failing assertion is the ordinary way a
    test using this helper ends."""
    before = _trigger_sql(conn)

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with candidates_barrier_lifted(conn):
            conn.execute(
                "UPDATE candidates SET pivot = 12.5 WHERE id = ?", (fire,))
            raise Boom("the body failed, as a failing assertion would")
    conn.commit()

    assert _trigger_sql(conn) == before
    assert barrier_installed(conn) is True
    assert _update_aborts(conn, fire)


# ---------------------------------------------------------------------------
# Scope: the subset parameter, and the pre-0037 no-op
# ---------------------------------------------------------------------------
def test_lifting_a_SUBSET_leaves_the_unnamed_triggers_armed(conn, fire) -> None:
    """``triggers=`` is a real narrowing, not decoration: a test that needs an
    UPDATE must not silently gain a DELETE it never asked for."""
    with candidates_barrier_lifted(
            conn, triggers=("trg_candidates_no_update",)):
        conn.execute("UPDATE candidates SET pivot = 12.5 WHERE id = ?", (fire,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM candidates WHERE id = ?", (fire,))
    conn.commit()

    assert set(_trigger_sql(conn)) == set(CANDIDATES_BARRIER_TRIGGERS)
    assert barrier_installed(conn) is True


def test_a_pre_0037_schema_is_a_silent_no_op(tmp_path: Path) -> None:
    """A fixture built on v36 has no barrier to lift.  The helper is a no-op
    there rather than an error, so a shared fixture can use it unconditionally
    -- and it must not CREATE anything on the way out."""
    c = open_connection(tmp_path / "v36.db")
    try:
        run_migrations(c, target_version=36)
        assert _trigger_sql(c) == {}
        with candidates_barrier_lifted(c):
            pass
        assert _trigger_sql(c) == {}
    finally:
        c.close()


# ---------------------------------------------------------------------------
# The helper's own construction
# ---------------------------------------------------------------------------
def test_the_helper_spells_no_trigger_body_of_its_own() -> None:
    """The reason the verbatim replay can never drift from the migration: there
    is no second copy of the DDL to drift.  A future edit that hard-codes a
    body -- the tempting repair when a restore looks wrong -- is caught here
    rather than by a silently-disarmed barrier three modules away."""
    source = HELPER_SOURCE.read_text(encoding="utf-8").lower()
    assert "create trigger" not in source
    assert "raise(abort" not in source


def test_the_helper_names_exactly_the_readers_barrier_trigger_set() -> None:
    """Two rosters, one barrier.  If migration 0037 ever grows a fourth
    CANDIDATES barrier trigger, the helper would drop three and restore three
    while the reader demands four -- every later admission refused, for a
    reason no test names.

    THE COMPARISON IS AGAINST THE CANDIDATES SUBSET, not against the reader's
    whole roster (Codex 22A-R3-01).  The reader now certifies SIX triggers --
    the three on ``candidates`` and the three on the EPOCH -- and this helper
    lifts only the first three, because no fixture has any business making the
    epoch mutable.  Asserting set equality against all six would demand the
    helper drop triggers it must never drop.
    """
    from swing.data.repos.candidates_immutability_epoch import (
        CANDIDATES_BARRIER_TRIGGER_NAMES,
    )

    assert set(CANDIDATES_BARRIER_TRIGGERS) == set(
        CANDIDATES_BARRIER_TRIGGER_NAMES)
    assert set(CANDIDATES_BARRIER_TRIGGER_NAMES) < set(BARRIER_TRIGGER_NAMES)
