"""Phase 12 Sub-sub-bundle C.B — dry-run validator shim.

Spec §5.5 + §4.6. Pure-SELECT validators that dry-run a proposed
``correction_target`` against schema-CHECK-mirror predicates + FK existence
+ aggregate invariants. NEVER mutates the DB. ALWAYS returns a 2-tuple
``(passes: bool, rejection_reason: str | None)``.

Composition: :func:`default_validator_chain` (T-B.13) returns a callable
that dispatches on ``affected_table`` to the right validator. Callers in
C.C bind ``affected_table`` + ``affected_row_id`` via ``functools.partial``
before passing the result to ``classify_discrepancy`` as ``validator_chain``.

Schema mirror references (do NOT add app-layer rules; mirror schema only):
- ``fills``: migration 0014 line 12-21 — ``quantity > 0``, ``price > 0``,
  ``action IN ('entry','trim','exit','stop')``, ``trade_id`` FK.
- ``trades``: migration 0014 line 134-156 — ``current_stop > 0``,
  ``state IN ('entered','managing','partial_exited','closed','reviewed')``.
- ``cash_movements``: migration 0003 line 77-85 — ``kind IN ('deposit',
  'withdraw')``, ``amount >= 0``.
- ``account_equity_snapshots``: migration 0017 line 327-337 —
  ``equity_dollars > 0``, ``source IN ('manual','schwab_api','tos_csv')``.

Aggregate-invariant dry-run (spec §5.5 + plan §C.2 acceptance #7): for
fill corrections, simulate ``_recompute_aggregates`` post-correction +
reject when simulated ``current_size < 0``.
"""
from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable, Mapping
from typing import Any

# Schema-CHECK-mirror constants (mirror schema VERBATIM; do NOT extend).
_FILL_ACTIONS = ("entry", "trim", "exit", "stop")
_TRADE_STATES = (
    "entered",
    "managing",
    "partial_exited",
    "closed",
    "reviewed",
)
_CASH_MOVEMENT_KINDS = ("deposit", "withdraw", "interest", "dividend", "fee")
_SNAPSHOT_SOURCES = ("manual", "schwab_api", "tos_csv")


# ---------------------------------------------------------------------------
# Fill validator (with aggregate-invariant dry-run)
# ---------------------------------------------------------------------------


