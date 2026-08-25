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

from swing.data.models import (
    FREEZE_TIER_LIVE_AT_ACCEPTANCE,
    FREEZE_TIER_PRE_BARRIER,
    LATCH_FREEZE_TIERS,
    PROVENANCE_ADMISSION_TIER_LAST_WORD,
    PROVENANCE_ADMISSION_TIER_LATCH,
    PROVENANCE_ADMISSION_TIERS,
)
from swing.evaluation.dates import is_trading_session, session_offset
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    PRICE_DP,
    mandate_limit_price,
    zone_cap_for_pivot,
)
from swing.latches.reader import (
    DecisionIntentsUnavailableError,
    build_latch_derivation,
)

# THE TIE RULE IS THE LADDER'S OWN, IMPORTED, NEVER RE-SPELLED (#11). A private
# second copy of the rank table or of the comparison is the comparator-vs-emitter
# divergence 21-A and 21-B each paid for; the leading underscore says `_Terminal`
# is internal to `swing.latches.service`, and importing it is a deliberate choice
# to INHERIT the ladder rather than to re-derive it. `_CLEAR_REASON_RANK` is
# inherited TRANSITIVELY -- `_Terminal.order_key` consults it -- so this module
# holds no copy of the rank table at all, and if the ladder's ranks move this
# module moves with them by construction (a function call, not a comment
# promising inheritance -- #31). The task-6 suite pins the two properties the
# tie rule actually depends on, so a rank change that would break it fails
# LOUDLY rather than silently changing an admission.
from swing.latches.service import _Terminal
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

# THE FREEZE-TIER AND ADMISSION-TIER ENUMS ARE RE-EXPORTED, NOT RE-DEFINED.
# They were declared here when this module was the arc's only Python surface;
# migration 0037 gave each a SQL CHECK and ``swing/data/models.py`` the
# dataclasses those CHECKs constrain, so the single source moved THERE -- an
# enum's Python mirror belongs beside the row it maps to, and ``swing.trades``
# importing DOWN into ``swing.data`` is the layering's own direction.  The
# names below are unchanged, so no caller had to move with them.
__all__ = [
    "FREEZE_TIER_LIVE_AT_ACCEPTANCE",
    "FREEZE_TIER_PRE_BARRIER",
    "LATCH_FREEZE_TIERS",
    "PROVENANCE_ADMISSION_TIERS",
    "PROVENANCE_ADMISSION_TIER_LAST_WORD",
    "PROVENANCE_ADMISSION_TIER_LATCH",
    "AUTHORIZATION_CLAUSES",
    "AUTHORIZATION_KEYS",
    "DECLINE_REASONS",
    "AcceptedLatchOrder",
    "LatchedProvenance",
    "LatchProbeInvariantError",
    "SCHWAB_ORDER_ID_ENVELOPE_KEY",
    "SCHWAB_SYMBOL_ENVELOPE_KEY",
    "TRUSTED_LATCH_FILL_ORIGINS",
    "aplus_trade_origin",
    "assert_fill_consistent_with_order",
    "mandate_alive_at",
    "broker_order_id_from_envelope",
    "instrument_symbol_from_envelope",
]

# The probe-evidence schema's own version, mirrored from migration 0037's
# citation trigger (`$.evidence_version`).  A row written under an older shape
# must be DISTINGUISHABLE rather than silently re-interpreted, which is only
# true if both halves name the same version -- so a drift test asserts the
# literal in the migration equals this constant (#11).
LATCH_PROBE_EVIDENCE_VERSION = "2026-08-24.1"


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


# ---------------------------------------------------------------------------
# THE PROBE -- ``mandate_alive_at``
#
# THREE-VALUED FOR ITS CALLERS, and rung 8 depends on the distinction (S2.4b):
#
#   PROVEN LIVE      -- ``admitted is True``
#   PROVEN DEAD      -- ``decline_reason == 'mandate_not_alive'``
#   UNPROVABLE       -- every other reason (coverage, decision evidence, the
#                       snapshot, fire derivability, an ambiguous membership)
#
# An UNPROVABLE competitor must NOT be dropped as an absent one: that is the
# exact inversion of this plan's posture everywhere else, and it would let the
# selected order be admitted while two live mandates may have existed.
# ---------------------------------------------------------------------------
def _probe_refusal(
    reason: str,
    *,
    order: AcceptedLatchOrder,
    **fields,
) -> LatchedProvenance:
    """A recognised link whose aliveness could not be established."""
    return LatchedProvenance(
        admitted=False,
        recognised_but_underivable=True,
        decline_reason=reason,
        order=order,
        **fields,
    )


