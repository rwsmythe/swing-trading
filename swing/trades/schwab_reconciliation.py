"""Schwab-API reconciliation service (Phase 11 Sub-bundle B T-B.4).

Mirrors `swing/trades/reconciliation.py:run_tos_reconciliation` shape per
plan §A.4 + §H.5. The function:

  - REJECTs caller-held transactions (Phase 8 R3→R4 lesson).
  - Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.
  - INSERTs reconciliation_runs row with `source='schwab_api'` +
    `schwab_api_call_id` populated.
  - Emits discrepancies for the 8 types Schwab data can surface:
    stop_mismatch, position_qty_mismatch, close_price_mismatch,
    entry_price_mismatch, unmatched_open_fill, unmatched_close_fill,
    cash_movement_mismatch, equity_delta.
  - On mid-emit failure: PRESERVES the run row via UPDATE state='failed'
    in a separate transaction (matches Phase 9 Sub-bundle B precedent).
  - Reuses Phase 9 Sub-bundle B `MATERIAL_BY_TYPE` lookup at INSERT time
    (Codex R1 M#2 lesson — material is authoritative at the lookup, NOT
    caller-supplied).

V1 scope: detection-only. Operator-side disposition uses the existing
`swing journal discrepancy {list,show,resolve}` CLI from Phase 9 Sub-bundle
B (the resolve helper is `swing.trades.reconciliation.resolve_discrepancy`;
NO new resolution surface required).

V1 fill-matching heuristic is INTENTIONALLY conservative (per plan §H.5
notes + spec §3.7 fill-matching subset):
  - Match by `(ticker, instruction → side, quantity, price-within-tolerance)`.
  - Schwab order_type ∈ {'STOP', 'STOP_LIMIT', 'TRAILING_STOP'} feeds
    stop_mismatch checks against journal `current_stop`.
  - Unmatched journal fills with no Schwab counterpart emit
    unmatched_open_fill / unmatched_close_fill (per journal_fill.action).
  - position_qty checks compare `schwab_account.positions` quantities
    against open journal trades (best-effort; V2 strengthens fill-side
    aggregation).
"""
from __future__ import annotations

import contextlib
import functools as _functools
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from typing import Any

from swing.data.datetime_helpers import now_ms
from swing.data.repos import reconciliation as repo
from swing.data.repos.account_equity_snapshots import (
    get_latest_snapshot_on_or_before,
)
from swing.data.repos.cash import list_cash
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import list_open_trades
from swing.trades.reconciliation import (
    DISCREPANCY_TYPES,
    EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS,
    MATERIAL_BY_TYPE,
)
from swing.trades.reconciliation_auto_correct import (
    InvalidOverrideComboError,
    ValidatorRejectedError,
    _apply_tier1_correction_inner,
    _apply_tier2_resolution_inner,
    _SandboxAutoRedirectShortCircuit,
    _stamp_pending_ambiguity_inner,
    _validate_override_combo,
)
from swing.trades.reconciliation_classifier import classify_discrepancy
from swing.trades.reconciliation_validators import default_validator_chain

log = logging.getLogger(__name__)


# Stop-order types that drive stop_mismatch detection.
_STOP_ORDER_TYPES = frozenset({"STOP", "STOP_LIMIT", "TRAILING_STOP", "TRAILING_STOP_LIMIT"})


# Working/armed status values that count for active stop-detection.
_ACTIVE_STOP_STATUSES = frozenset({
    "WORKING", "WAIT_TRG", "ACCEPTED", "PENDING_ACTIVATION", "QUEUED",
})


# Schwab transaction-type sets for cash_movement_mismatch matching.
# Codex R2 M#3 fix — ELECTRONIC_FUND is direction-ambiguous (Schwab uses
# it for both inbound + outbound EFTs); we list it in BOTH sets and use
# the sign of `net_amount` to disambiguate at match time.
_SCHWAB_DEPOSIT_TYPES = frozenset({
    "ACH_RECEIPT", "WIRE_IN", "CASH_RECEIPT", "ELECTRONIC_FUND",
})
_SCHWAB_WITHDRAW_TYPES = frozenset({
    "ACH_DISBURSEMENT", "WIRE_OUT", "CASH_DISBURSEMENT", "ELECTRONIC_FUND",
})


# ===========================================================================
# Arc 4b — auto-ingestion classifier + dedup ladder (step 6.5).
# ===========================================================================

# Deterministic deposit/withdraw Schwab types (sign-independent direction).
_CASH_DEPOSIT_TX_TYPES = frozenset({"ACH_RECEIPT", "WIRE_IN", "CASH_RECEIPT"})
_CASH_WITHDRAW_TX_TYPES = frozenset(
    {"ACH_DISBURSEMENT", "WIRE_OUT", "CASH_DISBURSEMENT"}
)
# Sign-disambiguated types (direction follows net_amount sign).
_CASH_SIGNED_TX_TYPES = frozenset({"ELECTRONIC_FUND", "JOURNAL"})
# Skip BY DESIGN — trade cash already enters the ledger via realized P&L.
_CASH_SKIP_TX_TYPES = frozenset(
    {"TRADE", "RECEIVE_AND_DELIVER", "TRADE_CORRECTION"}
)
# Skip but WARN when net_amount != 0 (visibility without guessing).
_CASH_SKIP_WARN_TX_TYPES = frozenset(
    {"MEMORANDUM", "MARGIN_CALL", "MONEY_MARKET", "SMA_ADJUSTMENT"}
)

# Journal-cash kind -> the Schwab transaction types that can match it (step-7
# journal→source scan, Arc 4b Task 7). interest/dividend/fee all ride
# DIVIDEND_OR_INTEREST; the SIGN of net_amount disambiguates income (+) vs
# fee (−). deposit/withdraw reuse the existing direction sets (which carry the
# sign-ambiguous ELECTRONIC_FUND in both).
_CASH_KIND_TO_SCHWAB_TYPES: dict[str, frozenset[str]] = {
    "deposit": _SCHWAB_DEPOSIT_TYPES,
    "withdraw": _SCHWAB_WITHDRAW_TYPES,
    "interest": frozenset({"DIVIDEND_OR_INTEREST"}),
    "dividend": frozenset({"DIVIDEND_OR_INTEREST"}),
    "fee": frozenset({"DIVIDEND_OR_INTEREST"}),
}
# Kinds whose matching Schwab net_amount must be POSITIVE (income/inflow).
_CASH_KIND_SIGN_POSITIVE = frozenset({"deposit", "interest", "dividend"})

# DIVIDEND_OR_INTEREST description markers. EMPTY by operator decision
# (2026-06-11): the live account has no dividend/interest history at the epoch,
# so every DIVIDEND_OR_INTEREST flags tier-2 (the safe default, spec §4.1). Real
# markers are seeded post-merge from a captured live payload (Task 11 runbook
# step 2) — NEVER invent strings (feedback_adversarial_review_verify_data_shapes).
_DIVIDEND_MARKERS: frozenset[str] = frozenset()
_INTEREST_MARKERS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CashDisposition:
    """Pure-classifier result. ``action`` ∈ {candidate, skip, flag, skip_warn}.

    ``kind`` is set only for ``candidate`` (the 5-kind vocabulary value);
    ``flag_reason`` is set only for ``flag`` (the source-direction enum).
    """
    action: str
    kind: str | None = None
    flag_reason: str | None = None


