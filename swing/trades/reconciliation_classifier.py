"""Phase 12 Sub-sub-bundle C.B — pure-logic discrepancy classifier.

Spec §4 ``classify_discrepancy`` + per-discrepancy-type sub-classifiers.

Public entry: :func:`classify_discrepancy` (pure function; no DB writes; no
external API calls; no transaction management). Caller supplies pre-fetched
``source_payload`` + ``journal_row`` data. Per-type sub-classifiers register
into ``_SUB_CLASSIFIERS`` at module-load time; ``classify_discrepancy``
dispatches on ``discrepancy.discrepancy_type``.

Determinism contract (spec §4.4): same inputs → same ``ClassificationResult``
byte-for-byte. Frozen dataclass equality is deep.

Failure-mode contract (spec §4.5): unknown ``discrepancy_type`` or
sub-classifier exception → ``(tier=2, ambiguity_kind='unsupported',
correction_target=None, correction_reason="classifier exception: ...")``.
Pipeline / CLI never crashes from a classifier defect.

Validator-respecting downgrade (spec §4.6): when ``validator_chain`` is
supplied AND the sub-classifier returned tier-1, the dispatcher invokes
``validator_chain(correction_target)``. On ``(False, reason)``, the
dispatcher downgrades to ``(tier=2, ambiguity_kind='validator_rejected',
correction_target=None, correction_reason="validator rejected proposed
correction: <reason or 'unknown'>")``.

Pass-2-tier-1-FORBIDDEN LOCK (spec §8.4): ``_classify_unmatched_open_fill``
+ ``_classify_unmatched_close_fill`` NEVER emit tier-1 in V1 regardless of
Pass-2 input shape. Order-level Schwab data is limit/order price, not
execution price; cannot drive tier-1 auto-correct without operator-side
broker-statement consultation.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from swing.data.models import ReconciliationDiscrepancy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationResult:
    """Classifier output — pure data shape; tier ∈ {1, 2}.

    Tier-3 is operator-initiated post-tier-1; the classifier NEVER emits
    ``tier=3``. ``ambiguity_kind`` MUST be ``None`` when ``tier == 1`` and
    MUST be one of the 7-value enum from migration 0019 line 125-129 when
    ``tier == 2`` (cross-column CHECK precedence per C.A lesson #2 +
    migration 0019 cross-column CHECK at lines 135-147).

    ``candidate_choices`` is ``None`` for tier-1; for tier-2 it is a list of
    per-choice dicts with keys ``code`` / ``description`` / ``requires_custom_value:
    bool`` per spec §6.2.1 LOCKED contract (Codex R5 Major #2 fix).
    """

    tier: int
    ambiguity_kind: str | None
    correction_target: dict[str, Any] | None
    correction_reason: str
    candidate_choices: list[dict[str, Any]] | None = None
    # Phase 12.5 #1 T-1.2 — multi-leg auto-redirect recipe (spec §6.1).
    # Populated ONLY by ``_classify_unmatched_fill_shared`` on the multi-leg
    # auto-redirect path; every other emit path leaves this at ``None`` via
    # the dataclass default. The recipe is consumed by the pivot loop (T-1.5)
    # to dispatch through ``apply_tier2_resolution(choice_code='split_into_partials',
    # resolved_by='auto_tier1_multi_leg', ...)`` per spec §2.3 + §6.5 LOCK.
    # MUST BE THE LAST FIELD (F23 / L-W4): preserves positional construction
    # at all pre-existing call sites and pins dataclass field order for
    # downstream consumers.
    auto_redirect_recipe: Mapping[str, Any] | None = None


# Callable contract: ``(correction_target) -> (passes, rejection_reason_or_None)``.
# The dispatcher calls this with a single positional arg; callers compose
# ``default_validator_chain`` via ``functools.partial`` at C.C construction
# time to bind ``affected_table`` + ``affected_row_id`` (spec §5.5).
ValidatorChainCallable = Callable[[Mapping[str, Any]], tuple[bool, str | None]]


# Dispatch table populated as sub-classifiers land (T-B.3..T-B.12 register
# into this dict at module-load time via direct assignment below their
# function definitions). Unknown discrepancy_type values miss this lookup
# and trigger the graceful-degradation path at the dispatcher.
_SUB_CLASSIFIERS: dict[str, Callable[..., ClassificationResult]] = {}


# ---------------------------------------------------------------------------
# Sub-bundle 1 T-1.8 — Shape C audit-key constants (post-Phase-12 mapper
# execution-grain widening).
# ---------------------------------------------------------------------------
#
# Shape C is the comparator emit shape introduced by T-1.6 when execution-
# grain price data is available from the V2 mapper. The comparator at
# ``swing/trades/schwab_reconciliation.py`` emits ``actual_value_json`` with
# EXACTLY these key-sets when the journal price diverges from the
# computed execution price (via ``_compute_execution_price`` single-leg or
# VWAP for multi-leg).
#
# The classifier's Shape C branch matches this exact key-set + emits tier-1
# with ``correction_target = {'price': source_payload['price']}``. Audit
# keys (``execution_legs`` + ``schwab_order_id`` + ``schwab_order_price``)
# are observational ONLY at classifier — they live in the persisted
# ``actual_value_json`` column and are queryable via
# ``SELECT json_extract(actual_value_json, '$.execution_legs') FROM
# reconciliation_discrepancies WHERE id = ?``. The classifier does NOT copy
# them into ``correction_reason`` (which would balloon the string).
#
# Per plan §A.1.8 + spec §3.2 + §5.2 + §10.3-§10.6.

_EXECUTION_AUDIT_KEYS: frozenset[str] = frozenset({
    "execution_legs", "schwab_order_id", "schwab_order_price",
})
_SHAPE_C_EXPECTED_KEYS: frozenset[str] = frozenset({"price"}) | _EXECUTION_AUDIT_KEYS


# ---------------------------------------------------------------------------
# Phase 12.5 #1 T-1.1 — multi-leg auto-redirect predicate + recipe synthesizer
# ---------------------------------------------------------------------------
#
# Operator-locked tolerances per spec §4.4 + §15.B #1 + #2 (2026-05-17):
# - price tolerance: $0.01 absolute (NO ``max(...)`` proportional override).
# - quantity tolerance at predicate: 1e-9 (stricter than the
#   ``apply_tier2_resolution`` handler's 1e-6; predicate-stricter asymmetry
#   is safe — handler accepts everything the predicate would have).
#
# Predicate + synthesizer are PURE (no DB, no API, no logging). T-1.11 adds
# the ONE documented canary ``logger.warning`` for empty-executions cases;
# DO NOT add logging here.
#
# Classifier-boundary contract (F25 / L-W6): predicate consumes
# ``Mapping``-shaped candidates ONLY — plain dicts with ``executions`` value
# of ``list[Mapping]`` carrying ``leg_id`` / ``price`` / ``quantity`` /
# ``time`` keys. ``SchwabExecutionLeg`` dataclass → dict conversion is
# T-1.3's responsibility at ``_orders_to_classifier_payload``.

_MULTI_LEG_PRICE_TOLERANCE: float = 0.01   # absolute $0.01; NO max(...) override path
_MULTI_LEG_QTY_TOLERANCE: float = 1e-9     # predicate-stricter than handler's 1e-6


def _multi_leg_auto_redirect_predicate(
    *,
    candidates: list[Mapping[str, Any]],
    journal_qty: float,
    journal_price: float,
    price_tolerance: float = _MULTI_LEG_PRICE_TOLERANCE,
) -> tuple[bool, str | None]:
    """Decide whether classifier may auto-redirect this candidate set to
    ``split_into_partials`` tier-1.

    Spec §4.3 — ALL 6 sub-conditions must hold:

      1. Every candidate carries a non-empty ``executions`` list.
      2. ``sum(len(c.executions) for c in candidates) >= 2``.
      3. Each leg's ``price`` and ``quantity`` is a real numeric value
         (not ``bool``), finite, and strictly positive.
      4. ``sum(leg.quantity)`` matches ``journal_qty`` within
         ``_MULTI_LEG_QTY_TOLERANCE`` (1e-9).
      5. ``abs(VWAP - journal_price) <= price_tolerance``. VWAP =
         ``sum(price*qty) / sum(qty)``.
      6. Per-leg consistency: ``abs(leg.price - VWAP) <= price_tolerance``
         for every leg.

    Sub-condition 3 executes BEFORE 4/5/6 so NaN/inf/bool inputs cannot
    poison the arithmetic.

    Returns ``(True, None)`` when ALL hold; otherwise ``(False, reason)``
    where ``reason`` cites the failing sub-condition + relevant numeric
    values for forensic transparency (spec §5.4).

    PURE function: no DB / API / logging.
    """
    # Sub-condition 1: every candidate has a non-empty executions list.
    for cand in candidates:
        executions = cand.get("executions")
        if executions is None or len(executions) == 0:
            order_id = cand.get("order_id", "<unknown>")
            return (
                False,
                f"sub-condition 1: candidate order_id={order_id} has no execution legs",
            )

    # Flatten all legs in input order for sub-conditions 2-6.
    all_legs: list[Mapping[str, Any]] = []
    for cand in candidates:
        for leg in cand["executions"]:
            all_legs.append(leg)

    # Sub-condition 2: total leg count >= 2.
    if len(all_legs) < 2:
        return (
            False,
            f"sub-condition 2: insufficient total leg count {len(all_legs)}; need at least 2",
        )

    # Sub-condition 3: per-leg numeric/finite/positive (BEFORE arithmetic).
    for i, leg in enumerate(all_legs, start=1):
        price = leg.get("price")
        qty = leg.get("quantity")
        if isinstance(price, bool) or isinstance(qty, bool):
            return (
                False,
                f"sub-condition 3: leg #{i} price={price!r} or "
                f"quantity={qty!r} is not numeric (bool rejected)",
            )
        if not isinstance(price, (int, float)) or not isinstance(qty, (int, float)):
            return (
                False,
                f"sub-condition 3: leg #{i} price={price!r} or "
                f"quantity={qty!r} is not numeric",
            )
        if not (math.isfinite(float(price)) and math.isfinite(float(qty))):
            return (
                False,
                f"sub-condition 3: leg #{i} price={price!r} or "
                f"quantity={qty!r} is not finite",
            )
        if float(price) <= 0.0 or float(qty) <= 0.0:
            return (
                False,
                f"sub-condition 3: leg #{i} price={price!r} or "
                f"quantity={qty!r} is not positive",
            )

    # Sub-condition 4: qty-sum matches journal_qty within tolerance.
    total_qty = sum(float(leg["quantity"]) for leg in all_legs)
    if abs(total_qty - float(journal_qty)) > _MULTI_LEG_QTY_TOLERANCE:
        return (
            False,
            f"sub-condition 4: execution leg qty sum {total_qty} does not "
            f"match journal_qty {journal_qty} within tolerance "
            f"{_MULTI_LEG_QTY_TOLERANCE}",
        )

    # Sub-condition 5: VWAP vs journal_price within tolerance.
    vwap = sum(float(leg["price"]) * float(leg["quantity"]) for leg in all_legs) / total_qty
    vwap_journal_delta = abs(vwap - float(journal_price))
    if vwap_journal_delta > price_tolerance:
        return (
            False,
            f"sub-condition 5: VWAP {vwap:.6f} vs journal_price "
            f"{journal_price:.6f} delta {vwap_journal_delta:.6f} exceeds "
            f"tolerance {price_tolerance}",
        )

    # Sub-condition 6: per-leg consistency vs VWAP. Cite the WORST outlier
    # (max abs-delta) for forensic transparency per spec §5.4 — a uniform
    # tolerance can fail multiple legs symmetrically; the operator wants
    # the outlier identified, not the first-walked failure.
    worst_idx: int | None = None
    worst_price: float = 0.0
    worst_delta: float = 0.0
    for i, leg in enumerate(all_legs, start=1):
        leg_price = float(leg["price"])
        leg_delta = abs(leg_price - vwap)
        if leg_delta > price_tolerance and leg_delta > worst_delta:
            worst_idx = i
            worst_price = leg_price
            worst_delta = leg_delta
    if worst_idx is not None:
        return (
            False,
            f"sub-condition 6: leg #{worst_idx} price {worst_price} vs VWAP "
            f"{vwap:.6f} delta {worst_delta:.6f} exceeds tolerance "
            f"{price_tolerance}",
        )

    return (True, None)


def _synthesize_split_into_partials_recipe(
    candidates: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Build the ``auto_redirect_recipe`` dict per spec §6.1.

    PRE-CONDITION: caller MUST have invoked
    :func:`_multi_leg_auto_redirect_predicate` first and received
    ``(True, None)``. This synthesizer is unsafe on declined inputs — it
    does NOT re-validate numeric types / empty executions / qty sums.

    Payload iteration order is the concatenation of
    ``candidates[i].executions[j]`` preserving input order.

    PURE function: no DB / API / logging.
    """
    payload: list[dict[str, Any]] = []
    for cand in candidates:
        executions = cand.get("executions") or []
        for leg in executions:
            payload.append(
                {
                    "qty": float(leg["quantity"]),
                    "price": float(leg["price"]),
                    "fill_datetime": str(leg["time"]),
                }
            )
    return {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# T-B.3 — entry_price_mismatch sub-classifier (CVGI 41 path)
# ---------------------------------------------------------------------------
#
# Spec §4.3.1 + §10.1 BINDING walkthrough.
#
# Tier-1 path: (ticker, date, quantity) match exactly between journal and
# source; only price differs. correction_target = {'price': source_price}.
#
# Tier-2 paths:
# - source_payload is None → schwab_returned_no_match
# - explicit multiple-match shape → multi_match_within_window (V1 default
#   per shipped emitter is single-fill match; this branch is defensive)


def _classify_entry_price_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.1 + §10.1 — CVGI 41 walkthrough.

    INPUT shape (per dispatch-brief reading of spec §4.3.1):
    - ``source_payload`` is the broker-side dict like ``{"price": 5.30}``
      (+ optional (ticker, date, quantity) tuple keys for completeness).
    - ``journal_row`` is the journal-side dict like ``{"price": 5.23,
      "quantity": 100, "ticker": "CVGI", "fill_datetime": "..."}``.

    LOGIC:
    - source_payload is None → tier-2 ``schwab_returned_no_match``.
    - source_payload signals multiple matches (list shape OR explicit
      ``_multi_match=True``) → tier-2 ``multi_match_within_window``.
    - Otherwise compare journal_row vs source_payload keys; if only price
      differs (or source_payload has only ``price`` key — V1 shipped
      emitter shape), emit tier-1 with correction_target = {'price': X}.
    """
    if source_payload is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="schwab_returned_no_match",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): Schwab returned no "
                f"matching record; classifier cannot disposition without "
                f"source data; operator dispositions manually"
            ),
            candidate_choices=[
                {
                    "code": "mark_unmatched",
                    "description": (
                        "Acknowledge no Schwab record matches; no journal "
                        "mutation"
                    ),
                    "requires_custom_value": False,
                },
                {
                    "code": "operator_truth",
                    "description": (
                        "Operator supplies the true execution price via "
                        "--custom-value '{\"price\": X.XX}'"
                    ),
                    "requires_custom_value": True,
                },
            ],
        )

    # Multi-match shape: list of dicts or explicit signal.
    if isinstance(source_payload, list) and len(source_payload) > 1:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="multi_match_within_window",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): {len(source_payload)} "
                f"Schwab records within match window; operator picks the "
                f"intended record"
            ),
            candidate_choices=(
                [
                    {
                        "code": f"pick_schwab_record_{i + 1}",
                        "description": (
                            f"Apply Schwab record #{i + 1} as the "
                            f"canonical source for this fill (REQUIRES "
                            f"--custom-value with operator-supplied "
                            f"execution-level field values; Pass-2 "
                            f"candidates are order-grain, not execution-"
                            f"grain — per spec §4.3.2 LOCK)"
                        ),
                        "requires_custom_value": True,
                    }
                    for i in range(len(source_payload))
                ]
                + [
                    {
                        "code": "mark_unmatched",
                        "description": (
                            "Acknowledge no canonical match; no mutation"
                        ),
                        "requires_custom_value": False,
                    },
                    {
                        "code": "custom",
                        "description": (
                            "Operator-supplied arbitrary payload via "
                            "--custom-value"
                        ),
                        "requires_custom_value": True,
                    },
                ]
            ),
        )

    # Single-match (V1 shipped emitter shape from
    # swing/trades/schwab_reconciliation.py:469-474).
    if not isinstance(source_payload, Mapping):
        # Unexpected scalar / sequence shape with length<=1; treat as
        # unsupported rather than crash.
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): source_payload shape "
                f"{type(source_payload).__name__} not understood by "
                f"classifier"
            ),
        )

    # Sub-bundle 1 T-1.8 — Shape C predicate.
    # ADDITIONAL (not replacement): Sub-bundle C.B Shape A + Shape B
    # predicates preserved unchanged below. Shape C matches the comparator
    # emit shape introduced at T-1.6 when execution-grain price data is
    # available via the V2 mapper. Strict-set equality on
    # _SHAPE_C_EXPECTED_KEYS prevents false-positive matches on partial
    # Shape C payloads (which fall through to the Shape A/B path → tier-2
    # unsupported). Per plan §A.1.8 + spec §3.2 + §5.2 + §10.3-§10.6.
    if frozenset(source_payload.keys()) == _SHAPE_C_EXPECTED_KEYS:
        price = source_payload.get("price")
        if (
            isinstance(price, (int, float))
            and not isinstance(price, bool)
            and math.isfinite(float(price))
        ):
            return ClassificationResult(
                tier=1,
                ambiguity_kind=None,
                correction_target={"price": float(price)},
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): Schwab execution-grain "
                    f"price ${float(price):.4f}; auto-correct journal to "
                    f"execution (Sub-bundle 1 T-1.8 Shape C; audit keys "
                    f"in actual_value_json)"
                ),
                candidate_choices=None,
            )

    source_price = source_payload.get("price")
    if source_price is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): source_payload missing "
                f"'price' key; classifier cannot disposition"
            ),
        )

    # Codex R1 Critical #1 — defensive numeric guard on source_price.
    # Reject NaN/inf/non-numeric so tier-1 emission never carries a value
    # that mirrors a schema CHECK violation downstream. The persisted-JSON
    # emitter (swing/trades/schwab_reconciliation.py:469-474) only writes
    # finite floats, but a defensive guard keeps the classifier honest.
    try:
        source_price_float = float(source_price)
    except (TypeError, ValueError):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): source_payload 'price' "
                f"is non-numeric ({source_price!r}); classifier cannot "
                f"disposition"
            ),
        )
    if not math.isfinite(source_price_float):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): source_payload 'price' "
                f"is NaN/inf ({source_price!r}); classifier cannot "
                f"disposition"
            ),
        )

    # Codex R2 Major #1 — explicit shape predicate per spec §4.3.1 LOCK.
    # Tier-1 is allowed for EXACTLY TWO source_payload shapes:
    #
    #   Shape A (persisted-JSON-only): keys == {'price'}. This is the
    #     shipped emitter contract from
    #     swing/trades/schwab_reconciliation.py:469-474 (verifies the
    #     (ticker, date, quantity) tuple pre-emit and persists only the
    #     mismatching price).
    #
    #   Shape B (full match-tuple-bearing): source carries 'ticker' AND
    #     'quantity' AND at least one date-form ('date' OR 'fill_datetime'),
    #     and ALL three tuple components match journal_row. Recognized keys
    #     are the union {'price', 'ticker', 'quantity', 'date',
    #     'fill_datetime'}; any extra unrecognized keys reject.
    #
    # Any other shape (partial tuple, mixed unrecognized keys, journal_row
    # missing while richer-than-Shape-A) → tier-2 'unsupported' rather than
    # emit an ungrounded auto-correct.
    tuple_keys = {"ticker", "date", "fill_datetime", "quantity"}
    recognized_keys = tuple_keys | {"price"}
    source_keys = set(source_payload.keys())
    extra_keys = source_keys - recognized_keys

    is_shape_a = source_keys == {"price"}
    # Shape B requires ticker + quantity + at least one date-form, AND no
    # unrecognized extra keys.
    has_full_tuple_keys = (
        "ticker" in source_keys
        and "quantity" in source_keys
        and ("date" in source_keys or "fill_datetime" in source_keys)
    )
    is_shape_b_candidate = (
        has_full_tuple_keys and not extra_keys and not is_shape_a
    )

    if not is_shape_a and not is_shape_b_candidate:
        sorted_keys = sorted(source_keys)
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): source_payload shape "
                f"ambiguous — neither persisted-JSON-only ({{'price'}}) "
                f"nor full match-tuple (ticker+date+quantity); got "
                f"keys={sorted_keys}"
            ),
        )

    # journal_row missing entirely → cannot verify even Shape A's pre-emit
    # invariant from this side. Tier-2 unsupported.
    if journal_row is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"entry_price_mismatch on "
                f"(ticker={discrepancy.ticker!r}, "
                f"fill_id={discrepancy.fill_id}): journal_row missing — "
                f"cannot verify (ticker, date, quantity) match tuple per "
                f"spec §4.3.1; operator dispositions manually"
            ),
        )

    # Shape B path: verify each present tuple component matches
    # journal_row. Any DISAGREEING field → tier-2 unsupported naming the
    # disagreeing field (per R1 fix discipline, preserved).
    if is_shape_b_candidate:
        # Ticker consistency: case-insensitive string equality.
        src_ticker = source_payload.get("ticker")
        jr_ticker = journal_row.get("ticker")
        if src_ticker is None or jr_ticker is None or (
            str(src_ticker).strip().upper() != str(jr_ticker).strip().upper()
        ):
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): ticker mismatch "
                    f"between source_payload ({src_ticker!r}) and "
                    f"journal_row ({jr_ticker!r}); cannot verify match "
                    f"tuple per spec §4.3.1"
                ),
            )

        # Quantity consistency: exact equality (after numeric coercion).
        src_qty = source_payload.get("quantity")
        jr_qty = journal_row.get("quantity")
        try:
            src_qty_f = float(src_qty) if src_qty is not None else None
            jr_qty_f = float(jr_qty) if jr_qty is not None else None
        except (TypeError, ValueError):
            src_qty_f = jr_qty_f = None
        if src_qty_f is None or jr_qty_f is None or src_qty_f != jr_qty_f:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): quantity mismatch "
                    f"between source_payload ({src_qty!r}) and "
                    f"journal_row ({jr_qty!r}); cannot verify match "
                    f"tuple per spec §4.3.1"
                ),
            )

        # Date consistency: ISO-date-prefix equality. source_payload may
        # carry 'date' (date-only) AND/OR 'fill_datetime' (full ISO);
        # journal_row likewise. Per R3 Major #1 (determinism principle
        # §4.4): when source_payload carries BOTH date forms, BOTH
        # normalized values must agree with each other AND with at least
        # one journal date form. Contradictory source date evidence →
        # tier-2 'unsupported' rather than silently picking one form.
        source_date_forms: list[tuple[str, str]] = []
        if "date" in source_payload and source_payload.get("date") is not None:
            source_date_forms.append(
                ("date", str(source_payload.get("date"))[:10])
            )
        if (
            "fill_datetime" in source_payload
            and source_payload.get("fill_datetime") is not None
        ):
            source_date_forms.append(
                (
                    "fill_datetime",
                    str(source_payload.get("fill_datetime"))[:10],
                )
            )
        journal_date_forms: list[tuple[str, str]] = []
        if journal_row.get("date") is not None:
            journal_date_forms.append(
                ("date", str(journal_row.get("date"))[:10])
            )
        if journal_row.get("fill_datetime") is not None:
            journal_date_forms.append(
                (
                    "fill_datetime",
                    str(journal_row.get("fill_datetime"))[:10],
                )
            )

        if not source_date_forms:
            # Shape B requires at least one source date form (predicate
            # above guards on 'date' or 'fill_datetime' being a KEY, but
            # both could be None-valued).
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): source_payload "
                    f"date evidence missing (no 'date' or "
                    f"'fill_datetime' value); cannot verify match tuple "
                    f"per spec §4.3.1"
                ),
            )

        # Internal source consistency: if both forms are present, their
        # normalized values must agree. Contradictory tuple evidence →
        # tier-2 unsupported (determinism principle §4.4).
        distinct_source_prefixes = {prefix for _, prefix in source_date_forms}
        if len(distinct_source_prefixes) > 1:
            conflicting = ", ".join(
                f"{key}={prefix}" for key, prefix in source_date_forms
            )
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): contradictory "
                    f"source date evidence ({conflicting}); cannot verify "
                    f"match tuple per spec §4.3.1 (determinism principle "
                    f"§4.4 defaults to tier-2 when tuple evidence "
                    f"conflicts)"
                ),
            )

        # Internal journal consistency (mirrors source-side check above
        # per R4 Major #1): if both journal forms are present, their
        # normalized values must agree. Contradictory tuple evidence on
        # the journal side → tier-2 unsupported (determinism principle
        # §4.4). Checked BEFORE the source-vs-journal disagreement check
        # so journal-internal inconsistency is reported with its
        # specific reason rather than getting masked by the cross-side
        # disagreement reason.
        distinct_journal_prefixes = {prefix for _, prefix in journal_date_forms}
        if len(distinct_journal_prefixes) > 1:
            conflicting = ", ".join(
                f"{key}={prefix}" for key, prefix in journal_date_forms
            )
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): contradictory "
                    f"journal date evidence ({conflicting}); cannot verify "
                    f"match tuple per spec §4.3.1 (determinism principle "
                    f"§4.4 defaults to tier-2 when tuple evidence "
                    f"conflicts)"
                ),
            )

        # Source-vs-journal date agreement: every source date form must
        # agree with at least one journal date form. Equivalently, since
        # source prefixes are unique here, the single source date prefix
        # must appear in the journal's date forms. Empty
        # journal_date_forms → no agreement possible.
        source_prefix = next(iter(distinct_source_prefixes))
        journal_prefixes = distinct_journal_prefixes
        if not journal_prefixes or source_prefix not in journal_prefixes:
            src_render = ", ".join(
                f"{key}={prefix}" for key, prefix in source_date_forms
            ) or "(none)"
            jr_render = ", ".join(
                f"{key}={prefix}" for key, prefix in journal_date_forms
            ) or "(none)"
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): date mismatch "
                    f"between source_payload ({src_render}) and "
                    f"journal_row ({jr_render}); cannot verify match "
                    f"tuple per spec §4.3.1"
                ),
            )

    journal_price = journal_row.get("price")
    # Format prices to 2 decimals so the reason string carries a stable
    # numeric representation regardless of Python's float repr (e.g.,
    # 5.30 → 5.3 by default; we render 5.30 explicitly for observability).
    try:
        journal_price_str = f"${float(journal_price):.2f}"
    except (TypeError, ValueError):
        journal_price_str = f"${journal_price}"
    try:
        source_price_str = f"${float(source_price):.2f}"
    except (TypeError, ValueError):
        source_price_str = f"${source_price}"
    return ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": source_price},
        correction_reason=(
            f"entry_price_mismatch on "
            f"(ticker={discrepancy.ticker!r}, "
            f"fill_id={discrepancy.fill_id}): journal {journal_price_str} "
            f"vs Schwab {source_price_str}; single-fill match; tier-1 "
            f"auto-correct (delta={discrepancy.delta_text})"
        ),
        candidate_choices=None,
    )


_SUB_CLASSIFIERS["entry_price_mismatch"] = _classify_entry_price_mismatch


# ---------------------------------------------------------------------------
# T-B.4 + T-B.5 — unmatched_open_fill / unmatched_close_fill sub-classifiers
# ---------------------------------------------------------------------------
#
# Spec §4.3.2 + §4.3.3 + §8.4 Pass-2-tier-1-FORBIDDEN LOCK + §10.2 DHC 39 +
# §10.3 VSAT 40 BINDING walkthroughs.
#
# V1 LOCK: NEVER emits tier-1 regardless of Pass-2 input shape.
# ``SchwabOrderResponse.price`` is limit/stop price, not execution price
# (§8.4 + §A.7.4 mapper verification). Sub-classifier dispatches on
# source_payload shape:
#   - None / {"matched": null} → tier-2 ``unsupported`` with
#     ``_pass_2_required=True`` signal in correction_reason. Backfill
#     path (T-D.8) reads this signal to fire Pass 2.
#   - list-shaped, 0 elements → tier-2 ``schwab_returned_no_match``.
#   - list-shaped, 1 element → tier-2 ``unknown_schwab_subtype``.
#   - list-shaped, N>=2, sum(qty) == journal_qty → tier-2
#     ``multi_partial_vs_consolidated``.
#   - list-shaped, N>=2, sum(qty) != journal_qty → tier-2
#     ``multi_match_within_window``.
#
# candidate_choices populated per the spec §6.2.1 LOCKED menu per
# ambiguity_kind:
#   - multi_partial_vs_consolidated → 4 choices (keep_journal_as_is
#     HIGHLIGHTED FIRST per §0.4 OQ-4 + consolidate_using_operator_vwap
#     + split_into_partials + custom).
#   - multi_match_within_window → N+2 choices (pick_schwab_record_<i>
#     for i=1..N + mark_unmatched + custom).
#   - schwab_returned_no_match → 2 choices (mark_unmatched + operator_truth).
#   - unknown_schwab_subtype → 3 choices (acknowledge + operator_truth + custom).
#   - unsupported (_pass_2_required signal) → 0 candidate_choices V1.


def _candidate_choices_multi_partial_vs_consolidated() -> list[dict[str, Any]]:
    """Spec §6.2.1 — 4 choices; ``keep_journal_as_is`` HIGHLIGHTED FIRST."""
    return [
        {
            "code": "keep_journal_as_is",
            "description": (
                "Acknowledge Schwab partial-fill aggregation; no journal "
                "mutation (V1 default recommendation per §14.OQ-4)"
            ),
            "requires_custom_value": False,
        },
        {
            "code": "consolidate_using_operator_vwap",
            "description": (
                "Keep journal consolidated; update price to operator-"
                "supplied VWAP. REQUIRES --custom-value '{\"price\": "
                "X.XX}' (operator computes VWAP from broker execution "
                "statement; V1 mapper cannot auto-derive execution-level "
                "prices)"
            ),
            "requires_custom_value": True,
        },
        {
            "code": "split_into_partials",
            "description": (
                "Replace journal fill with N partial fills. REQUIRES "
                "--custom-value with execution-level partial-fill payload "
                "(operator supplies per-execution qty + price from broker "
                "statement)"
            ),
            "requires_custom_value": True,
        },
        {
            "code": "custom",
            "description": (
                "Operator-supplied arbitrary payload via --custom-value"
            ),
            "requires_custom_value": True,
        },
    ]


def _candidate_choices_multi_match_within_window(
    n: int,
) -> list[dict[str, Any]]:
    """Spec §6.2.1 — N+2 choices (N pick_schwab_record_<i> + 2 fallbacks).

    Per Codex R1 Major #1 + spec §4.3.2 LOCK: pick_schwab_record_<N>
    choices REQUIRE operator-supplied execution-level field values
    because Pass-2 candidates are order-grain, not execution-grain.
    Setting ``requires_custom_value=True`` on every pick choice signals
    downstream CLI surfaces that ``--custom-value`` must be supplied.
    """
    choices: list[dict[str, Any]] = [
        {
            "code": f"pick_schwab_record_{i + 1}",
            "description": (
                f"Apply Schwab record #{i + 1} as the canonical source "
                f"for this fill (REQUIRES --custom-value with operator-"
                f"supplied execution-level field values; Pass-2 "
                f"candidates are order-grain, not execution-grain — per "
                f"spec §4.3.2 LOCK)"
            ),
            "requires_custom_value": True,
        }
        for i in range(n)
    ]
    choices.append(
        {
            "code": "mark_unmatched",
            "description": (
                "Acknowledge no canonical match; no journal mutation"
            ),
            "requires_custom_value": False,
        }
    )
    choices.append(
        {
            "code": "custom",
            "description": (
                "Operator-supplied arbitrary payload via --custom-value"
            ),
            "requires_custom_value": True,
        }
    )
    return choices


def _candidate_choices_schwab_returned_no_match() -> list[dict[str, Any]]:
    """Spec §6.2.1 — 2 choices."""
    return [
        {
            "code": "mark_unmatched",
            "description": (
                "Acknowledge no Schwab record matches; no journal mutation"
            ),
            "requires_custom_value": False,
        },
        {
            "code": "operator_truth",
            "description": (
                "Operator supplies the true source payload via --custom-value"
            ),
            "requires_custom_value": True,
        },
    ]


def _candidate_choices_unknown_schwab_subtype() -> list[dict[str, Any]]:
    """Spec §6.2.1 — 3 choices."""
    return [
        {
            "code": "acknowledge",
            "description": (
                "Acknowledge the V1 mapper limitation; no journal mutation"
            ),
            "requires_custom_value": False,
        },
        {
            "code": "operator_truth",
            "description": (
                "Operator supplies the true execution payload via "
                "--custom-value (e.g., per-execution price from broker "
                "statement)"
            ),
            "requires_custom_value": True,
        },
        {
            "code": "custom",
            "description": (
                "Operator-supplied arbitrary payload via --custom-value"
            ),
            "requires_custom_value": True,
        },
    ]


def _classify_unmatched_fill_shared(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
    direction: str,  # 'open' or 'close' — for reason rendering only
) -> ClassificationResult:
    """Shared core for unmatched_open_fill + unmatched_close_fill.

    V1 LOCK: NEVER emits tier-1 (Pass-2-tier-1-FORBIDDEN per spec §8.4).
    """
    ticker = discrepancy.ticker
    fill_id = discrepancy.fill_id

    # Sub-bundle 1 T-1.9 — Path B execution_unavailable sentinel
    # recognition (spec §5.2 + §6.1 OQ-A LOCK). Comparator T-1.6 emits
    # unmatched_*_fill with actual_value_json={"matched": null,
    # "execution_unavailable": True, "schwab_order_id": X,
    # "schwab_order_price": Y} when a matched Schwab order has no
    # execution-grain data (executions=None from V1 mapper path / sandbox
    # / mapper-coherence-check collapse case). V1 Pass-2 STAYS
    # tier-2-always (Pass-2-tier-1-FORBIDDEN LOCK per spec §1.5 + §6.6
    # OQ-F V2). This branch ONLY adds clearer correction_reason citing
    # `execution_unavailable=true` for operator-actionability — no LIFT.
    if (
        isinstance(source_payload, Mapping)
        and source_payload.get("execution_unavailable") is True
    ):
        schwab_order_id = source_payload.get("schwab_order_id", "<unknown>")
        schwab_order_price = source_payload.get("schwab_order_price")
        if (
            isinstance(schwab_order_price, (int, float))
            and not isinstance(schwab_order_price, bool)
        ):
            price_text = f"${float(schwab_order_price):.4f}"
        else:
            price_text = "(price unavailable)"
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"unmatched_{direction}_fill on "
                f"(ticker={ticker!r}, fill_id={fill_id}): Schwab order "
                f"{schwab_order_id} (order_price={price_text}) matched on "
                f"quantity but execution-grain data is unavailable "
                f"(execution_unavailable=true sentinel); please disposition "
                f"manually per broker execution statement (V1 LIFT scope = "
                f"Pass-1 only per spec §1.5; OQ-F V2 deferred)"
            ),
            candidate_choices=None,
        )

    # Pass-1-only or no-payload case (DHC 39 + VSAT 40 walkthrough — Pass 1
    # input shape ``actual_value_json={"matched": null}``; here we receive
    # source_payload=None OR source_payload == {"matched": None}.
    if source_payload is None or (
        isinstance(source_payload, Mapping)
        and "matched" in source_payload
        and source_payload.get("matched") is None
        and len(source_payload) == 1
    ):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"unmatched_{direction}_fill on "
                f"(ticker={ticker!r}, fill_id={fill_id}): Pass 1 input "
                f"insufficient to disposition (persisted JSON gives no "
                f"candidate enumeration); _pass_2_required=True; backfill "
                f"must re-fetch Schwab orders to disposition"
            ),
            candidate_choices=None,
        )

    # List-shaped Pass-2 payload branches.
    if isinstance(source_payload, list):
        n = len(source_payload)
        if n == 0:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="schwab_returned_no_match",
                correction_target=None,
                correction_reason=(
                    f"unmatched_{direction}_fill on "
                    f"(ticker={ticker!r}, fill_id={fill_id}): Schwab "
                    f"returned 0 orders for the match window; operator "
                    f"dispositions via mark_unmatched or operator_truth"
                ),
                candidate_choices=_candidate_choices_schwab_returned_no_match(),
            )
        if n == 1:
            # Phase 12.5 #1 T-1.2 — n=1 RECLASSIFICATION path per spec §6.5.
            # When the single candidate carries multi-leg ``executions`` AND
            # the predicate fires (per-leg consistency, qty sum + VWAP match
            # journal), RECLASSIFY ambiguity_kind to
            # ``multi_partial_vs_consolidated`` so the schema cross-column
            # CHECK pair (operator_resolved_ambiguity ↔
            # multi_partial_vs_consolidated) holds AND route the auto-redirect
            # through the existing
            # ``_TIER2_HANDLERS[('multi_partial_vs_consolidated',
            # 'split_into_partials')]`` registry entry (NO new handler key).
            single = source_payload[0]
            executions = single.get("executions") if isinstance(single, Mapping) else None
            recipe: Mapping[str, Any] | None = None
            predicate_reason: str | None = None
            reclassified_kind: str = "unknown_schwab_subtype"
            if (
                journal_row is not None
                and journal_row.get("price") is not None
                and journal_row.get("quantity") is not None
                and isinstance(executions, list)
                and len(executions) >= 2
            ):
                try:
                    journal_qty_f = float(journal_row["quantity"])
                    journal_price_f = float(journal_row["price"])
                except (TypeError, ValueError):
                    journal_qty_f = None  # type: ignore[assignment]
                    journal_price_f = None  # type: ignore[assignment]
                if journal_qty_f is not None and journal_price_f is not None:
                    fired, predicate_reason = _multi_leg_auto_redirect_predicate(
                        candidates=[single],
                        journal_qty=journal_qty_f,
                        journal_price=journal_price_f,
                    )
                    if fired:
                        recipe = _synthesize_split_into_partials_recipe([single])
                        reclassified_kind = "multi_partial_vs_consolidated"
            reason_text = (
                f"unmatched_{direction}_fill on "
                f"(ticker={ticker!r}, fill_id={fill_id}): Schwab "
                f"returned a single order at order-grain; V1 mapper "
                f"does not expose per-execution fill detail "
                f"(Pass-2-tier-1-FORBIDDEN per §8.4); operator "
                f"dispositions via acknowledge (keep journal as-is) "
                f"or operator_truth (supplies execution price)"
            )
            if recipe is None and predicate_reason is not None:
                reason_text = (
                    f"{reason_text} (multi-leg auto-redirect: declined "
                    f"({predicate_reason}))"
                )
            # When reclassified to multi_partial_vs_consolidated, swap the
            # candidate_choices menu to match the new ambiguity_kind.
            if reclassified_kind == "multi_partial_vs_consolidated":
                choices = _candidate_choices_multi_partial_vs_consolidated()
            else:
                choices = _candidate_choices_unknown_schwab_subtype()
            return ClassificationResult(
                tier=2,
                ambiguity_kind=reclassified_kind,
                correction_target=None,
                correction_reason=reason_text,
                candidate_choices=choices,
                auto_redirect_recipe=recipe,
            )
        # n >= 2: compare sum(quantity) vs journal quantity.
        try:
            schwab_qty_sum = sum(
                float(o.get("quantity", 0) or 0) for o in source_payload
            )
        except (AttributeError, TypeError, ValueError):
            schwab_qty_sum = None  # type: ignore[assignment]

        journal_qty = None
        if journal_row is not None:
            jq = journal_row.get("quantity")
            try:
                journal_qty = float(jq) if jq is not None else None
            except (TypeError, ValueError):
                journal_qty = None

        if (
            schwab_qty_sum is not None
            and journal_qty is not None
            and abs(schwab_qty_sum - journal_qty) < 1e-9
        ):
            # Phase 12.5 #1 T-1.2 — multi-leg auto-redirect predicate.
            # When the candidate set carries multi-leg ``executions`` AND
            # the predicate fires, synthesize the split_into_partials recipe;
            # callers (pivot loop T-1.5) route through
            # ``apply_tier2_resolution(choice_code='split_into_partials',
            # resolved_by='auto_tier1_multi_leg', ...)`` per spec §2.3.
            # When the predicate declines, append the decline reason to the
            # correction_reason for forensic transparency.
            journal_price = (
                journal_row.get("price") if journal_row is not None else None
            )
            recipe_mp: Mapping[str, Any] | None = None
            predicate_reason_mp: str | None = None
            if (
                journal_row is not None
                and journal_price is not None
                and isinstance(source_payload, list)
            ):
                try:
                    journal_price_f = float(journal_price)
                except (TypeError, ValueError):
                    journal_price_f = None  # type: ignore[assignment]
                if journal_price_f is not None:
                    fired_mp, predicate_reason_mp = _multi_leg_auto_redirect_predicate(
                        candidates=source_payload,
                        journal_qty=float(journal_qty),
                        journal_price=journal_price_f,
                    )
                    if fired_mp:
                        recipe_mp = _synthesize_split_into_partials_recipe(
                            source_payload
                        )
            base_reason_mp = (
                f"unmatched_{direction}_fill on "
                f"(ticker={ticker!r}, fill_id={fill_id}): journal "
                f"consolidated qty={journal_qty}; Schwab returns "
                f"{n} separate orders summing to qty={schwab_qty_sum}; "
                f"V1 mapper exposes order-level price only (per §8.4 "
                f"Pass-2-tier-1-FORBIDDEN lock) — operator must "
                f"consult broker execution statement and choose "
                f"keep_journal_as_is (no mutation) OR "
                f"consolidate_using_operator_vwap (requires "
                f"--custom-value with operator-computed VWAP) OR "
                f"split_into_partials (requires --custom-value with "
                f"execution-level partial payload)."
            )
            if recipe_mp is None and predicate_reason_mp is not None:
                reason_mp = (
                    f"{base_reason_mp} (multi-leg auto-redirect: declined "
                    f"({predicate_reason_mp}))"
                )
            else:
                reason_mp = base_reason_mp
            return ClassificationResult(
                tier=2,
                ambiguity_kind="multi_partial_vs_consolidated",
                correction_target=None,
                correction_reason=reason_mp,
                candidate_choices=(
                    _candidate_choices_multi_partial_vs_consolidated()
                ),
                auto_redirect_recipe=recipe_mp,
            )
        return ClassificationResult(
            tier=2,
            ambiguity_kind="multi_match_within_window",
            correction_target=None,
            correction_reason=(
                f"unmatched_{direction}_fill on "
                f"(ticker={ticker!r}, fill_id={fill_id}): Schwab returned "
                f"{n} orders within the match window with sum-qty="
                f"{schwab_qty_sum} != journal qty={journal_qty}; operator "
                f"picks the intended record or marks unmatched"
            ),
            candidate_choices=_candidate_choices_multi_match_within_window(n),
        )

    # Any other shape (scalar, non-list, non-{"matched": None} Mapping)
    # → tier-2 unsupported. Defense in depth.
    return ClassificationResult(
        tier=2,
        ambiguity_kind="unsupported",
        correction_target=None,
        correction_reason=(
            f"unmatched_{direction}_fill on "
            f"(ticker={ticker!r}, fill_id={fill_id}): source_payload "
            f"shape {type(source_payload).__name__} not understood by "
            f"classifier (Pass-2-tier-1-FORBIDDEN); operator dispositions "
            f"manually"
        ),
        candidate_choices=None,
    )


def _classify_unmatched_open_fill(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.2 + §8.4 Pass-2-tier-1-FORBIDDEN — DHC 39 walkthrough."""
    return _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row=journal_row,
        direction="open",
    )


_SUB_CLASSIFIERS["unmatched_open_fill"] = _classify_unmatched_open_fill


def _classify_unmatched_close_fill(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.3 — mirrors unmatched_open_fill symmetrically."""
    return _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row=journal_row,
        direction="close",
    )


_SUB_CLASSIFIERS["unmatched_close_fill"] = _classify_unmatched_close_fill


# ---------------------------------------------------------------------------
# T-B.6 — stop_mismatch sub-classifier
# ---------------------------------------------------------------------------
#
# Spec §4.3.4 — tier-1 ALLOWED (unlike unmatched_*_fill).
#
# LOGIC:
# - source_payload carries {"stop_price": X} for ticker + journal
#   current_stop differs → tier-1, correction_target={'current_stop': X}.
# - source_payload has multiple active stops → tier-2
#   multi_match_within_window.
# - source_payload is None OR has 0 active stops AND journal has stop →
#   tier-2 schwab_returned_no_match.
#
# Tier-1 emissions DO NOT consult Phase 9 risk_policy advisory thresholds
# (per spec §4.3.4 + §1.6 advisory-not-validator family). Advisories
# surface at Phase 10 dashboard time.


def _classify_stop_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.4 — stop_mismatch."""
    ticker = discrepancy.ticker
    trade_id = discrepancy.trade_id

    if source_payload is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="schwab_returned_no_match",
            correction_target=None,
            correction_reason=(
                f"stop_mismatch on (ticker={ticker!r}, "
                f"trade_id={trade_id}): Schwab returned no active stop "
                f"orders for this ticker; operator dispositions via "
                f"mark_unmatched or operator_truth"
            ),
            candidate_choices=_candidate_choices_schwab_returned_no_match(),
        )

    # Multi-match: list-shape with N>=2 active stops.
    if isinstance(source_payload, list):
        n = len(source_payload)
        if n == 0:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="schwab_returned_no_match",
                correction_target=None,
                correction_reason=(
                    f"stop_mismatch on (ticker={ticker!r}, "
                    f"trade_id={trade_id}): Schwab returned 0 active "
                    f"stops; operator dispositions via mark_unmatched "
                    f"or operator_truth"
                ),
                candidate_choices=_candidate_choices_schwab_returned_no_match(),
            )
        if n >= 2:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="multi_match_within_window",
                correction_target=None,
                correction_reason=(
                    f"stop_mismatch on (ticker={ticker!r}, "
                    f"trade_id={trade_id}): Schwab returned {n} active "
                    f"stops; operator picks the intended record"
                ),
                candidate_choices=_candidate_choices_multi_match_within_window(n),
            )
        # n == 1: unwrap to scalar-dict shape below.
        source_payload = source_payload[0]

    if not isinstance(source_payload, Mapping):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"stop_mismatch on (ticker={ticker!r}, "
                f"trade_id={trade_id}): source_payload shape "
                f"{type(source_payload).__name__} not understood"
            ),
        )

    source_stop = source_payload.get("stop_price")
    if source_stop is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"stop_mismatch on (ticker={ticker!r}, "
                f"trade_id={trade_id}): source_payload missing "
                f"'stop_price' key"
            ),
        )

    journal_stop = (journal_row or {}).get("current_stop") if journal_row else None
    try:
        journal_stop_str = f"${float(journal_stop):.2f}"
    except (TypeError, ValueError):
        journal_stop_str = f"${journal_stop}"
    try:
        source_stop_str = f"${float(source_stop):.2f}"
    except (TypeError, ValueError):
        source_stop_str = f"${source_stop}"
    return ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"current_stop": source_stop},
        correction_reason=(
            f"stop_mismatch on (ticker={ticker!r}, "
            f"trade_id={trade_id}): journal stop {journal_stop_str} vs "
            f"Schwab stop {source_stop_str}; single active stop match; "
            f"tier-1 auto-correct (advisory-not-validator family — "
            f"Phase 10 dashboard surfaces risk_policy advisories "
            f"separately)"
        ),
        candidate_choices=None,
    )