def validate_fill_correction(
    conn: sqlite3.Connection,
    fill_id: int,
    proposed_updates: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Dry-run a proposed UPDATE on ``fills.fill_id``; return ``(passes, reason)``.

    Reads the current row, applies ``proposed_updates`` to an in-memory
    dict copy, runs schema-CHECK-mirror predicates + FK existence +
    aggregate-invariant dry-run. NEVER mutates the DB.

    Aggregate invariant (spec §A.9 + plan §C.2 #7): simulate
    ``_recompute_aggregates`` post-correction by SELECTing all fills for
    the trade, swapping the proposed values into the corrected fill's
    dict, summing entry-vs-non-entry; reject when simulated
    ``current_size < 0``.
    """
    row = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        WHERE fill_id = ?
        """,
        (fill_id,),
    ).fetchone()
    if row is None:
        return (False, f"fill_id {fill_id} not found")

    current: dict[str, Any] = {
        "fill_id": row[0],
        "trade_id": row[1],
        "fill_datetime": row[2],
        "action": row[3],
        "quantity": row[4],
        "price": row[5],
        "reason": row[6],
        "rule_based": row[7],
        "fees": row[8],
        "manual_entry_confidence": row[9],
        "reconciliation_status": row[10],
        "tos_match_id": row[11],
    }
    merged = dict(current)
    merged.update(proposed_updates)

    # Schema CHECK: quantity > 0.
    quantity = merged["quantity"]
    if quantity is None or not isinstance(quantity, (int, float)):
        return (False, f"quantity must be numeric; got {quantity!r}")
    # Codex R1 Major #2 — mirror swing/data/models.py REAL-field discipline
    # (rejects NaN/inf on REAL columns; cf. models.py:888-896).
    if not math.isfinite(float(quantity)):
        return (False, f"quantity must be finite (got NaN/inf); got {quantity}")
    if quantity <= 0:
        return (False, f"quantity must be > 0; got {quantity}")

    # Schema CHECK: price > 0.
    price = merged["price"]
    if price is None or not isinstance(price, (int, float)):
        return (False, f"price must be numeric; got {price!r}")
    if not math.isfinite(float(price)):
        return (False, f"price must be finite (got NaN/inf); got {price}")
    if price <= 0:
        return (False, f"price must be > 0; got {price}")

    # Schema CHECK: action enum.
    action = merged["action"]
    if action not in _FILL_ACTIONS:
        return (
            False,
            f"action must be one of {_FILL_ACTIONS}; got {action!r}",
        )

    # FK existence: trade_id MUST resolve to a trades row.
    trade_id = merged["trade_id"]
    fk_row = conn.execute(
        "SELECT 1 FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    if fk_row is None:
        return (False, f"trade_id {trade_id} not found in trades")

    # Aggregate-invariant dry-run: simulate _recompute_aggregates.
    all_fills_rows = conn.execute(
        """
        SELECT fill_id, action, quantity
        FROM fills
        WHERE trade_id = ?
        """,
        (trade_id,),
    ).fetchall()
    simulated_size = 0.0
    for f_row in all_fills_rows:
        fid, faction, fqty = f_row
        if fid == fill_id:
            faction = merged["action"]
            fqty = merged["quantity"]
        if faction == "entry":
            simulated_size += fqty
        else:
            simulated_size -= fqty
    if simulated_size < 0:
        return (
            False,
            (
                f"current_size would be negative after correction "
                f"(simulated_size={simulated_size}); fill correction rejected"
            ),
        )
    return (True, None)


# ---------------------------------------------------------------------------
# Trade validator
# ---------------------------------------------------------------------------


def validate_trade_correction(
    conn: sqlite3.Connection,
    trade_id: int,
    proposed_updates: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Dry-run a proposed UPDATE on ``trades.id``; return ``(passes, reason)``.

    Schema mirror: ``current_stop > 0``, ``state`` enum. Only validates
    fields present in ``proposed_updates`` (the validator is the
    schema-CHECK-mirror layer for the *delta*; full-row invariants live at
    the SQL CHECK constraints).
    """
    row = conn.execute(
        "SELECT id, current_stop, state FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    if row is None:
        return (False, f"trade_id {trade_id} not found")

    if "current_stop" in proposed_updates:
        proposed_stop = proposed_updates["current_stop"]
        if proposed_stop is None or not isinstance(proposed_stop, (int, float)):
            return (
                False,
                f"current_stop must be numeric; got {proposed_stop!r}",
            )
        # Codex R1 Major #2 — mirror REAL-field discipline.
        if not math.isfinite(float(proposed_stop)):
            return (
                False,
                f"current_stop must be finite (got NaN/inf); got {proposed_stop}",
            )
        if proposed_stop <= 0:
            return (
                False,
                f"current_stop must be > 0; got {proposed_stop}",
            )

    if "state" in proposed_updates:
        proposed_state = proposed_updates["state"]
        if proposed_state not in _TRADE_STATES:
            return (
                False,
                f"state must be one of {_TRADE_STATES}; got {proposed_state!r}",
            )

    return (True, None)


# ---------------------------------------------------------------------------
# Cash-movement validator
# ---------------------------------------------------------------------------


def validate_cash_movement_correction(
    conn: sqlite3.Connection,
    movement_id: int,
    proposed_updates: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Dry-run a proposed UPDATE on ``cash_movements.id``.

    Schema mirror: ``kind IN ('deposit','withdraw')``, ``amount >= 0``.
    Sign-vs-kind consistency: spec §4.6 names the kind/amount pairing; the
    schema enforces ``amount >= 0`` AND the kind enum independently. The
    semantic "deposit/withdraw direction" lives at the writer layer
    (movements always carry positive amount + the kind enum names the
    direction). Validator stays at schema-CHECK-mirror.
    """
    row = conn.execute(
        "SELECT id, date, kind, amount FROM cash_movements WHERE id = ?",
        (movement_id,),
    ).fetchone()
    if row is None:
        return (False, f"cash_movement_id {movement_id} not found")

    current: dict[str, Any] = {
        "id": row[0],
        "date": row[1],
        "kind": row[2],
        "amount": row[3],
    }
    merged = dict(current)
    merged.update(proposed_updates)

    kind = merged["kind"]
    if kind not in _CASH_MOVEMENT_KINDS:
        return (
            False,
            f"kind must be one of {_CASH_MOVEMENT_KINDS}; got {kind!r}",
        )

    amount = merged["amount"]
    if amount is None or not isinstance(amount, (int, float)):
        return (False, f"amount must be numeric; got {amount!r}")
    # Codex R1 Major #2 — mirror REAL-field discipline.
    if not math.isfinite(float(amount)):
        return (False, f"amount must be finite (got NaN/inf); got {amount}")
    if amount < 0:
        return (False, f"amount must be >= 0; got {amount}")

    return (True, None)


# ---------------------------------------------------------------------------
# Snapshot validator
# ---------------------------------------------------------------------------


def validate_snapshot_correction(
    conn: sqlite3.Connection,
    snapshot_id: int,
    proposed_updates: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Dry-run a proposed UPDATE on ``account_equity_snapshots.snapshot_id``.

    Schema mirror (migration 0017 line 330-332): ``equity_dollars > 0``,
    ``source`` enum.
    """
    row = conn.execute(
        """
        SELECT snapshot_id, snapshot_date, equity_dollars, source
        FROM account_equity_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchone()
    if row is None:
        return (False, f"snapshot_id {snapshot_id} not found")

    current: dict[str, Any] = {
        "snapshot_id": row[0],
        "snapshot_date": row[1],
        "equity_dollars": row[2],
        "source": row[3],
    }
    merged = dict(current)
    merged.update(proposed_updates)

    equity_dollars = merged["equity_dollars"]
    if equity_dollars is None or not isinstance(equity_dollars, (int, float)):
        return (
            False,
            f"equity_dollars must be numeric; got {equity_dollars!r}",
        )
    # Codex R1 Major #2 — mirror REAL-field discipline.
    if not math.isfinite(float(equity_dollars)):
        return (
            False,
            f"equity_dollars must be finite (got NaN/inf); got {equity_dollars}",
        )
    if equity_dollars <= 0:
        return (
            False,
            f"equity_dollars must be > 0; got {equity_dollars}",
        )

    source = merged["source"]
    if source not in _SNAPSHOT_SOURCES:
        return (
            False,
            f"source must be one of {_SNAPSHOT_SOURCES}; got {source!r}",
        )

    return (True, None)


# ---------------------------------------------------------------------------
# T-B.13 — default_validator_chain dispatcher
# ---------------------------------------------------------------------------
#
# Spec §5.5 + plan §C.13. Returns a callable that dispatches on
# ``affected_table`` to one of the 4 shipped validators above.
#
# Composition contract: ``classify_discrepancy``'s dispatcher (T-B.1
# Step 2) invokes ``validator_chain(correction_target)`` with a single
# positional arg. To compose ``default_validator_chain`` with
# ``classify_discrepancy``, callers MUST partially-apply ``affected_table``
# + ``affected_row_id`` at construction time (e.g., via
# ``functools.partial``). This composition lives in C.C's auto-correction
# service where caller-context (the discrepancy's ``affected_table`` + the
# journal-row PK) is known.
#
# The returned callable signature is:
#   (correction_target: Mapping, *, affected_table: str,
#    affected_row_id: int) -> (passes: bool, reason: str | None)


def default_validator_chain(
    conn: sqlite3.Connection,
) -> Callable[..., tuple[bool, str | None]]:
    """Spec §5.5 — returns a callable that dispatches on ``affected_table``.

    The returned callable accepts ``correction_target`` as the first
    positional argument plus ``affected_table`` + ``affected_row_id`` as
    keyword-only arguments (kwargs-only per plan §C.13 #2 LOCK; preserves
    the brain-dead-clear signature when called downstream — callers MUST
    name the routing fields explicitly).

    Composition with ``classify_discrepancy``'s single-arg
    ``validator_chain``: bind ``affected_table`` + ``affected_row_id`` at
    construction time via ``functools.partial(chain, affected_table=X,
    affected_row_id=Y)``.
    """
    def _chain(
        correction_target: Mapping[str, Any],
        *,
        affected_table: str,
        affected_row_id: int,
    ) -> tuple[bool, str | None]:
        if affected_table == "fills":
            return validate_fill_correction(
                conn, affected_row_id, correction_target,
            )
        if affected_table == "trades":
            return validate_trade_correction(
                conn, affected_row_id, correction_target,
            )
        if affected_table == "cash_movements":
            return validate_cash_movement_correction(
                conn, affected_row_id, correction_target,
            )
        if affected_table == "account_equity_snapshots":
            return validate_snapshot_correction(
                conn, affected_row_id, correction_target,
            )
        return (
            False,
            (
                f"default_validator_chain has no validator registered for "
                f"affected_table={affected_table!r}"
            ),
        )

    return _chain
