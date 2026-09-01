"""22-A Task 2 -- migration 0037, at the SCHEMA grain.

Every assertion reads the LIVE schema (``sqlite_master``, ``PRAGMA``) or
EXECUTES a statement against it.  A test that greps the DDL it is validating
proves only that two strings match -- the two exceptions are deliberate and are
labelled where they occur (case 44 and the ``round(`` gate are properties OF THE
FILE, not of the schema, and cannot be established any other way).

EVERY BARRIER TEST ASSERTS ``PRAGMA recursive_triggers`` AT ITS DEFAULT RATHER
THAN SETTING IT.  A test that turns the pragma ON proves the trigger fires in a
world production is not in -- and the whole reason the epoch and the candidates
barrier each need a third trigger is that, at the DEFAULT, ``REPLACE`` does NOT
fire DELETE triggers.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    MigrationBackupRequiredException,
    _current_version,
    _phase22_arc_a_backup_gate,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.trades.latched_origin import (
    AUTHORIZATION_KEYS,
    LATCH_FREEZE_TIERS,
    LATCH_PROBE_EVIDENCE_VERSION,
    PROBE_EVIDENCE_KEYS,
    PROBE_GUARD_KEYS,
    PROVENANCE_ADMISSION_TIERS,
)
from tests._latch_link_fixtures_22a import (
    BROKER_ORDER_ID,
    DETECTION_DATE,
    INITIAL_STOP,
    PIVOT,
    accept_order,
    insert_intent,
    place_row,
    seed_fire,
    validity_row,
)
from tests.trades._cohort_provenance_fixtures import (
    build_cadl_case,
    set_fill_envelope,
)

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "swing" / "data" / "migrations" / "0037_latch_order_mandate_links.sql"
)

BARRIER_TRIGGERS = (
    "trg_candidates_no_update",
    "trg_candidates_no_delete",
    "trg_candidates_no_replace",
)
EPOCH_TRIGGERS = (
    "trg_candidates_epoch_no_update",
    "trg_candidates_epoch_no_delete",
    "trg_candidates_epoch_no_insert",
)


@pytest.fixture()
def conn(tmp_path: Path):
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _assert_default_pragma(conn: sqlite3.Connection) -> None:
    """The pragma is ASSERTED, never set.  See the module docstring."""
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 0


def _v36(tmp_path: Path, name: str = "v36.db") -> sqlite3.Connection:
    c = open_connection(tmp_path / name)
    run_migrations(c, target_version=36)
    return c


# ---------------------------------------------------------------------------
# The migration itself
# ---------------------------------------------------------------------------
def test_expected_schema_version_is_37() -> None:
    assert EXPECTED_SCHEMA_VERSION == 37


def test_migration_applies_to_a_v36_fixture_and_stamps_37(tmp_path: Path) -> None:
    c = _v36(tmp_path)
    try:
        assert _current_version(c) == 36
        run_migrations(c, target_version=37, backup_dir=tmp_path / "bak")
        assert _current_version(c) == 37
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')")}
        assert "latch_order_mandate_links" in names
        assert "candidates_immutability_epoch" in names
        assert set(BARRIER_TRIGGERS) <= names
        assert set(EPOCH_TRIGGERS) <= names
        assert "trg_latch_link_mint_on_acceptance" in names
    finally:
        c.close()


def test_running_the_migration_twice_is_a_no_op(conn) -> None:
    """AND THE VERSION GATE IS WHAT MAKES IT ONE (inherited finding 22A-R9-13).

    A second ``run_migrations`` never re-enters 0037 -- ``current >=
    target_version`` returns first -- so this test does NOT prove the epoch's
    BEFORE INSERT trigger works, and must not be cited as doing so.  That
    property is cases 35c and 35p, which execute the statements directly.
    """
    before = conn.execute(
        "SELECT * FROM candidates_immutability_epoch").fetchall()
    run_migrations(conn, target_version=37)
    assert _current_version(conn) == 37
    assert conn.execute(
        "SELECT * FROM candidates_immutability_epoch").fetchall() == before


def test_the_backup_gate_fires_only_on_the_exact_36_to_37_crossing(
        tmp_path: Path) -> None:
    """STRICT EQUALITY on pre_version, per the ``pre_version == target - 1``
    gotcha -- NOT ``<=``.  A multi-version jump bypasses this gate by design."""
    c = _v36(tmp_path)
    try:
        backup_dir = tmp_path / "bak"
        _phase22_arc_a_backup_gate(
            c, current_version=36, target_version=37, backup_dir=backup_dir)
        made = sorted(backup_dir.glob("swing-pre-22a-migration-*.db"))
        assert len(made) == 1
        # a pre-36 baseline does NOT fire it
        _phase22_arc_a_backup_gate(
            c, current_version=35, target_version=37, backup_dir=backup_dir)
        assert sorted(backup_dir.glob("swing-pre-22a-migration-*.db")) == made
        # and neither does a target below 37
        _phase22_arc_a_backup_gate(
            c, current_version=36, target_version=36, backup_dir=backup_dir)
        assert sorted(backup_dir.glob("swing-pre-22a-migration-*.db")) == made
    finally:
        c.close()


def test_the_backup_gate_requires_a_file_backed_source() -> None:
    c = sqlite3.connect(":memory:")
    try:
        with pytest.raises(MigrationBackupRequiredException):
            _phase22_arc_a_backup_gate(
                c, current_version=36, target_version=37, backup_dir=None)
    finally:
        c.close()


def test_the_pre_migration_table_set_names_the_table_the_migration_alters() -> None:
    """The H1 gate's own rule: a gate that does not require the one table its
    migration TOUCHES is not a belt.  0037 ALTERs provenance_corrections."""
    assert "provenance_corrections" in PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES
    assert "candidates" in PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES
    assert "latch_order_intents" in PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES


# ---------------------------------------------------------------------------
# The candidates barrier
# ---------------------------------------------------------------------------
def test_an_update_on_candidates_aborts(conn) -> None:
    _assert_default_pragma(conn)
    cid = seed_fire(conn)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("UPDATE candidates SET pivot = 1.0 WHERE id = ?", (cid,))
    assert "trg_candidates_no_update" in str(exc.value)


def test_delete_and_reinsert_of_the_same_identity_aborts_at_the_delete_case_26(
        conn) -> None:
    """Case 26 -- DELETE is barriered.

    ``candidates.id`` is a REUSABLE rowid, so a delete-and-reinsert of the same
    ``(id, evaluation_run_id, ticker)`` would silently repoint every citation at
    a different row.  The abort must happen AT THE DELETE: a test that only
    checks the final row is unchanged would pass an implementation that deleted
    and faithfully re-inserted.
    """
    _assert_default_pragma(conn)
    cid = seed_fire(conn)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
    assert "trg_candidates_no_delete" in str(exc.value)
    row = conn.execute(
        "SELECT pivot, initial_stop FROM candidates WHERE id = ?", (cid,)
    ).fetchone()
    assert row == (PIVOT, INITIAL_STOP)


@pytest.mark.parametrize(
    ("case_id", "statement", "must_abort"),
    [
        # 51a / 51b: the nightly's OWN shapes, which must keep working.
        ("51a", "ordinary INSERT, new run, same ticker", False),
        ("51b", "ordinary INSERT, new ticker, same run", False),
        # 51c / 51d / 51e: every conflict flavour.
        ("51c", "INSERT OR REPLACE on the UNIQUE", True),
        ("51d", "bare REPLACE on the rowid PK", True),
        ("51e", "INSERT OR IGNORE on a duplicate", True),
    ],
)
def test_the_conflict_scoped_insert_barrier(
        conn, case_id: str, statement: str, must_abort: bool) -> None:
    """Cases 51a-51e -- the five measured rows of the S4.5-replace table.

    A TWO-TRIGGER implementation passes 51a and 51b and FAILS 51c, 51d and 51e:
    at the default ``recursive_triggers=OFF`` the REPLACE conflict strategy does
    NOT fire the DELETE trigger, so it reaches the row with both barriers
    present, canonical and UNFIRED.  Measured: id moved 12284 -> 12285,
    pivot/stop rewritten, ``candidate_criteria`` CASCADE-wiped 1 -> 0.
    """
    _assert_default_pragma(conn)
    cid = seed_fire(conn)
    conn.execute(
        "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer, "
        "result) VALUES (?, 'TT1', 'trend_template', 'pass')", (cid,))
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (999, '2026-07-18T20:06:25', '2026-07-18', '2026-07-21', "
        "1, 1, 0, 0, 0, 0)")
    sql = {
        "51a": "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
               "rs_method) VALUES (999, 'FTRE', 'aplus', 'universe')",
        "51b": "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
               "rs_method) VALUES (121, 'ZZZZ', 'aplus', 'universe')",
        "51c": "INSERT OR REPLACE INTO candidates (evaluation_run_id, ticker, "
               "bucket, pivot, rs_method) "
               "VALUES (121, 'FTRE', 'aplus', 99.0, 'universe')",
        "51d": f"REPLACE INTO candidates (id, evaluation_run_id, ticker, "
               f"bucket, pivot, rs_method) "
               f"VALUES ({cid}, 121, 'FTRE', 'aplus', 99.0, 'universe')",
        "51e": "INSERT OR IGNORE INTO candidates (evaluation_run_id, ticker, "
               "bucket, pivot, rs_method) "
               "VALUES (121, 'FTRE', 'aplus', 99.0, 'universe')",
    }[case_id]
    if must_abort:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute(sql)
        assert "trg_candidates_no_replace" in str(exc.value), statement
        # the row and its criteria BOTH survive -- the cascade-wipe is what the
        # barrier exists to stop, and asserting only the pivot would miss it
        assert conn.execute(
            "SELECT pivot FROM candidates WHERE id = ?", (cid,)
        ).fetchone()[0] == PIVOT
        assert conn.execute(
            "SELECT COUNT(*) FROM candidate_criteria WHERE candidate_id = ?",
            (cid,)).fetchone()[0] == 1
    else:
        conn.execute(sql)  # must NOT raise: this is the nightly's own path


THE_51_CASE_IDS = ["51a", "51b", "51c", "51d", "51e"]


def test_insert_candidates_still_works_through_the_production_repo(
        conn) -> None:
    """The barrier must not touch the ONE production writer.

    ``insert_candidates`` is exercised through the repo rather than through a
    hand-written INSERT, because the property under test is that PRODUCTION
    still writes -- a byte-parity test on a synthetic statement would not see a
    divergence in how the real writer spells it.
    """
    from swing.data.models import Candidate
    from swing.data.repos.candidates import insert_candidates

    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (500, '2026-07-17T20:06:25', '2026-07-17', '2026-07-20', "
        "1, 1, 0, 0, 0, 0)")
    with conn:
        insert_candidates(conn, 500, [
            Candidate(
                ticker="NEWT", bucket="aplus", close=10.0, pivot=10.5,
                initial_stop=9.0, adr_pct=None, tight_streak=None,
                pullback_pct=None, prior_trend_pct=None, rs_rank=None,
                rs_return_12w_vs_spy=None, rs_method="universe",
                pattern_tag=None, notes=None, criteria=(),
            ),
        ])
    assert conn.execute(
        "SELECT COUNT(*) FROM candidates WHERE ticker = 'NEWT'"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# The epoch
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("case_id", "sql"),
    [
        ("35a", "UPDATE candidates_immutability_epoch "
                "SET max_candidate_id_at_barrier = 0"),
        ("35b", "DELETE FROM candidates_immutability_epoch"),
        ("35c", "INSERT OR REPLACE INTO candidates_immutability_epoch "
                "VALUES (1, 0, 'x')"),
        ("35n", "INSERT INTO candidates_immutability_epoch VALUES (2, 0, 'x')"),
        ("35p-replace", "REPLACE INTO candidates_immutability_epoch "
                        "VALUES (1, 0, 'x')"),
        ("35p-ignore", "INSERT OR IGNORE INTO candidates_immutability_epoch "
                       "VALUES (1, 0, 'x')"),
    ],
)
def test_the_epoch_refuses_every_write_path(conn, case_id: str, sql: str) -> None:
    """Cases 35a, 35b, 35c, 35n, 35p -- at the DEFAULT pragma.

    A TWO-trigger implementation passes 35a, 35b and 35n and FAILS 35c and 35p.
    The direction of that failure is the untolerable one: an
    ``INSERT OR REPLACE`` LOWERING the boundary stamps a PRE-barrier fire
    ``live_at_acceptance`` -- a false structural-proof label minted by the very
    mechanism that exists to make the proof honest.
    """
    _assert_default_pragma(conn)
    before = conn.execute(
        "SELECT * FROM candidates_immutability_epoch").fetchall()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
    assert conn.execute(
        "SELECT * FROM candidates_immutability_epoch").fetchall() == before


THE_35_CASE_IDS = ["35a", "35b", "35c", "35n", "35p"]


def test_the_epoch_boundary_is_seeded_from_the_live_max_candidate_id(
        tmp_path: Path) -> None:
    """A MEASUREMENT, not a constant somebody typed."""
    c = _v36(tmp_path)
    try:
        seed_fire(c, candidate_id=12284)
        c.commit()
        run_migrations(c, target_version=37, backup_dir=tmp_path / "bak")
        assert c.execute(
            "SELECT max_candidate_id_at_barrier FROM "
            "candidates_immutability_epoch").fetchone()[0] == 12284
    finally:
        c.close()


def test_the_low_id_tier_is_conservative_not_exact_case_33(conn) -> None:
    """Case 33 -- THIS TEST PINS A LIMITATION, NOT A GUARANTEE.

    The epoch compares CANDIDATE IDs, and an id is a proxy for creation order,
    not a timestamp.  Every candidate at-or-below the boundary is stamped
    ``pre_barrier_reconstructed``, and that is CONSERVATIVE in the safe
    direction: it can only refuse an admission, never manufacture one.  Its
    green must never be read as proof that the tier is EXACT.

    THE BOUNDARY ROW ITSELF IS PRE-BARRIER (inherited finding 22A-R9-02): a
    candidate whose id EQUALS ``max_candidate_id_at_barrier`` already existed
    when the barrier was installed, so the comparison is STRICTLY GREATER THAN.
    A ``>=`` implementation stamps it ``live_at_acceptance`` and mints a false
    structural-proof label for the one row the boundary is named after.

    **THIS ROW WAS VACUOUS AND COULD NOT FAIL** (semantic re-audit
    2026-08-31, upgraded from WEAKER at QA).  It SELECTed a
    ``CASE WHEN ? > (...)`` expression THE TEST ITSELF WROTE and asserted on
    its own expression; the only production input was
    ``max_candidate_id_at_barrier``.  A ``>=`` in the `0037` minting trigger
    or in ``freeze_tier_for_candidate`` left it GREEN -- and its own docstring
    NAMES that defect as the thing it exists to catch.  It now asks the
    PRODUCTION READER, on both sides of the boundary, so the strictness it
    describes is the strictness it measures.
    """
    from swing.data.repos.candidates_immutability_epoch import (
        freeze_tier_for_candidate,
    )

    boundary = conn.execute(
        "SELECT max_candidate_id_at_barrier FROM candidates_immutability_epoch"
    ).fetchone()[0]
    above = seed_fire(conn, candidate_id=boundary + 1, run_id=131,
                      action_session_date="2026-07-20")
    assert above == boundary + 1

    tier_at_boundary, installed = freeze_tier_for_candidate(conn, boundary)
    assert installed is True, (
        "the barrier must be standing, or the reader answers pre-barrier for "
        "a reason unrelated to the comparison")
    assert tier_at_boundary == "pre_barrier_reconstructed", (
        "the BOUNDARY ROW ITSELF must be pre-barrier; a `>=` reader mints a "
        "false structural-proof label for the row the boundary is named after")
    assert freeze_tier_for_candidate(conn, above)[0] == "live_at_acceptance", (
        "the reader refuses everything, so the row above is not what proves "
        "the boundary is strict")


# ---------------------------------------------------------------------------
# The messages
# ---------------------------------------------------------------------------
def test_every_barrier_message_is_legible_case_36(conn) -> None:
    """Case 36 -- CHARC CONDITION 2, ASSERTED AS CONTENT, NEVER AS BYTES.

    *A refusal that does not say what to do next is a dead end, not a guard.*
    Each message must name its own trigger, the ARC, and the recovery path.
    Byte-comparing the message would make an IMPROVEMENT to the wording a false
    red, which is how a legibility requirement decays into a string pin.

    **THE TRIGGER-NAME CLAUSE WAS UNFALSIFIABLE** (semantic re-audit
    2026-08-31, upgraded from WEAKER at QA and verified BY EXECUTION).  It
    asked ``name in body`` where ``body`` was the WHOLE ``sqlite_master.sql``
    -- which BEGINS ``CREATE TRIGGER <name>`` -- so the clause could not fail
    for any trigger, ever.  Measured over the six ``trg_candidates*`` rows:
    every header contains the name AND every RAISE message contains it too, so
    the intended property genuinely holds today; an edit removing the name
    from the MESSAGE simply left the row green.  All three clauses now read
    the text AFTER ``BEGIN``, which is the body the operator sees.
    """
    bodies = {
        name: sql for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")
    }
    guarded = (*BARRIER_TRIGGERS, *EPOCH_TRIGGERS,
               "trg_loml_no_update", "trg_loml_no_delete")
    for name in guarded:
        header, sep, message = bodies[name].partition("BEGIN")
        assert sep, f"{name} has no BEGIN, so its message cannot be located"
        assert name in header, f"{name} is not the trigger it claims to be"
        assert name in message, (
            f"{name} does not name itself in its own MESSAGE; the header names "
            f"it by construction, which is what made this clause vacuous")
        assert "22-A" in message, f"{name} does not name the arc"
        assert "reversibility header" in message, (
            f"{name} does not name the recovery path")


# ---------------------------------------------------------------------------
# The link table, the minting trigger and the backfill
# ---------------------------------------------------------------------------
def test_the_link_table_has_no_cap_shaped_column(conn) -> None:
    """S2.1 property 3: the cap is DERIVED from the frozen pivot at read time,
    so the SQL-vs-Python arithmetic fork cannot be reintroduced by a later
    edit."""
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(latch_order_mandate_links)")]
    assert not [c for c in cols if "cap" in c.lower()], cols


def test_the_minting_trigger_fires_on_a_broker_acceptance(conn) -> None:
    cid = seed_fire(conn)
    place_id, validity_id = accept_order(conn, cid)
    rows = conn.execute(
        "SELECT validity_intent_id, place_intent_id, candidate_id, ticker, "
        "broker_order_id, frozen_pivot, frozen_invalidation, actual_quantity, "
        "freeze_tier FROM latch_order_mandate_links").fetchall()
    assert rows == [(
        validity_id, place_id, cid, "FTRE", BROKER_ORDER_ID,
        PIVOT, INITIAL_STOP, 10, "live_at_acceptance",
    )]


@pytest.mark.parametrize("kind_over", [
    {"intent_kind": "place"},
    {"intent_kind": "validity", "validity_outcome": "rejected_by_broker",
     "actual_order_type": None, "actual_duration": None,
     "actual_limit_price": None, "actual_quantity": None,
     "actual_broker_order_id": None},
])
def test_the_minting_trigger_does_not_fire_on_any_other_shape(
        conn, kind_over: dict) -> None:
    cid = seed_fire(conn)
    place_id = insert_intent(conn, place_row(cid))
    row = validity_row(cid, place_id, key="key-other")
    row.update(kind_over)
    if row["intent_kind"] == "place":
        row = place_row(cid, idempotency_key="key-other")
    insert_intent(conn, row)
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_mandate_links").fetchone()[0] == 0


def test_a_junk_fire_mints_NULL_frozen_values_and_does_not_block_the_ledger(
        conn) -> None:
    """The trigger MUST be incapable of raising.

    ``candidates.pivot`` / ``initial_stop`` are unconstrained REAL columns, so a
    junk fire is representable, and the link table's own ``> 0`` CHECKs would
    otherwise ABORT the operator's acceptance record.  Cohort bookkeeping must
    never block a money-bearing operation (0036:26-38); admission later refuses
    ``frozen_value_unavailable``.
    """
    cid = seed_fire(conn, pivot=-1.0, initial_stop=None)
    accept_order(conn, cid)
    assert conn.execute(
        "SELECT frozen_pivot, frozen_invalidation FROM "
        "latch_order_mandate_links").fetchone() == (None, None)


def test_the_backfill_derives_its_tier_and_produces_pre_barrier_rows(
        tmp_path: Path) -> None:
    """The expected ONE row at ``pre_barrier_reconstructed`` is an OUTCOME of
    the derivation, never an input to it.

    The epoch is seeded from ``MAX(candidates.id)`` moments before the backfill
    runs, so EVERY candidate that exists is at-or-below the boundary and no
    backfilled link can be post-barrier.  An implementation that hard-coded
    ``'live_at_acceptance'`` -- the TWELFTH mirror site of the freeze-tier
    family, and the one an eleven-site value-set sweep could not find -- fails
    here.
    """
    c = _v36(tmp_path)
    try:
        cid = seed_fire(c)
        accept_order(c, cid)
        c.commit()
        run_migrations(c, target_version=37, backup_dir=tmp_path / "bak")
        rows = c.execute(
            "SELECT candidate_id, broker_order_id, freeze_tier, frozen_pivot "
            "FROM latch_order_mandate_links").fetchall()
        assert rows == [(cid, BROKER_ORDER_ID, "pre_barrier_reconstructed", PIVOT)]
    finally:
        c.close()


def test_the_link_table_is_append_only(conn) -> None:
    cid = seed_fire(conn)
    accept_order(conn, cid)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE latch_order_mandate_links SET ticker = 'X'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM latch_order_mandate_links")


def test_one_link_per_acceptance_is_structural(conn) -> None:
    """UNIQUE(validity_intent_id).  There is deliberately NO UNIQUE on
    ``broker_order_id`` -- a duplicate there would abort the LEDGER write, and
    cardinality is the READER's COUNT."""
    unique = {
        r[1]: r[2] for r in conn.execute(
            "PRAGMA index_list(latch_order_mandate_links)")
    }
    uniq_cols = set()
    for name, is_unique in unique.items():
        if is_unique:
            uniq_cols.update(
                r[2] for r in conn.execute(f"PRAGMA index_info('{name}')"))
    assert "validity_intent_id" in uniq_cols
    assert "broker_order_id" not in uniq_cols


