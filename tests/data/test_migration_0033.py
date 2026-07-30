"""Migration 0033 - latch_order_intents + the latch_view_events rebuild.

Arc 21-B, Task 1. The #11 one-commit multi-mirror task: every CHECK enum, its
Python frozenset and the dataclass validator are pinned against each other HERE.

TWO DISCIPLINES THIS FILE ENCODES, both learned the expensive way in this arc:
  * A CHECK PASSES WHEN ITS EXPRESSION IS NULL, so any guard built from a
    function that returns NULL on bad input silently admits exactly what it was
    written to reject. Probe it; never reason about it.
  * A COMMENT CLAIMING A GUARANTEE IS NOT A GUARANTEE. 0032's comment argued
    carefully for round-trip equality OVER `IS NOT NULL` -- correct about
    normalisation, wrong that normalisation was the whole space. When a
    constraint's comment explains why it is sufficient, treat that as a
    HYPOTHESIS TO PROBE.

NO CARDINALITIES. Every roster has ONE authority and every loop ITERATES it, so
a set that grows gains its cases automatically.
"""
from __future__ import annotations

import json
import re
import sqlite3

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES,
    _MIGRATIONS_DIR,
    ensure_schema,
)
from swing.latches.constants import (
    DERIVATION_FIELD_MANIFEST,
    DERIVATION_NULLABLE_ON_DECISION,
    LATCH_BROKER_SNAPSHOT_KEYS,
    LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES,
    LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES,
    LATCH_INTENT_KINDS,
)
from swing.latches.identity import LATCH_IDENTITY_COLUMNS

# --------------------------------------------------------------------------
# Fixtures. A migrated DB plus ONE real A+ candidates row, because
# `candidate_id` is NOT NULL / RESTRICT and the identity-coherence trigger
# requires the whole block to agree with it.
# --------------------------------------------------------------------------
_GOOD_TS = "2026-07-29T12:00:00"
_GOOD_SESSION = "2026-07-29"
_DIGEST64 = "a" * 64


def _fresh(tmp_path):
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T20:06:25', '2026-07-17', '2026-07-20', "
            "1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 18.34, 18.34, 14.88, 'universe')")
    return conn, int(cur.lastrowid)


@pytest.fixture
def conn_cid(tmp_path):
    conn, cid = _fresh(tmp_path)
    yield conn, cid
    conn.close()


def _snapshot_envelope(**over) -> str:
    env = {
        "broker_snapshot_ts": _GOOD_TS,
        "broker_snapshot_branch": "presence",
        "broker_snapshot_digest": _DIGEST64,
        "broker_snapshot_session": _GOOD_SESSION,
        "attributable_order_count": 1,
        "exact_framework_match_count": 0,
        "indeterminate": False,
    }
    env.update(over)
    return json.dumps(env)


def _place_row(cid: int, **over) -> dict:
    """A MINIMAL VALID `place` row -- the whole drift-capable derivation block
    included, because the schema requires it (the 'four bare numbers' guard one
    layer down)."""
    row = {
        "candidate_id": cid, "evaluation_run_id": 121, "ticker": "FTRE",
        "detection_date": "2026-07-20", "pipeline_run_id": None,
        "idempotency_key": "key-place", "action_session_date": _GOOD_SESSION,
        "recorded_ts": _GOOD_TS, "surface": "latch_panel",
        "intent_kind": "place",
        "framework_order_type": "LIMIT", "framework_duration": "GOOD_TILL_CANCEL",
        "framework_stop_price": None, "framework_limit_price": 18.89,
        "framework_quantity": 9,
        "derivation_zone_cap_pct": 3.0, "derivation_sizing_equity": 7500.0,
        "derivation_max_risk_pct": 0.005, "derivation_position_pct_cap": 0.15,
        "derivation_risk_policy_id": None,
        "derivation_sizing_basis": "limit_price",
        "derivation_regime_close": 19.20,
        "derivation_regime_close_session": _GOOD_SESSION,
        "derivation_real_equity": 1234.56, "derivation_equity_floor": 7500.0,
        "derivation_nightly_recommendation_shares": 10,
    }
    row.update(over)
    return row


def _insert(conn, row: dict) -> int:
    cols = ", ".join(row)
    ph = ", ".join("?" * len(row))
    cur = conn.execute(
        f"INSERT INTO latch_order_intents ({cols}) VALUES ({ph})",
        tuple(row.values()))
    return int(cur.lastrowid)


def _reject(conn, row: dict) -> None:
    """Assert IntegrityError -- the TYPE matters.

    A chain that calls `json_extract` OUTSIDE a `CASE WHEN json_valid(...)` gate
    raises `OperationalError('malformed JSON')` on a non-JSON value, and a test
    catching bare `Exception` would go GREEN against that weaker DDL.
    """
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _insert(conn, row)


# --------------------------------------------------------------------------
# Version, provenance, backup gate
# --------------------------------------------------------------------------
def test_expected_schema_version_is_33():
    assert EXPECTED_SCHEMA_VERSION == 33


def test_pre_migration_expected_tables_is_the_v32_set_derived():
    """0032 added exactly ONE table, so the v32 set is the 21-A set plus it.
    DERIVED, never hand-listed."""
    assert PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {"latch_view_events"})


@pytest.mark.parametrize("current,target,should_fire", [
    (32, 33, True),    # THE intended case -- without this cell a gate whose
                       # body is an unconditional `return` passes the whole test
    (31, 33, False),   # multi-version jump bypasses by design; also the cell
                       # that discriminates a buggy `current_version <= 32`
    (32, 32, False),   # target below the gate
    (33, 33, False),   # already past
])
def test_backup_gate_fires_only_on_the_strict_32_to_33_step(
        tmp_path, monkeypatch, current, target, should_fire):
    """STRICT `current_version == 32 AND target_version >= 33`, per the
    `pre_version == (target - 1)` gotcha (NEVER `<=`)."""
    from swing.data import db as db_mod
    fired = []
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_b_migration_backup",
        lambda src, *, dest_dir: (fired.append(src), tmp_path / "b.db")[1])
    monkeypatch.setattr(db_mod, "_verify_backup_integrity",
                        lambda path, *, expected_tables: None)
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_b_backup_gate(
        sqlite3.connect(":memory:"), current_version=current,
        target_version=target, backup_dir=tmp_path)
    assert bool(fired) is should_fire


def test_backup_gate_verifies_against_the_declared_table_set(tmp_path, monkeypatch):
    """A gate that backs up but verifies nothing is a false net."""
    from swing.data import db as db_mod
    seen = {}
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_b_migration_backup",
        lambda src, *, dest_dir: tmp_path / "b.db")
    monkeypatch.setattr(
        db_mod, "_verify_backup_integrity",
        lambda path, *, expected_tables: seen.update(t=expected_tables))
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_b_backup_gate(
        sqlite3.connect(":memory:"), current_version=32,
        target_version=33, backup_dir=tmp_path)
    assert seen["t"] == PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------
def test_identity_block_is_columns_two_to_six(conn_cid):
    """The 21-A contract, mechanically pinned on the NEW table too."""
    conn, _ = conn_cid
    cols = [r[1] for r in conn.execute("PRAGMA table_info(latch_order_intents)")]
    assert cols[0] == "intent_id"
    assert tuple(cols[1:6]) == LATCH_IDENTITY_COLUMNS


def test_candidate_id_is_not_null_and_restricts_deletes(conn_cid):
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, candidate_id=None))
    with conn:
        _insert(conn, _place_row(cid))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))


def test_pipeline_run_id_carries_no_references_clause():
    """DELIBERATELY a plain INTEGER (section C.2).

    `pipeline_runs` IS genuinely pruned, so RESTRICT would block that forever --
    but SET NULL is WORSE than either: the cascade is an UPDATE that
    `trg_loi_no_update` aborts, AND nulling would DESTROY the detection identity
    on the very event the ledger exists to remember.
    """
    stmt = _strip_sql_comments(_table_sql("latch_order_intents"))
    line = next(ln for ln in stmt.splitlines()
                if re.match(r"\s*pipeline_run_id\s+INTEGER", ln))
    assert "REFERENCES" not in line.upper()