_SUB_CLASSIFIERS["stop_mismatch"] = _classify_stop_mismatch


# ---------------------------------------------------------------------------
# T-B.7 — position_qty_mismatch sub-classifier (tier-2-always V1)
# ---------------------------------------------------------------------------
#
# Spec §4.3.5 LOCK: tier-1 auto-quantity-correction requires per-fill
# broker attribution V1 Schwab API doesn't provide cleanly.


def _classify_position_qty_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.5 — position_qty_mismatch (tier-2-always V1)."""
    ticker = discrepancy.ticker
    trade_id = discrepancy.trade_id

    # Source has 1 position record; journal fills sum to broker_qty;
    # small fills count (<=3) → multi_match_within_window per fill
    # (operator decides which fill is wrong-qty).
    if isinstance(source_payload, Mapping):
        # Single broker position record. Plan §C.7 acceptance #2 path:
        # broker has 1 record + journal fills sum to broker_qty + small
        # fills count (<=3) → multi_match_within_window.
        journal_fills = (journal_row or {}).get("fills") or []
        if (
            isinstance(journal_fills, list)
            and 0 < len(journal_fills) <= 3
        ):
            return ClassificationResult(
                tier=2,
                ambiguity_kind="multi_match_within_window",
                correction_target=None,
                correction_reason=(
                    f"position_qty_mismatch on (ticker={ticker!r}, "
                    f"trade_id={trade_id}): Schwab has 1 position record; "
                    f"journal has {len(journal_fills)} contributing fills; "
                    f"operator picks which fill carries the wrong qty"
                ),
                candidate_choices=(
                    _candidate_choices_multi_match_within_window(
                        len(journal_fills)
                    )
                ),
            )
        # Fall through to unsupported default.

    if source_payload is None or (
        isinstance(source_payload, list) and len(source_payload) == 0
    ):
        # Broker has 0 positions AND journal has open trade.
        return ClassificationResult(
            tier=2,
            ambiguity_kind="schwab_returned_no_match",
            correction_target=None,
            correction_reason=(
                f"position_qty_mismatch on (ticker={ticker!r}, "
                f"trade_id={trade_id}): Schwab has no open position for "
                f"this ticker but journal carries an open trade; operator "
                f"dispositions via mark_unmatched or operator_truth"
            ),
            candidate_choices=_candidate_choices_schwab_returned_no_match(),
        )

    return ClassificationResult(
        tier=2,
        ambiguity_kind="unsupported",
        correction_target=None,
        correction_reason=(
            f"position_qty_mismatch on (ticker={ticker!r}, "
            f"trade_id={trade_id}): tier-1 auto-quantity-correction "
            f"requires per-fill broker attribution V1 Schwab API does "
            f"not provide cleanly (spec §4.3.5 LOCK); operator "
            f"dispositions manually"
        ),
    )


_SUB_CLASSIFIERS["position_qty_mismatch"] = _classify_position_qty_mismatch


# ---------------------------------------------------------------------------
# T-B.8 — close_price_mismatch sub-classifier (tier-2-always V1)
# ---------------------------------------------------------------------------
#
# Spec §4.3.6 LOCK: tier-2-always V1; historical close-price corrections
# are V2 candidate (V1 cannot re-import OHLCV history).


def _classify_close_price_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,  # noqa: ARG001 — Shape C path doesn't consult journal_row
) -> ClassificationResult:
    """Spec §4.3.6 + §3.2 + §10.6 OQ-D — close_price_mismatch.

    Sub-bundle 1 T-1.8 widening: NEW Shape C branch (execution-grain audit-
    bearing payload) → tier-1 auto-correct. Legacy V1 fall-through preserved
    for non-Shape-C payloads (e.g., OHLCV-snapshot future consumers).

    Pre-T-1.8 behavior was tier-2-always (`unknown_schwab_subtype`). Post-
    T-1.8 the Shape C path lets the comparator's execution-grain
    `actual_value_json` drive tier-1 auto-correct symmetrically with
    entry_price_mismatch (per spec §10.6 OQ-D FIRED-STOP walkthrough).
    """
    ticker = discrepancy.ticker
    trade_id = discrepancy.trade_id

    # Sub-bundle 1 T-1.8 — Shape C branch (per plan §A.1.8 + spec §3.2 +
    # §10.6 OQ-D). Insert BEFORE existing tier-2-always V1 fall-through.
    # Mixed/partial Shape C OR non-Shape-C Mapping falls through to legacy
    # V1 tier-2 path below (preserves OHLCV-snapshot future consumer
    # compatibility per plan §A.1.8).
    if (
        isinstance(source_payload, Mapping)
        and frozenset(source_payload.keys()) == _SHAPE_C_EXPECTED_KEYS
    ):
        price = source_payload.get("price")
        if (
            isinstance(price, (int, float))
            and not isinstance(price, bool)
            and math.isfinite(float(price))
        ):
            return ClassificationResult(
                tier=1,
                ambiguity_kind=None,
                correction_target={"price": float(price)},
                correction_reason=(
                    f"close_price_mismatch on (ticker={ticker!r}, "
                    f"trade_id={trade_id}): Schwab execution-grain "
                    f"price ${float(price):.4f}; auto-correct journal "
                    f"to execution (Sub-bundle 1 T-1.8 Shape C; audit "
                    f"keys in actual_value_json)"
                ),
                candidate_choices=None,
            )

    # Legacy V1 tier-2-always path preserved per plan §A.1.8 fall-through
    # discipline.
    return ClassificationResult(
        tier=2,
        ambiguity_kind="unknown_schwab_subtype",
        correction_target=None,
        correction_reason=(
            f"close_price_mismatch on (ticker={ticker!r}, "
            f"trade_id={trade_id}): historical snapshot; V1 cannot "
            f"re-import OHLCV history (V2 candidate); operator "
            f"dispositions via acknowledge OR operator_truth"
        ),
        candidate_choices=_candidate_choices_unknown_schwab_subtype(),
    )


_SUB_CLASSIFIERS["close_price_mismatch"] = _classify_close_price_mismatch


# ---------------------------------------------------------------------------
# T-B.9 — cash_movement_mismatch sub-classifier
# ---------------------------------------------------------------------------
#
# Spec §4.3.7. Tier-1 single-match path; tier-2 otherwise.
#
# correction_target may carry multiple fields atomically per spec §4.4 +
# §3.1.1 multi-column atomic correction discipline; classifier supplies a
# multi-field dict + downstream service writes a correction_set_id-bundled
# set.


def _classify_cash_movement_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
) -> ClassificationResult:
    """Spec §4.3.7 — cash_movement_mismatch."""
    cash_movement_id = discrepancy.cash_movement_id

    if source_payload is None or (
        isinstance(source_payload, list) and len(source_payload) == 0
    ):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="schwab_returned_no_match",
            correction_target=None,
            correction_reason=(
                f"cash_movement_mismatch on "
                f"(cash_movement_id={cash_movement_id}): no matching "
                f"cash movement found on broker side; operator "
                f"dispositions via mark_unmatched or operator_truth"
            ),
            candidate_choices=_candidate_choices_schwab_returned_no_match(),
        )

    if isinstance(source_payload, list):
        if len(source_payload) > 1:
            n = len(source_payload)
            return ClassificationResult(
                tier=2,
                ambiguity_kind="multi_match_within_window",
                correction_target=None,
                correction_reason=(
                    f"cash_movement_mismatch on "
                    f"(cash_movement_id={cash_movement_id}): {n} broker "
                    f"cash movements match within window; operator picks "
                    f"the intended record"
                ),
                candidate_choices=_candidate_choices_multi_match_within_window(n),
            )
        # Single-match list of 1; unwrap.
        source_payload = source_payload[0]

    if not isinstance(source_payload, Mapping):
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"cash_movement_mismatch on "
                f"(cash_movement_id={cash_movement_id}): source_payload "
                f"shape {type(source_payload).__name__} not understood"
            ),
        )

    # Single-match: build multi-field correction_target from any keys
    # present in source_payload that differ from journal_row. Spec §4.4
    # allows multi-field atomic correction; downstream service bundles
    # via correction_set_id.
    journal_data = journal_row or {}
    correction_target: dict[str, Any] = {}
    for key in ("date", "kind", "amount", "ref"):
        if key in source_payload:
            source_val = source_payload[key]
            journal_val = journal_data.get(key)
            if source_val != journal_val:
                correction_target[key] = source_val

    if not correction_target:
        # source matches journal — discrepancy emit was stale.
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"cash_movement_mismatch on "
                f"(cash_movement_id={cash_movement_id}): source_payload "
                f"matches journal on all checked fields; discrepancy "
                f"appears stale; operator acknowledges"
            ),
        )

    field_list = ", ".join(sorted(correction_target.keys()))
    return ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target=correction_target,
        correction_reason=(
            f"cash_movement_mismatch on "
            f"(cash_movement_id={cash_movement_id}): single broker "
            f"match; tier-1 auto-correct on fields [{field_list}]"
        ),
        candidate_choices=None,
    )


_SUB_CLASSIFIERS["cash_movement_mismatch"] = _classify_cash_movement_mismatch


# ---------------------------------------------------------------------------
# T-B.10 — sector_tamper sub-classifier (tier-2-always V1)
# ---------------------------------------------------------------------------
#
# Spec §4.3.8 LOCK: Schwab doesn't supply sector data; operator-action-only.


def _classify_sector_tamper(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,  # noqa: ARG001
    journal_row: Mapping[str, Any] | None,  # noqa: ARG001
) -> ClassificationResult:
    """Spec §4.3.8 — sector_tamper (tier-2-always V1)."""
    ticker = discrepancy.ticker
    trade_id = discrepancy.trade_id
    return ClassificationResult(
        tier=2,
        ambiguity_kind="unknown_schwab_subtype",
        correction_target=None,
        correction_reason=(
            f"sector_tamper on (ticker={ticker!r}, "
            f"trade_id={trade_id}): requires operator override "
            f"(tier-3 path); Schwab does not supply sector data"
        ),
        candidate_choices=_candidate_choices_unknown_schwab_subtype(),
    )


_SUB_CLASSIFIERS["sector_tamper"] = _classify_sector_tamper


# ---------------------------------------------------------------------------
# T-B.11 — snapshot_mismatch sub-classifier (tier-2-always V1)
# ---------------------------------------------------------------------------
#
# Spec §4.3.9 LOCK: mirrors close_price_mismatch — tier-2-always V1.


def _classify_snapshot_mismatch(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,  # noqa: ARG001
    journal_row: Mapping[str, Any] | None,  # noqa: ARG001
) -> ClassificationResult:
    """Spec §4.3.9 — snapshot_mismatch (tier-2-always V1)."""
    return ClassificationResult(
        tier=2,
        ambiguity_kind="unknown_schwab_subtype",
        correction_target=None,
        correction_reason=(
            f"snapshot_mismatch on "
            f"(trade_id={discrepancy.trade_id}, "
            f"field_name={discrepancy.field_name!r}): historical "
            f"snapshot; V1 cannot re-derive OHLCV history (V2 candidate "
            f"for richer auto-correct); operator dispositions via "
            f"acknowledge OR operator_truth"
        ),
        candidate_choices=_candidate_choices_unknown_schwab_subtype(),
    )


_SUB_CLASSIFIERS["snapshot_mismatch"] = _classify_snapshot_mismatch


# ---------------------------------------------------------------------------
# T-B.12 — equity_delta sub-classifier (tier-2-always V1)
# ---------------------------------------------------------------------------
#
# Spec §4.3.10 LOCK: cash-basis-vs-MTM semantics divergence is a Phase 10
# operator-locked V2 candidate.


def _classify_equity_delta(
    *,
    discrepancy: ReconciliationDiscrepancy,
    source_payload: Any | None,  # noqa: ARG001
    journal_row: Mapping[str, Any] | None,  # noqa: ARG001
) -> ClassificationResult:
    """Spec §4.3.10 — equity_delta (tier-2-always V1)."""
    return ClassificationResult(
        tier=2,
        ambiguity_kind="field_shape_incompatible",
        correction_target=None,
        correction_reason=(
            f"equity_delta on (run_id={discrepancy.run_id}): requires "
            f"cash-basis-vs-MTM formalization (Phase 10 V2 candidate); "
            f"operator dispositions via acknowledge OR operator_truth"
        ),
        candidate_choices=_candidate_choices_unknown_schwab_subtype(),
    )


_SUB_CLASSIFIERS["equity_delta"] = _classify_equity_delta


def classify_discrepancy(
    discrepancy: ReconciliationDiscrepancy,
    *,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
    validator_chain: ValidatorChainCallable | None = None,
) -> ClassificationResult:
    """Pure classifier; dispatches on ``discrepancy.discrepancy_type``.

    Args:
        discrepancy: The ``ReconciliationDiscrepancy`` to classify.
        source_payload: Pre-fetched broker-side payload (shape varies per
            discrepancy_type; ``None`` means no broker data available).
        journal_row: Pre-fetched journal-side row (e.g., the ``fills`` row
            for fill-shaped discrepancies; ``None`` when unavailable).
        validator_chain: Optional callable that dry-runs the proposed
            ``correction_target`` against schema-CHECK-mirror predicates.
            When provided AND classifier emits tier-1, the dispatcher
            invokes the chain; a ``(False, reason)`` return downgrades to
            tier-2 ``validator_rejected``.

    Returns:
        ``ClassificationResult`` per spec §4.2. ALWAYS returns a result;
        never raises (spec §4.5 graceful-degradation contract).
    """
    sub = _SUB_CLASSIFIERS.get(discrepancy.discrepancy_type)
    if sub is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"no sub-classifier registered for discrepancy_type="
                f"{discrepancy.discrepancy_type!r}"
            ),
        )
    try:
        result = sub(
            discrepancy=discrepancy,
            source_payload=source_payload,
            journal_row=journal_row,
        )
    except Exception as e:  # noqa: BLE001 — graceful degradation per spec §4.5
        logger.warning(
            "classifier exception for discrepancy %s (%s): %s: %s",
            discrepancy.discrepancy_id,
            discrepancy.discrepancy_type,
            type(e).__name__,
            e,
        )
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"classifier exception: {type(e).__name__}: {e}"
            ),
        )

    if result.tier == 1 and validator_chain is not None:
        try:
            passes, reason = validator_chain(result.correction_target or {})
        except Exception as e:  # noqa: BLE001 — validator-side defect must not crash
            logger.warning(
                "validator_chain exception for discrepancy %s: %s: %s",
                discrepancy.discrepancy_id,
                type(e).__name__,
                e,
            )
            return ClassificationResult(
                tier=2,
                ambiguity_kind="validator_rejected",
                correction_target=None,
                correction_reason=(
                    f"validator chain raised: {type(e).__name__}: {e}"
                ),
            )
        if not passes:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="validator_rejected",
                correction_target=None,
                correction_reason=(
                    f"validator rejected proposed correction: "
                    f"{reason or 'unknown'}"
                ),
            )
    return result