# ---------------------------------------------------------------------------
# The provenance_corrections trigger replacement
# ---------------------------------------------------------------------------
def test_no_statement_sits_between_a_drop_and_its_create_case_44() -> None:
    """Case 44 -- CHARC CONDITION (a).

    A PROPERTY OF THE FILE, which is why this is one of the two text tests in
    the module.  ``executescript`` issues an implicit COMMIT and runs in
    autocommit, so without the explicit transaction -- and without the CREATE
    immediately following its DROP -- ``provenance_corrections`` would sit with
    NO append-only guard at all for the duration of a window (gotcha #9).
    """
    text = MIGRATION.read_text(encoding="utf-8")
    stripped = "\n".join(
        line for line in text.split("\n")
        if line.strip() and not line.strip().startswith("--")
    )
    assert stripped.count("BEGIN;") >= 1
    assert stripped.rstrip().endswith("COMMIT;")
    for name in ("trg_provenance_corrections_citation_graph",
                 "trg_provenance_corrections_append_only_update"):
        drop = f"DROP TRIGGER {name};"
        create = f"CREATE TRIGGER {name}"
        assert drop in stripped, name
        after = stripped.split(drop, 1)[1]
        between = after.split(create, 1)[0]
        assert between.strip() == "", (
            f"a statement sits between DROP and CREATE for {name}: {between!r}")
        # and both are INSIDE the one transaction
        assert stripped.index("BEGIN;") < stripped.index(drop)
        assert stripped.index(create) < stripped.rindex("COMMIT;")