def test_no_set_null_appears_anywhere_in_the_ledger_ddl():
    """On an UPDATE-forbidden table `ON DELETE SET NULL` is UNIMPLEMENTABLE --
    the cascade IS an UPDATE and the barrier aborts it. A PROSE rule survived
    three review rounds while the DDL contradicted it, so the assertion reads
    the DDL, not the intent."""
    # COMMENTS ARE STRIPPED FIRST: the pipeline_run_id block deliberately
    # DISCUSSES "SET NULL" in prose (explaining why it is not used here), so a
    # raw substring search would fail against correct DDL for the wrong reason.
    ddl = _strip_sql_comments(_table_sql("latch_order_intents"))
    assert "SET NULL" not in ddl.upper()
    # ...and the check is not vacuous: latch_view_events DOES keep its 0032
    # SET NULL, and that divergence is deliberate (it is not UPDATE-forbidden).
    assert "SET NULL" in _strip_sql_comments(
        _table_sql("latch_view_events")).upper()


def test_unique_idempotency_key_blocks_a_second_row(conn_cid):
    conn, cid = conn_cid
    with conn:
        _insert(conn, _place_row(cid))
    _reject(conn, _place_row(cid, action_session_date="2026-07-28"))


def test_the_ledger_indexes_exist(conn_cid):
    conn, _ = conn_cid
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='latch_order_intents'")}
    assert {"ix_loi_candidate_id", "ix_loi_ticker_detection",
            "ix_loi_action_session_date"} <= names


# --------------------------------------------------------------------------
# The append-only barrier
# --------------------------------------------------------------------------
def test_update_and_delete_both_abort_naming_the_append_only_rule(conn_cid):
    conn, cid = conn_cid
    with conn:
        iid = _insert(conn, _place_row(cid))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute(
                "UPDATE latch_order_intents SET ticker = 'XXXX' "
                "WHERE intent_id = ?", (iid,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute(
                "DELETE FROM latch_order_intents WHERE intent_id = ?", (iid,))


def test_deleting_a_parent_place_row_aborts_with_the_append_only_message(conn_cid):
    """`trg_loi_no_delete` fires FIRST for any delete here, so a test asserting
    'self-referencing RESTRICT' would prove the WRONG thing."""
    conn, cid = conn_cid
    with conn:
        parent = _insert(conn, _place_row(cid))
        _insert(conn, _validity_row(cid, parent))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute(
                "DELETE FROM latch_order_intents WHERE intent_id = ?", (parent,))


# --------------------------------------------------------------------------
# intent_kind + the three-state conditionals
# --------------------------------------------------------------------------
def test_every_intent_kind_in_the_roster_is_accepted(conn_cid):
    """ITERATES the roster, so a new kind gains its case automatically."""
    conn, cid = conn_cid
    made = set()
    for i, kind in enumerate(sorted(LATCH_INTENT_KINDS)):
        with conn:
            _insert(conn, _row_for_kind(conn, cid, kind, f"k{i}"))
        made.add(kind)
    assert made == set(LATCH_INTENT_KINDS)


def test_an_unknown_intent_kind_is_rejected(conn_cid):
    conn, cid = conn_cid
    _reject(conn, _bare_row(cid, "bogus", "k-bogus"))


def test_a_decline_requires_a_non_blank_reason_and_no_other_kind_may_carry_one(
        conn_cid):
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, intent_kind="decline", idempotency_key="d1"))
    _reject(conn, _place_row(cid, intent_kind="decline", decline_reason="   ",
                             idempotency_key="d2"))
    _reject(conn, _place_row(cid, decline_reason="not mine", idempotency_key="d3"))


def test_an_attest_requires_a_disposition_and_no_other_kind_may_carry_one(conn_cid):
    conn, cid = conn_cid
    _reject(conn, _bare_row(cid, "attest", "a1"))
    _reject(conn, _place_row(cid, attested_disposition="was_away",
                             idempotency_key="a2"))


def test_a_cancel_must_name_one_broker_order(conn_cid):
    """HAZARD (c) MADE STRUCTURAL: there is no by-ticker cancel path anywhere
    and the schema makes one UNWRITABLE."""
    conn, cid = conn_cid
    _reject(conn, _bare_row(cid, "cancel", "c1"))
    _reject(conn, _bare_row(cid, "cancel", "c2", actual_broker_order_id="  "))
    with conn:
        _insert(conn, _bare_row(cid, "cancel", "c3",
                                actual_broker_order_id="1002937461"))


def test_a_place_or_decline_row_may_not_carry_a_broker_order_id(conn_cid):
    """A broker order id is an OBSERVATION; a decision has observed nothing."""
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, actual_broker_order_id="1002937461"))


def test_a_place_row_missing_any_framework_field_is_rejected(conn_cid):
    conn, cid = conn_cid
    for fname in ("framework_order_type", "framework_limit_price",
                  "framework_quantity", "framework_duration"):
        _reject(conn, _place_row(cid, **{fname: None}))


@pytest.mark.parametrize("col,bad", [
    ("framework_order_type", "MARKET"),
    ("framework_duration", "DAY"),
    ("derivation_sizing_basis", "vibes"),
])
def test_provenance_enum_checks_reject_a_typo(conn_cid, col, bad):
    """An audit-grade column that accepts anything will later look
    authoritative while holding a typo."""
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, **{col: bad}))


def test_the_stop_leg_is_conditioned_on_the_order_type(conn_cid):
    conn, cid = conn_cid
    # a STOP_LIMIT without its trigger is not the mandate
    _reject(conn, _place_row(cid, framework_order_type="STOP_LIMIT",
                             framework_stop_price=None))
    # a LIMIT carrying one is the REJECTED FTRE shape
    _reject(conn, _place_row(cid, framework_order_type="LIMIT",
                             framework_stop_price=18.34))
    with conn:
        _insert(conn, _place_row(cid, framework_order_type="STOP_LIMIT",
                                 framework_stop_price=18.34))


def test_the_regime_close_and_its_session_are_a_paired_null(conn_cid):
    """A close without the session it is DATED is exactly the provenance-free
    number 21-G exists to eliminate; a session without a close is a claim about
    a price that is not there. On a place row BOTH are required, so the pairing
    is proved on a kind that permits NULLs -- and the place-required CHECK is
    proved separately."""
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, derivation_regime_close=None))
    _reject(conn, _place_row(cid, derivation_regime_close_session=None))


# --------------------------------------------------------------------------
# The derivation block -- required set DERIVED, exemptions pinned BOTH ways
# --------------------------------------------------------------------------
def _derivation_columns_from_schema(conn) -> set[str]:
    return {r[1] for r in conn.execute("PRAGMA table_info(latch_order_intents)")
            if r[1].startswith("derivation_")}


def test_the_manifest_equals_the_schemas_derivation_columns(conn_cid):
    """MANIFEST ASSERTION 1: a derivation column added to the DDL WITHOUT a
    manifest row FAILS -- the annotated-manifest shape applied here."""
    conn, _ = conn_cid
    assert ({f.column for f in DERIVATION_FIELD_MANIFEST}
            == _derivation_columns_from_schema(conn))


def test_the_manifest_nullable_set_equals_the_exemption_roster():
    """MANIFEST ASSERTION 2, plus: every nullable row carries a REASON. An
    unexplained exemption is the hand-kept list the manifest replaces."""
    assert ({f.column for f in DERIVATION_FIELD_MANIFEST if f.nullable}
            == set(DERIVATION_NULLABLE_ON_DECISION))
    for f in DERIVATION_FIELD_MANIFEST:
        if f.nullable:
            assert f.null_reason.strip()


