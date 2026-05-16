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

    # Codex R1 Critical #1 — (ticker, date, quantity) consistency check per
    # spec §4.3.1 LOGIC verbatim. The persisted-JSON-only shape from the
    # shipped emitter (swing/trades/schwab_reconciliation.py:469-474) carries
    # ONLY a 'price' key and is verified pre-emit, so it falls through to
    # tier-1. If a caller supplies a richer payload AND any of
    # (ticker, date, quantity) disagrees with journal_row, downgrade to
    # tier-2 'unsupported' rather than emit an ungrounded auto-correct.
    # journal_row missing entirely → also tier-2 unsupported (cannot verify
    # match tuple).
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

    # Ticker consistency: case-insensitive string equality.
    if "ticker" in source_payload:
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
    if "quantity" in source_payload:
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

    # Date consistency: ISO-date-prefix equality. source_payload may carry
    # 'date' (date-only) OR 'fill_datetime' (full ISO); journal_row likewise.
    # Normalize to first 10 chars and compare.
    src_date_raw = source_payload.get("date")
    if src_date_raw is None:
        src_date_raw = source_payload.get("fill_datetime")
    if src_date_raw is not None:
        jr_date_raw = journal_row.get("fill_datetime")
        if jr_date_raw is None:
            jr_date_raw = journal_row.get("date")
        src_date_prefix = (
            str(src_date_raw)[:10] if src_date_raw is not None else None
        )
        jr_date_prefix = (
            str(jr_date_raw)[:10] if jr_date_raw is not None else None
        )
        if (
            src_date_prefix is None
            or jr_date_prefix is None
            or src_date_prefix != jr_date_prefix
        ):
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unsupported",
                correction_target=None,
                correction_reason=(
                    f"entry_price_mismatch on "
                    f"(ticker={discrepancy.ticker!r}, "
                    f"fill_id={discrepancy.fill_id}): date mismatch "
                    f"between source_payload ({src_date_raw!r}) and "
                    f"journal_row (fill_datetime/date={jr_date_raw!r}); "
                    f"cannot verify match tuple per spec §4.3.1"
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
            return ClassificationResult(
                tier=2,
                ambiguity_kind="unknown_schwab_subtype",
                correction_target=None,
                correction_reason=(
                    f"unmatched_{direction}_fill on "
                    f"(ticker={ticker!r}, fill_id={fill_id}): Schwab "
                    f"returned a single order at order-grain; V1 mapper "
                    f"does not expose per-execution fill detail "
                    f"(Pass-2-tier-1-FORBIDDEN per §8.4); operator "
                    f"dispositions via acknowledge (keep journal as-is) "
                    f"or operator_truth (supplies execution price)"
                ),
                candidate_choices=_candidate_choices_unknown_schwab_subtype(),
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
            return ClassificationResult(
                tier=2,
                ambiguity_kind="multi_partial_vs_consolidated",
                correction_target=None,
                correction_reason=(
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
                ),
                candidate_choices=(
                    _candidate_choices_multi_partial_vs_consolidated()
                ),
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
    source_payload: Any | None,  # noqa: ARG001 — V1 doesn't consult source
    journal_row: Mapping[str, Any] | None,  # noqa: ARG001 — V1 doesn't consult journal
) -> ClassificationResult:
    """Spec §4.3.6 — close_price_mismatch (tier-2-always V1)."""
    ticker = discrepancy.ticker
    trade_id = discrepancy.trade_id
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