def _old_append_only_columns() -> set[str]:
    """The columns the PRE-0037 trigger protected, PARSED OUT OF 0036.

    Computed against the OLD guarantee rather than re-typed, because a
    hand-maintained roster fails the same way as the count it replaced.
    """
    text = (MIGRATION.parent / "0036_provenance_corrections.sql").read_text(
        encoding="utf-8")
    body = text.split("CREATE TRIGGER trg_provenance_corrections_append_only_update", 1)[1]
    body = body.split("BEGIN", 1)[0]
    return set(re.findall(r"NEW\.(\w+) IS(?: NOT)? OLD\.\1", body)) | set(
        re.findall(r"NEW\.(\w+) = OLD\.\1", body))


def test_the_old_append_only_guarantee_survives_the_replacement_case_43(
        conn) -> None:
    """Case 43 -- CHARC CONDITION (b), COMPUTED AGAINST THE OLD GUARANTEE.

    For EVERY column the PRE-0037 trigger protected, a barred write must STILL
    fail post-migration.  A test written only against the six new columns passes
    a replacement that silently dropped protection on an old one -- which is the
    discriminating half and the whole reason the roster is parsed out of 0036
    rather than re-typed here.

    THE UPDATES ARE REAL.  Asserting that a column NAME appears in the trigger
    text passes against an ``=`` comparison on a nullable column and proves
    nothing, because ``NULL = NULL`` is NULL and a NULL ``WHEN`` guard does not
    fire the trigger.
    """
    old_cols = _old_append_only_columns()
    assert len(old_cols) >= 25, sorted(old_cols)
    ids = _seed_correction(conn)
    protected = old_cols - {"entry_fill_id", "risk_policy_id_at_correction"}
    info = {r[1]: r[2] for r in conn.execute(
        "PRAGMA table_info(provenance_corrections)")}
    for col in sorted(protected):
        value = 0 if info.get(col, "TEXT").upper() == "INTEGER" else "x"
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            conn.execute(
                f"UPDATE provenance_corrections SET {col} = ? "
                f"WHERE provenance_correction_id = ?", (value, ids["row_id"]))


def test_the_six_new_columns_are_append_only_in_all_three_directions(
        conn) -> None:
    """Driven off ``PRAGMA table_info`` rather than a re-typed roster.

    THREE directions per column -- NULL -> value, value -> NULL and
    value -> different-value -- because ``NEW.col = OLD.col`` on a NULLABLE
    column evaluates to NULL when both sides are NULL, the ``WHEN`` guard is
    then NULL, and the trigger DOES NOT FIRE.  An ``=`` implementation would
    silently permit a rewrite of exactly the columns that carry the latch
    citation.
    """
    ids = _seed_correction(conn)
    new_cols = [
        "admission_tier", "cited_latch_link_id",
        "cited_latch_validity_intent_id", "cited_latch_place_intent_id",
        "cited_latch_broker_order_id", "cited_latch_probe_json",
    ]
    present = [r[1] for r in conn.execute(
        "PRAGMA table_info(provenance_corrections)")]
    assert set(new_cols) <= set(present)
    for col in new_cols:
        for value in (None, 1, "other"):
            with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
                conn.execute(
                    f"UPDATE provenance_corrections SET {col} = ? "
                    f"WHERE provenance_correction_id = ?",
                    (value, ids["row_id"]))


def test_an_existing_correction_row_survives_the_migration_as_last_word(
        tmp_path: Path) -> None:
    """The CADL row's tier is TRUE of it: it was admitted by the last-word
    guard, which is what ``last_word`` names.

    THE ROW MUST PRE-DATE THE MIGRATION or the test proves the DEFAULT on a new
    row rather than the BACKFILL of an old one -- and the production repo
    cannot write it at v36, because its column tuple is at HEAD (V1 has no
    version branch and should not grow one: #11's remedy here is to migrate the
    FIXTURE, not to branch the writer).  So the row is derived by the real
    service on a v37 database and REPLAYED into the v36 one through its OWN
    column set, which is what a genuinely pre-existing row looks like.
    """
    head = ensure_schema(tmp_path / "head.db")
    try:
        head_ids = _seed_correction(head)
        cols_v37 = [r[1] for r in head.execute(
            "PRAGMA table_info(provenance_corrections)")]
        values = dict(zip(cols_v37, head.execute(
            "SELECT * FROM provenance_corrections "
            "WHERE provenance_correction_id = ?",
            (head_ids["row_id"],)).fetchone(), strict=True))
    finally:
        head.close()

    old = _v36(tmp_path)
    try:
        ids = build_cadl_case(old)
        assert ids["trade_id"] == head_ids["trade_id"], (
            "the two fixtures must produce identical ids or the replayed row "
            "would cite rows that do not exist in the v36 database")
        cols_v36 = [r[1] for r in old.execute(
            "PRAGMA table_info(provenance_corrections)")]
        assert set(cols_v36) < set(cols_v37), "v36 must be the NARROWER shape"
        payload = {c: values[c] for c in cols_v36}
        old.execute(
            f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
            f"VALUES ({', '.join('?' * len(payload))})",
            tuple(payload.values()))
        old.commit()

        run_migrations(old, target_version=37, backup_dir=tmp_path / "bak")

        row = old.execute(
            "SELECT admission_tier, cited_latch_link_id, "
            "cited_latch_validity_intent_id, cited_latch_place_intent_id, "
            "cited_latch_broker_order_id, cited_latch_probe_json "
            "FROM provenance_corrections").fetchone()
        assert row == ("last_word", None, None, None, None, None)
    finally:
        old.close()


def test_a_latch_ladder_row_with_no_citation_is_refused(conn) -> None:
    """The paired-NULL rule: the tier a row claims and the evidence it carries
    may not disagree.

    THE PLANTED ROW TARGETS A SECOND TRADE, and that is not cosmetic.  Copying
    the seeded row onto its OWN trade_id collides with
    ``ux_provenance_corrections_trade``, so the statement is refusable on two
    independent grounds and the test would be asserting whichever BEFORE INSERT
    trigger SQLite happened to fire first -- an order SQLite documents as
    UNDEFINED.  Since ``trg_pc_no_replace`` landed it fires first in practice,
    which is how this surfaced.  Retargeting the row makes it otherwise
    insertable, so the citation-graph refusal is the ONLY one available and the
    assertion means what it says.
    """
    ids = _seed_correction(conn)
    other = build_cadl_case(conn, ticker="ZZTOP")
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_correction(
            conn, ids, admission_tier="latch_ladder",
            trade_id=other["trade_id"], entry_fill_id=other["fill_id"])


# ---------------------------------------------------------------------------
# The mirrors (#11)
# ---------------------------------------------------------------------------
def _sql_enum_values(conn: sqlite3.Connection, table: str, column: str) -> set[str]:
    """Read the CHECK enum out of the LIVE schema, never out of the file."""
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,)).fetchone()[0]
    pattern = re.compile(
        rf"CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
    match = pattern.search(sql)
    assert match, f"no CHECK enum found for {table}.{column} in the live schema"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_the_sql_and_python_freeze_tier_enums_agree(conn) -> None:
    """THE DRIFT TEST IS THE ONE MIRROR THAT DEFENDS THE SET (#11, amended).

    Once a value crosses SQL, a Python constant, a TRIGGER body, a JSON envelope
    and prose, the canonical triple UNDERSTATES the mirror family -- the
    measured count on this arc was ELEVEN sites, then TWELVE.  A value-set sweep
    does not find a hard-coded single member.  This comparator does not depend
    on anyone choosing the right grep.
    """
    assert _sql_enum_values(
        conn, "latch_order_mandate_links", "freeze_tier") == LATCH_FREEZE_TIERS


def test_the_sql_and_python_admission_tier_enums_agree(conn) -> None:
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' "
        "AND name = 'provenance_corrections'").fetchone()[0]
    found = set(re.findall(
        r"admission_tier IN \(([^)]*)\)", sql))
    assert found, "no admission_tier CHECK enum in the live schema"
    values = set(re.findall(r"'([^']+)'", found.pop()))
    assert values == PROVENANCE_ADMISSION_TIERS