def _as_date(raw) -> date | None:
    """The TEXT-column -> ``date`` boundary, converted at the callsite."""
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _decision_ordering_refusal(
    conn, *, candidate_set, fill_session: date,
) -> str | None:
    """``None``, or the reason the decision ledger cannot be ordered against
    the fill.

    ``horizon_session_override`` scopes FIRES and BARS; it does NOT scope
    DECISIONS. `admissible_decisions` filters on `action_session_date` and never
    examines `recorded_ts`, while `_order_key` lets a LATER-RECORDED row win --
    so a `place` recorded AFTER the fill can outrank an earlier `decline` and
    make a historical probe admit a mandate that was dead when it filled.
    Migration `0033` draws exactly this distinction: `action_session_date` says
    WHICH SESSION'S MANDATE, `recorded_ts` says WHEN THE ANSWER HAPPENED.

    THE COMPARISON IS DATE-TO-DATE IN ONE DOMAIN, DELIBERATELY COARSE.
    `recorded_ts` is naive LOCAL and the entry carries only a DATE; inventing a
    third clock domain to order them is what this arc declines to do (D37). So
    the rule can only ever REFUSE, never admit something it should not.

    THIS IS A SECOND READ OF THE LEDGER AND THAT IS SOUND, where a second read
    of the ARCHIVE would not be: `latch_order_intents` carries
    `trg_loi_no_update` / `trg_loi_no_delete`, so the rows cannot change between
    the derivation's read and this one. The parquet has no such guarantee, which
    is why coverage is computed from `derivation.archive_closes` instead.

    A read failure here refuses `decision_evidence_unavailable` -- the same
    reason the strict loader raises -- because the two are the same ignorance.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch

    post_dates: list[int] = []
    unorderable: list[int] = []
    for candidate_id in sorted(candidate_set):
        try:
            rows = list_intents_for_latch(conn, candidate_id=candidate_id)
        except Exception as exc:  # noqa: BLE001 -- ignorance, not a crash
            log.warning(
                "22-A: decision-ledger read failed at candidate %s; the probe "
                "cannot tell an absent decline from an unread one: %s",
                candidate_id, exc)
            return "decision_evidence_unavailable"
        for intent in rows:
            if intent.intent_kind not in ("place", "decline"):
                continue
            # Only intents the probe would ADMIT are in scope: one whose mandate
            # session post-dates the fill was never about this fill.
            mandate_session = _as_date(intent.action_session_date)
            if mandate_session is not None and mandate_session > fill_session:
                continue
            recorded = _as_date(intent.recorded_ts)
            if recorded is None or recorded == fill_session:
                # An UNPARSEABLE stamp is as unorderable as a same-day one.
                unorderable.append(intent.intent_id or 0)
            elif recorded > fill_session:
                post_dates.append(intent.intent_id or 0)
    if post_dates:
        # Named FIRST because it is the DEFINITE fact -- the evidence provably
        # post-dates the fill -- while a same-day stamp is only an ambiguity.
        log.warning(
            "22-A: decision intents %s were recorded AFTER the fill session %s; "
            "the probe refuses rather than judging a mandate on evidence that "
            "had not happened when it filled", post_dates, fill_session)
        return "decision_evidence_post_dates_fill"
    if unorderable:
        return "decision_ordering_ambiguous"
    return None


def _fill_wins(latch, fill_session: date) -> tuple[bool, str | None]:
    """``(alive, admission_basis)`` -- the LADDER's comparison, not a local one.

    A re-derivation of `_resolve_terminal`'s `fill.order_key <= nonfill.order_key`
    with the SUBJECT's own `(fill_session, rank 0)` supplied, computed from the
    imported `_Terminal` so it cannot drift from the rule it inherits.

    `fill` is EXCLUDED from the widening: with the subject excluded from the
    probe, a `fill` terminal is ANOTHER trade's fill -- a genuine consumption,
    refused as such, never admitted.
    """
    if latch.clear_reason is None:
        return True, "armed"
    if latch.clear_reason == "fill":
        return False, None
    clear_session = latch.clear_session
    if clear_session is None:
        # A terminal with no date cannot be argued onto the fill session.
        return False, None
    subject = _Terminal("fill", fill_session)
    nonfill = _Terminal(latch.clear_reason, clear_session)
    if subject.order_key > nonfill.order_key:
        return False, None
    if clear_session != fill_session:
        # UNREACHABLE through the production probe: `horizon_session_override`
        # bounds every walk at-or-before the fill session, so a terminal cannot
        # be dated LATER. Raised rather than branched on for the same reason
        # `criteria_lapsed` is: the evidence contract binds the tie basis to
        # `clear_session == fill_session`, and a silent branch here would mint a
        # row the citation trigger must then reject.
        raise LatchProbeInvariantError(
            f"terminal {latch.clear_reason!r} is dated {clear_session}, AFTER "
            f"the fill session {fill_session}; the probe's own horizon bound "
            f"makes this impossible, so the bound did not take"
        )
    return True, "subject_fill_wins_same_session_tie"


def _coverage_view(derivation, latch, *, ticker: str, fill_session: date):
    """``(coverage_object, archive_status, missing_sessions)``.

    Computed SOLELY from `derivation.archive_closes` / `archive_status` -- the
    EXACT bars the fold judged -- and NEVER from a second `load_bars_with_status`
    call. The parquet is mutable, so a second read can report a complete window
    over bars the fold never saw: one read, one world.

    `ok` does NOT imply COMPLETE. The reader permits an empty or partial bar set
    on a successful read and `_eligible_bars` judges only the sessions it was
    handed, so an `ok` archive missing an INTERIOR session silently hides a
    breach.
    """
    status = derivation.archive_status.get(ticker)
    required_upper = session_offset(fill_session, -1)
    if required_upper < latch.anchor:
        # THE WINDOW IS EMPTY and the mandate is alive BY CONSTRUCTION: no
        # session has elapsed since the fire. This is the common good case --
        # fire tonight, fill at tomorrow's open -- and a naive "require bars"
        # rule refuses exactly it.
        return {"window_empty": True}, status, []
    expected: list[date] = []
    cursor = latch.anchor
    while cursor <= required_upper:
        expected.append(cursor)
        cursor = session_offset(cursor, 1)
    closes = derivation.archive_closes.get(ticker) or {}
    observed = [s for s in expected if s in closes]
    missing = [s for s in expected if s not in closes]
    coverage = {
        "expected_sessions": [s.isoformat() for s in expected],
        "observed_sessions": [s.isoformat() for s in observed],
        "missing_sessions": [s.isoformat() for s in missing],
    }
    return coverage, status, missing


def mandate_alive_at(
    conn,
    cfg,
    *,
    order: AcceptedLatchOrder,
    fill_session: date,
    exclude_trade_ids: frozenset[int],
) -> LatchedProvenance:
    """Was THIS mandate alive when THIS fill happened?

    THE JUDGMENT IS DELEGATED; ONLY THE INPUTS ARE GUARDED. `derive_latches`
    already implements RD's full precedence ladder including the invalidation
    rung, so this function authors NO second invalidation comparison (S0(1)).
    What it adds is the set of guards that make the delegated answer
    trustworthy, each of which can REFUSE and each of which records the input it
    judged in `probe_evidence`.

    `exclude_trade_ids` has NO DEFAULT deliberately. On the CORRECTION path the
    subject trade already exists, and `_match_fill`'s windowed rung admits any
    NULL-candidate, same-ticker, in-zone entry -- so an unexcluded probe returns
    `clear_reason='fill'` for the very mandate it is being asked about, and the
    arc's own live application becomes unreachable. A defaulted parameter is how
    that defect comes back silently.
    """
    if not is_trading_session(fill_session):
        # An implementation skipping this walks `session_offset` from a weekend
        # and shifts the WHOLE probe window.
        return _probe_refusal(
            "fill_session_not_a_session", order=order,
            horizon_session=fill_session)

    # THE SNAPSHOT NULL CHECK RUNS FIRST, BEFORE THE PROBE. A link with no
    # frozen value can never be cross-checked whatever the probe answers; and a
    # junk fire is DEGRADED by `derive_latches`, so a later check would report
    # `fire_not_derivable` and hide the real defect behind a symptom.
    if order.frozen_pivot is None or order.frozen_invalidation is None:
        return _probe_refusal(
            "frozen_value_unavailable", order=order,
            horizon_session=fill_session, freeze_tier=order.freeze_tier)

    try:
        derivation = build_latch_derivation(
            conn, cfg,
            horizon_session_override=fill_session,
            # RD's bound: a latch NEVER dies of drift, and `criteria_lapsed` IS
            # the drift rung. Forced OFF rather than tolerated, because the
            # ladder resolves EARLIEST-first: a lapse at D3 would MASK an
            # invalidation at D5, so treating a lapse as "alive" would be blind
            # rather than conservative.
            criteria_lapse_armed_override=False,
            exclude_trade_ids=frozenset(exclude_trade_ids),
            # A lost decline ledger must not read as "no decline".
            strict_decisions=True,
        )
    except DecisionIntentsUnavailableError as exc:
        log.warning(
            "22-A: the decision ledger could not be read for the %s probe at "
            "%s, so an absent decline is indistinguishable from an unread one: "
            "%s", order.ticker, fill_session, exc)
        return _probe_refusal(
            "decision_evidence_unavailable", order=order,
            horizon_session=fill_session, freeze_tier=order.freeze_tier)

    # SELECTION IS BY `candidate_set` MEMBERSHIP, NEVER BY IDENTITY. The set is
    # "the opening fire PLUS every re-confirmation" and the fold keeps the
    # OPENING candidate as the identity, so an accepted order placed against a
    # same-pivot RE-CONFIRMATION would return `fire_not_derivable` under an
    # identity match -- a refusal manufactured by the lookup, not by the mandate.
    containing = [
        latch for latch in derivation.latches
        if order.candidate_id in latch.candidate_set
    ]
    common = {
        "horizon_session": fill_session,
        "bars_through": derivation.derivation_session,
        "freeze_tier": order.freeze_tier,
    }
    if not containing:
        return _probe_refusal("fire_not_derivable", order=order, **common)
    if len(containing) > 1:
        log.warning(
            "22-A: fire %s is inside %d latches (%s); exactly one may contain "
            "it", order.candidate_id, len(containing),
            [lat.identity.candidate_id for lat in containing])
        return _probe_refusal(
            "ambiguous_fire_membership", order=order, **common)
    latch = containing[0]

    if latch.clear_reason == "criteria_lapsed":
        # RAISED, NOT BRANCHED ON: the rung is forced off above, so seeing it
        # back means the force did not take, and a silent branch would hide it.
        raise LatchProbeInvariantError(
            f"the probe returned clear_reason='criteria_lapsed' for candidate "
            f"{order.candidate_id} with the rung forced OFF; the force did not "
            f"take, and treating a drift-cleared latch as dead would violate "
            f"RD's bound that a latch never dies of drift"
        )

    ordering = _decision_ordering_refusal(
        conn, candidate_set=latch.candidate_set, fill_session=fill_session)
    if ordering is not None:
        # BEFORE the verdict is trusted: the as-of rule is about whether the
        # INPUT was admissible, not about what the ladder concluded from it.
        return _probe_refusal(ordering, order=order, **common)

    alive, basis = _fill_wins(latch, fill_session)
    if not alive:
        evidence = dict(common)
        if latch.clear_reason == "fill":
            # THE `fill` TERMINAL IS WEAKER EVIDENCE THAN IT LOOKS: the windowed
            # rung matches ANY NULL-candidate, same-ticker, in-zone entry and
            # never inspects a broker order id. The refusal NAMES the matched
            # trade and its basis so a heuristic-driven refusal is visible as
            # one rather than presented as proof.
            log.warning(
                "22-A: the %s mandate reads CONSUMED at %s by trade %s matched "
                "on %r; that rung never inspects a broker order id, so this "
                "refusal is heuristic evidence, not proof",
                order.ticker, latch.clear_session, latch.clear_trade_id,
                latch.fill_link_basis)
        return _probe_refusal(
            "mandate_not_alive", order=order,
            clear_reason=latch.clear_reason,
            clear_session=latch.clear_session,
            probe_evidence={
                "fill_terminal_trade_id": latch.clear_trade_id,
                "fill_terminal_link_basis": latch.fill_link_basis,
            } if latch.clear_reason == "fill" else None,
            **{k: v for k, v in evidence.items()},
        )

    coverage, status, missing = _coverage_view(
        derivation, latch, ticker=order.ticker, fill_session=fill_session)
    window_empty = coverage.get("window_empty", False) is True
    if not window_empty and (status != ARCHIVE_STATUS_OK or missing):
        # An interior hole could HIDE a breach, so an unverifiable window must
        # not be read as a survival. Refusal-only asymmetry, as everywhere else.
        log.warning(
            "22-A: aliveness for %s at %s is UNVERIFIABLE (archive_status=%r, "
            "missing sessions %s)", order.ticker, fill_session, status,
            coverage.get("missing_sessions"))
        return _probe_refusal(
            "aliveness_unverifiable", order=order,
            clear_reason=latch.clear_reason, clear_session=latch.clear_session,
            window_empty=window_empty, archive_status=status,
            probe_evidence={"coverage": coverage}, **common)

    # THE SNAPSHOT CROSS-CHECK -- RD's gate, enforced AT the comparison, and
    # THE ARC'S SINGLE ROUNDING AUTHORITY. It happens HERE, in Python, at
    # PRICE_DP, ONCE. The citation trigger does NOT repeat it: it binds the RAW
    # operands to their sources by identity and records THIS comparison's
    # verdict as a datum. A SQL-side re-comparison is forbidden in both
    # available forms -- raw equality refuses truthful sub-cent drift, and
    # SQLite's `round()` is a DIFFERENT rounding rule from Python's.
    #
    # The comparison is the link's frozen value against the LATCH's, per RD
    # constraint 1: the mandate is frozen at its OPENING fire, so that is the
    # number the mandate actually declared. Where an order was placed against a
    # re-confirmation whose stop had drifted from the opening fire's, the two
    # differ and this refuses -- which is the correct, fail-closed answer.
    invalidation_equal = (
        round(float(order.frozen_invalidation), PRICE_DP)
        == round(float(latch.latched_initial_stop), PRICE_DP))
    pivot_equal = (
        round(float(order.frozen_pivot), PRICE_DP)
        == round(float(latch.latched_pivot), PRICE_DP))
    if not (invalidation_equal and pivot_equal):
        log.warning(
            "22-A: frozen-value DRIFT for %s (link %s): frozen "
            "(pivot=%r, invalidation=%r) vs latched (pivot=%r, invalidation=%r)",
            order.ticker, order.link_id, order.frozen_pivot,
            order.frozen_invalidation, latch.latched_pivot,
            latch.latched_initial_stop)
        return _probe_refusal(
            "frozen_value_drift", order=order,
            clear_reason=latch.clear_reason, clear_session=latch.clear_session,
            window_empty=window_empty, archive_status=status,
            probe_evidence={"coverage": coverage}, **common)

    # The LIVE operands are read from the CANDIDATE the link cites, because that
    # is what the citation trigger binds `$.live_*_raw` to. They agree with the
    # latch's frozen pair for every row that reaches here -- the cross-check
    # above is what makes that true rather than assumed.
    live = conn.execute(
        "SELECT pivot, initial_stop FROM candidates WHERE id = ?",
        (order.candidate_id,),
    ).fetchone()
    live_pivot, live_invalidation = (None, None) if live is None else live

    evidence = {
        "evidence_version": LATCH_PROBE_EVIDENCE_VERSION,
        "fire_candidate_id": order.candidate_id,
        "ticker": order.ticker,
        "fill_session": fill_session.isoformat(),
        # `horizon_session` IS the fill session and is SQL-BOUND; `bars_through`
        # is the exchange-calendar-derived prior session and is service-validated
        # (a trigger cannot walk an exchange calendar). Collapsing the two into
        # one `probe_session` gave it two incompatible definitions, under which a
        # truthful correction could not have been written at all.
        "horizon_session": fill_session.isoformat(),
        "bars_through": derivation.derivation_session.isoformat(),
        "clear_reason": latch.clear_reason,
        "clear_session": (
            latch.clear_session.isoformat()
            if latch.clear_session is not None else None),
        "admission_basis": basis,
        "criteria_lapse_forced_off": 1,
        "freeze_tier": order.freeze_tier,
        "archive_status": status,
        "frozen_invalidation_raw": order.frozen_invalidation,
        "live_invalidation_raw": live_invalidation,
        "frozen_pivot_raw": order.frozen_pivot,
        "live_pivot_raw": live_pivot,
        "invalidation_equal_at_dp": 1 if invalidation_equal else 0,
        "pivot_equal_at_dp": 1 if pivot_equal else 0,
        "compare_dp": PRICE_DP,
        "coverage": coverage,
    }
    return LatchedProvenance(
        admitted=True,
        recognised_but_underivable=False,
        decline_reason=None,
        order=order,
        clear_reason=latch.clear_reason,
        clear_session=latch.clear_session,
        horizon_session=fill_session,
        bars_through=derivation.derivation_session,
        window_empty=window_empty,
        archive_status=status,
        probe_evidence=evidence,
        freeze_tier=order.freeze_tier,
    )
