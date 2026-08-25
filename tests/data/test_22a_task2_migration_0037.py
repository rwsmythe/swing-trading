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

import re
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    _current_version,
    _phase22_arc_a_backup_gate,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.trades.latched_origin import (
    AUTHORIZATION_KEYS,
    LATCH_FREEZE_TIERS,
    PROVENANCE_ADMISSION_TIERS,
)
from tests.trades._cohort_provenance_fixtures import build_cadl_case
from tests._latch_link_fixtures_22a import (
    BROKER_ORDER_ID,
    INITIAL_STOP,
    PIVOT,
    accept_order,
    insert_intent,
    place_row,
    seed_fire,
    validity_row,
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
    from swing.data.repos.candidates import insert_candidates
    from swing.data.models import Candidate

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
    """
    boundary = conn.execute(
        "SELECT max_candidate_id_at_barrier FROM candidates_immutability_epoch"
    ).fetchone()[0]
    at = seed_fire(conn, candidate_id=boundary + 1, run_id=131,
                   action_session_date="2026-07-20")
    assert at == boundary + 1
    tier_at_boundary = conn.execute(
        "SELECT CASE WHEN ? > (SELECT max_candidate_id_at_barrier FROM "
        "candidates_immutability_epoch WHERE epoch_id = 1) "
        "THEN 'live_at_acceptance' ELSE 'pre_barrier_reconstructed' END",
        (boundary,)).fetchone()[0]
    tier_above = conn.execute(
        "SELECT CASE WHEN ? > (SELECT max_candidate_id_at_barrier FROM "
        "candidates_immutability_epoch WHERE epoch_id = 1) "
        "THEN 'live_at_acceptance' ELSE 'pre_barrier_reconstructed' END",
        (boundary + 1,)).fetchone()[0]
    assert tier_at_boundary == "pre_barrier_reconstructed"
    assert tier_above == "live_at_acceptance"


# ---------------------------------------------------------------------------
# The messages
# ---------------------------------------------------------------------------
def test_every_barrier_message_is_legible_case_36(conn) -> None:
    """Case 36 -- CHARC CONDITION 2, ASSERTED AS CONTENT, NEVER AS BYTES.

    *A refusal that does not say what to do next is a dead end, not a guard.*
    Each message must name its own trigger, the ARC, and the recovery path.
    Byte-comparing the message would make an IMPROVEMENT to the wording a false
    red, which is how a legibility requirement decays into a string pin.
    """
    bodies = {
        name: sql for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")
    }
    guarded = (*BARRIER_TRIGGERS, *EPOCH_TRIGGERS,
               "trg_loml_no_update", "trg_loml_no_delete")
    for name in guarded:
        body = bodies[name]
        assert name in body, f"{name} does not name itself in its own message"
        assert "22-A" in body, f"{name} does not name the arc"
        assert "reversibility header" in body, (
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
    may not disagree."""
    ids = _seed_correction(conn)
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_correction(conn, ids, admission_tier="latch_ladder")


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
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

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