def test_the_migrations_authorization_closure_list_matches_the_roster() -> None:
    """22A-R9-07: the ``$.authorization`` schema is WRITTEN OUT in Python and
    the migration's closure list DERIVES from it.

    The path list in the migration is the MACHINE-READABLE source of truth (the
    0033 ``LATCH_BROKER_SNAPSHOT_KEYS`` precedent), and this test asserts exact
    SET EQUALITY with ``AUTHORIZATION_CLAUSES`` -- so neither is a
    hand-maintained copy of the other and a rung added to one without the other
    fails here rather than in production.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    marker = "json_remove(json_extract(NEW.cited_latch_probe_json, '$.authorization'),"
    assert marker in text
    after = text.split(marker, 1)[1]
    closure = after.split("= '{}'", 1)[0]
    keys = set(re.findall(r"'\$\.(\w+)'", closure))
    assert keys == set(AUTHORIZATION_KEYS), (
        f"migration closure list and AUTHORIZATION_CLAUSES disagree: "
        f"only in SQL {sorted(keys - set(AUTHORIZATION_KEYS))}, "
        f"only in Python {sorted(set(AUTHORIZATION_KEYS) - keys)}"
    )
    assert len(keys) == 16, sorted(keys)


def test_the_migration_performs_no_rounding_in_a_price_position() -> None:
    """THE SINGLE ROUNDING AUTHORITY, made mechanical.

    Python rounds half-to-EVEN and SQLite half-AWAY-from-zero; they disagree on
    the eighth-dollar values, and 24 live ``candidates`` rows sit on that
    family.  Without this gate the rule is a paragraph, and the single most
    likely way to lose it is a later reader "repairing" an identity check into a
    rounded one.

    THE SCAN IS CASE- AND WHITESPACE-NORMALIZED (inherited finding 22A-R9-05c):
    a literal ``round(`` match misses ``ROUND(``, ``Round(``, ``round (`` and a
    newline-split call, so the gate is applied to the collapsed lower-cased
    text.  Comments are stripped first -- the migration DISCUSSES rounding at
    length, and a gate that fires on its own rationale would be re-argued away.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.split("\n") if not line.strip().startswith("--"))
    normalized = re.sub(r"\s+", "", code).lower()
    assert "round(" not in normalized, (
        "migration 0037 performs a rounding: SQL stores and binds, it never "
        "rounds and never compares two independently-sourced prices"
    )


# ---------------------------------------------------------------------------
# Shared correction-row seeding
# ---------------------------------------------------------------------------
def _seed_correction(conn: sqlite3.Connection) -> dict:
    """A real Demand-C correction row, written through the PRODUCTION service.

    Derived from the real emitter rather than hand-written, so the append-only
    tests operate on the shape production actually stores.
    """
    from swing.trades.cohort_provenance_correction import correct_cohort_provenance
    from tests.trades._cohort_provenance_fixtures import (
    build_cadl_case,
    set_fill_envelope,
)

    ids = build_cadl_case(conn)
    if conn.in_transaction:
        conn.commit()
    correct_cohort_provenance(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason="22-A task 2 append-only fixture",
    )
    ids["row_id"] = conn.execute(
        "SELECT provenance_correction_id FROM provenance_corrections "
        "WHERE trade_id = ?", (ids["trade_id"],)).fetchone()[0]
    return ids


def _insert_correction(conn: sqlite3.Connection, ids: dict, **over) -> None:
    """A RAW INSERT of a SECOND correction row, copying the first and applying
    ``over`` -- the raw-INSERT technique, because a dataclass-only design would
    accept every incoherent shape a trigger has to reject."""
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(provenance_corrections)")]
    values = list(conn.execute(
        "SELECT * FROM provenance_corrections WHERE provenance_correction_id = ?",
        (ids["row_id"],)).fetchone())
    payload = dict(zip(cols, values, strict=True))
    payload["provenance_correction_id"] = None
    payload.update(over)
    conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
        f"VALUES ({', '.join('?' * len(payload))})",
        tuple(payload.values()),
    )


# ---------------------------------------------------------------------------
# THE CITATION TRIGGER IS SATISFIABLE
#
# NO CASE ID: the formal evidence-contract cases (34*, 39*, 48*, 49*) belong to
# task 11.  This is the property that must hold BEFORE any of them can be
# written, and it is the one a refusal-only test set cannot establish -- the
# plan's own history has an instance where the trigger required the probe
# session to equal the fill session while the service could only supply the
# derivation's PRIOR session, so a truthful correction row could not have been
# written at all.  A trigger nothing can pass looks exactly like a strict one
# until someone tries.
# ---------------------------------------------------------------------------
def seed_latch_ladder_citation(conn: sqlite3.Connection) -> dict:
    """A TRUTHFUL ``latch_ladder`` correction payload, from real emitters.

    Shared with task 11, which mutates ONE field at a time out of it: an
    omission or a fidelity case is only discriminating if the row it starts
    from is genuinely accepted.
    """
    from tests._latch_link_fixtures_22a import (
        insert_intent as _insert_intent,
    )
    from tests._latch_link_fixtures_22a import (
        place_row as _place_row,
    )
    from tests._latch_link_fixtures_22a import (
        validity_row as _validity_row,
    )
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    ids = _seed_correction(conn)
    run_id, candidate_id = ids["evaluation_run_id"], ids["candidate_id"]
    session = conn.execute(
        "SELECT action_session_date FROM evaluation_runs WHERE id = ?",
        (run_id,)).fetchone()[0]
    place = _place_row(candidate_id, run_id=run_id)
    place.update(ticker=CADL_TICKER, detection_date=session,
                 action_session_date=session, recorded_ts="2026-08-11T12:00:00")
    place_id = _insert_intent(conn, place)
    # THE ACCEPTED QUANTITY MUST COVER THE FILL, or the baseline is a state the
    # SERVICE could never produce: `assert_fill_consistent_with_order` refuses
    # `quantity_exceeds_order` when the executed shares exceed the accepted
    # order's own quantity, and the citation trigger now proves the same
    # inequality (Codex 22A-R5-01). The 0033 fixture's default is 10 while
    # CADL's entry fill is 19, so the value is READ from the fill rather than
    # typed -- a fixture that quietly disagrees with the emitter is this
    # project's most-repeated test defect.
    accepted_quantity = int(conn.execute(
        "SELECT quantity FROM fills WHERE trade_id = ? AND action = 'entry' "
        "ORDER BY fill_id LIMIT 1", (ids["trade_id"],)).fetchone()[0])
    validity = _validity_row(candidate_id, place_id, run_id=run_id)
    validity.update(ticker=CADL_TICKER, detection_date=session,
                    action_session_date=session,
                    recorded_ts="2026-08-11T12:05:00",
                    actual_quantity=accepted_quantity)
    validity_id = _insert_intent(conn, validity)
    conn.commit()

    def _row(table: str, where: str, args: tuple) -> dict:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        return dict(zip(cols, conn.execute(
            f"SELECT * FROM {table} WHERE {where}", args).fetchone(),
            strict=True))

    link = _row("latch_order_mandate_links", "1 = 1", ())
    row = _row("provenance_corrections", "provenance_correction_id = ?",
               (ids["row_id"],))
    fill_id = row["entry_fill_id_at_correction"]

    # The fill must LOOK like the broker fill the citation claims: the five
    # envelope guards are SQL-BOUND to it at CORRECTION time, because by then
    # the operator-submitted values are PERSISTED on the fill this row already
    # anchors on (inherited finding 22A-R9-06).
    conn.execute("UPDATE fills SET fill_origin = 'schwab_auto' "
                 " WHERE fill_id = ?", (fill_id,))
    # THE READING IS WRITTEN WITH THE DOCUMENT, as production writes them
    # (PERSIST-CANONICAL): migration 0037 compares the AUTHORITY'S stored
    # reading of the envelope, never the envelope.
    set_fill_envelope(conn, fill_id, json.dumps(
        {"schwab_order_id": link["broker_order_id"],
         "schwab_instrument_symbol": CADL_TICKER}))
    conn.commit()
    # THE FILL SNAPSHOT IS RE-FROZEN FROM THE FILL AS IT NOW STANDS, through
    # the PRODUCTION freezer (Codex 22A-R15-01).  The correction row this
    # payload is copied from was written BEFORE the two UPDATEs above, so its
    # frozen `envelope` operand is the pre-update value -- a payload truthful
    # about every other source and STALE about this one.  The citation trigger
    # now binds the four fill-side operands to the cited fill, so a stale
    # freeze would make the baseline unacceptable and every mutation case
    # built on it undiscriminating.  `_EntryFill.snapshot()` is the production
    # emitter, not a hand-written dict.
    from swing.trades.cohort_provenance_correction import (
        resolve_authoritative_entry_fill,
    )
    row["entry_fill_snapshot_json"] = json.dumps(
        resolve_authoritative_entry_fill(conn, row["trade_id"]).snapshot(),
        sort_keys=True)
    quantity, price = conn.execute(
        "SELECT quantity, price FROM fills WHERE fill_id = ?",
        (fill_id,)).fetchone()
    pivot, initial_stop = conn.execute(
        "SELECT pivot, initial_stop FROM candidates WHERE id = ?",
        (candidate_id,)).fetchone()
    fill_session = row["entry_fill_session_date"]

    authorization = {
        "rung1_link_ticker": CADL_TICKER,
        "rung2_link_parent": place_id,
        "rung3_validity_outcome": "accepted_by_broker",
        "rung3b_latest_validity_child": validity_id,
        "rung3c_link_broker_order_id": link["broker_order_id"],
        "rung4_governing_place_intent": place_id,
        "rung5_cancel_intent_id": None,
        "rung6_consuming_trade_id": None,
        "rung7_consumption_scan_fill_ids": [fill_id],
        "rung8_competitor_link_ids": [],
        "rung9_stored_freeze_tier": link["freeze_tier"],
        "guard_fill_origin": "schwab_auto",
        "guard_envelope_symbol": CADL_TICKER,
        "guard_quantity": quantity,
        "guard_framework_price_bound": price,
        "guard_broker_limit_bound": validity["actual_limit_price"],
    }
    assert set(authorization) == set(AUTHORIZATION_KEYS), (
        "the blob builder and the roster disagree: "
        f"{sorted(set(authorization) ^ set(AUTHORIZATION_KEYS))}")
    blob = {
        "evidence_version": LATCH_PROBE_EVIDENCE_VERSION,
        "fire_candidate_id": candidate_id,
        "ticker": CADL_TICKER,
        "fill_session": fill_session,
        "horizon_session": fill_session,
        "bars_through": "2026-08-11",
        "clear_reason": None,
        "clear_session": None,
        "admission_basis": "armed",
        "criteria_lapse_forced_off": 1,
        "freeze_tier": link["freeze_tier"],
        "archive_status": "ok",
        "frozen_invalidation_raw": link["frozen_invalidation"],
        "live_invalidation_raw": initial_stop,
        "frozen_pivot_raw": link["frozen_pivot"],
        "live_pivot_raw": pivot,
        "invalidation_equal_at_dp": 1,
        "pivot_equal_at_dp": 1,
        "compare_dp": 2,
        "coverage": {"expected_sessions": ["2026-08-11"],
                     "observed_sessions": ["2026-08-11"],
                     "missing_sessions": []},
        "probe_guards": {
            "fill_session_is_session": {"input": fill_session,
                                        "verdict": "pass"},
            "fire_membership": {"input": 1, "verdict": "pass"},
            "decision_ordering": {
                "input": [[place_id, "2026-08-11T12:00:00"]],
                "verdict": "pass"},
        },
        "authorization": {
            key: {"input": value, "verdict": "pass"}
            for key, value in authorization.items()
        },
    }
    assert set(blob) == set(PROBE_EVIDENCE_KEYS), (
        "the blob builder and the evidence roster disagree: "
        f"{sorted(set(blob) ^ set(PROBE_EVIDENCE_KEYS))}")
    row["provenance_correction_id"] = None
    row.update(
        admission_tier="latch_ladder",
        cited_latch_link_id=link["link_id"],
        cited_latch_validity_intent_id=validity_id,
        cited_latch_place_intent_id=place_id,
        cited_latch_broker_order_id=link["broker_order_id"],
        cited_latch_probe_json=json.dumps(blob),
    )
    # Clear the last_word row so the one-per-trade UNIQUE index does not fire.
    conn.execute("DROP TRIGGER trg_provenance_corrections_append_only_delete")
    conn.execute("DELETE FROM provenance_corrections")
    conn.commit()
    return row


def _insert_payload(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
        f"VALUES ({', '.join('?' * len(payload))})", tuple(payload.values()))


def test_a_truthful_latch_ladder_citation_is_accepted(conn) -> None:
    """THE TRIGGER IS SATISFIABLE.

    Every SQL-bound clause is satisfied from its real source -- the link's own
    columns, both intents, the cited candidate, and the fill the correction
    already anchors on -- and the row inserts.  Without this, a refusal-only
    test set goes green against a trigger no truthful row can pass.
    """
    payload = seed_latch_ladder_citation(conn)
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier, cited_latch_link_id FROM provenance_corrections"
    ).fetchone() == ("latch_ladder", payload["cited_latch_link_id"])


def test_a_fabricated_input_on_a_sql_bound_rung_is_rejected(conn) -> None:
    """PRESENCE IS NOT FIDELITY.

    The same truthful row with ONE bound entry's ``input`` mutated away from
    its source and every ``verdict`` still ``'pass'``.  A presence-only trigger
    -- sixteen keys, sixteen passes -- ACCEPTS it, and an admission whose
    recorded inputs are invented is indistinguishable at audit from an
    unchecked one.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    blob["authorization"]["rung3c_link_broker_order_id"]["input"] = "9999999999"
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_payload(conn, payload)


def test_a_missing_authorization_entry_is_rejected_not_read_as_a_pass(
        conn) -> None:
    """AND THIS IS THE CLAUSE THE COALESCE WRAPPER EXISTS FOR.

    A missing JSON key makes ``json_type`` NULL, ``NULL = 'text'`` NULL, and a
    NULL ``WHEN`` clause DOES NOT FIRE the trigger -- so without
    ``COALESCE(..., 0)`` around the latch block this row is silently ACCEPTED.
    Measured on 3.50.4 before the wrapper was written.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    del blob["authorization"]["rung7_consumption_scan_fill_ids"]
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_payload(conn, payload)


# ---------------------------------------------------------------------------
# 22A-R2-04 -- THE PROBE'S OWN GUARDS GET VERDICT SLOTS, AND THE KEY-SET CHECK
# STOPS BEING CIRCULAR.
#
# The predecessor's key-set test derived its expectation FROM migration 0037,
# so an implementation and a migration that omitted the SAME refusal-capable
# clause both passed.  Adding keys to a closed object guarded by a circular
# test leaves the new keys equally unguarded.
#
# THE REPAIR IS THE SHAPE ALREADY USED FOR ``$.authorization``: an INDEPENDENT
# Python roster is the source, and BOTH the migration's closure list AND the
# emitted blob are compared against IT -- never against each other.  Dropping a
# key now requires editing three artifacts rather than two, and the two that
# omit it fail against the third.
#
# NO CASE ID: these are properties of the evidence contract that task 11's
# formal cases (34*/39*/48*/49*) build ON.  They are named without a
# ``_case_<slug>`` suffix so the closure walk does not read them as case
# coverage.
# ---------------------------------------------------------------------------
def test_the_migrations_probe_evidence_closure_list_matches_the_roster() -> None:
    """The TOP-LEVEL closure list is the roster, exactly.

    Direction matters: the roster is the independent third party.  A key
    dropped from the migration alone fails here; a key dropped from the emitter
    alone fails the task-6 emission test; a key dropped from both still fails
    both, which is precisely what the circular version could not do.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    marker = "json_remove(NEW.cited_latch_probe_json,"
    assert marker in text
    closure = text.split(marker, 1)[1].split("= '{}'", 1)[0]
    keys = set(re.findall(r"'\$\.(\w+)'", closure))
    assert keys == set(PROBE_EVIDENCE_KEYS), (
        f"migration closure list and PROBE_EVIDENCE_KEYS disagree: "
        f"only in SQL {sorted(keys - set(PROBE_EVIDENCE_KEYS))}, "
        f"only in Python {sorted(set(PROBE_EVIDENCE_KEYS) - keys)}"
    )


def test_the_migrations_probe_guard_closure_list_matches_the_roster() -> None:
    """``$.probe_guards`` is closed on the PROBE_GUARD_CLAUSES roster."""
    text = MIGRATION.read_text(encoding="utf-8")
    marker = "json_remove(json_extract(NEW.cited_latch_probe_json, '$.probe_guards'),"
    assert marker in text
    closure = text.split(marker, 1)[1].split("= '{}'", 1)[0]
    keys = set(re.findall(r"'\$\.(\w+)'", closure))
    assert keys == set(PROBE_GUARD_KEYS), (
        f"migration probe-guard closure and PROBE_GUARD_CLAUSES disagree: "
        f"only in SQL {sorted(keys - set(PROBE_GUARD_KEYS))}, "
        f"only in Python {sorted(set(PROBE_GUARD_KEYS) - keys)}"
    )


def test_a_truthful_probe_guard_block_is_ACCEPTED(conn) -> None:
    """THE ACCEPTED BASELINE for the three new guards.

    A refusal-only test set cannot establish that a guard can EVER accept, and
    this plan's own history contains a trigger nothing could satisfy.  Every
    variation below starts HERE and moves ONE field.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    assert set(blob["probe_guards"]) == set(PROBE_GUARD_KEYS)
    _insert_payload(conn, payload)


@pytest.mark.parametrize("guard_key", sorted(PROBE_GUARD_KEYS))
def test_an_omitted_probe_guard_entry_is_REJECTED(conn, guard_key) -> None:
    """ONE guard removed from the accepted baseline -- REJECTED.

    This is the omission direction the closure list enforces, and it is what
    makes "passed" and "never ran" distinguishable for the PROBE's own guards
    rather than only for the authorizer's rungs.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    del blob["probe_guards"][guard_key]
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_payload(conn, payload)


def test_a_fire_membership_input_other_than_one_is_REJECTED(conn) -> None:
    """Exactly ONE latch may contain the fire.  Two is not an admission."""
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    blob["probe_guards"]["fire_membership"]["input"] = 2
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_payload(conn, payload)


def test_a_fill_session_guard_input_not_bound_to_the_fill_is_REJECTED(
        conn) -> None:
    """The session the guard says it judged must BE the row's fill session."""
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    blob["probe_guards"]["fill_session_is_session"]["input"] = "2026-01-05"
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_payload(conn, payload)


@pytest.mark.parametrize("guard_key", sorted(PROBE_GUARD_KEYS))
def test_a_non_pass_probe_guard_verdict_is_REJECTED(conn, guard_key) -> None:
    """A guard that did not pass contradicts the admission it sits inside."""
    payload = seed_latch_ladder_citation(conn)
    blob = json.loads(payload["cited_latch_probe_json"])
    blob["probe_guards"][guard_key]["verdict"] = "refuse"
    payload["cited_latch_probe_json"] = json.dumps(blob)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_payload(conn, payload)


# ---------------------------------------------------------------------------
# ROUND-3 CRITICALS -- both VERIFIED BY EXECUTION before they were fixed.
# NO CASE IDS: 50a-50e are the plan's barrier-integrity cases and they cover
# the `candidates` triggers.  These are the same property on the surfaces the
# plan's roster did not name, which is why they are additions rather than
# re-labellings of an existing case.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("trigger", [
    "trg_candidates_epoch_no_update",
    "trg_candidates_epoch_no_delete",
    "trg_candidates_epoch_no_insert",
])
def test_dropping_an_EPOCH_trigger_disarms_structural_admission(
        conn, trigger) -> None:
    """22A-R3-01 -- the EPOCH's own triggers are part of the barrier.

    MEASURED BEFORE THE FIX: drop the three epoch triggers, move
    ``max_candidate_id_at_barrier``, and ``freeze_tier_for_candidate`` returns
    a DIFFERENT tier while ``barrier_installed()`` still returns True -- all
    three of rung 9's operands agreeing on a tier nothing backs.  That is a
    WRONG ACCEPTANCE, the direction that contaminates H1 invisibly.

    The reader pinned three triggers and the structural claim rests on six.
    """
    from swing.data.repos.candidates_immutability_epoch import barrier_installed

    assert barrier_installed(conn) is True
    conn.execute(f"DROP TRIGGER {trigger}")
    conn.commit()
    assert barrier_installed(conn) is False