def _classify_cash_transaction(tx: Any) -> CashDisposition:
    """Map a SchwabTransactionResponse to a cash disposition (PURE — no DB, no
    Schwab calls; the Phase-12 classifier discipline). Spec §4.1 table."""
    ttype = tx.type
    net = float(tx.net_amount)
    if ttype in _CASH_DEPOSIT_TX_TYPES:
        return CashDisposition(action="candidate", kind="deposit")
    if ttype in _CASH_WITHDRAW_TX_TYPES:
        return CashDisposition(action="candidate", kind="withdraw")
    if ttype in _CASH_SIGNED_TX_TYPES:
        if net > 0:
            return CashDisposition(action="candidate", kind="deposit")
        if net < 0:
            return CashDisposition(action="candidate", kind="withdraw")
        return CashDisposition(action="skip")  # zero-amount is not a movement
    if ttype == "DIVIDEND_OR_INTEREST":
        if net < 0:
            return CashDisposition(action="flag", flag_reason="negative_income_amount")
        desc = (tx.description or "").upper()
        if any(m in desc for m in _DIVIDEND_MARKERS):
            return CashDisposition(action="candidate", kind="dividend")
        if any(m in desc for m in _INTEREST_MARKERS):
            return CashDisposition(action="candidate", kind="interest")
        return CashDisposition(
            action="flag", flag_reason="unrecognized_income_description")
    if ttype in _CASH_SKIP_TX_TYPES:
        return CashDisposition(action="skip")
    if ttype in _CASH_SKIP_WARN_TX_TYPES:
        if net != 0:
            return CashDisposition(action="skip_warn")
        return CashDisposition(action="skip")
    # Unknown type — visibility without guessing (skip_warn on nonzero).
    return CashDisposition(action="skip_warn" if net != 0 else "skip")


def _within_cash_match_window(date_a_iso: str, date_b_iso: str, *, days: int = 4) -> bool:
    """True when two ISO dates are within ``days`` calendar days INCLUSIVE.

    THE shared cash date-window predicate — used by BOTH the Task-6 ref-less
    fallback AND the Task-7 journal→source scan (the Arc-6 shared-predicate
    lesson: two implementations WILL diverge).
    """
    a = _date.fromisoformat(date_a_iso)
    b = _date.fromisoformat(date_b_iso)
    return abs((a - b).days) <= days


# Price-tolerance for fill matching (matches Phase 9 Sub-bundle B default).
_PRICE_TOLERANCE_DEFAULT: float = 0.01


def _compute_execution_price(so: Any) -> float | None:
    """Sub-bundle 1 T-1.4 — compute execution-grain price from a Schwab order.

    Per spec §5.1 + plan §A.1.4. Pure function (no DB, no logging).

    - ``so.executions is None`` OR empty → returns ``None`` (caller's
      responsibility to fall through to Path B sentinel emit per spec §6.1
      OQ-A LOCK).
    - Single leg → returns leg price.
    - Multi leg → returns VWAP across legs:
      ``sum(leg.price * leg.quantity) / sum(leg.quantity)``.

    Defensive ``total_qty <= 0`` guard is belt-and-suspenders — the
    ``SchwabExecutionLeg.__post_init__`` validator rejects ``quantity <= 0``
    at construction, so this branch is unreachable in practice. Retained
    for static-analysis clarity + future-proofing if the dataclass
    validator widens.
    """
    executions = getattr(so, "executions", None)
    if executions is None or not executions:
        return None
    if len(executions) == 1:
        return executions[0].price
    total_qty = sum(leg.quantity for leg in executions)
    if total_qty <= 0:
        return None
    return sum(leg.price * leg.quantity for leg in executions) / total_qty


def _is_execution_bearing_candidate(o: Any) -> bool:
    """Sub-bundle 1 T-1.6 — candidate-pool guard for the comparator.

    Per spec §5.3 + §6.4 OQ-D LOCK + Codex R1 M#1+#2 fix + plan §A.0.1 D4
    deviation closure.

    V1 filter at ``schwab_reconciliation.py:641-645`` was
    ``status=='FILLED' AND price is not None``, which excluded two
    operationally-legitimate execution-bearing cases:

    - **MARKET fills** with ``price=None`` AND ``executions=[leg @
      exec_price]`` (Schwab does not surface an order-grain price for
      MARKET orders; the execution price lives ONLY in executionLegs).
    - **Partial-then-canceled** orders (``status='CANCELED'`` with
      ``filledQuantity > 0`` AND ``executions=[leg, ...]``) where the
      operator placed an order, partial-filled, then canceled the
      remainder — Schwab keeps the executed legs visible.
    - **Partial-then-replaced** orders (``status='REPLACED'`` mirror).

    V2 filter admits:

    - ``status='FILLED'`` AND (``price is not None`` OR ``executions``
      non-empty). Preserves V1 backward-compat for FILLED-with-price +
      ``executions=None`` (legacy mapper path / sandbox / mapper-
      coherence-check collapse case) — Path B sentinel emit handles those
      downstream.
    - ``status='CANCELED'`` AND ``executions`` non-empty.
    - ``status='REPLACED'`` AND ``executions`` non-empty.

    FILLED orders where BOTH ``price is None`` AND ``executions is None``
    are REJECTED entirely (defensive — such orders carry NO data the
    comparator can compare against; they represent corrupt / truncated
    Schwab responses; near-zero in operator's production data per Codex
    R2 Major #2 fix analysis).
    """
    status = getattr(o, "status", "")
    if status == "FILLED":
        return (
            getattr(o, "price", None) is not None
            or bool(getattr(o, "executions", None))
        )
    if status in ("CANCELED", "REPLACED"):
        return bool(getattr(o, "executions", None))
    return False


