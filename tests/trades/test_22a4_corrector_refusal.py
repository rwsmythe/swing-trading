"""22-A4 Task 1b -- the corrector REFUSES `trades.attempt_id` with a typed error.

(m8a), (m8b), (m8d) of the plan's S3 roster.

CHARC's attached condition on the 22-A4 authorization: the tier-2 corrector
ADMITS `field_name="attempt_id"` today and migration 0038's write-once trigger
then ABORTs it, so the operator receives a raw `sqlite3.IntegrityError` --
authorize-then-abort, the class he ruled binding on 2026-09-01. The trigger
stays the guard of record (it covers writers not yet written); the typed
refusal is its LEGIBLE FACE.

Pre-fix for every row here is the RED the plan declares: `sqlite3.IntegrityError`
raised by `trg_trades_attempt_id_immutable` AFTER the corrector has already
authorized the write (and, on the multi-field and tier-3 paths, after earlier
writes have executed).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import swing.trades.reconciliation_auto_correct as reconciliation_auto_correct_mod
from swing.data.db import ensure_schema
from swing.data.models import ReconciliationCorrection
from swing.data.repos.reconciliation_corrections import insert_correction
from swing.trades.reconciliation_auto_correct import (
    ImmutableJournalFieldError,
    ReservedJournalFieldError,
    _apply_tier3_override_inner,
    apply_tier2_resolution,
    apply_tier3_override,
)

# 36 characters each, the shape migration 0038's CHECK admits.
MINTED_TOKEN = "11111111-2222-4333-8444-555555555555"
OTHER_TOKEN = "99999999-8888-4777-8666-555555555555"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _seed_trade_anchored_world(
    conn: sqlite3.Connection, *, tier2: bool = True,
    ambiguity_kind: str = "unsupported",
) -> dict[str, Any]:
    """A trade carrying a minted token + a TRADES-anchored discrepancy.

    `fill_id` is deliberately NULL so `_resolve_affected_target` resolves to
    `trades` (its precedence puts `fills` first whenever a fill_id is present).

    `tier2=True` plants the pending-ambiguity shape the tier-2 surface needs,
    under `ambiguity_kind` (default `"unsupported"`, which is what every
    pre-existing caller here needs; pass e.g. `"validator_rejected"` for a
    caller that dispatches to a different tier-2 handler).
    `tier2=False` plants an `unresolved` / NULL-`ambiguity_kind` row, which is
    what the TIER-3 surface needs: the schema's cross-column CHECK pairs
    `ambiguity_kind IS NOT NULL` with the two ambiguity resolutions ONLY, so a
    successful tier-3 override (which stamps `operator_overridden`) is
    schema-illegal against a pending-ambiguity row. Using the tier-2 shape for
    the tier-3 negative control would have made that control unsatisfiable for
    a reason unrelated to this task.
    """
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at, attempt_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00", MINTED_TOKEN),
    )
    trade_id = int(cur.lastrowid)
    run_cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES (?, ?, ?)",
        ("schwab_api", "2026-09-07T12:00:00", "running"),
    )
    run_id = int(run_cur.lastrowid)
    disc_cur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, material_to_review,
            resolution, ambiguity_kind, resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "stop_mismatch", trade_id, None, "CVGI", "current_stop",
            '{"current_stop": 4.0}', '{"current_stop": 4.5}', 1,
            "pending_ambiguity_resolution" if tier2 else "unresolved",
            ambiguity_kind if tier2 else None,
            "classifier did not recognize the shape" if tier2 else None,
            "2026-09-07T12:00:00",
        ),
    )
    disc_id = int(disc_cur.lastrowid)
    conn.commit()
    return {"trade_id": trade_id, "run_id": run_id, "discrepancy_id": disc_id}


def _seed_correction_head(
    conn: sqlite3.Connection, world: dict[str, Any],
) -> int:
    """An unsuperseded single-row `trades`-anchored correction head to override."""
    head = ReconciliationCorrection(
        correction_id=0,
        discrepancy_id=world["discrepancy_id"],
        correction_action="operator_resolved_ambiguity",
        correction_choice="operator_truth",
        affected_table="trades",
        affected_row_id=world["trade_id"],
        field_name="current_stop",
        pre_correction_value_json='{"current_stop": 4.0}',
        source_canonical_value_json='{"current_stop": 4.5}',
        applied_value_json='{"current_stop": 4.5}',
        operator_truth_value_json=None,
        applied_at="2026-09-07T12:05:00.000Z",
        applied_by="operator",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=None,
        schwab_api_call_id=None,
        reconciliation_run_id=world["run_id"],
        correction_reason="seed head",
        notes=None,
    )
    correction_id = insert_correction(conn, head)
    conn.commit()
    return correction_id


class _StatementTrace:
    """Collect every statement the connection executes.

    `set_trace_callback` fires per prepared statement, which is what makes the
    (m8b)/(m8d) discriminators possible: the persisted STATE after a refusal is
    identical under a preflight and under a backstop-only implementation
    whenever an outer transaction rolls back, so the assertion has to be on the
    WORK THAT WAS DONE, not on the state that survived.
    """

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __call__(self, sql: str) -> None:
        self.statements.append(" ".join(str(sql).split()))

    def count_startswith(self, prefix: str) -> int:
        upper = prefix.upper()
        return sum(1 for s in self.statements if s.upper().startswith(upper))


def _journal_update_count(trace: _StatementTrace) -> int:
    return (
        trace.count_startswith("UPDATE trades SET")
        + trace.count_startswith("UPDATE fills SET")
    )


# ---------------------------------------------------------------------------
# (m8a) SERVICE -- the typed refusal
# ---------------------------------------------------------------------------


def test_m8a_tier2_operator_truth_refuses_attempt_id_with_a_typed_error(
    conn: sqlite3.Connection,
) -> None:
    """Pre-fix: `sqlite3.IntegrityError` from `trg_trades_attempt_id_immutable`
    -- the corrector authorized the write and the database aborted it.
    Post-fix: exactly `ImmutableJournalFieldError`, the token unchanged, and a
    message naming the column as WRITE-ONCE IDENTITY that no surface writes."""
    world = _seed_trade_anchored_world(conn)

    with pytest.raises(ImmutableJournalFieldError) as exc:
        apply_tier2_resolution(
            conn,
            discrepancy_id=world["discrepancy_id"],
            choice_code="operator_truth",
            operator_custom_payload={"attempt_id": OTHER_TOKEN},
            operator_reason="broker says the attempt token was different",
        )

    message = str(exc.value)
    assert "trades.attempt_id" in message
    assert "WRITE-ONCE" in message
    assert "no surface writes" in message.lower()
    assert message.endswith("Nothing was written.")

    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == MINTED_TOKEN


def test_m8a_the_refusal_is_a_ValueError_so_both_delivery_handlers_reach_it(
) -> None:
    """The TYPE is the condition, not a style choice.

    `ReservedJournalFieldError` inherits directly from `Exception`, and BOTH
    delivery callers catch `ValueError` with no handler for a bare `Exception`
    subclass -- so a bare-`Exception` refusal would surface as an uncaught CLI
    traceback and a web 500, which is the same operator experience the
    condition exists to replace, arriving one layer out."""
    assert issubclass(ImmutableJournalFieldError, ValueError)


# ---------------------------------------------------------------------------
# (m8b) ORDER-INDEPENDENCE -- the preflight half
# ---------------------------------------------------------------------------


def test_m8b_multi_field_refusal_issues_zero_journal_updates(
    conn: sqlite3.Connection,
) -> None:
    """An ordinary field FIRST and `attempt_id` LAST.

    Post-fix: the preflight refuses before any write -- ZERO journal UPDATE
    statements, no correction row, and the discrepancy still pending.
    Against a backstop-only implementation (the check only in
    `_update_journal_field`) the ordinary field's UPDATE has ALREADY executed
    when the refusal fires, so the statement count is non-zero -- the JSON-key-
    order dependence the module's own comment says it was restructured to
    eliminate."""
    world = _seed_trade_anchored_world(conn)
    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ImmutableJournalFieldError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_truth",
                operator_custom_payload={
                    "current_stop": 4.5,
                    "attempt_id": OTHER_TOKEN,
                },
                operator_reason="ordinary field first, attempt_id last",
            )
    finally:
        conn.set_trace_callback(None)

    assert _journal_update_count(trace) == 0, trace.statements
    assert trace.count_startswith("INSERT INTO reconciliation_corrections") == 0

    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.0
    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == MINTED_TOKEN
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (world["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"


def test_m8b_the_refusal_does_not_depend_on_json_key_order(
    conn: sqlite3.Connection,
) -> None:
    """`attempt_id` FIRST gets the same answer as `attempt_id` LAST."""
    world = _seed_trade_anchored_world(conn)
    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ImmutableJournalFieldError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_truth",
                operator_custom_payload={
                    "attempt_id": OTHER_TOKEN,
                    "current_stop": 4.5,
                },
                operator_reason="attempt_id first",
            )
    finally:
        conn.set_trace_callback(None)
    assert _journal_update_count(trace) == 0, trace.statements
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.0


def test_m8b_a_non_immutable_multi_field_correction_still_applies(
    conn: sqlite3.Connection,
) -> None:
    """The negative control: the refusal is exactly as wide as the new
    immutable set. A widening that swept in ordinary `trades` columns would
    remove a legitimate tier-2 capability."""
    world = _seed_trade_anchored_world(conn)
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=world["discrepancy_id"],
        choice_code="operator_truth",
        operator_custom_payload={"current_stop": 4.5, "state": "managing"},
        operator_reason="ordinary multi-field correction",
    )
    assert result.correction_id is not None
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.5


# ---------------------------------------------------------------------------
# (B-1) THE THIRD CORRECTOR PATH -- `operator_alternative`, which
# `_preflight_reserved_transitions` never reaches. Reviewer B found this on
# `84e90bab`; CHARC ruled it INTRODUCED, IN ENVELOPE, 2026-09-08 (the fix
# leg's own ledger). `("validator_rejected", "operator_alternative")` routes
# through `_handle_single_field_correction`, which selected
# `field_name = next(iter(correction_target.keys()))` and handed the
# immutable guard ONLY that one key -- so a two-key payload's `attempt_id`
# was silently dropped whenever `current_stop` happened to be first.
# ---------------------------------------------------------------------------


def test_b1_operator_alternative_refuses_trailing_attempt_id_with_zero_writes(
    conn: sqlite3.Connection,
) -> None:
    """The trailing-key row: `current_stop` first, `attempt_id` last.

    Pre-fix (reproduced live at QA on `84e90bab`): NO exception at all --
    `_handle_single_field_correction` selected `current_stop` as the sole
    field, wrote it, left `attempt_id` untouched, and terminalized the
    discrepancy as `operator_resolved_ambiguity`. Post-fix: the whole-payload
    immutable guard fires before the field-name selection, so the answer does
    not depend on which key came first.
    """
    world = _seed_trade_anchored_world(conn, ambiguity_kind="validator_rejected")
    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ImmutableJournalFieldError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_alternative",
                operator_custom_payload={
                    "current_stop": 4.5,
                    "attempt_id": OTHER_TOKEN,
                },
                operator_reason="ordinary field first, attempt_id last",
            )
    finally:
        conn.set_trace_callback(None)

    assert _journal_update_count(trace) == 0, trace.statements
    assert trace.count_startswith("INSERT INTO reconciliation_corrections") == 0

    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.0
    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == MINTED_TOKEN
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (world["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"


def test_b1_operator_alternative_refuses_leading_attempt_id_with_zero_writes(
    conn: sqlite3.Connection,
) -> None:
    """The leading-key row: `attempt_id` first gets the same answer as
    `attempt_id` last -- the defect was key-order dependent and the fix must
    not be."""
    world = _seed_trade_anchored_world(conn, ambiguity_kind="validator_rejected")
    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ImmutableJournalFieldError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_alternative",
                operator_custom_payload={
                    "attempt_id": OTHER_TOKEN,
                    "current_stop": 4.5,
                },
                operator_reason="attempt_id first",
            )
    finally:
        conn.set_trace_callback(None)

    assert _journal_update_count(trace) == 0, trace.statements
    assert trace.count_startswith("INSERT INTO reconciliation_corrections") == 0

    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.0
    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == MINTED_TOKEN
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (world["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"


# ---------------------------------------------------------------------------
# (m8d) THE TIER-3 OVERRIDE PATH -- the surface the preflight never reached
# ---------------------------------------------------------------------------


def test_m8d_tier3_override_refuses_before_step_4(
    conn: sqlite3.Connection,
) -> None:
    """`apply_tier3_override` with an ordinary field FIRST and `attempt_id` LAST.

    `_preflight_reserved_transitions` is called from exactly one place --
    `_handle_multi_field_correction` -- and NOT from
    `_apply_tier3_override_inner`, which is a supported operator surface
    (`swing journal discrepancy override-correction`). That path INSERTs the
    new correction row (step 4), advances the prior row's
    `superseded_by_correction_id` (step 5), and only then walks the payload
    field by field (step 6).

    The STATEMENT COUNTS are the discriminator, not the persisted state: the
    public entry point owns the ROLLBACK, so a backstop-only implementation
    raises the SAME typed error and leaves the SAME state -- and a state-only
    assertion would certify it. Under backstop-only the counts read >= 3 (the
    correction INSERT, the supersession UPDATE, and the first field's UPDATE).
    """
    world = _seed_trade_anchored_world(conn, tier2=False)
    head_id = _seed_correction_head(conn, world)

    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ImmutableJournalFieldError):
            apply_tier3_override(
                conn,
                correction_id=head_id,
                operator_truth_value={
                    "current_stop": 4.5,
                    "attempt_id": OTHER_TOKEN,
                },
                operator_reason="operator override naming the attempt token",
            )
    finally:
        conn.set_trace_callback(None)

    assert trace.count_startswith("INSERT INTO reconciliation_corrections") == 0
    assert trace.count_startswith("UPDATE reconciliation_corrections") == 0
    assert trace.count_startswith("UPDATE trades") == 0, trace.statements


def test_m8d_tier3_inner_on_the_composition_surface_writes_nothing(
    conn: sqlite3.Connection,
) -> None:
    """The module's own documented composition surface -- its docstring invites
    callers to compose via `_apply_tier3_override_inner` inside an existing tx,
    and such a caller owns the rollback.

    So: hold the transaction, call the inner directly, ROLL BACK NOTHING, and
    read. Post-fix, no NEW correction row exists and the seeded head is still
    the chain head (the plan's "zero rows" is zero NEW rows -- a tier-3
    override targets an existing head by construction). Against a
    backstop-only implementation a correction row EXISTS and the head's
    `superseded_by_correction_id` has MOVED -- persisted, because on this
    surface nobody rolled back.

    Reading on the writer's own connection inside the open transaction is the
    correct instrument HERE: the question is what was WRITTEN, not what is
    durable, and only this connection can see uncommitted work.
    """
    world = _seed_trade_anchored_world(conn, tier2=False)
    head_id = _seed_correction_head(conn, world)

    conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(ImmutableJournalFieldError):
            _apply_tier3_override_inner(
                conn,
                correction_id=head_id,
                operator_truth_value={
                    "current_stop": 4.5,
                    "attempt_id": OTHER_TOKEN,
                },
                operator_reason="composed inside a caller-held transaction",
            )
        rows = conn.execute(
            "SELECT correction_id, superseded_by_correction_id "
            "FROM reconciliation_corrections ORDER BY correction_id",
        ).fetchall()
        assert rows == [(head_id, None)], rows
        assert conn.execute(
            "SELECT current_stop, attempt_id FROM trades WHERE id = ?",
            (world["trade_id"],),
        ).fetchone() == (4.0, MINTED_TOKEN)
    finally:
        conn.rollback()


def test_m8d_a_non_immutable_tier3_override_still_applies(
    conn: sqlite3.Connection,
) -> None:
    """Negative control on the tier-3 surface: the head refusal must not
    refuse an ordinary override."""
    world = _seed_trade_anchored_world(conn, tier2=False)
    head_id = _seed_correction_head(conn, world)
    result = apply_tier3_override(
        conn,
        correction_id=head_id,
        operator_truth_value={"current_stop": 4.75},
        operator_reason="ordinary tier-3 override",
    )
    assert result.correction_id != head_id
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == 4.75
    assert conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?", (head_id,),
    ).fetchone()[0] == result.correction_id


# ---------------------------------------------------------------------------
# (m8e) THE NEGATIVE CONTROL ON THE WIDENING
# ---------------------------------------------------------------------------
# (m8e) ONCE HELD TWO PARAMETRIZED ROWS asserting that `ATTEMPT_ID`,
# `Attempt_Id`, `[attempt_id]` and `"attempt_id"` each raised the typed,
# `ValueError`-derived `ImmutableJournalFieldError`. They are SUPERSEDED BY
# REPLACEMENT by the (m8f) closure block below -- not relaxed, and not merely
# renumbered.
#
# WHY THEY COULD NOT SURVIVE THE FIX: `A4X-R3-03` found that the resolved-name
# normalizer those rows pinned missed three FURTHER spellings, and CHARC ruled
# (2026-09-08) that THE ENUMERATION IS THE DEFECT -- SQLite's identifier
# grammar is not the corrector's to re-implement. Under the byte-exact-first
# invariant that replaced it, no non-canonical spelling reaches the immutable
# check at all, so `ImmutableJournalFieldError` is the WRONG assertion for a
# variant: a test still demanding it would require the very resolver whose
# deletion is the fix. (m8f) covers all SEVEN known spellings, on BOTH surfaces,
# under the strictly stronger zero-rows-written assertion, and pins separately
# that the CANONICAL spelling keeps the typed `ValueError` refusal both
# delivery handlers reach.
#
# THE ONE CLAIM (m8e) STILL OWNS is the negative control below. It is not a
# weaker (m8f) row: it excludes the defect ONE DOOR DOWN -- a check that
# refuses a legitimate column because its name merely CONTAINS an immutable
# one. Byte-exactness and substring matching agree on every (m8f) row and
# disagree only here.


def test_m8e_a_column_that_merely_CONTAINS_the_name_is_not_refused(
    conn: sqlite3.Connection,
) -> None:
    """The negative control on the widening: normalisation must not turn the
    exact-membership test into a substring test. `current_stop` is a real,
    correctable column and must still apply."""
    world = _seed_trade_anchored_world(conn, tier2=False)
    head_id = _seed_correction_head(conn, world)
    result = apply_tier3_override(
        conn,
        correction_id=head_id,
        operator_truth_value={"current_stop": 4.25},
        operator_reason="the widening must not over-refuse",
    )
    assert result.correction_id != head_id


# ---------------------------------------------------------------------------
# (m8f) THE CLOSURE TEST -- BYTE-EXACT FIRST, SO NO NON-CANONICAL SPELLING
#       SURVIVES TO ANY NAME-INTERPRETING CHECK (CHARC, 2026-09-08, R2)
# ---------------------------------------------------------------------------
# `A4X-R3-03` found a THIRD and FOURTH quoting form after the first three were
# enumerated -- `'attempt_id'`, `(attempt_id)` and `/*x*/attempt_id` all reach
# the column through `UPDATE ... SET`, and the resolved-name normalizer (which
# stripped ONE matched pair from `[]`, `""` and backticks, then casefolded)
# returned every one of them UNCHANGED. THE ENUMERATION IS THE DEFECT: SQLite's
# identifier grammar is not this module's to re-implement.
#
# The ruled invariant, and what these rows measure: the operator-supplied field
# name is validated BYTE-EXACT against `PRAGMA table_info` as the FIRST gate on
# every corrector path -- before any check that INTERPRETS the name and before
# any write -- so every later check, the immutable membership included, compares
# the CANONICAL name only.
#
# THE NAIVE SUBSTITUTES EACH ROW FAILS AGAINST, and they are two different
# implementations rather than one:
#   * a BYTE-EXACT-ONLY immutable set with no first gate (the pre-`74cb2815`
#     shape): `ATTEMPT_ID`, `[attempt_id]` and a double-quoted spelling miss the
#     early check entirely, tier-3 steps 4 and 5 WRITE, and the refusal arrives
#     at step 6.
#   * the SHIPPED NORMALIZER (`74cb2815`): the same holds for `'attempt_id'`,
#     `(attempt_id)` and `/*x*/attempt_id`, which its three-pair strip does not
#     touch -- and for the first three it raises `ImmutableJournalFieldError`,
#     which is NOT what a byte-exact-first implementation raises, so every row
#     here is red against it too.
#
# WHAT THE SURVIVING REFUSAL IS, stated rather than implied: a non-canonical
# spelling is refused by the byte-exact gate as `ReservedJournalFieldError`,
# which derives from bare `Exception` and reaches NEITHER delivery handler.
# That legibility gap is D34's -- the register's third instance, CHARC
# 2026-09-08 -- and is deliberately NOT closed here. The reason text is already
# right. The CANONICAL spelling still gets the typed, `ValueError`-derived
# `ImmutableJournalFieldError` that reaches both handlers; the last row pins it.
_NON_CANONICAL_SPELLINGS = (
    "ATTEMPT_ID",          # R1 Major 3 -- casing
    "Attempt_Id",          # A4X-R4-02 -- mixed casing; (m8e) named it, (m8f)
                           # dropped it on the SUPERSEDED-BY-REPLACEMENT pass
    "[attempt_id]",        # R1 Major 3 -- bracket quoting
    '"attempt_id"',        # R1 Major 3 -- double quoting
    "'attempt_id'",        # R3-03 -- single quoting
    "(attempt_id)",        # R3-03 -- parenthesised
    "/*x*/attempt_id",     # R3-03 -- leading comment
)


@pytest.mark.parametrize("spelling", _NON_CANONICAL_SPELLINGS)
def test_m8f_tier3_composition_surface_writes_zero_rows_for_any_spelling(
    conn: sqlite3.Connection, spelling: str,
) -> None:
    """ZERO rows written, INCLUDING tier-3 steps 4 and 5's rows.

    The composition surface is the instrument: the caller holds the
    transaction and rolls back NOTHING, so a refusal that arrives at step 6
    leaves the new correction row and the advanced chain pointer PERSISTED and
    readable. The statement trace is asserted alongside the persisted state
    because on the PUBLIC entry point the rollback would hide both.
    """
    world = _seed_trade_anchored_world(conn, tier2=False)
    head_id = _seed_correction_head(conn, world)

    trace = _StatementTrace()
    conn.execute("BEGIN IMMEDIATE")
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ReservedJournalFieldError) as exc:
            _apply_tier3_override_inner(
                conn,
                correction_id=head_id,
                operator_truth_value={
                    "current_stop": 4.5,
                    spelling: OTHER_TOKEN,
                },
                operator_reason="a non-canonical spelling of a write-once column",
            )
        assert "must match a real column EXACTLY" in str(exc.value)
        # NOT the immutable check's error: byte-exact ran FIRST, so the
        # spelling never reached a check that interprets the name.
        assert not isinstance(exc.value, ImmutableJournalFieldError)
        assert trace.count_startswith(
            "INSERT INTO reconciliation_corrections",
        ) == 0, trace.statements
        assert trace.count_startswith(
            "UPDATE reconciliation_corrections",
        ) == 0, trace.statements
        assert _journal_update_count(trace) == 0, trace.statements
        assert conn.execute(
            "SELECT correction_id, superseded_by_correction_id "
            "FROM reconciliation_corrections ORDER BY correction_id",
        ).fetchall() == [(head_id, None)]
        assert conn.execute(
            "SELECT current_stop, attempt_id FROM trades WHERE id = ?",
            (world["trade_id"],),
        ).fetchone() == (4.0, MINTED_TOKEN)
    finally:
        conn.set_trace_callback(None)
        conn.rollback()


@pytest.mark.parametrize("spelling", _NON_CANONICAL_SPELLINGS)
def test_m8f_tier2_multi_field_refuses_any_spelling_before_the_first_update(
    conn: sqlite3.Connection, spelling: str,
) -> None:
    """The ordinary field FIRST and the spelling LAST -- the whole-payload
    property `_preflight_reserved_transitions` was built for, now carried by
    the byte-exact gate as well. A backstop-only byte-exact check would let
    `current_stop`'s UPDATE execute before the spelling was reached."""
    world = _seed_trade_anchored_world(conn)
    trace = _StatementTrace()
    conn.set_trace_callback(trace)
    try:
        with pytest.raises(ReservedJournalFieldError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_truth",
                operator_custom_payload={
                    "current_stop": 4.5,
                    spelling: OTHER_TOKEN,
                },
                operator_reason="ordinary field first, a spelling last",
            )
    finally:
        conn.set_trace_callback(None)

    assert _journal_update_count(trace) == 0, trace.statements
    assert trace.count_startswith("INSERT INTO reconciliation_corrections") == 0
    assert conn.execute(
        "SELECT current_stop, attempt_id FROM trades WHERE id = ?",
        (world["trade_id"],),
    ).fetchone() == (4.0, MINTED_TOKEN)


def test_m8f_the_canonical_spelling_keeps_the_typed_ValueError_refusal(
    conn: sqlite3.Connection,
) -> None:
    """Byte-exactness must not be bought with the typed refusal.

    `attempt_id` IS a byte-exact column, so it passes the first gate and
    reaches the immutable membership check, which raises the
    `ValueError`-derived `ImmutableJournalFieldError` both delivery handlers
    name. An implementation that put the immutable set behind the byte-exact
    gate but DROPPED it would fail here.
    """
    world = _seed_trade_anchored_world(conn)
    with pytest.raises(ImmutableJournalFieldError) as exc:
        apply_tier2_resolution(
            conn,
            discrepancy_id=world["discrepancy_id"],
            choice_code="operator_truth",
            operator_custom_payload={"attempt_id": OTHER_TOKEN},
            operator_reason="the canonical spelling",
        )
    assert isinstance(exc.value, ValueError)
    assert "trades.attempt_id" in str(exc.value)


# ---------------------------------------------------------------------------
# (m8g) THE `operator_alternative` PATH -- the corrector path (m8f)'s closure
#       test never reaches (`A4X-R4-01`, CHARC 2026-09-08).
# ---------------------------------------------------------------------------
# `_handle_operator_alternative` -> `_handle_single_field_correction` is the
# third of the four corrector paths named at
# `reconciliation_auto_correct.py:2745`'s comment, and it is the one path
# every (m8f) row above does NOT close: those rows drive `operator_truth`
# (via `apply_tier2_resolution`) and `_apply_tier3_override_inner` directly,
# never `choice_code="operator_alternative"`. The byte-exact gate at that line
# was added so "every corrector path" would be literally true; deleting it
# still leaves every (m8f) row passing.
#
# ZERO-WRITE ASSERTIONS CANNOT DISCRIMINATE THIS MUTANT: `_update_journal_
# field`'s OWN singular `_assert_real_column_name` backstop still runs before
# any UPDATE on this path too, so a journal-write-count assertion reads 0
# whether the gate at `:2745` is present or not. What the gate's absence
# actually exposes is that `_validate_correction_target` (which INTERPRETS
# the name semantically) and `_read_journal_value` (whose SELECT interpolates
# the name directly) would each be REACHED on the raw, un-gated spelling --
# so the discriminator spies on those two functions and asserts NEITHER is
# called, not on what got written.


@pytest.mark.parametrize("spelling", _NON_CANONICAL_SPELLINGS)
def test_m8g_operator_alternative_reaches_neither_semantic_check_for_any_spelling(
    conn: sqlite3.Connection, spelling: str,
) -> None:
    world = _seed_trade_anchored_world(
        conn, ambiguity_kind="validator_rejected",
    )

    real_validate = reconciliation_auto_correct_mod._validate_correction_target
    real_read = reconciliation_auto_correct_mod._read_journal_value
    with (
        patch.object(
            reconciliation_auto_correct_mod, "_validate_correction_target",
            wraps=real_validate,
        ) as validate_spy,
        patch.object(
            reconciliation_auto_correct_mod, "_read_journal_value",
            wraps=real_read,
        ) as read_spy,
    ):
        with pytest.raises(ReservedJournalFieldError) as exc:
            apply_tier2_resolution(
                conn,
                discrepancy_id=world["discrepancy_id"],
                choice_code="operator_alternative",
                operator_custom_payload={spelling: OTHER_TOKEN},
                operator_reason=(
                    "a non-canonical spelling via the operator_alternative "
                    "surface"
                ),
            )
        assert "must match a real column EXACTLY" in str(exc.value)
        assert validate_spy.call_count == 0
        assert read_spy.call_count == 0

    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (world["trade_id"],),
    ).fetchone()[0] == MINTED_TOKEN
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