def test_a_same_name_NOOP_epoch_trigger_does_not_satisfy_the_check(conn) -> None:
    """AND THE DISCRIMINATOR THE BODY CHECK DEMANDS.

    *A body check never exercised against a wrong body is the existence check
    wearing better clothes.*  A name-only implementation counts six and admits.
    """
    from swing.data.repos.candidates_immutability_epoch import barrier_installed

    conn.execute("DROP TRIGGER trg_candidates_epoch_no_update")
    conn.execute(
        "CREATE TRIGGER trg_candidates_epoch_no_update BEFORE UPDATE ON "
        "candidates_immutability_epoch BEGIN SELECT 1; END")
    conn.commit()
    assert barrier_installed(conn) is False


def test_the_link_table_is_closed_to_REPLACE(conn) -> None:
    """22A-R3-10 -- the arc's OWN table was fail-open to INSERT OR REPLACE.

    MEASURED BEFORE THE FIX at the DEFAULT ``recursive_triggers=0``: an
    ``INSERT OR REPLACE`` rewrote ``frozen_pivot`` 18.34 -> 999.99 with BOTH
    append-only triggers present and unfired, because REPLACE's implicit DELETE
    does not fire DELETE triggers unless the pragma is ON.  This migration
    repairs exactly that bypass for ``candidates`` and for the epoch and left
    the link table -- the durable record the whole admission proof rests on --
    open.
    """
    _assert_default_pragma(conn)
    candidate_id = seed_fire(conn)
    accept_order(conn, candidate_id)
    conn.commit()
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(latch_order_mandate_links)")]
    row = dict(zip(cols, conn.execute(
        "SELECT * FROM latch_order_mandate_links").fetchone(), strict=True))
    row["frozen_pivot"] = 999.99
    for verb in ("INSERT OR REPLACE INTO", "REPLACE INTO",
                 "INSERT OR IGNORE INTO"):
        with pytest.raises(sqlite3.IntegrityError, match="trg_loml_no_replace"):
            conn.execute(
                f"{verb} latch_order_mandate_links ({', '.join(row)}) "
                f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    assert conn.execute(
        "SELECT frozen_pivot FROM latch_order_mandate_links").fetchone()[0] \
        == PIVOT


def test_a_SECOND_link_on_a_DIFFERENT_validity_row_still_INSERTS(conn) -> None:
    """AND THE ACCEPTED BASELINE FOR THE NEW BARRIER.

    A refusal-only test set cannot establish that a guard can EVER accept, and
    a conflict-scoped barrier written one clause too wide would block the
    MINTING TRIGGER itself -- every acceptance after the first.  Two genuine
    acceptances on two fires must both mint.
    """
    first = seed_fire(conn)
    accept_order(conn, first)
    # A SECOND fire on the SAME (run, ticker) is impossible -- the
    # conflict-scoped candidates barrier refuses it -- and a second fire on
    # the same run with a different ticker breaks the identity trigger that
    # binds an intent's block to its candidate.  Both were tried; the shape
    # that exists in production is a LATER RUN re-firing the same ticker.
    second = seed_fire(conn, run_id=199)
    accept_order(conn, second, key="second-validity", place_key="second-place",
                 run_id=199, actual_broker_order_id="second-order")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_mandate_links").fetchone()[0] == 2


# ---------------------------------------------------------------------------
# THE REPLACE-BYPASS SWEEP REACHES TWO MORE TABLES (22A-R3-11 + the
# CHARC-directed latch_order_intents probe, both VERIFIED BY EXECUTION here
# before either trigger was written).
#
# NO CASE ID: neither table is a plan case.  ``provenance_corrections`` is
# Demand C's audit table of record and ``latch_order_intents`` is the ledger
# the minting trigger fires from -- 22-A's whole evidence chain rests on the
# OII validity row.  Both carry no_update + no_delete and NO no_replace, each
# with TWO conflict targets (a rowid PK and a UNIQUE), which is the same shape
# this migration already repaired for ``candidates`` and for its own link
# table.
#
# EVERY TABLE BELOW GETS BOTH DIRECTIONS.  A barrier proven only by refusals is
# not proven: a guard one clause too wide blocks the production writer, and on
# ``latch_order_intents`` the production writer's own conflict path is exactly
# what a blanket guard changes.  So each table gets an ACCEPTED baseline driven
# through its PRODUCTION writer, and the refusals are varied out of it.
# ---------------------------------------------------------------------------
def _pc_replace_payload(conn: sqlite3.Connection, row_id: int, **over):
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(provenance_corrections)")]
    vals = list(conn.execute(
        "SELECT * FROM provenance_corrections "
        "WHERE provenance_correction_id = ?", (row_id,)).fetchone())
    payload = dict(zip(cols, vals, strict=True))
    payload.update(over)
    return payload, ", ".join(payload), ", ".join("?" * len(payload))


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
@pytest.mark.parametrize("target", ["rowid_pk", "unique_trade"])
def test_a_conflicting_insert_on_provenance_corrections_aborts(
        conn, verb: str, target: str) -> None:
    """22A-R3-11, reproduced then closed.

    MEASURED before the trigger existed, on a fresh v37 fixture at the DEFAULT
    ``recursive_triggers=0``: the direct UPDATE and DELETE are both blocked by
    the 0036 append-only triggers, and ``INSERT OR REPLACE`` then rewrote
    ``correction_reason`` on the live-shaped row with BOTH of those triggers
    present and UNFIRED.  REPLACE's implicit DELETE does not fire a DELETE
    trigger unless ``PRAGMA recursive_triggers`` is ON, and this repo never
    turns it on.

    BOTH conflict targets are exercised, because guarding one leaves the other
    as a live REPLACE path -- the same half-swept shape as the bypass itself.
    """
    _assert_default_pragma(conn)
    ids = _seed_correction(conn)
    row_id = ids["row_id"]
    before = conn.execute(
        "SELECT provenance_correction_id, correction_reason "
        "FROM provenance_corrections").fetchall()
    over = {"correction_reason": "REWRITTEN BY REPLACE"}
    if target == "unique_trade":
        # collide ONLY on ux_provenance_corrections_trade, with the PK left to
        # SQLite -- the shape that MOVES the audit row's own id
        over["provenance_correction_id"] = None
    payload, names, holes = _pc_replace_payload(conn, row_id, **over)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute(
            f"{verb} INTO provenance_corrections ({names}) VALUES ({holes})",
            tuple(payload.values()))
    assert "trg_pc_no_replace" in str(exc.value)
    assert conn.execute(
        "SELECT provenance_correction_id, correction_reason "
        "FROM provenance_corrections").fetchall() == before


def test_the_production_correction_writer_still_appends(conn) -> None:
    """THE ACCEPTED BASELINE, through the PRODUCTION service.

    ``insert_provenance_correction`` issues a PLAIN INSERT and
    ``correct_cohort_provenance`` refuses a second correction per trade at its
    own ladder, so the trigger must never see a production conflict.  This is
    the direction a refusal-only test set cannot establish, and it runs through
    the real writer rather than a synthetic statement because the property
    under test is that PRODUCTION still writes.
    """
    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )

    first = _seed_correction(conn)
    second = build_cadl_case(conn, ticker="ZZTOP")
    if conn.in_transaction:
        conn.commit()
    correct_cohort_provenance(
        conn,
        trade_id=second["trade_id"],
        cited_candidate_id=second["candidate_id"],
        cited_recommendation_id=second["daily_recommendation_id"],
        reason="the ordinary append, on a DIFFERENT trade",
    )
    trades = {r[0] for r in conn.execute(
        "SELECT trade_id FROM provenance_corrections")}
    assert trades == {first["trade_id"], second["trade_id"]}


