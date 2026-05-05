"""State-machine service — single write path for trade.state mutations.

Per spec §3 + §3.5.1: 5-state lifecycle; 5 allowed transitions; operation-
contextual validation (NOT retroactive invariants on existing rows).
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any, Literal

# (from_state, to_state) tuples representing every allowed transition.
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("entered", "managing"),
    ("managing", "partial_exited"),
    ("managing", "closed"),
    ("partial_exited", "closed"),
    ("closed", "reviewed"),
})


# Per spec §3.5.1: the validator selects the exact required-field set per
# operation; no fallback to "validate everything for the target state."
OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "entry_create": (
        "ticker", "entry_date", "entry_price", "initial_shares", "initial_stop",
        "trade_origin", "pre_trade_locked_at",
        "thesis", "why_now", "invalidation_condition", "expected_scenario",
        "premortem_technical", "premortem_market_sector", "premortem_execution",
        "event_risk_present", "gap_risk_present",
        "emotional_state_pre_trade",
        "market_regime", "catalyst",
        "manual_entry_confidence",
    ),
    "transition_managing": (),
    "transition_partial_exited": (),
    "transition_closed": (),
    "transition_reviewed": (
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence",
        "lesson_learned",
    ),
}


_CONDITIONAL_FIELD_RULES: tuple[tuple[str, Any, tuple[str, ...]], ...] = (
    # (gating_field, gating_value, required-when-gated fields)
    ("event_risk_present", 1, ("event_handling", "event_type", "event_date")),
    ("gap_risk_present", 1, ("gap_risk_handling",)),
    ("catalyst", "other", ("catalyst_other_description",)),
)


class InvalidStateTransition(ValueError):  # noqa: N818
    """Raised when state_transition is called with a (from, to) pair not in ALLOWED_TRANSITIONS."""


class MissingPreTradeFieldsException(ValueError):  # noqa: N818
    """Raised when validate_for_operation returns a non-empty missing list
    AND the caller is in entry-create context. Carries the structured field
    list for surface-specific error rendering (form re-render highlights, CLI
    stderr, hyp-recs panel error)."""

    def __init__(self, *, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__(
            f"Missing required pre-trade fields: {', '.join(missing_fields)}"
        )


Operation = Literal[
    "entry_create",
    "transition_managing",
    "transition_partial_exited",
    "transition_closed",
    "transition_reviewed",
]


def validate_for_operation(
    req: Mapping[str, Any], *,
    op: Operation,
    current_state: str | None,
) -> list[str]:
    """Returns a sorted list of missing/empty required-field names; empty if valid.

    Operation-contextual: each `op` selects an exact required-field set;
    no inheritance from "the target state's required fields." Legacy rows
    pre-Phase-7 are exempt by NULLABLE schema; transition operations on
    legacy rows only validate their delta fields, not pre-trade fields.

    Conditional fields (event_*, gap_*, catalyst_other_description) are
    appended to the missing list when the gating flag indicates required.
    """
    missing: list[str] = []
    required = OPERATION_REQUIRED_FIELDS.get(op, ())
    for field in required:
        value = req.get(field) if isinstance(req, Mapping) else getattr(req, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    # Conditional rules (only fire on entry_create; transitions don't re-check pre-trade).
    if op == "entry_create":
        for gating_field, gating_value, deps in _CONDITIONAL_FIELD_RULES:
            actual = (
                req.get(gating_field) if isinstance(req, Mapping)
                else getattr(req, gating_field, None)
            )
            if actual == gating_value:
                for dep in deps:
                    val = (
                        req.get(dep) if isinstance(req, Mapping)
                        else getattr(req, dep, None)
                    )
                    if val is None or (isinstance(val, str) and not val.strip()):
                        missing.append(dep)
    return sorted(set(missing))


def state_transition(
    conn: sqlite3.Connection, *,
    trade_id: int,
    new_state: str,
    event_ts: str,
    rationale: str | None = None,
) -> None:
    """Single write path for trade.state mutation. Atomic: state UPDATE +
    trade_events audit row in same transaction (caller's `with conn:`).

    Rejects illegal transitions per ALLOWED_TRANSITIONS; rejects unknown
    trade_id; rejects unknown new_state.
    """
    if new_state not in {"entered", "managing", "partial_exited", "closed", "reviewed"}:
        raise InvalidStateTransition(f"unknown state: {new_state!r}")
    row = conn.execute(
        "SELECT state FROM trades WHERE id = ?", (trade_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"trade {trade_id} not found")
    current_state = row[0]
    if (current_state, new_state) not in ALLOWED_TRANSITIONS:
        raise InvalidStateTransition(
            f"transition {current_state!r} -> {new_state!r} not allowed"
        )
    conn.execute(
        "UPDATE trades SET state = ? WHERE id = ?", (new_state, trade_id),
    )
    payload = {"from_state": current_state, "to_state": new_state}
    # Use 'note' event_type since 'state_transition' is NOT in the CHECK enum;
    # the audit's payload_json carries the structured transition.
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale, notes)
        VALUES (?, ?, 'note', ?, ?, ?)
        """,
        (
            trade_id, event_ts, json.dumps(payload, sort_keys=True),
            rationale, f"state_transition {current_state}->{new_state}",
        ),
    )