def test_every_required_derivation_column_is_not_null_on_a_place_row(conn_cid):
    """The required set is a SET DIFFERENCE, never a hand-kept list or a count:
    {every derivation_* column in PRAGMA table_info} - the exemption roster. A
    hand-kept list is how three of these columns went unanchored in the first
    place."""
    conn, cid = conn_cid
    required = _derivation_columns_from_schema(conn) - set(
        DERIVATION_NULLABLE_ON_DECISION)
    assert required, "the required set must not be empty"
    for col in sorted(required):
        _reject(conn, _place_row(cid, **{col: None}))


def test_every_exempt_derivation_column_is_nullable_on_a_place_row(conn_cid):
    """The exemption roster is pinned in BOTH directions, so it cannot quietly
    grow: an un-pinned exemption list is the same failure one size down."""
    conn, cid = conn_cid
    for i, col in enumerate(sorted(DERIVATION_NULLABLE_ON_DECISION)):
        with conn:
            _insert(conn, _place_row(cid, idempotency_key=f"ex{i}",
                                     **{col: None}))


@pytest.mark.parametrize("col", [
    "derivation_sizing_equity", "derivation_equity_floor",
    "derivation_zone_cap_pct", "derivation_max_risk_pct",
    "derivation_position_pct_cap",
    "derivation_nightly_recommendation_shares",
    "framework_quantity",
])
def test_non_positive_is_rejected_by_column_name(conn_cid, col):
    """SPECIFIED BY COLUMN NAME, deliberately. A bullet reading 'non-positive
    equity is rejected' invites a CHECK that breaks the ruled floor semantics on
    the ONE column that must not have one."""
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, **{col: 0}))
    _reject(conn, _place_row(cid, **{col: -1}))


@pytest.mark.parametrize("value", [0, -1234.56])
def test_real_equity_at_zero_or_negative_is_ACCEPTED(conn_cid, value):
    """THE DELIBERATE ACCEPT. `derivation_real_equity` may be ZERO or NEGATIVE
    and that is not an error -- it IS the account, and it is exactly why the
    floor exists. The accept-cells are as load-bearing as the reject-cells."""
    conn, cid = conn_cid
    with conn:
        _insert(conn, _place_row(cid, idempotency_key=f"re{value}",
                                 derivation_real_equity=value))


def test_actual_quantity_must_be_positive(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, actual_quantity=0))


@pytest.mark.parametrize("col", [
    "framework_limit_price", "framework_stop_price",
])
def test_framework_prices_must_be_positive(conn_cid, col):
    """The price columns were SHAPE-constrained and never VALUE-constrained, so
    a raw append could store a negative or zero price -- and on an
    accepted_by_broker validity row that price enters the agreement DENOMINATOR
    and reports a delta computed from a price that cannot exist."""
    conn, cid = conn_cid
    row = _place_row(cid, framework_order_type="STOP_LIMIT",
                     framework_stop_price=18.34)
    row[col] = -1.0
    _reject(conn, row)


def test_actual_prices_must_be_positive(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, actual_limit_price=-1.0))


# --------------------------------------------------------------------------
# THE DATE / TIME GUARD -- BOTH HALVES, PLUS THE YEAR, PINNED INDEPENDENTLY
# --------------------------------------------------------------------------
# Each cell FAILS against a DIFFERENT defective guard, which is why they are
# never combined into one "a malformed date is rejected" test:
#   NORMALISING ('2026-02-30' -> '2026-03-02')  FAILS an IS NOT NULL-only guard
#   INVALID     ('2026-99-99' -> NULL)          FAILS the round-trip-only guard
#                                               0032 shipped
#   YEAR ZERO   ('0000-01-01')                  FAILS BOTH of the above, because
#                                               SQLite round-trips year zero
#                                               happily while
#                                               date.fromisoformat RAISES on it
_BAD_DATES = [
    pytest.param("2026-02-30", id="normalising"),
    pytest.param("2026-99-99", id="invalid"),
    pytest.param("0000-01-01", id="year-zero"),
]
_BAD_STAMPS = [
    pytest.param("2026-02-30T12:00:00", id="normalising"),
    pytest.param("2026-99-99T12:00:00", id="invalid"),
    pytest.param("0000-01-01T00:00:00", id="year-zero"),
    pytest.param("2026-07-28 12:00:00", id="space-separator"),
    pytest.param("2026-07-28T24:00:00", id="hour-24"),
    pytest.param("2026-07-28T12:60:00", id="minute-60"),
    pytest.param("2026-07-28T12:00:60", id="second-60"),
    pytest.param("2026-07-28TAB:00:00", id="non-digits"),
    pytest.param("2026-07-28T12:00", id="wrong-length"),
]


@pytest.mark.parametrize("col", ["detection_date", "action_session_date"])
@pytest.mark.parametrize("bad", _BAD_DATES)
def test_ledger_date_columns_reject_each_malformed_shape(conn_cid, col, bad):
    conn, cid = conn_cid
    row = _place_row(cid, **{col: bad})
    if col == "detection_date":
        # The identity trigger would also abort, but for a DIFFERENT reason, so
        # pin the CHECK on a column the trigger does not read: assert the CHECK
        # itself against a table with the trigger's own subject satisfied is
        # impossible here, so assert the message is NOT the identity one.
        with pytest.raises(sqlite3.IntegrityError) as exc:
            with conn:
                _insert(conn, row)
        assert "identity block" in str(exc.value) or "CHECK" in str(exc.value)
        return
    _reject(conn, row)


@pytest.mark.parametrize("bad", _BAD_DATES)
def test_regime_close_session_rejects_each_malformed_shape(conn_cid, bad):
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, derivation_regime_close_session=bad))


@pytest.mark.parametrize("bad", _BAD_STAMPS)
def test_recorded_ts_rejects_each_malformed_shape(conn_cid, bad):
    """`recorded_ts` DRIVES THE MONTHLY REPORT'S CUTOFF AND ORDERING.

    The SPACE and HOUR-24 cells are the discriminators: the naive
    `datetime(x) = replace(x,'T',' ')` form ACCEPTS both (verified empirically),
    and a space-separated stamp sorts differently from a T-separated one in the
    exact ORDER BY the report uses.
    """
    conn, cid = conn_cid
    _reject(conn, _place_row(cid, recorded_ts=bad))


@pytest.mark.parametrize("good", ["2026-07-28T12:00:00", "2026-07-28T23:59:59"])
def test_recorded_ts_accepts_the_canonical_form(conn_cid, good):
    conn, cid = conn_cid
    with conn:
        _insert(conn, _place_row(cid, idempotency_key=good, recorded_ts=good))


@pytest.mark.parametrize("good", ["0001-01-01", "9999-12-31"])
def test_the_year_guard_does_not_merely_narrow_the_useful_range(conn_cid, good):
    """Paired with the year-zero REJECT, so the fix cannot be 'reject anything
    that looks unusual'."""
    conn, cid = conn_cid
    with conn:
        _insert(conn, _place_row(cid, idempotency_key=good,
                                 derivation_regime_close_session=good))


# --------------------------------------------------------------------------
# The validity row + the envelope
# --------------------------------------------------------------------------
def _bare_row(cid: int, kind: str, key: str, **over) -> dict:
    row = {
        "candidate_id": cid, "evaluation_run_id": 121, "ticker": "FTRE",
        "detection_date": "2026-07-20", "pipeline_run_id": None,
        "idempotency_key": key, "action_session_date": _GOOD_SESSION,
        "recorded_ts": _GOOD_TS, "surface": "latch_panel", "intent_kind": kind,
    }
    # DELIBERATELY does NOT auto-populate `attested_disposition` /
    # `actual_broker_order_id`: their ABSENCE is exactly what several rejection
    # tests probe, and a helper that filled them in would make those tests
    # vacuous. `_row_for_kind` adds them for the VALID-row cases.
    row.update(over)
    return row


