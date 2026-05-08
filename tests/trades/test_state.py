"""State-machine service tests — 25-cell transition matrix + validation.

Spec §3.5.1: per-operation required-field tuple. ALLOWED_TRANSITIONS:
5 allowed pairs out of 25 (5×5).
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.trades.state import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransition,
    MissingPreTradeFieldsException,
    OPERATION_REQUIRED_FIELDS,
    state_transition,
    validate_for_operation,
)


ALL_STATES = ["entered", "managing", "partial_exited", "closed", "reviewed"]


def _seed_v14(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    return conn


def _seed_trade_in_state(conn, state: str) -> int:
    trade = Trade(
        id=None, ticker="TST", entry_date="2026-05-01",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T16:00:00",
    )
    return insert_trade_with_event(conn, trade, event_ts="2026-05-01T16:00:00")


@pytest.mark.parametrize("from_state,to_state", [
    (f, t) for f in ALL_STATES for t in ALL_STATES
])
def test_transition_matrix_25_cells(tmp_path, from_state, to_state):
    """5x5 transition matrix: 5 allowed, 20 rejected."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade_in_state(conn, from_state)
    is_allowed = (from_state, to_state) in ALLOWED_TRANSITIONS
    if is_allowed:
        with conn:
            state_transition(
                conn, trade_id=trade_id, new_state=to_state,
                event_ts="2026-05-02T16:00:00",
            )
        cur = conn.execute("SELECT state FROM trades WHERE id = ?", (trade_id,))
        assert cur.fetchone()[0] == to_state
    else:
        with pytest.raises(InvalidStateTransition):
            with conn:
                state_transition(
                    conn, trade_id=trade_id, new_state=to_state,
                    event_ts="2026-05-02T16:00:00",
                )


def test_allowed_transitions_count_is_exactly_5():
    """Sanity: no over- or under-counting in the allowed set."""
    assert len(ALLOWED_TRANSITIONS) == 5


def test_allowed_transitions_set_contents():
    """Spec-locked: 5 allowed pairs."""
    assert ALLOWED_TRANSITIONS == frozenset({
        ("entered", "managing"),
        ("managing", "partial_exited"),
        ("managing", "closed"),
        ("partial_exited", "closed"),
        ("closed", "reviewed"),
    })


def test_validate_for_operation_entry_create_rejects_missing_thesis():
    req = {
        "ticker": "TST", "entry_date": "2026-05-01", "entry_price": 10.0,
        "initial_shares": 100, "initial_stop": 9.0,
        "trade_origin": "manual_off_pipeline",
        "pre_trade_locked_at": "2026-05-01T16:00:00",
        # 'thesis' missing
        "why_now": "x", "invalidation_condition": "y", "expected_scenario": "z",
        "premortem_technical": "a", "premortem_market_sector": "b",
        "premortem_execution": "c",
        "event_risk_present": 0, "gap_risk_present": 0,
        "emotional_state_pre_trade": '["calm"]',
        "market_regime": "Bullish", "catalyst": "technical_only",
        "manual_entry_confidence": "normal",
    }
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert "thesis" in missing


def test_validate_for_operation_entry_create_complete_passes():
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["entry_create"]}
    req["entry_price"] = 10.0
    req["initial_shares"] = 100
    req["initial_stop"] = 9.0
    req["event_risk_present"] = 0
    req["gap_risk_present"] = 0
    req["emotional_state_pre_trade"] = '["calm"]'
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert missing == []


def test_validate_for_operation_transition_managing_no_required_fields():
    """transition_managing has no required fields (trigger event suffices)."""
    missing = validate_for_operation({}, op="transition_managing", current_state="entered")
    assert missing == []


def test_validate_for_operation_transition_reviewed_requires_phase6_fields():
    req = {}
    missing = validate_for_operation(req, op="transition_reviewed", current_state="closed")
    for required in (
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence",
        "lesson_learned",
    ):
        assert required in missing