@pytest.mark.parametrize(
    "verb,target",
    [("INSERT OR REPLACE", "rowid_pk"),
     ("REPLACE", "rowid_pk"),
     ("REPLACE", "unique_key")],
)
def test_a_conflicting_insert_on_latch_order_intents_aborts(
        conn, verb: str, target: str) -> None:
    """The CHARC-directed probe, reproduced then closed.

    MEASURED before the trigger existed, on a fresh v37 fixture at the DEFAULT
    pragma: a ``place`` intent with no minted link is fully REPLACE-exposed on
    BOTH targets -- ``framework_limit_price`` rewritten 18.89 -> 999.99 through
    the rowid PK, and a bare REPLACE colliding on ``UNIQUE(idempotency_key)``
    additionally MOVED ``intent_id`` 1 -> 2.  ``trg_loi_no_update`` and
    ``trg_loi_no_delete`` were present and unfired for every one.

    THE FIXTURE IS THE UNLINKED SHAPE DELIBERATELY.  A row a link CITES is
    blocked by ``latch_order_mandate_links``' ON DELETE RESTRICT FK -- the
    INCIDENTAL protection this migration's own header warns about at
    ``candidates``: it covers the post-acceptance population and leaves the
    pre-acceptance one exposed.  Three of the five live intent rows are
    unlinked ``place`` rows.  A test blocked by that FK proves nothing about
    THIS guard, so the fixture asserts the link count is zero first.
    """
    _assert_default_pragma(conn)
    cid = seed_fire(conn)
    pid = insert_intent(conn, place_row(cid))
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_mandate_links").fetchone()[0] == 0
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(latch_order_intents)")]
    vals = list(conn.execute(
        "SELECT * FROM latch_order_intents WHERE intent_id = ?", (pid,)
    ).fetchone())
    payload = dict(zip(cols, vals, strict=True))
    payload["framework_limit_price"] = 999.99
    if target == "unique_key":
        payload["intent_id"] = None
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute(
            f"{verb} INTO latch_order_intents ({', '.join(payload)}) "
            f"VALUES ({', '.join('?' * len(payload))})",
            tuple(payload.values()))
    assert "trg_loi_no_replace" in str(exc.value)
    assert conn.execute(
        "SELECT intent_id, framework_limit_price FROM latch_order_intents"
    ).fetchall() == [(pid, 18.89)]


def test_the_production_intent_writer_still_appends_and_still_replays(
        conn) -> None:
    """THE ACCEPTED BASELINE, through ``record_intent`` itself.

    TWO properties, and the second is what makes the blanket guard safe on this
    table.  ``record_intent``'s ladder is SELECT-first: a REPLAY is answered by
    step 1 and never reaches the INSERT, so the guard never sees it.  Without
    that, a conflict-scoped trigger here would be exactly the "one clause too
    wide" failure -- on this table the append path IS the production path.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import record_intent

    cid = seed_fire(conn)
    intent = LatchOrderIntent(intent_id=None, **place_row(cid))
    first = record_intent(conn, intent=intent)
    assert first.intent_id is not None
    replayed = record_intent(conn, intent=intent)
    assert replayed.intent_id == first.intent_id       # step 1, not the guard
    second = record_intent(conn, intent=LatchOrderIntent(
        intent_id=None, **place_row(cid, idempotency_key="key-place-2")))
    assert second.intent_id != first.intent_id         # the ordinary append
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_intents").fetchone()[0] == 2


@pytest.mark.parametrize(
    "trigger", ["trg_pc_no_replace", "trg_loi_no_replace"])
def test_the_two_new_barrier_messages_are_legible(conn, trigger: str) -> None:
    """CHARC's CONDITION 2, asserted as CONTENT and never as a byte-string.

    A byte-comparison against a pinned literal passes on a message that names
    nothing, which is the failure mode legibility exists to prevent.
    """
    row = conn.execute(
        "SELECT sql, tbl_name FROM sqlite_master "
        "WHERE type = 'trigger' AND name = ?", (trigger,)).fetchone()
    assert row is not None, f"{trigger} is not installed"
    body, tbl = row
    assert trigger in body, "the message must name the GUARD"
    assert "22-A" in body, "the message must name the ARC"
    assert "reversibility header" in body, "the message must name the RECOVERY"
    assert "INSERT OR REPLACE" in body, "the message must name what it refuses"
    assert tbl == {
        "trg_pc_no_replace": "provenance_corrections",
        "trg_loi_no_replace": "latch_order_intents",
    }[trigger]


def test_the_lost_race_no_op_survives_the_intents_barrier(conn) -> None:
    """THE COMPOSITION, and it is the property the barrier's design rests on.

    ``record_intent``'s step 1 SELECT answers an ordinary replay, so the test
    above proves only that the guard is not reached on the COMMON path.  The
    contract ``record_intent`` actually pins is the LOST RACE -- both requests
    missing step 1 -- and that path DOES reach the INSERT.  MEASURED before the
    companion change: under a conflict-scoped ``BEFORE INSERT`` barrier the
    bare ``ON CONFLICT(idempotency_key) DO NOTHING`` ABORTS, because a BEFORE
    INSERT trigger fires before conflict resolution and cannot see which
    resolution algorithm the statement carries.

    The race is simulated the same way the repo's own test simulates it -- by
    making the step-1 read miss exactly once -- rather than by hand-writing the
    statement, because the property under test is that the PRODUCTION writer
    survives the barrier, and a synthetic statement would not see a divergence
    in how the real writer spells it.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos import latch_order_intents as repo

    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'trg_loi_no_replace'").fetchone()[0] == 1
    cid = seed_fire(conn)
    intent = LatchOrderIntent(intent_id=None, **place_row(cid))
    winner = repo.record_intent(conn, intent=intent)

    calls = {"n": 0}
    real = repo.get_intent_by_key

    def _miss_once(conn_, *, idempotency_key):
        calls["n"] += 1
        if calls["n"] == 1:
            return None                     # pretend step 1 missed
        return real(conn_, idempotency_key=idempotency_key)

    repo.get_intent_by_key = _miss_once
    try:
        loser = repo.record_intent(conn, intent=intent)
    finally:
        repo.get_intent_by_key = real
    assert loser.intent_id == winner.intent_id
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_intents").fetchone()[0] == 1