def _validity_row(cid: int, parent_id: int, key: str = "key-validity",
                  **over) -> dict:
    """A COMPLETE accepted_by_broker validity row.

    THE FIXTURE MUST BE COMPLETE OR IT CANNOT INSERT: an accepted row is
    required to carry a non-blank `actual_broker_order_id` AND the full
    roster envelope, and it inherits the parent's `action_session_date` (the
    trigger's session leg). A fixture listing only the four `actual_*` order
    fields FAILS against the correct schema, and the tempting repair is to
    weaken the CHECKs rather than complete the fixture.
    """
    row = {
        "candidate_id": cid, "evaluation_run_id": 121, "ticker": "FTRE",
        "detection_date": "2026-07-20", "pipeline_run_id": None,
        "idempotency_key": key, "action_session_date": _GOOD_SESSION,
        "recorded_ts": _GOOD_TS, "surface": "latch_panel",
        "intent_kind": "validity",
        "validated_place_intent_id": parent_id,
        "validity_outcome": "accepted_by_broker",
        "validity_detail": _snapshot_envelope(),
        "actual_order_type": "LIMIT", "actual_duration": "GOOD_TILL_CANCEL",
        "actual_stop_price": None, "actual_limit_price": 18.89,
        "actual_quantity": 10, "actual_broker_order_id": "1002937461",
    }
    row.update(over)
    return row


def _make_parent(conn, cid: int, key: str = "key-place", **over) -> int:
    with conn:
        return _insert(conn, _place_row(cid, idempotency_key=key, **over))


def _row_for_kind(conn, cid: int, kind: str, key: str) -> dict:
    if kind in ("place", "decline"):
        extra = {"decline_reason": "too extended"} if kind == "decline" else {}
        return _place_row(cid, intent_kind=kind, idempotency_key=key, **extra)
    if kind == "validity":
        return _validity_row(cid, _make_parent(conn, cid, key=f"{key}-parent"),
                             key=key)
    if kind == "attest":
        return _bare_row(cid, kind, key, attested_disposition="was_away")
    if kind == "cancel":
        return _bare_row(cid, kind, key,
                         actual_broker_order_id="1002937461")
    return _bare_row(cid, kind, key)


def test_a_validity_row_requires_both_outcome_and_parent_link(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, validity_outcome=None))


def test_a_validity_row_with_a_null_parent_link_is_rejected(conn_cid):
    """ITS OWN RED TEST. The parent-link TRIGGER fires only
    `WHEN NEW.validated_place_intent_id IS NOT NULL`, so it is STRUCTURALLY
    BLIND to the NULL case; only the CHECK catches it, and without a test aimed
    at the CHECK an orphan validity row goes green and the parent-scoped
    execution-outcome model silently loses its anchor."""
    conn, cid = conn_cid
    _make_parent(conn, cid)
    row = _validity_row(cid, 1)
    row["validated_place_intent_id"] = None
    _reject(conn, row)


@pytest.mark.parametrize("kind", ["place", "decline", "cancel", "attest"])
def test_a_non_validity_row_may_not_carry_any_validity_column(conn_cid, kind):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    for col, val in (("validity_outcome", "unknown"),
                     ("validity_detail", _snapshot_envelope()),
                     ("validated_place_intent_id", parent)):
        base = _row_for_kind(conn, cid, kind, f"nv-{kind}-{col}")
        base[col] = val
        _reject(conn, base)


def test_a_validity_row_may_not_carry_any_framework_or_derivation_value(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    for col in (["framework_order_type", "framework_limit_price"]
                + [f.column for f in DERIVATION_FIELD_MANIFEST]):
        val = "LIMIT" if col == "framework_order_type" else 1.0
        _reject(conn, _validity_row(cid, parent, **{col: val}))


def test_a_validity_row_MAY_carry_a_divergent_observed_order(conn_cid):
    """THE ARC'S OWN WORKED EXAMPLE. Framework LIMIT 18.89 / 9 sh vs actual
    LIMIT 18.89 / 10 sh. If this could not INSERT, the ledger could record
    agreements and NEVER a divergence -- the one thing it exists to measure.
    Note `exact_framework_match_count` is 0, not 1: the order is ATTRIBUTABLE to
    the latch and does NOT match the framework params, and a fixture setting it
    to 1 would quietly re-assert the exact-match gate that was removed."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    with conn:
        vid = _insert(conn, _validity_row(cid, parent))
    row = conn.execute(
        "SELECT framework_quantity, actual_quantity, validity_outcome "
        "FROM latch_order_intents WHERE intent_id = ?", (vid,)).fetchone()
    assert row == (None, 10, "accepted_by_broker")
    parent_qty = conn.execute(
        "SELECT framework_quantity FROM latch_order_intents WHERE intent_id = ?",
        (parent,)).fetchone()[0]
    assert parent_qty == 9
    env = json.loads(conn.execute(
        "SELECT validity_detail FROM latch_order_intents WHERE intent_id = ?",
        (vid,)).fetchone()[0])
    assert env["exact_framework_match_count"] == 0
    assert env["attributable_order_count"] == 1


@pytest.mark.parametrize("col", [
    "actual_order_type", "actual_duration", "actual_limit_price",
    "actual_quantity", "actual_broker_order_id",
])
def test_an_accepted_validity_row_missing_any_actual_field_is_rejected(
        conn_cid, col):
    """The agreement DENOMINATOR requires a KNOWN actual side, and exact linkage
    comes from validity rows -- so an accepted row missing any of these would
    look authoritative while satisfying neither claim."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, **{col: None}))


@pytest.mark.parametrize("col", ["actual_order_type", "actual_duration"])
def test_an_accepted_validity_row_may_not_carry_UNKNOWN(conn_cid, col):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, **{col: "UNKNOWN"}))


@pytest.mark.parametrize("outcome", [
    "rejected_by_broker", "not_submitted", "unknown"])
def test_a_non_accepted_validity_row_carries_no_observed_order_at_all(
        conn_cid, outcome):
    """An outcome and its evidence must not be able to DISAGREE: a
    `not_submitted` row beside an observed broker order id would sit in an
    append-only ledger carrying an authoritative-looking exact linkage that
    CONTRADICTS its own verdict."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, validity_outcome=outcome))
    # ...and the SAME row with every observed value NULL is ACCEPTED.
    with conn:
        _insert(conn, _validity_row(
            cid, parent, key=f"na-{outcome}", validity_outcome=outcome,
            actual_order_type=None, actual_duration=None, actual_stop_price=None,
            actual_limit_price=None, actual_quantity=None,
            actual_broker_order_id=None))


def test_an_accepted_stop_limit_requires_its_stop_and_a_limit_forbids_one(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, actual_order_type="STOP_LIMIT",
                                actual_stop_price=None))
    _reject(conn, _validity_row(cid, parent, actual_order_type="LIMIT",
                                actual_stop_price=18.34))


def test_a_bad_validity_outcome_is_rejected(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, validity_outcome="filled"))


# --- the envelope, generated per roster key -------------------------------
def test_the_envelope_roster_mirrors_the_migrations_json_remove_path_list():
    """THE MACHINE-READABLE SOURCE OF TRUTH. `json_remove(...)`'s path list IS
    the roster; the constant mirrors it under #11. No site states the count: a
    cardinality is exactly the kind of fact that goes stale when an adjacent
    edit lands, and when it did, the fragment's emitted set and the row's
    required set disagreed by one -- making the audit row UNWRITABLE."""
    sql = _migration_sql()
    block = re.search(r"json_remove\(validity_detail,(.*?)\)\s*=\s*'\{\}'",
                      sql, re.S)
    assert block, "could not locate the json_remove path list"
    paths = set(re.findall(r"'\$\.([a-z_]+)'", block.group(1)))
    assert paths == set(LATCH_BROKER_SNAPSHOT_KEYS)


@pytest.mark.parametrize("missing", sorted(LATCH_BROKER_SNAPSHOT_KEYS))
def test_a_validity_row_missing_any_one_roster_key_is_rejected(conn_cid, missing):
    """GENERATED by iterating the roster, so a key added to it gains its own
    case automatically. THE DISCRIMINATOR: verified empirically, the bare
    presence-and-shape CHECK chain ACCEPTS a missing key, because
    `json_extract` returns NULL and a SQLite CHECK PASSES on NULL."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    env = json.loads(_snapshot_envelope())
    env.pop(missing)
    _reject(conn, _validity_row(cid, parent, validity_detail=json.dumps(env)))