def _resolve_match_quantity(so: Any) -> float:
    """Sub-bundle 1 T-1.5 — execution-grain quantity match per Codex R1 M#2.

    Per spec §5.3 + plan §A.1.5. Pure function.

    - ``so.executions`` populated (truthy) → returns ``sum(leg.quantity for
      leg in executions)``. Closes the in-row quantity comparison defect
      for partial fills where ``order.quantity`` reflects the OPEN order
      size, not the FILLED quantity (e.g., ordered 200 shares but only 100
      filled in a single leg of an in-flight order).
    - else (``None`` or empty list) → returns ``so.quantity`` (V1 behavior
      preserved for legacy V1 mapper path / sandbox / mapper-coherence-
      check collapse case).

    Comparator T-1.7 swaps the V1 ``so.quantity`` reference at
    ``schwab_reconciliation.py:658`` for this helper to admit partial
    fills into the match candidate pool correctly.
    """
    executions = getattr(so, "executions", None)
    if executions:
        return sum(leg.quantity for leg in executions)
    return so.quantity


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes `run_schwab_reconciliation` while holding
    an open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha — single-transaction services
    own BEGIN IMMEDIATE / COMMIT / ROLLBACK; they REJECT caller-held
    transactions rather than silently auto-detecting.
    """


def _find_working_stop_for_ticker(
    orders: list[Any], ticker: str,
) -> Any | None:
    """Return the most-recent working stop order for ticker, or None."""
    candidates = [
        o for o in orders
        if (
            getattr(o, "instrument_symbol", "") == ticker
            and getattr(o, "order_type", "") in _STOP_ORDER_TYPES
            and getattr(o, "status", "") in _ACTIVE_STOP_STATUSES
            and getattr(o, "price", None) is not None
        )
    ]
    if not candidates:
        return None
    # Most-recent by enter_time (string-comparable ISO format).
    return sorted(
        candidates,
        key=lambda o: getattr(o, "enter_time", ""),
        reverse=True,
    )[0]


def _find_position_qty(
    schwab_positions: list[dict], ticker: str,
) -> float | None:
    """Return |longQuantity - shortQuantity| for ticker; None if absent.

    Schwab's positions entries shape:
      {"instrument": {"symbol": "AAPL", ...},
       "longQuantity": 50, "shortQuantity": 0, ...}
    """
    for p in schwab_positions:
        if not isinstance(p, dict):
            continue
        instr = p.get("instrument") or {}
        if not isinstance(instr, dict):
            continue
        sym = instr.get("symbol")
        if sym != ticker:
            continue
        long_q = float(p.get("longQuantity", 0) or 0)
        short_q = float(p.get("shortQuantity", 0) or 0)
        # Convention: long position positive; short position negative
        # (journal qty is signed too on the fill side; we compare absolute
        # values here for simplicity — V2 hardens for short-side trades).
        return long_q - short_q
    return None


def _emit(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    discrepancy_type: str,
    field_name: str,
    counters: dict,
    dedup_seen: set,
    ticker: str | None = None,
    trade_id: int | None = None,
    fill_id: int | None = None,
    cash_movement_id: int | None = None,
    expected_value_json: str | None = None,
    actual_value_json: str | None = None,
    delta_text: str | None = None,
    dedup_key_override: tuple | None = None,
) -> int:
    """Phase 9 Sub-bundle B emit pattern — MATERIAL_BY_TYPE lookup at INSERT
    time + within-run dedup tuple (orphan-fill payload disambiguator).

    ``dedup_key_override`` (Arc 4b) REPLACES the ``payload_key`` slot of the
    within-run dedup tuple. Source-direction cash emits all carry the CONSTANT
    ``actual_value_json = {"matched": null}`` so the default payload_key would
    collide; passing ``("missing_journal_row", transaction_id)`` keeps two
    distinct unmatched transactions in one run as two rows (spec §4.3).
    """
    if discrepancy_type not in DISCREPANCY_TYPES:
        raise ValueError(
            f"emit: unknown discrepancy_type {discrepancy_type!r}"
        )
    payload_key: tuple | str | None = None
    if dedup_key_override is not None:
        payload_key = dedup_key_override
    elif fill_id is None and cash_movement_id is None:
        payload_key = actual_value_json
    key = (
        trade_id, discrepancy_type, field_name, ticker,
        fill_id, cash_movement_id, payload_key,
    )
    if key in dedup_seen:
        return -1
    dedup_seen.add(key)

    material = MATERIAL_BY_TYPE[discrepancy_type]
    did = repo.insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type=discrepancy_type,
        field_name=field_name,
        material_to_review=int(material),
        created_at=now_ms(),
        trade_id=trade_id,
        fill_id=fill_id,
        cash_movement_id=cash_movement_id,
        ticker=ticker,
        expected_value_json=expected_value_json,
        actual_value_json=actual_value_json,
        delta_text=delta_text,
        resolution="unresolved",
    )
    counters["discrepancies_count"] += 1
    counters["unresolved_discrepancies_count"] += 1
    return did


def _extract_source_payload(
    disc: Any,
    schwab_orders: list[Any],
) -> Any | None:
    """T-C.5 helper — derive a classifier-friendly source_payload from
    the emitted discrepancy's `actual_value_json` shape.

    For entry_price_mismatch / close_price_mismatch the V1 emitter
    persists ``{"price": so.price}`` (single-match shape) so the
    classifier reads it directly via JSON deserialization.

    For unmatched_open_fill / unmatched_close_fill the emitter persists
    ``{"matched": null}`` (spec §4 sentinel) so the classifier emits
    tier-2 schwab_returned_no_match. We pass ``None`` as the
    source_payload — the classifier's "None → schwab_returned_no_match"
    fallthrough handles it (matches the spec §10.3 walkthrough shape).

    For stop_mismatch / position_qty_mismatch / cash_movement_mismatch
    / equity_delta we read the actual_value_json as-is.
    """
    if disc.actual_value_json is None:
        return None
    try:
        payload = json.loads(disc.actual_value_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    # Sentinel: unmatched_*_fill emits {"matched": null} → no Schwab record.
    # Check the "matched" key is explicitly present + null to avoid
    # mis-classifying single-key payloads like {"price": 5.30}.
    if (
        isinstance(payload, dict)
        and "matched" in payload
        and payload["matched"] is None
        and len(payload) == 1
    ):
        return None
    return payload


def _fetch_journal_row(
    conn: sqlite3.Connection, disc: Any,
) -> dict[str, Any] | None:
    """T-C.5 helper — read the journal row associated with the
    discrepancy's FK columns.

    For fill_id → fills row; for trade_id → trades row; for
    cash_movement_id → cash_movements row. Returns ``None`` for
    discrepancies whose FK columns are all NULL (e.g., equity_delta
    where the snapshot is implicit).
    """
    if disc.fill_id is not None:
        row = conn.execute(
            "SELECT fill_id, trade_id, fill_datetime, action, quantity, price "
            "FROM fills WHERE fill_id = ?",
            (int(disc.fill_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "fill_id": row[0], "trade_id": row[1],
            "fill_datetime": row[2], "action": row[3],
            "quantity": row[4], "price": row[5],
        }
    if disc.trade_id is not None:
        row = conn.execute(
            "SELECT id, ticker, current_stop FROM trades WHERE id = ?",
            (int(disc.trade_id),),
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "ticker": row[1], "current_stop": row[2]}
    if disc.cash_movement_id is not None:
        row = conn.execute(
            "SELECT id, date, kind, amount FROM cash_movements WHERE id = ?",
            (int(disc.cash_movement_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "date": row[1], "kind": row[2], "amount": row[3],
        }
    return None


def _resolve_affected_table(disc: Any) -> str:
    """T-C.5 helper — mirror of
    ``swing.trades.reconciliation_auto_correct._resolve_affected_target``
    but returns only the table name (the row_id is derived in C.C
    inner from the FK columns directly)."""
    if disc.fill_id is not None:
        return "fills"
    if disc.cash_movement_id is not None:
        return "cash_movements"
    if disc.trade_id is not None:
        return "trades"
    return "account_equity_snapshots"


def _resolve_affected_row_id(disc: Any) -> int | None:
    if disc.fill_id is not None:
        return int(disc.fill_id)
    if disc.cash_movement_id is not None:
        return int(disc.cash_movement_id)
    if disc.trade_id is not None:
        return int(disc.trade_id)
    return None


def _pivot_classify_and_dispatch_for_run(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    schwab_orders: list[Any],
    schwab_api_call_id: int | None,
    environment: str | None,
    counters: dict[str, int],
) -> None:
    """Spec §7.1 LOCKED pivot — savepoint-per-discrepancy classify +
    dispatch. Called inside the outer reconciliation_run transaction
    AFTER all emitters have landed; the function NEVER raises out
    (graceful-degradation per spec §7.4), EXCEPT for
    :class:`InvalidOverrideComboError` (developer-bug signal per Phase
    12.5 #1 spec §7.4 R4 M2 LOCK + plan §F invariant F16 + F21) which
    propagates out so the overall reconciliation_run fails-fast at
    integration time rather than being hidden inside
    ``tier_errored_count`` graceful-degradation.
    """
    counters.setdefault("tier1_applied_count", 0)
    counters.setdefault("tier2_pending_count", 0)
    counters.setdefault("tier_errored_count", 0)
    counters.setdefault("tier1_multi_leg_auto_redirected_count", 0)
    counters.setdefault("sandbox_auto_redirect_skipped_count", 0)

    # Read the newly-emitted discrepancies for this run.
    discrepancies = repo.list_discrepancies_for_run(conn, run_id=run_id)
    if not discrepancies:
        return

    for disc in discrepancies:
        # Only act on still-unresolved rows — pre-resolved rows (rare
        # via pre-Phase-12 import paths) are passed-through.
        if disc.resolution != "unresolved":
            continue

        sp_name = f"correction_sp_{disc.discrepancy_id}"
        conn.execute(f"SAVEPOINT {sp_name}")
        try:
            source_payload = _extract_source_payload(disc, schwab_orders)
            journal_row = _fetch_journal_row(conn, disc)
            affected_table = _resolve_affected_table(disc)
            affected_row_id = _resolve_affected_row_id(disc)
            # Build validator chain partial (kwargs-only binding).
            if affected_row_id is not None:
                validator_chain = _functools.partial(
                    default_validator_chain(conn),
                    affected_table=affected_table,
                    affected_row_id=affected_row_id,
                )
            else:
                validator_chain = None

            classification = classify_discrepancy(
                disc,
                source_payload=source_payload,
                journal_row=journal_row,
                validator_chain=validator_chain,
            )

            if classification.tier == 1:
                try:
                    result = _apply_tier1_correction_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        classification=classification,
                        schwab_api_call_id=schwab_api_call_id,
                        environment=environment,
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    # Plan §D.5 step 1 LOCK: increment counter ONLY when
                    # the inner returned a real correction_id. Sandbox
                    # short-circuit returns id=None → counter stays at 0
                    # naturally (no journal mutation occurred).
                    if result.correction_id is not None:
                        counters["tier1_applied_count"] += 1
                except ValidatorRejectedError as e:
                    # ROLLBACK TO undoes partial UPDATEs, but does NOT
                    # release the savepoint (SQLite semantics).
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    # Fall through to tier-2 stamp in a FRESH savepoint
                    # so failures here don't try to ROLLBACK TO an
                    # already-released sp_name (Codex R2 Minor #1).
                    fb_sp = f"correction_fallback_sp_{disc.discrepancy_id}"
                    conn.execute(f"SAVEPOINT {fb_sp}")
                    try:
                        _stamp_pending_ambiguity_inner(
                            conn,
                            discrepancy_id=disc.discrepancy_id,
                            ambiguity_kind="validator_rejected",
                            resolution_reason=str(e),
                        )
                        conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        counters["tier2_pending_count"] += 1
                    except Exception as fb_exc:  # noqa: BLE001
                        with contextlib.suppress(sqlite3.Error):
                            conn.execute(
                                f"ROLLBACK TO SAVEPOINT {fb_sp}"
                            )
                            conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        log.warning(
                            "tier-2 fallback stamp failed for discrepancy "
                            "%d: %s", disc.discrepancy_id, fb_exc,
                        )
                        counters["tier_errored_count"] += 1
            elif (
                classification.tier == 2
                and classification.auto_redirect_recipe is not None
            ):
                # Phase 12.5 #1 T-1.5 — multi-leg auto-redirect path.
                # Defensive future-proofing per F20: the initial pivot
                # cannot currently emit the recipe (source_payload reads
                # the persisted ``{"matched": null}`` sentinel for
                # ``unmatched_*_fill`` discrepancies; the classifier
                # treats that as the no-payload sentinel), so this branch
                # is a guard for any future emit-shape widening AND a
                # symmetry mirror of the backfill operational firing site
                # at ``reconciliation_backfill._handle_pass_2`` (where
                # ``_orders_to_classifier_payload`` builds the rich
                # list-shape source_payload from freshly-fetched Schwab
                # orders WITH execution-grain data).
                recipe = classification.auto_redirect_recipe
                try:
                    # Defense-in-depth: validate override combo BEFORE
                    # any mutation. Mirrors the T-1.4 service-layer
                    # guard. InvalidOverrideComboError MUST propagate
                    # per F21 (handled by the outer catch ladder below).
                    _validate_override_combo(
                        choice_code=recipe["choice_code"],
                        applied_by_override=recipe["applied_by_override"],
                        correction_action_override=recipe[
                            "correction_action_override"
                        ],
                        resolved_by_override=recipe["resolved_by"],
                    )
                    _stamp_pending_ambiguity_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        ambiguity_kind=classification.ambiguity_kind
                        or "multi_partial_vs_consolidated",
                        resolution_reason=classification.correction_reason,
                    )
                    _apply_tier2_resolution_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        choice_code=recipe["choice_code"],
                        operator_custom_payload=recipe["payload"],
                        operator_reason=(
                            f"multi-leg auto-redirect: "
                            f"{classification.correction_reason}"
                        ),
                        applied_by_override=recipe["applied_by_override"],
                        correction_action_override=recipe[
                            "correction_action_override"
                        ],
                        resolved_by_override=recipe["resolved_by"],
                        risk_policy_id=None,
                        schwab_api_call_id=schwab_api_call_id,
                        environment=environment or "production",
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    counters["tier1_multi_leg_auto_redirected_count"] += 1
                except _SandboxAutoRedirectShortCircuit:
                    # T-1.6 sandbox short-circuit. ROLLBACK TO unwinds
                    # the immediately-preceding stamp + RELEASE clears
                    # the savepoint. Discrepancy state returns to
                    # 'unresolved'.
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    counters["sandbox_auto_redirect_skipped_count"] += 1
                    log.warning(
                        "auto-redirect short-circuited under sandbox "
                        "for discrepancy %d",
                        disc.discrepancy_id,
                    )
                except InvalidOverrideComboError:
                    # Developer-bug per F21 + spec §7.4 R4 M2 LOCK:
                    # clean savepoint + re-raise out of the per-disc
                    # try-block so the outer catch ladder propagates
                    # (the outer ``except InvalidOverrideComboError``
                    # added below MUST come BEFORE the generic
                    # ``except Exception``).
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    raise
                except (ValidatorRejectedError, ValueError) as e:
                    # Spec §7.5 fallback: roll back the auto-redirect
                    # attempt + fresh-savepoint stamp
                    # pending_ambiguity_resolution for manual operator
                    # review. NOTE: InvalidOverrideComboError is a
                    # ValueError subclass — the earlier
                    # ``except InvalidOverrideComboError`` catch above
                    # guarantees it never reaches this catch.
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    fb_sp = (
                        f"correction_fallback_sp_{disc.discrepancy_id}"
                    )
                    conn.execute(f"SAVEPOINT {fb_sp}")
                    try:
                        _stamp_pending_ambiguity_inner(
                            conn,
                            discrepancy_id=disc.discrepancy_id,
                            ambiguity_kind="multi_partial_vs_consolidated",
                            resolution_reason=(
                                f"multi-leg auto-redirect declined "
                                f"post-classifier: {e}"
                            ),
                        )
                        conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        counters["tier2_pending_count"] += 1
                    except Exception as fb_exc:  # noqa: BLE001
                        with contextlib.suppress(sqlite3.Error):
                            conn.execute(
                                f"ROLLBACK TO SAVEPOINT {fb_sp}"
                            )
                            conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        log.warning(
                            "auto-redirect §7.5 fallback stamp failed "
                            "for discrepancy %d: %s",
                            disc.discrepancy_id, fb_exc,
                        )
                        counters["tier_errored_count"] += 1
            else:
                # Tier-2 — stamp pending_ambiguity_resolution via the
                # canonical service helper inside the active savepoint.
                _stamp_pending_ambiguity_inner(
                    conn,
                    discrepancy_id=disc.discrepancy_id,
                    ambiguity_kind=classification.ambiguity_kind
                    or "unsupported",
                    resolution_reason=classification.correction_reason,
                )
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                counters["tier2_pending_count"] += 1
        except InvalidOverrideComboError:
            # Phase 12.5 #1 spec §7.4 R4 M2 LOCK + F21 — developer-bug
            # propagates out of the pivot loop. SAVEPOINT cleanup was
            # already performed by the per-disc auto-redirect catch
            # above before re-raise; defense-in-depth here in case the
            # exception was raised outside that try-block (e.g., from
            # _validate_override_combo at the dispatcher seam).
            with contextlib.suppress(sqlite3.Error):
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            raise
        except Exception as e:  # noqa: BLE001 — graceful degradation
            with contextlib.suppress(sqlite3.Error):
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            log.warning(
                "classifier or apply exception for discrepancy %d: %s",
                disc.discrepancy_id, e,
            )
            counters["tier_errored_count"] += 1


# ===========================================================================
# Arc 4b — ingestion helpers (source-direction emit, suppression, coverage-gap,
# the dedup-ladder ingest). All run INSIDE run_schwab_reconciliation's BEGIN.
# ===========================================================================

# Resolution states that make a source-direction transactionId terminal-or-
# pending (durably suppressed). A terminal disposition is FINAL for the txid.
_SOURCE_SUPPRESSION_STATES = (
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
    "acknowledged_immaterial",
)


def _source_direction_suppressed(conn: sqlite3.Connection, tx_id: str) -> bool:
    """True when a pending-or-terminal source-direction discrepancy already
    exists for this transactionId (spec §4.3 cross-run suppression belt)."""
    placeholders = ",".join("?" * len(_SOURCE_SUPPRESSION_STATES))
    row = conn.execute(
        "SELECT 1 FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='cash_movement_mismatch' "
        "AND field_name='missing_journal_row' "
        "AND json_extract(expected_value_json, '$.transactionId') = ? "
        f"AND resolution IN ({placeholders}) LIMIT 1",
        (str(tx_id), *_SOURCE_SUPPRESSION_STATES),
    ).fetchone()
    return row is not None


def _emit_source_direction_cash(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    tx: Any,
    flag_reason: str,
    counters: dict,
    dedup_seen: set,
    candidate_cash_movement_ids: list[int] | None = None,
) -> int:
    """Emit a source→journal cash_movement_mismatch (field_name=
    'missing_journal_row', all FK NULL). actual_value_json is EXACTLY
    {"matched": null} (the sole-key shape is LOAD-BEARING — _extract_source_
    payload maps it to None → the classifier routes schwab_returned_no_match).
    The flag_reason lives in expected_value_json, never in actual."""
    expected: dict[str, Any] = {
        "transactionId": str(tx.transaction_id),
        "date": tx.transaction_date,
        "type": tx.type,
        "net_amount": float(tx.net_amount),
        "description": tx.description,
        "flag_reason": flag_reason,
    }
    if candidate_cash_movement_ids is not None:
        expected["candidate_cash_movement_ids"] = sorted(candidate_cash_movement_ids)
    return _emit(
        conn,
        run_id=run_id,
        discrepancy_type="cash_movement_mismatch",
        field_name="missing_journal_row",
        counters=counters,
        dedup_seen=dedup_seen,
        expected_value_json=json.dumps(expected, sort_keys=True),
        actual_value_json=json.dumps({"matched": None}, sort_keys=True),
        dedup_key_override=("missing_journal_row", str(tx.transaction_id)),
    )


def _detect_coverage_gap(
    conn: sqlite3.Connection, *, period_start: str, cash_warnings: list[dict],
) -> None:
    """Spec §4.5 — read the most-recent COMPLETED schwab_api run's period_end;
    if older than the current run's period_start, a window was never scanned →
    warn. First-ever run emits an informational note (not a warning). The
    current run's own row is state='running' so it is excluded by construction.
    """
    row = conn.execute(
        "SELECT period_end FROM reconciliation_runs "
        "WHERE source='schwab_api' AND state='completed' "
        "AND finished_ts IS NOT NULL "
        "ORDER BY finished_ts DESC LIMIT 1"
    ).fetchone()
    if row is None or row[0] is None:
        cash_warnings.append({
            "step": "schwab_orders",
            "reason": "coverage_first_run",
            "detail": "coverage_first_run: no prior completed schwab_api run",
        })
        return
    prior_period_end = row[0]
    if prior_period_end < period_start:  # ISO string compare valid for ISO dates
        cash_warnings.append({
            "step": "schwab_orders",
            "reason": "coverage_gap",
            "detail": f"coverage_gap: {prior_period_end} .. {period_start}",
        })
        log.warning(
            "cash coverage gap: %s .. %s never scanned",
            prior_period_end, period_start,
        )


def _empty_cash_counters() -> dict[str, int]:
    return {
        "cash_transactions_checked": 0,
        "cash_candidates": 0,
        "cash_ingested_count": 0,
        "cash_matched_by_ref_count": 0,
        "cash_matched_by_fallback_count": 0,
        "cash_flagged_count": 0,
        "cash_skipped_trade_count": 0,
        "cash_pending_suppressed_count": 0,
    }


def _ingest_cash_transactions(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    schwab_transactions: list[Any],
    price_tolerance: float,
    cash_warnings: list[dict],
    dedup_seen: set | None = None,
    counters: dict | None = None,
) -> dict[str, int]:
    """The ref-idempotent, append-only ingestion ladder (spec §4.2). Returns a
    cash-counters dict. Runs INSIDE the caller's transaction (step 6.5)."""
    from swing.data.models import CashMovement
    from swing.data.repos.cash import find_by_ref, insert_cash

    if dedup_seen is None:
        dedup_seen = set()
    if counters is None:
        # Standalone use (unit tests): a throwaway run-counter for _emit.
        counters = {"discrepancies_count": 0, "unresolved_discrepancies_count": 0}

    cc = _empty_cash_counters()
    claimed_ids: set[int] = set()

    for tx in schwab_transactions:
        cc["cash_transactions_checked"] += 1
        disp = _classify_cash_transaction(tx)

        if disp.action == "skip":
            if tx.type in ("TRADE", "RECEIVE_AND_DELIVER", "TRADE_CORRECTION"):
                cc["cash_skipped_trade_count"] += 1
            continue
        if disp.action == "skip_warn":
            cash_warnings.append({
                "step": "schwab_orders",
                "reason": "skipped_nonzero_noncash",
                "detail": (
                    f"skipped {tx.type} netAmount={float(tx.net_amount):+.2f} "
                    f"(non-cash type)"
                ),
            })
            continue
        if disp.action == "flag":
            # Income flags (unrecognized / negative). Suppression-belt first.
            if _source_direction_suppressed(conn, str(tx.transaction_id)):
                cc["cash_pending_suppressed_count"] += 1
                continue
            _emit_source_direction_cash(
                conn, run_id=run_id, tx=tx, flag_reason=disp.flag_reason,
                counters=counters, dedup_seen=dedup_seen)
            cc["cash_flagged_count"] += 1
            continue

        # --- candidate: the dedup ladder ---
        cc["cash_candidates"] += 1
        tx_id = str(tx.transaction_id)
        # 1. Primary: transactionId-in-ref.
        if find_by_ref(conn, ref=tx_id) is not None:
            cc["cash_matched_by_ref_count"] += 1
            continue
        # 2. Cross-run suppression belt.
        if _source_direction_suppressed(conn, tx_id):
            cc["cash_pending_suppressed_count"] += 1
            continue
        # 3. Ref-less fallback among same-kind journal rows in the ±4d window.
        target = abs(float(tx.net_amount))
        cands: list[int] = []
        for r in conn.execute(
            "SELECT id, date, amount FROM cash_movements "
            "WHERE ref IS NULL AND kind = ?", (disp.kind,),
        ).fetchall():
            cid, cdate, camount = r[0], r[1], r[2]
            if cid in claimed_ids:
                continue
            if abs(float(camount) - target) > price_tolerance:
                continue
            if not _within_cash_match_window(cdate, tx.transaction_date, days=4):
                continue
            cands.append(cid)
        if len(cands) == 1:
            claimed_ids.add(cands[0])
            cc["cash_matched_by_fallback_count"] += 1
            continue
        if len(cands) >= 2:
            _emit_source_direction_cash(
                conn, run_id=run_id, tx=tx, flag_reason="fallback_multi_match",
                counters=counters, dedup_seen=dedup_seen,
                candidate_cash_movement_ids=cands)
            cc["cash_flagged_count"] += 1
            continue
        # 4. No match → INSERT (append-only; ref = the idempotency key).
        desc = tx.description
        note = (
            f"auto-ingested from Schwab: {desc} [reconciliation run {run_id}]"
            if desc else f"auto-ingested from Schwab [reconciliation run {run_id}]"
        )
        insert_cash(conn, CashMovement(
            id=None, date=tx.transaction_date, kind=disp.kind,
            amount=target, ref=tx_id, note=note))
        cc["cash_ingested_count"] += 1

    return cc


def run_schwab_reconciliation(
    conn: sqlite3.Connection,
    *,
    account_hash: str,
    period_start: str,
    period_end: str,
    schwab_orders: list[Any],
    schwab_transactions: list[Any],
    schwab_account: Any,
    pipeline_run_id: int | None = None,
    schwab_api_call_id: int | None = None,
    price_tolerance: float = _PRICE_TOLERANCE_DEFAULT,
    environment: str | None = None,
) -> Any:
    """Reconcile Schwab API responses against the journal.

    Algorithm:
      1. Reject caller-held tx.
      2. BEGIN IMMEDIATE.
      3. INSERT reconciliation_runs (source='schwab_api', ...).
      4. Emit stop_mismatch per open journal trade vs Schwab working-stops.
      5. Emit position_qty_mismatch per open trade vs Schwab positions.
      6. Emit unmatched_open_fill / unmatched_close_fill / price_mismatch
         per journal-fill ↔ Schwab-order matching.
      7. Emit cash_movement_mismatch per journal-cash-movement vs Schwab
         transactions (V1 single-direction emit — journal cash movements
         absent on Schwab side).
      8. Emit equity_delta if |journal_equity − source_NLV| > $10.
      9. UPDATE state='completed', finished_ts, summary.
     10. COMMIT.

    Failure-path: outer rollback + open NEW transaction to UPDATE state='failed'
    (preserves audit row per spec §3.3.3). Discrepancies emitted prior to the
    failure are LOST (we ROLLBACK the whole run) — this differs from Phase 9
    Sub-bundle B which preserves partial discrepancies because TOS-CSV emits
    via a generator-style emitter that already committed. For V1 Schwab path,
    the all-or-nothing semantic is simpler + the discrepancy state is fully
    re-deriveable from the same source response.

    Returns:
        The persisted `ReconciliationRun` dataclass (final state =
        'completed' or 'failed').

    Raises:
        CallerHeldTransactionError on caller-held tx.
        Any exception during emit propagates (after the failure-path UPDATE
        is applied + committed).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "run_schwab_reconciliation owns its own transaction; caller MUST "
            "NOT hold an open transaction. See CLAUDE.md gotcha "
            "'in_transaction auto-detect outer transaction guards re-introduce "
            "the very race the explicit lock was meant to close'."
        )

    started_ts = now_ms()

    # Pre-compute snapshot fields BEFORE BEGIN so any read-side helpers that
    # might open their own implicit auto-tx don't conflict with our BEGIN.
    source_nlv: float | None = (
        float(schwab_account.net_liquidating_value)
        if schwab_account is not None else None
    )
    journal_snap = get_latest_snapshot_on_or_before(
        conn, asof_date=period_end,
    )
    journal_equity: float | None = (
        journal_snap.equity_dollars if journal_snap is not None else None
    )
    equity_delta: float | None = None
    if source_nlv is not None and journal_equity is not None:
        # Sign convention per Phase 9 Sub-bundle C T-C.6 = journal MINUS source.
        equity_delta = journal_equity - source_nlv

    # Pre-read open trades + their fills + journal cash_movements (read-side;
    # uses implicit auto-tx if any but won't conflict because we haven't
    # BEGIN-ed yet).
    open_trades = list_open_trades(conn)
    trade_fills: dict[int, list] = {
        t.id: list_fills_for_trade(conn, trade_id=t.id) for t in open_trades
    }
    # Filter journal cash_movements to the reconciliation period.
    all_journal_cash = list_cash(conn)
    journal_cash_in_period = [
        cm for cm in all_journal_cash
        if (
            cm.date and period_start <= cm.date <= period_end
        )
    ]

    counters: dict[str, int] = {
        "discrepancies_count": 0,
        "unresolved_discrepancies_count": 0,
        "trades_reconciled_count": len(open_trades),
        "fills_reconciled_count": 0,
    }
    dedup_seen: set = set()
    cash_warnings: list[dict] = []  # Arc 4b — #27 channel (Task 9 surfaces it)
    cash_counters: dict[str, int] = _empty_cash_counters()

    # Outer transaction. We INSERT the run row, emit discrepancies, then
    # UPDATE state='completed' (or UPDATE state='failed' on mid-emit error).
    #
    # Codex R1 M#5 fix — mirror swing/trades/reconciliation.py:run_tos_reconciliation
    # failure-path semantics per spec §3.3.3: PRESERVE the run row + any
    # partial discrepancies emitted prior to the failure via UPDATE state='failed'
    # in the SAME outer transaction, then COMMIT (audit-trail integrity over
    # rollback purity). The previous design rolled back the whole transaction
    # and INSERTed a fresh failed-state row, which (a) lost partial discrepancy
    # rows and (b) diverged from Phase 9 Sub-bundle B's contract.
    run_id: int | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        run_id = repo.insert_run(
            conn,
            source="schwab_api",
            state="running",
            started_ts=started_ts,
            source_artifact_path=(
                f"schwab_api:call/{schwab_api_call_id}"
                if schwab_api_call_id is not None
                else "schwab_api:run"
            ),
            source_artifact_sha256=None,
            period_start=period_start,
            period_end=period_end,
            account_equity_journal_dollars=journal_equity,
            account_equity_source_dollars=source_nlv,
            equity_delta_dollars=equity_delta,
            schwab_api_call_id=schwab_api_call_id,
        )

        # --- 4. Stop mismatch ---
        for t in open_trades:
            if t.current_stop is None:
                continue
            stop_order = _find_working_stop_for_ticker(schwab_orders, t.ticker)
            if stop_order is None:
                # Open trade with no Schwab-side working stop is NOT itself a
                # discrepancy (operator may not have placed a working stop;
                # the journal carries the mental-stop value). V2 may add a
                # "missing_working_stop" advisory; V1 silent.
                continue
            schwab_price = float(stop_order.price)
            if abs(schwab_price - t.current_stop) > price_tolerance:
                _emit(
                    conn,
                    run_id=run_id,
                    discrepancy_type="stop_mismatch",
                    field_name="current_stop",
                    counters=counters,
                    dedup_seen=dedup_seen,
                    ticker=t.ticker,
                    trade_id=t.id,
                    expected_value_json=json.dumps(
                        {"current_stop": t.current_stop}, sort_keys=True,
                    ),
                    actual_value_json=json.dumps(
                        {"stop_price": schwab_price}, sort_keys=True,
                    ),
                    delta_text=(
                        f"${schwab_price - t.current_stop:+.2f} "
                        f"(schwab minus journal)"
                    ),
                )

        # --- 5. Position qty mismatch ---
        schwab_positions = getattr(schwab_account, "positions", []) or []
        for t in open_trades:
            schwab_qty = _find_position_qty(schwab_positions, t.ticker)
            if schwab_qty is None:
                continue
            # Journal qty = sum of entry-side fill quantities - close-side fill quantities.
            journal_qty = 0.0
            for f in trade_fills.get(t.id, []):
                sign = 1.0 if f.action == "entry" else -1.0
                journal_qty += sign * float(f.quantity)
            if abs(schwab_qty - journal_qty) > price_tolerance:
                _emit(
                    conn,
                    run_id=run_id,
                    discrepancy_type="position_qty_mismatch",
                    field_name="position_qty",
                    counters=counters,
                    dedup_seen=dedup_seen,
                    ticker=t.ticker,
                    trade_id=t.id,
                    expected_value_json=json.dumps(
                        {"qty": journal_qty}, sort_keys=True,
                    ),
                    actual_value_json=json.dumps(
                        {"qty": schwab_qty}, sort_keys=True,
                    ),
                    delta_text=(
                        f"{schwab_qty - journal_qty:+.2f} "
                        f"(schwab minus journal)"
                    ),
                )

        # --- 6. Fill matching (price + unmatched) ---
        # Sub-bundle 1 T-1.6: candidate-pool widening via
        # `_is_execution_bearing_candidate` per plan §A.0.1 D4 + Codex R1
        # M#1+M#2. Admits MARKET fills with price=None + executions populated,
        # AND partial-then-canceled / partial-then-replaced orders with
        # non-empty executions, AND legacy FILLED-with-price-no-executions
        # (V1 backward compat → Path B sentinel emit downstream).
        schwab_filled = [
            o for o in schwab_orders
            if _is_execution_bearing_candidate(o)
        ]
        # Build a map of journal-fill identity -> matched Schwab order index.
        matched_schwab_idx: set = set()
        for t in open_trades:
            for f in trade_fills.get(t.id, []):
                counters["fills_reconciled_count"] += 1
                # Find a Schwab order matching (ticker, qty within tolerance).
                match_idx = None
                for idx, so in enumerate(schwab_filled):
                    if idx in matched_schwab_idx:
                        continue
                    if so.instrument_symbol != t.ticker:
                        continue
                    # Sub-bundle 1 T-1.7: execution-grain quantity-match per
                    # Codex R1 M#2. _resolve_match_quantity returns
                    # sum(legs.quantity) when executions populated; else
                    # so.quantity (V1 backward compat). Closes the in-row
                    # quantity comparison defect for partial fills where
                    # order.quantity reflects the OPEN order size, not the
                    # FILLED quantity.
                    if abs(
                        _resolve_match_quantity(so) - float(f.quantity)
                    ) > price_tolerance:
                        continue
                    match_idx = idx
                    break
                if match_idx is None:
                    # Unmatched journal fill.
                    dtype = (
                        "unmatched_open_fill" if f.action == "entry"
                        else "unmatched_close_fill"
                    )
                    _emit(
                        conn,
                        run_id=run_id,
                        discrepancy_type=dtype,
                        field_name="fill_match",
                        counters=counters,
                        dedup_seen=dedup_seen,
                        ticker=t.ticker,
                        trade_id=t.id,
                        fill_id=f.fill_id,
                        expected_value_json=json.dumps(
                            {
                                "qty": float(f.quantity),
                                "price": float(f.price),
                                "action": f.action,
                            },
                            sort_keys=True,
                        ),
                        actual_value_json=json.dumps(
                            {"matched": None}, sort_keys=True,
                        ),
                    )
                    continue
                matched_schwab_idx.add(match_idx)
                so = schwab_filled[match_idx]
                # Sub-bundle 1 T-1.6: switch price comparison to
                # execution-grain via `_compute_execution_price`. When
                # `executions` is None / empty (V1 mapper / sandbox /
                # mapper-coherence-check collapse), Path B emits
                # unmatched_*_fill with `execution_unavailable=true`
                # sentinel per spec §6.1 OQ-A LOCK.
                execution_price = _compute_execution_price(so)
                if execution_price is None:
                    # OQ-A Path B sentinel emit.
                    dtype_b = (
                        "unmatched_open_fill" if f.action == "entry"
                        else "unmatched_close_fill"
                    )
                    _emit(
                        conn,
                        run_id=run_id,
                        discrepancy_type=dtype_b,
                        field_name="fill_match",
                        counters=counters,
                        dedup_seen=dedup_seen,
                        ticker=t.ticker,
                        trade_id=t.id,
                        fill_id=f.fill_id,
                        expected_value_json=json.dumps(
                            {
                                "qty": float(f.quantity),
                                "price": float(f.price),
                                "action": f.action,
                            },
                            sort_keys=True,
                        ),
                        actual_value_json=json.dumps(
                            {
                                "matched": None,
                                "execution_unavailable": True,
                                "schwab_order_id": so.order_id,
                                "schwab_order_price": so.price,
                            },
                            sort_keys=True,
                        ),
                    )
                    continue
                if abs(execution_price - float(f.price)) > price_tolerance:
                    dtype = (
                        "entry_price_mismatch" if f.action == "entry"
                        else "close_price_mismatch"
                    )
                    # Sub-bundle 1 T-1.6 Shape C contract: actual_value_json
                    # key-set EXACTLY {"price", "execution_legs",
                    # "schwab_order_id", "schwab_order_price"} for the T-1.8
                    # Pass-1 classifier predicate. Naming "schwab_order_price"
                    # (NOT "schwab_limit_price") covers MKT (None) / STOP
                    # (trigger) / LIMIT (limit) order_types gracefully per
                    # plan §A.1.6 R3 m#2.
                    _emit(
                        conn,
                        run_id=run_id,
                        discrepancy_type=dtype,
                        field_name="price",
                        counters=counters,
                        dedup_seen=dedup_seen,
                        ticker=t.ticker,
                        trade_id=t.id,
                        fill_id=f.fill_id,
                        expected_value_json=json.dumps(
                            {"price": float(f.price)}, sort_keys=True,
                        ),
                        actual_value_json=json.dumps(
                            {
                                "price": execution_price,
                                "execution_legs": [
                                    {
                                        "leg_id": leg.leg_id,
                                        "price": leg.price,
                                        "quantity": leg.quantity,
                                        "time": leg.time,
                                    }
                                    for leg in so.executions
                                ],
                                "schwab_order_id": so.order_id,
                                "schwab_order_price": so.price,
                            },
                            sort_keys=True,
                        ),
                        # 4-decimal precision per plan §A.1.6: covers
                        # CVGI $0.0056 + LION $0.0001 sub-cent debugging.
                        delta_text=(
                            f"${execution_price - float(f.price):+.4f} "
                            f"(schwab execution minus journal)"
                        ),
                    )

        # --- 6.5. Arc 4b auto-ingestion (runs INSIDE this BEGIN, BEFORE the
        # step-7 journal->source scan). Coverage-gap detection first, then the
        # ref-idempotent append-only ingest ladder. INSERTs into cash_movements
        # mean step 7 + the equity check (Task 8) RE-READ list_cash afterwards.
        _detect_coverage_gap(
            conn, period_start=period_start, cash_warnings=cash_warnings)
        cash_counters = _ingest_cash_transactions(
            conn,
            run_id=run_id,
            schwab_transactions=schwab_transactions,
            price_tolerance=price_tolerance,
            cash_warnings=cash_warnings,
            dedup_seen=dedup_seen,
            counters=counters,
        )
        # Re-read journal cash after ingestion so step 7 scans the updated
        # ledger (freshly-ingested rows match their own source tx by ref).
        all_journal_cash = list_cash(conn)
        journal_cash_in_period = [
            cm for cm in all_journal_cash
            if (cm.date and period_start <= cm.date <= period_end)
        ]

        # --- 7. Cash-movement mismatch (Codex R1 M#6 fix) ---
        # For each journal cash_movement in the period, try to match against
        # a Schwab transaction by (date, amount within tolerance) + the
        # `kind` -> Schwab-type mapping (deposit -> ACH_RECEIPT/WIRE_IN/...;
        # withdraw -> ACH_DISBURSEMENT/WIRE_OUT/...). When the journal-side
        # has a row with no Schwab counterpart, emit cash_movement_mismatch.
        # V1 conservative: this is the journal-without-source direction;
        # source-side-without-journal (Schwab has TX not in journal) is a
        # V2 widening (operator may post-hoc the cash_movement after running
        # reconciliation).
        _matched_schwab_tx: set = set()
        for cm in journal_cash_in_period:
            j_amount = abs(float(cm.amount))
            # Arc 4b Task 7 — the 5-kind kind->type map (interest/dividend/fee
            # ride DIVIDEND_OR_INTEREST; sign disambiguates). Unknown kinds
            # cannot occur (the CHECK + validator constrain to the 5).
            expected_types = _CASH_KIND_TO_SCHWAB_TYPES.get(cm.kind, frozenset())
            # Sign: deposit/interest/dividend match a POSITIVE net_amount;
            # withdraw/fee match a NEGATIVE one. Disambiguates the sign-
            # ambiguous ELECTRONIC_FUND + the income/fee split on DIVIDEND_OR_
            # INTEREST. Strict inequalities — zero net_amount matches neither.
            want_sign_positive = cm.kind in _CASH_KIND_SIGN_POSITIVE
            match_idx = None
            for idx, tx in enumerate(schwab_transactions):
                if idx in _matched_schwab_tx:
                    continue
                if tx.type not in expected_types:
                    continue
                if (
                    (want_sign_positive and tx.net_amount <= 0)
                    or (not want_sign_positive and tx.net_amount >= 0)
                ):
                    continue
                # Arc 4b Task 7 — ±4-day shared window predicate (was an exact-
                # date equality; the brittleness that produced the live 66/67).
                if not _within_cash_match_window(
                    tx.transaction_date, cm.date, days=4,
                ):
                    continue
                if abs(abs(tx.net_amount) - j_amount) > price_tolerance:
                    continue
                match_idx = idx
                break
            if match_idx is None:
                # Journal-direction pending-only suppression (spec §4.3): skip
                # the emit when an OPEN pending already exists for this cm.id
                # (counted, so the run record still shows the condition).
                if cm.id is not None and conn.execute(
                    "SELECT 1 FROM reconciliation_discrepancies "
                    "WHERE discrepancy_type='cash_movement_mismatch' "
                    "AND cash_movement_id = ? "
                    "AND resolution='pending_ambiguity_resolution' LIMIT 1",
                    (int(cm.id),),
                ).fetchone() is not None:
                    cash_counters["cash_pending_suppressed_count"] += 1
                    continue
                _emit(
                    conn,
                    run_id=run_id,
                    discrepancy_type="cash_movement_mismatch",
                    field_name="net_amount",
                    counters=counters,
                    dedup_seen=dedup_seen,
                    cash_movement_id=cm.id,
                    expected_value_json=json.dumps(
                        {
                            "date": cm.date,
                            "kind": cm.kind,
                            "amount": cm.amount,
                        },
                        sort_keys=True,
                    ),
                    actual_value_json=json.dumps(
                        {"matched": None}, sort_keys=True,
                    ),
                )
            else:
                _matched_schwab_tx.add(match_idx)

        # --- 8. Equity delta ---
        if equity_delta is not None and abs(equity_delta) > EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS:
            _emit(
                conn,
                run_id=run_id,
                discrepancy_type="equity_delta",
                field_name="net_liquidating_value",
                counters=counters,
                dedup_seen=dedup_seen,
                expected_value_json=json.dumps(
                    {"equity_dollars": journal_equity}, sort_keys=True,
                ),
                actual_value_json=json.dumps(
                    {"equity_dollars": source_nlv}, sort_keys=True,
                ),
                delta_text=f"${equity_delta:+.2f} (journal minus source)",
            )

        # --- 8.5. PHASE 12 C.C PIVOT: classify + dispatch per discrepancy ---
        # Spec §7.1 LOCKED savepoint-per-discrepancy discipline. NEVER raises
        # out (graceful degradation per spec §7.4). Plan §D.5 step 3 LOCK:
        # under sandbox we STILL iterate + classify (so classifier counters
        # reflect what would have happened) but pass environment='sandbox'
        # through to `_apply_tier1_correction_inner` which short-circuits
        # the journal mutation. tier1_applied_count stays 0 naturally
        # because the inner returns correction_id=None and the counter
        # increment guards on that.
        _pivot_classify_and_dispatch_for_run(
            conn,
            run_id=run_id,
            schwab_orders=schwab_orders,
            schwab_api_call_id=schwab_api_call_id,
            environment=environment,
            counters=counters,
        )

        # --- 9. UPDATE state='completed' ---
        finished_ts = now_ms()
        if finished_ts < started_ts:
            finished_ts = started_ts

        # Codex R1 Major #3 — recompute unresolved_discrepancies_count
        # post-pivot. _emit increments at INSERT time; the pivot flips
        # rows OFF 'unresolved' (tier-1 → auto_corrected_from_schwab;
        # tier-2 → pending_ambiguity_resolution). Recomputing from the
        # canonical resolution column is more robust than tracking
        # decrement deltas in counter state.
        unresolved_now = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE run_id = ? AND resolution = 'unresolved'",
            (run_id,),
        ).fetchone()[0]
        counters["unresolved_discrepancies_count"] = int(unresolved_now)

        summary = {
            "open_trades_checked": len(open_trades),
            "schwab_orders_checked": len(schwab_orders),
            "schwab_transactions_checked": len(schwab_transactions),
            "discrepancies_emitted": counters["discrepancies_count"],
            "tier1_applied_count": counters.get("tier1_applied_count", 0),
            "tier2_pending_count": counters.get("tier2_pending_count", 0),
            "tier3_overridden_count": 0,  # always 0 — tier-3 is post-run operator-initiated
            "tier_errored_count": counters.get("tier_errored_count", 0),
            # Arc 4b — auto-ingestion counters + the #27 cash_warnings channel.
            **cash_counters,
            "cash_warnings": cash_warnings,
        }
        repo.update_run_completed(
            conn,
            run_id=run_id,
            finished_ts=finished_ts,
            trades_reconciled_count=counters["trades_reconciled_count"],
            fills_reconciled_count=counters["fills_reconciled_count"],
            discrepancies_count=counters["discrepancies_count"],
            unresolved_discrepancies_count=counters["unresolved_discrepancies_count"],
            summary_json=json.dumps(summary, sort_keys=True),
            account_equity_journal_dollars=journal_equity,
            account_equity_source_dollars=source_nlv,
            equity_delta_dollars=equity_delta,
        )
        conn.commit()
    except CallerHeldTransactionError:
        raise
    except Exception as exc:
        # Codex R1 M#5 — failure-path PRESERVES the run row + partial
        # discrepancies inside the SAME outer transaction per spec §3.3.3.
        # Mirrors run_tos_reconciliation: UPDATE state='failed', COMMIT.
        # If run_id is None (failure BEFORE the run-row INSERT landed),
        # rollback semantics apply (outer-layer failure; nothing to preserve).
        if run_id is None:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            raise
        try:
            failed_finished_ts = now_ms()
            if failed_finished_ts < started_ts:
                failed_finished_ts = started_ts
            # Best-effort UPDATE in the same outer transaction. If the BEGIN
            # IMMEDIATE write-lock was lost (concurrent force_clear), the
            # update may fail; suppress + commit-or-rollback to avoid
            # masking the original exception. Either way the original
            # exception propagates to the caller.
            try:
                repo.update_run_failed(
                    conn,
                    run_id=run_id,
                    finished_ts=failed_finished_ts,
                    error_message=f"{type(exc).__name__}: {exc!s}"[:200],
                )
                conn.commit()
            except sqlite3.Error:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
        finally:
            # Always propagate the original exception.
            pass
        raise

    out = repo.get_run(conn, run_id)
    assert out is not None  # we just committed
    return out


__all__ = [
    "CallerHeldTransactionError",
    "run_schwab_reconciliation",
]