# ===========================================================================
# THE `-1` PRIMARY-KEY CONTRACT (CHARC-ruled 2026-08-26, on 22A-R8-02)
#
# 22A-R8-02 measured that an OMITTED `INTEGER PRIMARY KEY` presents as `-1` in
# a `BEFORE INSERT` trigger, not NULL, and its `> 0` narrowing was reverted
# because it failed 56 tests at the end of a dispatch.  The measurement was
# right and the revert was right; the ruling supplies the encoding.
#
# THE CONTRACT, and the discriminating set IS the ruling -- an encoding that
# passes all three directions is correct whatever its spelling:
#   1. an ordinary append SUCCEEDS
#   2. a conflicting REPLACE ABORTS
#   3. an explicit conflicting id ABORTS
#
# Plus the two halves the ruling attaches: a NEW table additionally carries
# `CHECK (pk > 0)`, so a negative id can never exist and the sentinel is
# unambiguous forever; an EXISTING table -- where a CHECK would mean a table
# rebuild this convention forbids -- verifies no-negative-ids and DECLARES the
# residual.
# ===========================================================================
_NO_REPLACE_PK = {
    "trg_candidates_no_replace": ("candidates", "id"),
    "trg_loml_no_replace": ("latch_order_mandate_links", "link_id"),
    "trg_loi_no_replace": ("latch_order_intents", "intent_id"),
    "trg_pc_no_replace": ("provenance_corrections", "provenance_correction_id"),
    # THE FIFTH MEMBER, ADDED BY THE CLOSURE CHECK BELOW (self-sweep SS-12).
    # `fill_envelope_identity` shipped with a no-REPLACE barrier in the
    # persist-canonical reshape and this roster did not grow with it, so the
    # `-1` idiom and the three-direction set were never asserted on the one
    # table where they had NEVER been checked at all.
    "trg_fei_no_replace": ("fill_envelope_identity", "identity_id"),
}

# NEW tables additionally carry `CHECK (pk > 0)`; an EXISTING table cannot
# without a rebuild.  Kept as data so the closure check below can hold every
# barrier to the half of the ruling that applies to it.
_NEW_TABLES_WITH_PK_CHECK = {
    "latch_order_mandate_links": "link_id",
    "fill_envelope_identity": "identity_id",
}


def test_the_no_replace_roster_is_CLOSED_over_the_installed_barriers(
        conn) -> None:
    """THE ROSTER IS NOT THE FIX; THE CLOSURE CHECK IS (self-sweep SS-12).

    A hand-maintained roster is the same instrument as the count it replaced
    and it fails the same way -- this one shipped one member short the moment a
    fifth barrier landed, and every parametrized case above went on passing
    because a roster cannot report what is missing from it.  So the roster is
    held against what the SCHEMA actually installs: every trigger whose name
    ends `_no_replace` must be a member, and every member must be installed.
    """
    installed = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            "  AND name LIKE '%_no_replace'")
    }
    assert installed == set(_NO_REPLACE_PK), (
        f"only in the schema: {sorted(installed - set(_NO_REPLACE_PK))}; "
        f"only in the roster: {sorted(set(_NO_REPLACE_PK) - installed)}")


@pytest.mark.parametrize("table", sorted(_NEW_TABLES_WITH_PK_CHECK))
def test_every_new_table_carries_the_pk_positivity_CHECK(
        conn, table: str) -> None:
    """The half of the `-1` ruling a NEW table can hold, asserted on ALL of
    them rather than on the one that happened to be remembered."""
    pk = _NEW_TABLES_WITH_PK_CHECK[table]
    ddl = " ".join(conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,)).fetchone()[0].split())
    assert f"CHECK ({pk} > 0)" in ddl, (
        f"{table} is a NEW table and does not carry CHECK ({pk} > 0), so its "
        f"no-REPLACE barrier's `-1` sentinel can collide with a real row")


def test_an_omitted_integer_primary_key_presents_as_minus_one() -> None:
    """THE PREMISE, MEASURED HERE, because the whole idiom rests on it.

    Reproduced independently rather than inherited: an omitted PK AND an
    explicit `NULL` both arrive as `-1`, and `NEW.<pk> IS NULL` is FALSE for
    both -- so the `IS NOT NULL` form NEVER FIRES and is dead text.  It also
    shows the live hazard: with a row at id `-1` present, the old idiom aborts
    an ORDINARY append.
    """
    probe = sqlite3.connect(":memory:")
    try:
        probe.executescript(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT);"
            "CREATE TABLE seen (raw TEXT, is_null INT, ne_minus_one INT);"
            "CREATE TRIGGER trg BEFORE INSERT ON t BEGIN"
            "  INSERT INTO seen VALUES (CAST(NEW.id AS TEXT),"
            "                           NEW.id IS NULL, NEW.id != -1);"
            "END;")
        probe.execute("INSERT INTO t (v) VALUES ('omitted')")
        probe.execute("INSERT INTO t (id, v) VALUES (NULL, 'explicit null')")
        probe.execute("INSERT INTO t (id, v) VALUES (7, 'explicit')")
        assert probe.execute("SELECT * FROM seen").fetchall() == [
            ("-1", 0, 0), ("-1", 0, 0), ("7", 0, 1)]

        hazard = sqlite3.connect(":memory:")
        hazard.executescript(
            "CREATE TABLE u (id INTEGER PRIMARY KEY, v TEXT);"
            "CREATE TRIGGER u_old BEFORE INSERT ON u"
            " WHEN EXISTS (SELECT 1 FROM u"
            "               WHERE (NEW.id IS NOT NULL AND id = NEW.id))"
            " BEGIN SELECT RAISE(ABORT, 'the retired idiom fired'); END;")
        hazard.execute("INSERT INTO u (id, v) VALUES (-1, 'sentinel')")
        with pytest.raises(sqlite3.IntegrityError, match="retired idiom"):
            hazard.execute("INSERT INTO u (v) VALUES ('ordinary append')")
        hazard.close()
    finally:
        probe.close()


@pytest.mark.parametrize("trigger", sorted(_NO_REPLACE_PK))
def test_the_pk_conflict_clause_uses_the_minus_one_idiom(
        conn, trigger: str) -> None:
    """Every no-REPLACE barrier spells the PK clause the ONE way that fires.

    Asserted as CONTENT rather than as a byte-string: the presence of the
    working form AND the absence of the dead one, because a body could carry
    both and read as guarded.
    """
    _table, pk = _NO_REPLACE_PK[trigger]
    body = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        (trigger,)).fetchone()
    assert body is not None, f"{trigger} is not installed"
    body = " ".join(body[0].split())
    assert f"NEW.{pk} != -1 AND {pk} = NEW.{pk}" in body, (
        f"{trigger} does not carry the -1 idiom on {pk}")
    assert f"NEW.{pk} IS NOT NULL" not in body, (
        f"{trigger} still carries the IS NOT NULL form on {pk}, which never "
        f"fires and is dead text")


# --------------------------------------------------------------------------
# SITE 1 -- candidates (EXISTING table; the residual is declared below)
# --------------------------------------------------------------------------
def _second_run(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (999, '2026-07-18T20:06:25', '2026-07-18', '2026-07-21', "
        "1, 1, 0, 0, 0, 0)")


def test_candidates_the_three_directions(conn) -> None:
    """DIRECTION 1 append, DIRECTION 2 REPLACE, DIRECTION 3 explicit id."""
    cid = seed_fire(conn)
    _second_run(conn)
    conn.execute(                                             # 1
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)"
        " VALUES (999, 'AAAA', 'aplus', 'universe')")
    with pytest.raises(sqlite3.IntegrityError,               # 2
                       match="trg_candidates_no_replace"):
        conn.execute(
            "INSERT OR REPLACE INTO candidates (evaluation_run_id, ticker, "
            "bucket, pivot, rs_method) "
            "VALUES (121, 'FTRE', 'aplus', 99.0, 'universe')")
    with pytest.raises(sqlite3.IntegrityError,               # 3
                       match="trg_candidates_no_replace"):
        # a DIFFERENT run and ticker, so ONLY the PK clause can fire
        conn.execute(
            "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
            "rs_method) VALUES (?, 999, 'BBBB', 'aplus', 'universe')", (cid,))


def test_candidates_an_ordinary_append_survives_a_minus_one_row(conn) -> None:
    """THE DISCRIMINATOR the idiom exists for.

    PRE-FIX (`NEW.id IS NOT NULL AND id = NEW.id`): the ordinary append ABORTS,
    because the omitted id arrives as `-1` and matches the sentinel row.
    POST-FIX it succeeds.  One row, one dimension.
    """
    seed_fire(conn)
    _second_run(conn)
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
        "rs_method) VALUES (-1, 999, 'CCCC', 'aplus', 'universe')")
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)"
        " VALUES (999, 'DDDD', 'aplus', 'universe')")
    assert conn.execute(
        "SELECT COUNT(*) FROM candidates WHERE evaluation_run_id = 999"
    ).fetchone()[0] == 2


# --------------------------------------------------------------------------
# SITE 2 -- latch_order_intents (EXISTING table)
# --------------------------------------------------------------------------
def _intent_payload(conn: sqlite3.Connection, source: int, **over) -> dict:
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(latch_order_intents)")]
    vals = list(conn.execute(
        "SELECT * FROM latch_order_intents WHERE intent_id = ?",
        (source,)).fetchone())
    payload = dict(zip(cols, vals, strict=True))
    payload.update(over)
    return payload


def _insert_raw(conn: sqlite3.Connection, table: str, payload: dict) -> None:
    conn.execute(
        f"INSERT INTO {table} ({', '.join(payload)}) "
        f"VALUES ({', '.join('?' * len(payload))})", tuple(payload.values()))


def test_latch_order_intents_the_three_directions(conn) -> None:
    cid = seed_fire(conn)
    pid = insert_intent(conn, place_row(cid))
    insert_intent(conn, place_row(cid, idempotency_key="key-place-append"))  # 1
    with pytest.raises(sqlite3.IntegrityError,                               # 2
                       match="trg_loi_no_replace"):
        _insert_raw(conn, "latch_order_intents",
                    _intent_payload(conn, pid, framework_limit_price=999.99))
    with pytest.raises(sqlite3.IntegrityError,                               # 3
                       match="trg_loi_no_replace"):
        # a DIFFERENT idempotency key, so ONLY the PK clause can fire
        _insert_raw(conn, "latch_order_intents",
                    _intent_payload(conn, pid,
                                    idempotency_key="key-place-explicit"))


