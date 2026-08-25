"""22-A -- the order<->mandate LINK, and the provenance it authorizes.

THE ROOT THIS ARC CLOSES.  ``derive_trade_origin`` resolves a fill's cohort
keys from ``_latest_complete_evaluation_run_id`` -- the latest complete run,
NOT the run the operator acted on.  A ticker that drops off the screen between
recommendation and fill therefore derives ``manual_off_pipeline`` with NULL
keys even when a broker-validated latch order for the mandate EXISTS.  The
operator's own words: *"when I enter position after my order fires with the
ticker not in the decision table that day, there is no clear entry for me to
choose to indicate what cohort it belongs to."*

WHAT THIS MODULE IS, AND WHAT IT DELIBERATELY IS NOT.  It authors a LINK, a
CONSULTATION and the GUARDS that make the consultation sound.  It authors NO
second invalidation comparison: ``swing/latches/service.py:derive_latches``
already implements RD's full precedence ladder including the invalidation
rung, and this module DELEGATES to it (plan S0(1)).  The delegation is a
function call rather than a comment promising inheritance -- gotcha #31.

THE UNIFORM FILL-WINS BOUND (RD, 2026-08-24), delivered STRUCTURALLY.  A
breach on a session STRICTLY BEFORE the fill sits inside the derivation's
``bar_bound`` and produces ``clear_reason='invalidation'`` at that earlier
date, so the resolver refuses.  A breach ON the fill session is OUTSIDE
``bar_bound`` -- the probe never loads that bar -- so it returns
``clear_reason is None`` and the resolver admits.  **The ground is a
measurement argument, not leniency: refusing same-session collapses is
SURVIVORSHIP BIAS.  The fastest loser is the fill that collapses the day it
triggers, and ejecting exactly those trades censors H1's left tail and biases
its mean UP.  An implementation that refuses case 5b is not being
conservative; it is silently improving H1's apparent results.**
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date

from swing.latches.constants import (
    PRICE_DP,
    mandate_limit_price,
    zone_cap_for_pivot,
)
from swing.metrics.funnel import APLUS_TRADE_ORIGIN

log = logging.getLogger(__name__)

# THE ENVELOPE KEY IS SINGLE-SOURCED (#11).  The writer at
# ``swing/trades/entry_auto_fill.py`` and every reader use this constant; a
# second spelling is how the two halves of one contract drift apart.
SCHWAB_ORDER_ID_ENVELOPE_KEY = "schwab_order_id"
SCHWAB_SYMBOL_ENVELOPE_KEY = "schwab_instrument_symbol"

# Only a broker-sourced fill can carry broker-grade identity.  ``operator_typed``
# is excluded because its "order id" is whatever was typed into the form.
TRUSTED_LATCH_FILL_ORIGINS = frozenset(
    {"schwab_auto", "schwab_auto_then_operator_corrected"}
)

# The two-valued freeze tier under SINGLE-STATE.  ``gap_era_reconstructed``
# and the era model it names are CARVED to 22-A2, so a pre-barrier
# reconstruction can never be read as a post-barrier freeze.
FREEZE_TIER_LIVE_AT_ACCEPTANCE = "live_at_acceptance"
FREEZE_TIER_PRE_BARRIER = "pre_barrier_reconstructed"
LATCH_FREEZE_TIERS = frozenset(
    {FREEZE_TIER_LIVE_AT_ACCEPTANCE, FREEZE_TIER_PRE_BARRIER}
)

PROVENANCE_ADMISSION_TIER_LAST_WORD = "last_word"
PROVENANCE_ADMISSION_TIER_LATCH = "latch_ladder"
PROVENANCE_ADMISSION_TIERS = frozenset(
    {PROVENANCE_ADMISSION_TIER_LAST_WORD, PROVENANCE_ADMISSION_TIER_LATCH}
)


class LatchProbeInvariantError(RuntimeError):
    """The probe returned a state the forced configuration makes impossible.

    Raised rather than branched on: ``criteria_lapsed`` is FORCED OFF (plan
    S2.3.4, RD's bound that a latch never dies of drift), so seeing it back
    means the force did not take, and a silent branch would hide that.
    """


# ---------------------------------------------------------------------------
# THE DECLINE-REASON ROSTER -- THIRTY-THREE.
#
# Counted by reading the members below, never by grepping for a word.  The
# plan records why the method has to be stated: a ``^[a-z_]+$`` regex over an
# earlier version of this block returned one FEWER than the read, because one
# member contained a DIGIT -- a regex under-counting a roster in the very act
# of fixing an under-count.
# ---------------------------------------------------------------------------
DECLINE_REASONS: frozenset[str] = frozenset({
    "no_config",
    "no_envelope",
    "no_order_id",
    "untrusted_fill_origin",
    "no_accepted_latch_order",
    "ambiguous_accepted_orders",
    "linked_validity_not_accepted",
    "quantity_exceeds_order",
    "ambiguous_ticker_orders",
    "competitor_liveness_unverifiable",
    "validity_superseded",
    "place_cycle_superseded",
    "link_parent_incoherent",
    "order_cancelled",
    "cancel_ordering_ambiguous",
    "ticker_mismatch",
    "fill_outside_frozen_zone",
    "link_field_unbound",
    "mandate_already_consumed",
    "consumption_evidence_unavailable",
    "fill_session_not_a_session",
    "fire_not_derivable",
    "ambiguous_fire_membership",
    "frozen_value_unavailable",
    "frozen_value_drift",
    "pre_barrier_unproven",
    "aliveness_unverifiable",
    "mandate_not_alive",
    "keys_not_derivable",
    "decision_evidence_unavailable",
    "decision_evidence_post_dates_fill",
    "decision_ordering_ambiguous",
    "barrier_not_installed",
})


# ---------------------------------------------------------------------------
# THE ``$.authorization`` EVIDENCE SCHEMA -- WRITTEN OUT (22A-R9-07).
#
# The plan called this object "closed and exact" and never specified it: no
# key names, no ``input`` shapes, no required types, no per-rung binding.  Two
# executors could produce incompatible schemas while both following the
# document, so the migration's closure list was not deterministically
# implementable.  It is specified HERE, in Python, and a test asserts the
# migration's closure list matches this roster -- so the two cannot drift and
# neither is a hand-maintained copy of the other.
#
# THE STANDING RULE THIS SERVES (plan S4.3): *if a clause can REFUSE an
# admission, the evidence blob records the INPUT it judged and the VERDICT it
# reached, or "passed" and "never ran" are indistinguishable at audit.*
#
# SIXTEEN entries = the ELEVEN ladder rungs of S2.4 + the FIVE envelope
# guards, enumerated separately.  One lumped ``envelope_guards`` entry cannot
# distinguish "all five passed" from "one ran and four never did".
# ---------------------------------------------------------------------------
SQL_BOUND = "sql_bound"
SERVICE_VALIDATED = "service_validated"


@dataclass(frozen=True)
class AuthorizationClause:
    """One refusal-capable clause's slot in the ``$.authorization`` object."""

    key: str
    binding: str          # SQL_BOUND | SERVICE_VALIDATED
    input_type: str       # the json_type() the trigger asserts
    nullable: bool        # whether JSON null is an allowed input
    source: str           # the column the trigger binds ``input`` to
    what: str


AUTHORIZATION_CLAUSES: tuple[AuthorizationClause, ...] = (
    AuthorizationClause(
        "rung1_link_ticker", SQL_BOUND, "text", False,
        "latch_order_mandate_links.ticker",
        "the link's ticker equals the request's",
    ),
    AuthorizationClause(
        "rung2_link_parent", SQL_BOUND, "integer", False,
        "latch_order_mandate_links.place_intent_id",
        "the place parent resolves to a place row on the same candidate",
    ),
    AuthorizationClause(
        "rung3_validity_outcome", SQL_BOUND, "text", False,
        "latch_order_intents.validity_outcome",
        "the linked validity row's OWN outcome is accepted_by_broker",
    ),
    AuthorizationClause(
        "rung3b_latest_validity_child", SQL_BOUND, "integer", False,
        "max(latch_order_intents.intent_id) over the place's validity children",
        "the linked validity row is still the LATEST validity child",
    ),
    AuthorizationClause(
        "rung3c_link_broker_order_id", SQL_BOUND, "text", False,
        "latch_order_intents.actual_broker_order_id",
        "every duplicated link field equals its authoritative source",
    ),
    AuthorizationClause(
        "rung4_governing_place_intent", SQL_BOUND, "integer", False,
        "max(latch_order_intents.intent_id) over the candidate's place rows",
        "the linked place is the GOVERNING place cycle as of the fill",
    ),
    AuthorizationClause(
        "rung5_cancel_intent_id", SQL_BOUND, "integer", True,
        "latch_order_intents cancel rows at-or-before the fill session",
        "no cancellation of this broker order at-or-before the fill",
    ),
    AuthorizationClause(
        "rung6_consuming_trade_id", SQL_BOUND, "integer", True,
        "fills.schwab_source_value_json order id on OTHER trades",
        "no other trade has consumed THIS ORDER",
    ),
    AuthorizationClause(
        "rung7_consumption_scan_fill_ids", SERVICE_VALIDATED, "array", False,
        "-- scan result; no subquery can reach it",
        "consumption evidence is INTACT for every fill it must scan",
    ),
    AuthorizationClause(
        "rung8_competitor_link_ids", SERVICE_VALIDATED, "array", False,
        "-- derivation state; no subquery can reach it",
        "exactly ONE competitor-free accepted link on this TICKER",
    ),
    AuthorizationClause(
        "rung9_stored_freeze_tier", SQL_BOUND, "text", False,
        "latch_order_mandate_links.freeze_tier",
        "the stored tier is live_at_acceptance AND both barriers exist",
    ),
    AuthorizationClause(
        "guard_fill_origin", SQL_BOUND, "text", False,
        "fills.fill_origin",
        "the fill's origin is broker-sourced",
    ),
    AuthorizationClause(
        "guard_envelope_symbol", SQL_BOUND, "text", False,
        "json_extract(fills.schwab_source_value_json, '$.schwab_instrument_symbol')",
        "the envelope's instrument symbol equals the request's ticker",
    ),
    AuthorizationClause(
        "guard_quantity", SQL_BOUND, "real", False,
        "fills.quantity",
        "0 < shares <= the accepted order's quantity",
    ),
    AuthorizationClause(
        "guard_framework_price_bound", SQL_BOUND, "real", False,
        "fills.price",
        "the fill price is inside the FRAMEWORK's frozen zone",
    ),
    AuthorizationClause(
        "guard_broker_limit_bound", SQL_BOUND, "real", True,
        "latch_order_intents.actual_limit_price",
        "the fill price does not exceed the ACCEPTED order's own limit",
    ),
)

AUTHORIZATION_KEYS: tuple[str, ...] = tuple(c.key for c in AUTHORIZATION_CLAUSES)


@dataclass(frozen=True)
class AcceptedLatchOrder:
    """One broker-accepted latch order, with the fire's FROZEN values.

    ``frozen_pivot`` / ``frozen_invalidation`` are NULLABLE by construction:
    ``candidates.pivot`` and ``candidates.initial_stop`` are unconstrained REAL
    columns, so the minting trigger guards each copy with a ``CASE`` and lands
    NULL rather than aborting the LEDGER write on a junk fire.  Cohort
    bookkeeping must never block a money-bearing operation (0036:26-38);
    admission later refuses ``frozen_value_unavailable``.

    NO CAP COLUMN.  The buy-zone cap is a pure function of the frozen pivot
    (``zone_cap_for_pivot``), so storing it would duplicate arithmetic into SQL
    and carry a false "frozen" claim.  It is derived at read time.

    ``actual_limit_price`` is the ACCEPTED ORDER's own limit, carried from the
    validity JOIN the lookup already performs.  ``actual_stop_price`` is
    DELIBERATELY not carried: no rung reads it, and the divergence WARNING
    names the two BOUNDS rather than the stop.
    """

    link_id: int
    validity_intent_id: int
    place_intent_id: int
    candidate_id: int
    evaluation_run_id: int
    ticker: str
    detection_date: str
    broker_order_id: str
    frozen_pivot: float | None
    frozen_invalidation: float | None
    actual_quantity: int | None
    freeze_tier: str
    actual_limit_price: float | None


@dataclass(frozen=True)
class LatchedProvenance:
    """The resolver's verdict for one fill.

    THREE outcomes, never two (plan S2.2).  ``admitted`` writes the three
    fire-derived keys.  ``recognised_but_underivable`` -- a link WAS
    recognised and admission then failed for ANY reason -- writes the HONEST
    UNSET row and SUPPRESSES the ordinary candidate/origin chain.  Neither
    flag set is the ORDINARY path, which is byte-identical to ``main``'s.
    """

    admitted: bool
    recognised_but_underivable: bool
    decline_reason: str | None
    order: AcceptedLatchOrder | None = None
    clear_reason: str | None = None
    clear_session: date | None = None
    horizon_session: date | None = None
    bars_through: date | None = None
    window_empty: bool = False
    archive_status: str | None = None
    trade_origin: str | None = None
    candidate_id: int | None = None
    hypothesis_label: str | None = None
    probe_evidence: dict | None = None
    freeze_tier: str | None = None

    def __post_init__(self) -> None:
        if self.decline_reason is not None and self.decline_reason not in DECLINE_REASONS:
            raise ValueError(
                f"decline_reason {self.decline_reason!r} is not a member of the "
                f"33-member roster; a reason no rung can emit is a roster "
                f"member whose case would be written against dead code"
            )
        if self.admitted and self.recognised_but_underivable:
            raise ValueError(
                "admitted and recognised_but_underivable are mutually exclusive"
            )
        if self.admitted and self.decline_reason is not None:
            raise ValueError("an admitted provenance carries no decline reason")


def broker_order_id_from_envelope(raw: str | None) -> str | None:
    """The broker order id inside a fill's Schwab envelope, or ``None``.

    NEVER RAISES.  This is a read-only consumer of an operator-submitted blob,
    so the posture is graceful-degrade + log: malformed JSON, a non-dict, a
    missing key, a non-string value and an empty string all return ``None``.
    A WARNING fires only when the JSON is PRESENT but unusable -- an absent
    envelope is the ordinary non-Schwab case and is not noteworthy.
    """
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        log.warning(
            "22-A: fill envelope is present but not a JSON string (%r); "
            "treating the order id as absent", type(raw).__name__,
        )
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        log.warning(
            "22-A: fill envelope is not valid JSON; treating the order id as "
            "absent (the fill still records, cohort bookkeeping degrades)"
        )
        return None
    if not isinstance(payload, dict):
        log.warning(
            "22-A: fill envelope decoded to %s, not an object; treating the "
            "order id as absent", type(payload).__name__,
        )
        return None
    value = payload.get(SCHWAB_ORDER_ID_ENVELOPE_KEY)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        log.warning(
            "22-A: fill envelope carries a non-string or empty %s; treating "
            "the order id as absent", SCHWAB_ORDER_ID_ENVELOPE_KEY,
        )
        return None
    return value.strip()


def instrument_symbol_from_envelope(raw: str | None) -> str | None:
    """The envelope's instrument symbol, degrading exactly as the order id does."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get(SCHWAB_SYMBOL_ENVELOPE_KEY)
    return value.strip() if isinstance(value, str) and value.strip() else None


def assert_fill_consistent_with_order(
    order: AcceptedLatchOrder,
    *,
    ticker: str,
    price: float,
    shares: float,
    fill_origin: str,
    envelope_symbol: str | None,
) -> str | None:
    """The FIVE envelope guards.  Returns a decline reason, or ``None``.

    THESE ARE REFUSAL GUARDS, NOT IDENTITY EVIDENCE, and the plan demotes them
    deliberately (S2.4.1): ``fill_origin`` is computed server-side but FROM the
    same hidden inputs, so no rung here is independent evidence.  The residual
    is declared at L10 with its threat model.

    CONNECTION-FREE BY DESIGN.  A pure function over the order and the
    submitted envelope is what makes every envelope guard testable without a
    database and keeps all five in one place.  That is why
    ``actual_limit_price`` was added to ``AcceptedLatchOrder`` rather than the
    signature growing a connection.
    """
    if fill_origin not in TRUSTED_LATCH_FILL_ORIGINS:
        return "untrusted_fill_origin"
    if ticker != order.ticker:
        return "ticker_mismatch"
    if envelope_symbol is not None and envelope_symbol != ticker:
        return "ticker_mismatch"

    # QUANTITY IS AN INEQUALITY, NOT AN EQUALITY (review 22A-R5-04).  An
    # accepted validity row records the ORDER quantity while the fill records
    # the EXECUTED quantity, and a partial-then-cancelled order legitimately
    # executes fewer shares.  An equality rung would write honest-unset
    # provenance for a genuine order and a genuine fill -- minting the very
    # empty-cohort-key row this arc exists to stop.
    if not shares > 0:
        return "quantity_exceeds_order"
    if order.actual_quantity is not None and shares > float(order.actual_quantity):
        return "quantity_exceeds_order"

    if order.frozen_pivot is None:
        return "frozen_value_unavailable"

    # FRAMEWORK CONFORMITY.  The upper bound comes from ``mandate_limit_price``
    # -- IMPORTED, NEVER RE-ROUNDED.  ``round(zone_cap, 2)`` is a SECOND
    # rounding rule for a quantity that already has one, and on the live VSTS
    # cap of 17.407 it yields 17.41, which EXCEEDS the cap: it would bless a
    # price outside the buy zone, which is exactly what the floor ruling exists
    # to prevent.  49.5% of two-decimal pivots produce a cap whose third
    # decimal is non-zero, so the disagreement is the ORDINARY case.
    framework_floor = round(float(order.frozen_pivot), PRICE_DP)
    framework_cap = mandate_limit_price(zone_cap_for_pivot(order.frozen_pivot))
    submitted = round(float(price), PRICE_DP)
    if submitted < framework_floor or submitted > framework_cap:
        return "fill_outside_frozen_zone"

    # BROKER REALITY.  The accepted order could not fill above its own limit,
    # so a price above it did not come from this order.  A DIVERGENCE between
    # the two bounds is a WARNING, not a refusal -- 0033's schema permits them
    # to differ; what refuses is a price outside EITHER bound.
    if order.actual_limit_price is not None:
        broker_cap = round(float(order.actual_limit_price), PRICE_DP)
        if broker_cap != framework_cap:
            log.warning(
                "22-A: broker-accepted limit %.2f diverges from the framework "
                "cap %.2f for order %s (link %s); the schema permits this, so "
                "it is reported rather than refused",
                broker_cap, framework_cap, order.broker_order_id, order.link_id,
            )
        if submitted > broker_cap:
            return "fill_outside_frozen_zone"
    return None


def aplus_trade_origin() -> str:
    """``pipeline_aplus``, from the metrics module rather than a third spelling."""
    return APLUS_TRADE_ORIGIN