@pytest.mark.parametrize("missing_field", [
    "reviewed_at", "mistake_tags",
    "entry_grade", "management_grade", "exit_grade", "process_grade",
    "disqualifying_process_violation",
    "realized_R_if_plan_followed",
    "mistake_cost_confidence",
    "lesson_learned",
])
def test_transition_reviewed_per_field_discriminator(missing_field):
    """Discriminating per-field test: each Phase 6 review field, removed individually,
    surfaces in the missing list."""
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["transition_reviewed"]}
    req["disqualifying_process_violation"] = 0
    req["realized_R_if_plan_followed"] = 0.0
    del req[missing_field]
    missing = validate_for_operation(req, op="transition_reviewed", current_state="closed")
    assert missing_field in missing


def test_validate_for_operation_event_risk_conditional():
    """When event_risk_present=1, event_handling/type/date become required."""
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["entry_create"]}
    req["entry_price"] = 10.0
    req["initial_shares"] = 100
    req["initial_stop"] = 9.0
    req["event_risk_present"] = 1  # gating
    req["gap_risk_present"] = 0
    req["emotional_state_pre_trade"] = '["calm"]'
    # event_handling/type/date missing
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    for required in ("event_handling", "event_type", "event_date"):
        assert required in missing


def test_validate_for_operation_gap_risk_conditional():
    """When gap_risk_present=1, gap_risk_handling becomes required."""
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["entry_create"]}
    req["entry_price"] = 10.0
    req["initial_shares"] = 100
    req["initial_stop"] = 9.0
    req["event_risk_present"] = 0
    req["gap_risk_present"] = 1  # gating
    req["emotional_state_pre_trade"] = '["calm"]'
    # gap_risk_handling missing
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert "gap_risk_handling" in missing


def test_validate_for_operation_catalyst_other_conditional():
    """When catalyst='other', catalyst_other_description becomes required."""
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["entry_create"]}
    req["entry_price"] = 10.0
    req["initial_shares"] = 100
    req["initial_stop"] = 9.0
    req["event_risk_present"] = 0
    req["gap_risk_present"] = 0
    req["emotional_state_pre_trade"] = '["calm"]'
    req["catalyst"] = "other"  # gating
    # catalyst_other_description missing (not in OPERATION_REQUIRED_FIELDS, but conditional)
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert "catalyst_other_description" in missing


def test_state_transition_writes_trade_events_audit_row(tmp_path):
    """state_transition emits a 'note'-type trade_events row with structured payload."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade_in_state(conn, "entered")
    with conn:
        state_transition(
            conn, trade_id=trade_id, new_state="managing",
            event_ts="2026-05-02T16:00:00", rationale="first stop adjust",
        )
    rows = conn.execute(
        "SELECT event_type, payload_json, rationale, notes FROM trade_events "
        "WHERE trade_id = ? ORDER BY id DESC LIMIT 1", (trade_id,),
    ).fetchall()
    assert len(rows) == 1
    event_type, payload_json, rationale, notes = rows[0]
    assert event_type == "note"
    assert "managing" in payload_json
    assert "entered" in payload_json
    assert rationale == "first stop adjust"
    assert "state_transition" in notes


def test_state_transition_unknown_state_raises(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade_in_state(conn, "entered")
    with pytest.raises(InvalidStateTransition, match="unknown state"):
        with conn:
            state_transition(
                conn, trade_id=trade_id, new_state="bogus_state",
                event_ts="2026-05-02T16:00:00",
            )


def test_state_transition_unknown_trade_id_raises(tmp_path):
    conn = _seed_v14(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        with conn:
            state_transition(
                conn, trade_id=9999, new_state="managing",
                event_ts="2026-05-02T16:00:00",
            )


def test_missing_pre_trade_fields_exception_carries_field_list():
    exc = MissingPreTradeFieldsException(missing_fields=["thesis", "why_now"])
    assert exc.missing_fields == ["thesis", "why_now"]
    assert "thesis" in str(exc)
    assert "why_now" in str(exc)