def test_latch_order_intents_an_ordinary_append_survives_a_minus_one_row(
        conn) -> None:
    """The same discriminator, one table over.

    ``record_intent`` is the PRODUCTION writer and it omits the PK, so under
    the retired idiom a single `-1` row would have blocked every subsequent
    acceptance record on this box.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import record_intent

    cid = seed_fire(conn)
    pid = insert_intent(conn, place_row(cid))
    _insert_raw(conn, "latch_order_intents",
                _intent_payload(conn, pid, intent_id=-1,
                                idempotency_key="key-sentinel"))
    appended = record_intent(conn, intent=LatchOrderIntent(
        intent_id=None, **place_row(cid, idempotency_key="key-after")))
    assert appended.intent_id is not None and appended.intent_id > 0


# --------------------------------------------------------------------------
# SITE 3 -- latch_order_mandate_links (the NEW table: it carries the CHECK)
# --------------------------------------------------------------------------
def _mint_second_link(conn: sqlite3.Connection) -> tuple[int, int]:
    """A SECOND acceptance on a second fire, minted by the trigger itself."""
    cid2 = seed_fire(conn, run_id=777, ticker="AAAA",
                     action_session_date=DETECTION_DATE)
    place2 = insert_intent(conn, place_row(
        cid2, run_id=777, ticker="AAAA", idempotency_key="key-place-2"))
    insert_intent(conn, validity_row(
        cid2, place2, run_id=777, ticker="AAAA",
        idempotency_key="key-validity-2",
        actual_broker_order_id="2002937461"))
    row = conn.execute(
        "SELECT link_id, validity_intent_id FROM latch_order_mandate_links "
        "WHERE candidate_id = ?", (cid2,)).fetchone()
    assert row is not None, "the minting trigger did not fire for the 2nd fire"
    return int(row[0]), int(row[1])


def _link_payload(conn: sqlite3.Connection, source: int, **over) -> dict:
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(latch_order_mandate_links)")]
    vals = list(conn.execute(
        "SELECT * FROM latch_order_mandate_links WHERE link_id = ?",
        (source,)).fetchone())
    payload = dict(zip(cols, vals, strict=True))
    payload.update(over)
    return payload


def test_latch_order_mandate_links_the_three_directions(conn) -> None:
    cid = seed_fire(conn)
    place = insert_intent(conn, place_row(cid))
    insert_intent(conn, validity_row(cid, place))
    first = int(conn.execute(
        "SELECT link_id FROM latch_order_mandate_links").fetchone()[0])
    second, second_validity = _mint_second_link(conn)                     # 1
    assert second != first
    with pytest.raises(sqlite3.IntegrityError,                            # 2
                       match="trg_loml_no_replace"):
        _insert_raw(conn, "latch_order_mandate_links",
                    _link_payload(conn, first, frozen_pivot=99.0))
    with pytest.raises(sqlite3.IntegrityError,                            # 3
                       match="trg_loml_no_replace"):
        # the SECOND link's validity id, so ONLY the PK clause can fire
        _insert_raw(conn, "latch_order_mandate_links",
                    _link_payload(conn, second, link_id=first,
                                  validity_intent_id=second_validity))


def test_a_negative_link_id_can_never_exist(conn) -> None:
    """THE NEW TABLE CARRIES THE CHECK, which is the half an existing table
    cannot have without a rebuild.

    It runs on the STORED value AFTER assignment, so an omitted id (assigned a
    positive rowid) passes while an explicit `-1` is refused outright -- and
    the `-1` sentinel is therefore unambiguous on this table FOREVER, rather
    than by convention.
    """
    cid = seed_fire(conn)
    place = insert_intent(conn, place_row(cid))
    insert_intent(conn, validity_row(cid, place))
    first = int(conn.execute(
        "SELECT link_id FROM latch_order_mandate_links").fetchone()[0])
    assert first > 0, "an omitted AUTOINCREMENT id must still land positive"
    # A `validity_intent_id` NO LINK CITES, so `trg_loml_no_replace` cannot
    # fire and the CHECK is demonstrably what refuses. The place intent is
    # such a row: the FK only requires a `latch_order_intents` id.
    with pytest.raises(sqlite3.IntegrityError, match="link_id > 0"):
        _insert_raw(conn, "latch_order_mandate_links",
                    _link_payload(conn, first, link_id=-1,
                                  validity_intent_id=place))


# --------------------------------------------------------------------------
# SITE 3b -- fill_envelope_identity (NEW table; Codex 22A-R11-06)
# --------------------------------------------------------------------------
_FEI_COLS = ("fill_id, envelope_raw, envelope_state, broker_order_id, "
             "instrument_symbol, canonicalizer_version, recorded_ts")


def _fei(conn, *, identity_id=None, fill_id=11, raw="docA", order="ORDER-A"):
    cols = _FEI_COLS if identity_id is None else "identity_id, " + _FEI_COLS
    vals = [fill_id, raw, "canonical", order, "AAA", "v1", "2026-08-26T00:00Z"]
    if identity_id is not None:
        vals.insert(0, identity_id)
    holes = ", ".join("?" * len(vals))
    return cols, holes, vals


def test_fill_envelope_identity_the_three_directions(conn) -> None:
    """DIRECTION 1 append, DIRECTION 2 REPLACE, DIRECTION 3 explicit id."""
    cols, holes, vals = _fei(conn)
    conn.execute(                                                         # 1
        f"INSERT INTO fill_envelope_identity ({cols}) VALUES ({holes})", vals)
    first = int(conn.execute(
        "SELECT identity_id FROM fill_envelope_identity").fetchone()[0])
    cols, holes, vals = _fei(conn, order="REWRITTEN")
    with pytest.raises(sqlite3.IntegrityError,                            # 2
                       match="trg_fei_no_replace"):
        conn.execute(
            f"INSERT OR REPLACE INTO fill_envelope_identity ({cols}) "
            f"VALUES ({holes})", vals)
    # a DIFFERENT (fill_id, envelope_raw), so ONLY the PK clause can fire
    cols, holes, vals = _fei(conn, identity_id=first, fill_id=22, raw="docB")
    with pytest.raises(sqlite3.IntegrityError,                            # 3
                       match="trg_fei_no_replace"):
        conn.execute(
            f"INSERT INTO fill_envelope_identity ({cols}) VALUES ({holes})",
            vals)


def test_a_negative_identity_id_can_never_exist(conn) -> None:
    """22A-R11-06, REPRODUCED FIRST on sqlite 3.50.4 at recursive_triggers=0.

    PRE-FIX: insert an identity explicitly at `-1`, then `INSERT OR REPLACE` a
    `-1` row with a DIFFERENT `(fill_id, envelope_raw)`; the first row was
    SILENTLY DELETED and replaced, `trg_fei_no_delete` never fired, and the
    table's own append-only guarantee was false.  The barrier ignores
    `NEW.identity_id = -1` because an OMITTED integer primary key presents as
    `-1`, so the sentinel MUST be impossible as a stored value -- which a NEW
    table can guarantee with a CHECK and an existing one cannot.

    POST-FIX the FIRST insert is refused, so the bypass has no state to start
    from.  Asserted on the CHECK by name, and the `(fill_id, envelope_raw)`
    pair is fresh so `trg_fei_no_replace` cannot be what fires.
    """
    cols, holes, vals = _fei(conn, identity_id=-1, fill_id=33, raw="docC")
    with pytest.raises(sqlite3.IntegrityError, match="identity_id > 0"):
        conn.execute(
            f"INSERT INTO fill_envelope_identity ({cols}) VALUES ({holes})",
            vals)


# --------------------------------------------------------------------------
# SITE 4 -- provenance_corrections (EXISTING table)
# --------------------------------------------------------------------------
def test_provenance_corrections_the_three_directions(conn) -> None:
    """DIRECTIONS 1 and 2 restate the shipped pair here so the SET is legible
    as a set; DIRECTION 3 is new.

    WHAT DIRECTION 3 DOES NOT ISOLATE, stated rather than left implicit: this
    payload conflicts on the PK *and* on ``ux_provenance_corrections_trade``,
    because isolating the PK clause needs a VALID citation graph for a trade
    that has no correction yet, and the citation-graph trigger is precisely
    what stops such a payload being faked.  The DIRECTION is proved; the
    clause attribution is not, and the two are different claims.
    """
    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )

    first = _seed_correction(conn)
    row_id = int(first["row_id"])
    second = build_cadl_case(conn, ticker="ZZTOP")
    if conn.in_transaction:
        conn.commit()
    correct_cohort_provenance(                                            # 1
        conn, trade_id=second["trade_id"],
        cited_candidate_id=second["candidate_id"],
        cited_recommendation_id=second["daily_recommendation_id"],
        reason="the ordinary append, on a DIFFERENT trade")
    second_row = int(conn.execute(
        "SELECT provenance_correction_id FROM provenance_corrections "
        "WHERE trade_id = ?", (second["trade_id"],)).fetchone()[0])

    payload, names, holes = _pc_replace_payload(                          # 2
        conn, row_id, correction_reason="REWRITTEN BY REPLACE")
    with pytest.raises(sqlite3.IntegrityError, match="trg_pc_no_replace"):
        conn.execute(
            f"INSERT OR REPLACE INTO provenance_corrections ({names}) "
            f"VALUES ({holes})", tuple(payload.values()))

    payload, names, holes = _pc_replace_payload(                          # 3
        conn, second_row, provenance_correction_id=row_id)
    with pytest.raises(sqlite3.IntegrityError, match="trg_pc_no_replace"):
        conn.execute(
            f"INSERT INTO provenance_corrections ({names}) VALUES ({holes})",
            tuple(payload.values()))


# --------------------------------------------------------------------------
# THE DECLARED RESIDUAL, for the three EXISTING tables
# --------------------------------------------------------------------------
def test_the_three_existing_tables_have_no_negative_ids_by_their_writers(
) -> None:
    """THE RESIDUAL, DECLARED AND VERIFIED AT ITS SOURCE (CHARC's ruling).

    A `CHECK (pk > 0)` on `candidates`, `latch_order_intents` or
    `provenance_corrections` would mean a TABLE REBUILD, which this migration
    convention forbids.  So the sentinel's unambiguity on those three rests on
    a weaker fact, and the weakness is stated: **an explicit `-1` INSERT is
    indistinguishable from an omitted one**, and the barrier would then refuse
    ordinary appends exactly as the retired idiom did.

    AND THE SCOPE IS EXACTLY THREE, WHICH IS NOW TRUE BY CONSTRUCTION RATHER
    THAN BY THE ROSTER HAPPENING TO BE RIGHT (Codex 22A-R11-06).  When this
    declaration was written the arc had ONE new table; `fill_envelope_identity`
    then shipped WITHOUT the CHECK, so the residual silently covered a fourth
    table nobody had declared.  Every NEW table now carries the CHECK, and
    `test_every_new_table_carries_the_pk_positivity_CHECK` walks them, so a
    future new table cannot join this residual by omission.

    INCIDENCE ZERO, ESTABLISHED BY READING EACH WRITER'S COLUMN LIST rather
    than by grepping for the column name -- a name grep cannot see a writer
    that never mentions the PK, which is the shape all three have:

      * `swing/data/repos/candidates.py` -- the `candidates` INSERT names 17
        columns and `id` is not among them.
      * `swing/data/repos/latch_order_intents.py` -- `_INSERT_COLS` is
        `_COL_NAMES[1:]`, the PK sliced off by construction.
      * `swing/data/repos/provenance_corrections.py` -- `_COLUMNS` excludes
        `provenance_correction_id`; it appears only in `_SELECT`.

    This test READS those three column lists so the declaration cannot rot
    into prose: a writer that starts naming its PK fails here.
    """
    from swing.data.repos.latch_order_intents import _INSERT_COLS
    from swing.data.repos.provenance_corrections import _COLUMNS

    assert "intent_id" not in _INSERT_COLS
    assert "provenance_correction_id" not in _COLUMNS
    candidates_src = (
        Path(__file__).resolve().parents[2] / "swing" / "data" / "repos"
        / "candidates.py").read_text(encoding="utf-8")
    insert = candidates_src[candidates_src.index("INSERT INTO candidates"):]
    column_list = insert[insert.index("(") + 1:insert.index(")")]
    assert "id" not in [c.strip() for c in column_list.split(",")], (
        "the candidates writer now names its own primary key; the declared "
        "residual above assumed it did not")