@pytest.mark.parametrize("detail", [
    pytest.param(None, id="null"),
    pytest.param("not json at all", id="non-json"),
    pytest.param("[1,2,3]", id="json-array"),
    pytest.param("42", id="json-scalar"),
    pytest.param("{}", id="empty-object"),
])
def test_a_degenerate_validity_detail_is_rejected_as_IntegrityError(
        conn_cid, detail):
    """The EMPTY OBJECT is the load-bearing cell, and the exception TYPE is too:
    a chain calling `json_extract` outside a `CASE WHEN json_valid(...)` gate
    raises `OperationalError('malformed JSON')` on the non-JSON value, and a
    test catching bare `Exception` would go GREEN against that weaker DDL."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(cid, parent, validity_detail=detail))


def test_an_extra_envelope_key_is_rejected(conn_cid):
    """EXACTLY the roster, not AT-LEAST. Extra keys would otherwise ride into an
    append-only audit row unaudited -- and since `actual_digest` covers only
    `broker_snapshot_digest`, two envelopes differing ONLY by extra content
    share an idempotency key, so the second is replayed and its extra content
    silently dropped instead of rejected."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(
        cid, parent, validity_detail=_snapshot_envelope(surprise="extra")))


@pytest.mark.parametrize("over,label", [
    ({"broker_snapshot_branch": "bogus"}, "bad-branch"),
    ({"broker_snapshot_branch": "unavailable"}, "unavailable-branch"),
    ({"broker_snapshot_digest": "a" * 63}, "digest-63"),
    ({"broker_snapshot_digest": "A" * 64}, "digest-uppercase"),
    ({"broker_snapshot_digest": "z" * 64}, "digest-non-hex"),
    ({"broker_snapshot_ts": "2026-07-28 12:00:00"}, "ts-space"),
    ({"broker_snapshot_ts": "2026-07-28T24:00:00"}, "ts-hour-24"),
    ({"broker_snapshot_session": "2026-02-30"}, "session-normalising"),
    ({"broker_snapshot_session": "2026-99-99"}, "session-invalid"),
    ({"attributable_order_count": -1}, "count-negative"),
    ({"attributable_order_count": "1"}, "count-string"),
    ({"exact_framework_match_count": 1.5}, "count-float"),
    ({"indeterminate": "true"}, "indeterminate-string"),
])
def test_envelope_value_shapes_are_enforced_not_merely_presence(
        conn_cid, over, label):
    """Presence-only checks let a raw append store an invalid branch, a
    malformed timestamp, a non-hex digest or a non-boolean flag -- and an
    append-only ledger keeps it forever.

    `unavailable` is the newest and most important reject: an UNKNOWN order book
    renders NO validity prompt in either direction, so a persisted row whose own
    snapshot says the book was unavailable is a row asserting an execution
    outcome it had NO EVIDENCE for -- forever."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    _reject(conn, _validity_row(
        cid, parent, validity_detail=_snapshot_envelope(**over)))


@pytest.mark.parametrize(
    "branch", sorted(LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES))
def test_every_persisted_branch_is_accepted(conn_cid, branch):
    """Paired with the `unavailable` reject, so the test discriminates a
    NARROWED enum from a BROKEN one."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    with conn:
        _insert(conn, _validity_row(
            cid, parent, key=f"br-{branch}",
            validity_detail=_snapshot_envelope(broker_snapshot_branch=branch)))


def test_the_persisted_branch_set_is_a_STRICT_subset_of_the_render_set():
    """Equality would mean the narrowing had been silently undone. TWO
    vocabularies, because the render status and the persisted answer are
    MEASURED DIFFERENTLY and do not share one enum."""
    assert (LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES
            < LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES)


# --------------------------------------------------------------------------
# The validity-parent trigger -- ALL THREE LEGS
# --------------------------------------------------------------------------
@pytest.mark.parametrize("parent_kind", ["decline", "cancel", "attest"])
def test_a_validity_row_may_not_point_at_a_non_place_row(conn_cid, parent_kind):
    """The self-FK only prevents a DANGLING pointer; on its own it happily
    accepts a validity row pointing at a decline, a cancel or another validity,
    any of which attaches an execution outcome to the WRONG order."""
    conn, cid = conn_cid
    with conn:
        bad_parent = _insert(conn, _row_for_kind(
            conn, cid, parent_kind, f"pk-{parent_kind}"))
    with pytest.raises(sqlite3.IntegrityError, match="validity parent"):
        with conn:
            _insert(conn, _validity_row(cid, bad_parent, key="v-badkind"))


def test_a_validity_row_may_not_point_at_a_validity_row(conn_cid):
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    with conn:
        first = _insert(conn, _validity_row(cid, parent, key="v1"))
    with pytest.raises(sqlite3.IntegrityError, match="validity parent"):
        with conn:
            _insert(conn, _validity_row(cid, first, key="v2"))


def test_a_validity_row_may_not_point_at_a_place_row_on_another_latch(
        tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(122, '2026-07-24T20:06:25', '2026-07-24', '2026-07-27', "
                "1, 1, 0, 0, 0, 0)")
            cur = conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(122, 'VSTS', 'aplus', 16.90, 16.90, 14.20, 'universe')")
        other_cid = int(cur.lastrowid)
        parent = _make_parent(conn, cid)
        row = _validity_row(other_cid, parent, key="v-crosslatch")
        row["evaluation_run_id"] = 122
        row["ticker"] = "VSTS"
        row["detection_date"] = "2026-07-27"
        with pytest.raises(sqlite3.IntegrityError, match="validity parent"):
            with conn:
                _insert(conn, row)
    finally:
        conn.close()


def test_the_aged_prompt_is_ACCEPTED_and_the_anchor_derived_one_is_REJECTED(
        conn_cid):
    """THE SESSION LEG, AND THE PAIR IS THE DISCRIMINATOR.

    An aged prompt is the NORMAL case: the parent `place` lands in session N and
    its `validity` child is written 20 sessions later carrying the PARENT's
    `action_session_date` (= N) and its OWN `recorded_ts` (in N+20). The SAME
    child carrying `action_session_date` = N+20 -- i.e. an implementation that
    reached for the SUBMITTED ANCHOR instead of copying the parent -- must be
    REJECTED. Without the second half the test passes against a trigger with no
    session leg at all, and every monthly read afterwards would attribute the
    mandate to the wrong month.
    """
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)          # action_session_date 2026-07-29
    with conn:
        _insert(conn, _validity_row(
            cid, parent, key="aged-ok", recorded_ts="2026-08-26T09:15:00"))
    with pytest.raises(sqlite3.IntegrityError, match="validity parent"):
        with conn:
            _insert(conn, _validity_row(
                cid, parent, key="aged-bad", action_session_date="2026-08-26",
                recorded_ts="2026-08-26T09:15:00"))


def test_multiple_validity_rows_for_one_parent_stay_legal(conn_cid):
    """A CORRECTION is a NEW row -- which is what append-only REQUIRES."""
    conn, cid = conn_cid
    parent = _make_parent(conn, cid)
    with conn:
        _insert(conn, _validity_row(cid, parent, key="c1"))
        _insert(conn, _validity_row(
            cid, parent, key="c2", validity_outcome="unknown",
            actual_order_type=None, actual_duration=None,
            actual_stop_price=None, actual_limit_price=None,
            actual_quantity=None, actual_broker_order_id=None))
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_intents WHERE intent_kind='validity'"
    ).fetchone()[0] == 2


