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

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ReconciliationCorrection
from swing.data.repos.reconciliation_corrections import insert_correction
from swing.trades.reconciliation_auto_correct import (
    ImmutableJournalFieldError,
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
) -> dict[str, Any]:
    """A trade carrying a minted token + a TRADES-anchored discrepancy.

    `fill_id` is deliberately NULL so `_resolve_affected_target` resolves to
    `trades` (its precedence puts `fills` first whenever a fill_id is present).

    `tier2=True` plants the pending-ambiguity shape the tier-2 surface needs.
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
            "unsupported" if tier2 else None,
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