def test_deleting_a_referenced_risk_policy_row_raises_rather_than_cascading(
        conn_cid):
    """The FK/immutability COHERENCE test. RESTRICT, not SET NULL: a SET NULL
    cascade is an UPDATE, and `trg_loi_no_update` would abort it with a
    confusing message instead of nulling."""
    conn, cid = conn_cid
    pid = conn.execute(
        "SELECT policy_id FROM risk_policy ORDER BY policy_id LIMIT 1"
    ).fetchone()
    if pid is None:
        pytest.skip("no risk_policy row on a fresh schema")
    with conn:
        _insert(conn, _place_row(cid, derivation_risk_policy_id=int(pid[0])))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("DELETE FROM risk_policy WHERE policy_id = ?", (pid[0],))


# --------------------------------------------------------------------------
# The latch_view_events REBUILD
# --------------------------------------------------------------------------
def test_the_rebuilt_unique_is_the_bridge_key_triple(conn_cid):
    """Asserted by PRAGMA INTROSPECTION, plus a NEGATIVE assertion that nothing
    keys telemetry on (evaluation_run_id, ticker, ...). Introspection cannot
    drift from the prose the way a task-list bullet can."""
    conn, _ = conn_cid
    keys = []
    for idx in conn.execute("PRAGMA index_list(latch_view_events)"):
        if not idx[2]:            # not unique
            continue
        cols = tuple(r[2] for r in conn.execute(
            f"PRAGMA index_info('{idx[1]}')"))
        keys.append(cols)
    assert ("candidate_id", "view_session_date", "surface") in keys
    assert not any("evaluation_run_id" in k for k in keys)


def test_a_second_row_on_the_same_latch_session_surface_is_rejected(conn_cid):
    conn, cid = conn_cid
    with conn:
        _insert_view(conn, cid)
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _insert_view(conn, cid)


@pytest.mark.parametrize("first,last,ever,ok", [
    pytest.param(1, 0, 1, True, id="offered-then-withheld-LEGAL"),
    pytest.param(0, 1, 1, True, id="withheld-then-offered-LEGAL"),
    pytest.param(1, 0, 0, False, id="ever-below-first"),
    pytest.param(0, 1, 0, False, id="ever-below-last"),
])
def test_the_monotonicity_checks_pin_ever_and_ONLY_ever(
        conn_cid, first, last, ever, ok):
    """FOUR CELLS, because a test covering only the two rejections passes
    against a DDL that ALSO forbids the legal pair.

    `(first=1, last=0, ever=1)` is DELIBERATELY LEGAL: it is the true record of
    an offered 09:00 render followed by a withheld 18:00 one, and asserting it
    is rejected would re-impose the false 'last means ever' invariant the third
    column was added to remove.
    """
    conn, cid = conn_cid
    if ok:
        with conn:
            _insert_view(conn, cid, first=first, last=last, ever=ever)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                _insert_view(conn, cid, first=first, last=last, ever=ever)


@pytest.mark.parametrize("bad", _BAD_STAMPS)
@pytest.mark.parametrize("col", ["first_viewed_ts", "last_viewed_ts"])
def test_the_rebuilt_view_timestamps_reject_each_malformed_shape(
        conn_cid, col, bad):
    """0032 guarded these ONLY by `last >= first` -- an ORDERING constraint, not
    a SHAPE one -- so a raw append could store a malformed or absurd view
    timestamp that hydrates fine and renders as AUTHORITATIVE TELEMETRY."""
    conn, cid = conn_cid
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _insert_view(conn, cid, **{col: bad})


def test_the_view_timestamp_ordering_check_is_still_enforced_independently(
        conn_cid):
    """PRESERVED unchanged beside the shape guards: it answers a DIFFERENT
    question, and the ordering guarantee is not implied by either shape guard."""
    conn, cid = conn_cid
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _insert_view(conn, cid, first_viewed_ts="2026-07-29T18:00:00",
                         last_viewed_ts="2026-07-29T09:00:00")


def test_a_bad_view_surface_is_rejected(conn_cid):
    conn, cid = conn_cid
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _insert_view(conn, cid, surface="dashboard")


def test_the_post_0033_table_rejects_the_dates_the_v32_table_ACCEPTED(tmp_path):
    """THE ONE PLACE THE REBUILT TABLE IS DELIBERATELY STRICTER THAN 0032.

    Asserting BOTH halves is the point: a preservation suite that only re-runs
    0032's own assertions would pass IDENTICALLY whether or not the correction
    landed. So this proves the v32 table ACCEPTS '2026-99-99' and the v33 table
    REJECTS it -- i.e. that the migration CHANGED something.
    """
    from swing.data.db import run_migrations
    # A RAW sqlite connection, per the in-tree `_fresh(target=N)` pattern:
    # `connect()` REFUSES a non-current schema by design.
    conn32 = sqlite3.connect(str(tmp_path / "v32.db"))
    run_migrations(conn32, target_version=32, backup_dir=tmp_path)
    assert conn32.execute("SELECT version FROM schema_version").fetchone()[0] == 32
    _seed_candidate(conn32)
    old_insert = (
        "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, "
        "ticker, detection_date, pipeline_run_id, view_session_date, "
        "first_viewed_ts, last_viewed_ts, view_count, "
        "latch_state_at_first_view, latch_state_at_last_view) VALUES "
        "(1, 121, 'FTRE', '2026-07-20', NULL, ?, '2026-07-29T10:00:00', "
        "'2026-07-29T10:00:00', 1, 'armed', 'armed')")
    # THE PREMISE, asserted inline so it cannot rot: the SHIPPED guard ACCEPTS
    # a length-correct INVALID date, because `date('2026-99-99')` is NULL and a
    # SQLite CHECK PASSES on NULL.
    with conn32:
        conn32.execute(old_insert, ("2026-99-99",))
    assert conn32.execute(
        "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1
    # ...and the rebuilt table REJECTS it. (The pre-existing bad row is dropped
    # first: the rebuild COPIES rows, and the point here is the CHECK, not the
    # copy.)
    with conn32:
        conn32.execute("DELETE FROM latch_view_events")
    run_migrations(conn32, target_version=33, backup_dir=tmp_path)
    assert conn32.execute("SELECT version FROM schema_version").fetchone()[0] == 33
    with pytest.raises(sqlite3.IntegrityError):
        with conn32:
            _insert_view(conn32, 1, view_session_date="2026-99-99")
    conn32.close()


def test_a_pre_0033_row_survives_the_rebuild_with_actionability_zero(tmp_path):
    """THE LEGACY BACKFILL IS `0`, NOT `1`. The old schema recorded no
    actionability at all, so asserting those views WERE actionable manufactures
    evidence in the flattering-to-the-instrument direction. `0` asserts strictly
    less -- 'no actionable presentation is RECORDED for this row' -- which is
    literally true of a row written by a schema that recorded no such thing.
    A backfill of `1` FAILS this test."""
    from swing.data.db import run_migrations
    conn = sqlite3.connect(str(tmp_path / "v32.db"))
    run_migrations(conn, target_version=32, backup_dir=tmp_path)
    _seed_candidate(conn)
    with conn:
        conn.execute(
            "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, "
            "ticker, detection_date, pipeline_run_id, view_session_date, "
            "first_viewed_ts, last_viewed_ts, view_count, "
            "latch_state_at_first_view, latch_state_at_last_view) VALUES "
            "(1, 121, 'FTRE', '2026-07-20', NULL, '2026-07-28', "
            "'2026-07-28T10:00:00', '2026-07-28T11:00:00', 3, 'armed', 'armed')")
    run_migrations(conn, target_version=33, backup_dir=tmp_path)
    row = conn.execute(
        "SELECT surface, actionable_at_first_view, actionable_at_last_view, "
        "actionable_ever_viewed, view_count FROM latch_view_events").fetchone()
    assert row == ("latch_panel", 0, 0, 0, 3)
    conn.close()


# --------------------------------------------------------------------------
# The rebuild is MECHANICAL -- three tests, none a substitute for another
# --------------------------------------------------------------------------
def test_the_migration_applies_to_a_real_v32_db_without_error(tmp_path):
    """Catches SYNTAX, unbalanced parens and unresolvable references -- the
    class no prose review sees. The plan's own DDL block carries PLACEHOLDERS,
    so a literal copy MUST fail this test."""
    from swing.data.db import run_migrations
    conn = sqlite3.connect(str(tmp_path / "v32.db"))
    run_migrations(conn, target_version=32, backup_dir=tmp_path)
    run_migrations(conn, target_version=33, backup_dir=tmp_path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 33
    conn.close()


def _normalise(expr: str) -> str:
    return re.sub(r"\s+", " ", expr).strip()


def _parse_checks(stmt: str) -> set[str]:
    """Every CHECK expression in a CREATE TABLE statement, whitespace-normalised.

    Paren-balanced scan rather than a regex, because several of these CHECKs
    contain nested parens (COALESCE, CASE WHEN, json_remove).
    """
    out: set[str] = set()
    for m in re.finditer(r"CHECK\s*\(", stmt):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(stmt)):
            if stmt[j] == "(":
                depth += 1
            elif stmt[j] == ")":
                depth -= 1
                if depth == 0:
                    out.add(_normalise(_strip_sql_comments(stmt[i + 1:j])))
                    break
    return out


def _strip_sql_comments(text: str) -> str:
    return "\n".join(
        ln.split("--", 1)[0] if "--" in ln else ln for ln in text.splitlines())


def _migration_sql() -> str:
    return (_MIGRATIONS_DIR / "0033_latch_order_intents.sql").read_text(
        encoding="utf-8")


def _sql_0032() -> str:
    return (_MIGRATIONS_DIR / "0032_latch_view_telemetry.sql").read_text(
        encoding="utf-8")


def _table_sql(table: str, sql: str | None = None) -> str:
    src = sql if sql is not None else _migration_sql()
    m = re.search(rf"CREATE TABLE {table}(_new)?\s*\((.*?)\n\);", src, re.S)
    assert m, f"could not locate the CREATE TABLE for {table}"
    return m.group(2)


def test_the_check_set_diff_equals_what_the_delta_list_introduces():
    """THE ORACLE IS DERIVED FROM THE DELTA LIST, NOT RESTATED BESIDE IT.

    A CHECK-SET DIFF at EXPRESSION granularity catches an ADDED or
    silently-ALTERED constraint, which NEITHER of the other two rebuild tests
    can: the 0032-preservation suite only re-runs KNOWN rejections, and
    `executescript` is happy with a constraint nobody intended.

    Delta (d) is a `UNIQUE` and contributes NOTHING to a CHECK diff; it, the
    three indexes and both triggers are asserted by their own introspection
    tests. NO CARDINALITY appears here: add a CHECK to a delta and the oracle
    follows it automatically, which a hand-kept 'ADDED (10)' could not do.
    """
    old = _parse_checks(_table_sql("latch_view_events", _sql_0032()))
    new = _parse_checks(_table_sql("latch_view_events"))

    # expected_removed = the CHECK expressions delta (c) SUPERSEDES
    expected_removed = {c for c in old if "date(" in c and " = " in c}
    assert expected_removed, "the weak date CHECKs must be found in 0032"
    # expected_added = the CHECK expressions deltas (a), (b), (c) and (e)
    # INTRODUCE -- identified by the columns/predicates each delta names.
    def _is_added(c: str) -> bool:
        return (
            "surface IN" in c                                  # delta (a)
            or "actionable_" in c                              # delta (b)
            or ("COALESCE" in c and ("detection_date" in c
                                     or "view_session_date" in c))  # delta (c)
            or ("COALESCE" in c and ("first_viewed_ts" in c
                                     or "last_viewed_ts" in c))     # delta (e)
        )
    expected_added = {c for c in new if _is_added(c)}
    assert expected_added, "the delta CHECKs must be found in 0033"

    assert new - old == expected_added
    assert old - new == expected_removed
    # ...and everything else is byte-identical modulo whitespace.
    assert (old - expected_removed) == (new - expected_added)


def test_the_rebuilt_triggers_are_0032s_bodies_verbatim():
    """Compare the post-0033 `sqlite_master` trigger SQL against 0032's,
    modulo whitespace -- rather than merely asserting that the triggers FIRE."""
    def _triggers(sql: str) -> dict[str, str]:
        out = {}
        for m in re.finditer(
                r"CREATE TRIGGER (trg_lve_\w+)(.*?)\nEND;", sql, re.S):
            out[m.group(1)] = _normalise(_strip_sql_comments(m.group(2)))
        return out
    old, new = _triggers(_sql_0032()), _triggers(_migration_sql())
    assert set(old) == set(new)
    for name in old:
        assert old[name] == new[name], f"{name} body drifted"


# --------------------------------------------------------------------------
# THE ANNOTATED ENUM-MIRROR MANIFEST
# --------------------------------------------------------------------------
# NOT A GREP AND NOT A PROSE COUNT, and the evidence is on disk: `grep -c "IN ("`
# on 0032 returns 0, because its two latch-state enums wrap the line as
# `IN\n    ('armed',...)` -- so the rule MISSES real enums -- while on 0033 it
# MATCHES a pile of NON-enum predicates. A prose count is no better: it was
# wrong twice.
#
# So every `IN`-list AND every `col = 'literal'` predicate in 0033's CREATE TABLE
# statements is parsed, and EVERY entry must be classified either
#   MIRRORED       -- naming its Python frozenset, or
#   NO_ENUM_MIRROR -- with a written reason.
# AN UNCLASSIFIED PREDICATE FAILS THE TEST. That is what makes a twelfth enum
# fail rather than join the blind spot.
_NO_MIRROR = "NO_ENUM_MIRROR"


def _mirror_manifest() -> dict[tuple[str, tuple[str, ...]], object]:
    from swing.latches.constants import (
        LATCH_ACTUAL_DURATIONS,
        LATCH_ACTUAL_ORDER_TYPES,
        LATCH_ATTESTED_DISPOSITIONS,
        LATCH_SIZING_BASES,
        LATCH_STATES,
        LATCH_VALIDITY_OUTCOMES,
        LATCH_VIEW_SURFACES,
        MANDATE_ORDER_DURATIONS,
        MANDATE_ORDER_TYPES,
    )
    return {
        # ---- MIRRORED: a real schema enum with a Python authority ----
        ("latch_state_at_first_view", None): LATCH_STATES,
        ("latch_state_at_last_view", None): LATCH_STATES,
        ("surface", None): LATCH_VIEW_SURFACES,
        ("intent_kind", None): LATCH_INTENT_KINDS,
        ("attested_disposition", None): LATCH_ATTESTED_DISPOSITIONS,
        ("validity_outcome", None): LATCH_VALIDITY_OUTCOMES,
        ("framework_order_type", None): MANDATE_ORDER_TYPES,
        ("framework_duration", None): MANDATE_ORDER_DURATIONS,
        ("actual_order_type", None): LATCH_ACTUAL_ORDER_TYPES,
        ("actual_duration", None): LATCH_ACTUAL_DURATIONS,
        ("derivation_sizing_basis", None): LATCH_SIZING_BASES,
        # The JSON-EXPRESSED enum. It escaped every earlier mirror list purely
        # because it is written as a `json_extract(...) IN (...)` predicate
        # rather than a column `CHECK (col IN (...))` -- a difference in SYNTAX,
        # not in kind, and exactly the shape of hole the #11 rule exists to
        # close.
        ("json_extract(validity_detail, '$.broker_snapshot_branch')", None):
            LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES,
        # ---- NO_ENUM_MIRROR, each with its reason ----
        ("actionable_at_first_view", ("0", "1")): (
            _NO_MIRROR, "a NUMERIC BOUND, not an enum"),
        ("actionable_at_last_view", ("0", "1")): (
            _NO_MIRROR, "a NUMERIC BOUND, not an enum"),
        ("actionable_ever_viewed", ("0", "1")): (
            _NO_MIRROR, "a NUMERIC BOUND, not an enum"),
        ("intent_kind", ("decline",)): (
            _NO_MIRROR, "a shape-exclusion DISCRIMINATOR on one member; the "
                        "enum itself is mirrored by the column CHECK"),
        ("intent_kind", ("attest",)): (
            _NO_MIRROR, "a shape-exclusion DISCRIMINATOR on one member"),
        ("intent_kind", ("validity",)): (
            _NO_MIRROR, "a shape-exclusion DISCRIMINATOR on one member"),
        ("intent_kind", ("decline", "place", "validity")): (
            _NO_MIRROR, "a shape-exclusion SUBSET of the mirrored enum, keyed "
                        "on the ORDER-BEARING kinds so a future kind is "
                        "excluded BY DEFAULT"),
        ("intent_kind", ("decline", "place")): (
            _NO_MIRROR, "a shape-exclusion SUBSET of the mirrored enum"),
        ("actual_order_type", ("LIMIT", "STOP_LIMIT")): (
            _NO_MIRROR, "a RESTATEMENT inside the accepted-by-broker "
                        "completeness CHECK, not its own enum"),
        ("validity_outcome", ("accepted_by_broker",)): (
            _NO_MIRROR, "a conditional DISCRIMINATOR on one enum member"),
        ("json_type(validity_detail)", ("object",)): (
            _NO_MIRROR, "a SQLite TYPE predicate, not a domain enum"),
        ("json_type(validity_detail, '$.attributable_order_count')",
         ("integer",)): (_NO_MIRROR, "a SQLite TYPE predicate"),
        ("json_type(validity_detail, '$.exact_framework_match_count')",
         ("integer",)): (_NO_MIRROR, "a SQLite TYPE predicate"),
        ("json_type(validity_detail, '$.indeterminate')", ("false", "true")): (
            _NO_MIRROR, "a SQLite TYPE predicate over a JSON boolean"),
    }


def _parsed_enum_predicates() -> dict[tuple[str, tuple[str, ...]], None]:
    """Every `<lhs> IN (<string/int literals>)` and `<lhs> = '<literal>'` in
    0033's CREATE TABLE statements, whitespace-normalised so line-WRAPPED ones
    are found (the exact shape a `grep "IN ("` misses)."""
    found: dict[tuple[str, tuple[str, ...]], None] = {}
    for table in ("latch_view_events", "latch_order_intents"):
        stmt = _normalise(_strip_sql_comments(_table_sql(table)))
        for m in re.finditer(
                r"([\w.]+(?:\([^()]*\))?)\s+(?:NOT\s+)?IN\s*\(([^()]*?)\)",
                stmt):
            lits = tuple(sorted(re.findall(r"'([^']*)'|(\d+)", m.group(2))
                                and [a or b for a, b in
                                     re.findall(r"'([^']*)'|(\d+)", m.group(2))]))
            found[(m.group(1), lits)] = None
        for m in re.finditer(r"([\w.]+)\s*=\s*'([^']*)'", stmt):
            found[(m.group(1), (m.group(2),))] = None
    return found


def test_every_in_list_predicate_in_0033_is_CLASSIFIED():
    """AN UNCLASSIFIED PREDICATE FAILS. Silence is the failure mode; annotation
    is the fix. Naming only a SUBSET is how the #11 rule gets violated while its
    own test passes."""
    manifest = _mirror_manifest()
    unclassified = []
    for lhs, lits in _parsed_enum_predicates():
        if (lhs, lits) in manifest or (lhs, None) in manifest:
            continue
        unclassified.append((lhs, lits))
    assert not unclassified, (
        "these 0033 predicates are UNCLASSIFIED -- add each to the manifest as "
        f"MIRRORED (naming its frozenset) or NO_ENUM_MIRROR (with a reason): "
        f"{unclassified}")


def test_every_mirrored_enum_agrees_between_sql_and_python():
    """The three-mirror agreement, PARSED from the migration SQL. A CHECK that
    ACCEPTS a value the Python validator REJECTS means the DB holds rows the read
    path cannot hydrate -- the dangerous asymmetry direction."""
    manifest = _mirror_manifest()
    parsed = _parsed_enum_predicates()
    checked = 0
    for lhs, expected in manifest.items():
        if lhs[1] is not None:
            continue
        column = lhs[0]
        members = {lits for (got_lhs, lits) in parsed if got_lhs == column}
        # the WIDEST parsed set for this lhs is the column's own enum CHECK;
        # the narrower ones are the classified shape-exclusion subsets.
        assert members, f"no IN/= predicate parsed for {column}"
        widest = max(members, key=len)
        assert set(widest) == set(expected), (
            f"{column}: SQL {sorted(widest)} != Python {sorted(expected)}")
        checked += 1
    assert checked == len([k for k in manifest if k[1] is None])


def test_the_model_validators_use_the_SAME_frozensets_not_copies():
    """Drift is impossible BY CONSTRUCTION, not merely detected after the fact."""
    from swing.data import models as m
    from swing.latches import constants as c
    pairs = [
        (m._LATCH_INTENT_KINDS, c.LATCH_INTENT_KINDS),
        (m._LATCH_VIEW_SURFACES, c.LATCH_VIEW_SURFACES),
        (m._LATCH_ATTESTED_DISPOSITIONS, c.LATCH_ATTESTED_DISPOSITIONS),
        (m._LATCH_VALIDITY_OUTCOMES, c.LATCH_VALIDITY_OUTCOMES),
        (m._LATCH_ACTUAL_ORDER_TYPES, c.LATCH_ACTUAL_ORDER_TYPES),
        (m._LATCH_ACTUAL_DURATIONS, c.LATCH_ACTUAL_DURATIONS),
        (m._LATCH_SIZING_BASES, c.LATCH_SIZING_BASES),
        (m._MANDATE_ORDER_TYPES, c.MANDATE_ORDER_TYPES),
        (m._MANDATE_ORDER_DURATIONS, c.MANDATE_ORDER_DURATIONS),
        (m._LATCH_BROKER_SNAPSHOT_KEYS, c.LATCH_BROKER_SNAPSHOT_KEYS),
        (m._LATCH_SNAPSHOT_BRANCHES,
         c.LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES),
    ]
    for got, want in pairs:
        assert got is want


# --------------------------------------------------------------------------
# helpers for the view-events raw inserts
# --------------------------------------------------------------------------
def _seed_candidate(conn) -> None:
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T20:06:25', '2026-07-17', '2026-07-20', "
            "1, 1, 0, 0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
            "close, pivot, initial_stop, rs_method) VALUES "
            "(1, 121, 'FTRE', 'aplus', 18.34, 18.34, 14.88, 'universe')")


def _insert_view(conn, cid: int, *, first: int = 1, last: int = 1,
                 ever: int = 1, surface: str = "latch_panel",
                 view_session_date: str = "2026-07-29",
                 first_viewed_ts: str = "2026-07-29T10:00:00",
                 last_viewed_ts: str = "2026-07-29T11:00:00") -> int:
    cur = conn.execute(
        "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, "
        "ticker, detection_date, pipeline_run_id, surface, view_session_date, "
        "first_viewed_ts, last_viewed_ts, view_count, "
        "latch_state_at_first_view, latch_state_at_last_view, "
        "actionable_at_first_view, actionable_at_last_view, "
        "actionable_ever_viewed) VALUES "
        "(?, 121, 'FTRE', '2026-07-20', NULL, ?, ?, ?, ?, 1, 'armed', 'armed', "
        "?, ?, ?)",
        (cid, surface, view_session_date, first_viewed_ts, last_viewed_ts,
         first, last, ever))
    return int(cur.lastrowid)
