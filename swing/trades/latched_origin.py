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
import math
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
    "PROBE_GUARD_CLAUSES",
    "PROBE_GUARD_KEYS",
    "PROBE_EVIDENCE_KEYS",
    "PROBE_EMITTED_EVIDENCE_KEYS",
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
    "authorize_accepted_order",
    "competitor_liveness_rung",
    "resolve_latched_provenance",
    "find_accepted_latch_order",
    "ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS",
    "broker_order_id_from_envelope",
    "envelope_is_canonical",
    "envelope_recognises_an_order",
    "instrument_symbol_from_envelope",
]

# The probe-evidence schema's own version, mirrored from migration 0037's
# citation trigger (`$.evidence_version`).  A row written under an older shape
# must be DISTINGUISHABLE rather than silently re-interpreted, which is only
# true if both halves name the same version -- so a drift test asserts the
# literal in the migration equals this constant (#11).
LATCH_PROBE_EVIDENCE_VERSION = "2026-08-25.1"

# THE ENVELOPE CANONICALISER'S OWN VERSION (22-A round 11, PERSIST-CANONICAL).
# Every stored reading records the version that produced it, so a reading made
# under an older grammar is DISTINGUISHABLE rather than silently trusted.  Bump
# this whenever `canonical_envelope_identity` would answer a document
# differently; `record_identity` then RAISES on the disagreement instead of
# preferring either answer.
#
# AND THE SENTENCE ABOVE NAMES ITS ENFORCEMENT (Codex 22A-R11-03).  It used to
# be true only of the two callers that ask about ONE document -- the fills
# writer and the correction subject -- while the population pass that walks
# EVERY OTHER trade's entry fill, which is exactly what the consumption scans
# consult, excluded any row that already had a reading.  A stale reading was
# therefore neither re-checked nor filtered, and it ADMITTED A SECOND CONSUMER
# of one mandate (measured).  `ensure_entry_fill_identities` now re-verifies
# the whole population through the same drift check, so bumping this constant
# is LOUD on every document whose answer moved and SILENT on every document
# whose answer did not -- the discriminator is the ANSWER, never the label.
ENVELOPE_CANONICALIZER_VERSION = "2026-08-26.1"

ENVELOPE_CANONICAL = "canonical"
ENVELOPE_REFUSED = "refused"
# Mirrored by migration 0037's `CHECK (envelope_state IN (...))` (#11 -- the
# schema CHECK, the Python constant and the writer land in ONE task).
ENVELOPE_STATES: frozenset[str] = frozenset({
    ENVELOPE_CANONICAL, ENVELOPE_REFUSED})


class LatchProbeInvariantError(RuntimeError):
    """The probe returned a state the forced configuration makes impossible.

    Raised rather than branched on: ``criteria_lapsed`` is FORCED OFF (plan
    S2.3.4, RD's bound that a latch never dies of drift), so seeing it back
    means the force did not take, and a silent branch would hide that.
    """


# ---------------------------------------------------------------------------
# THE DECLINE-REASON ROSTER -- THIRTY-SIX.
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
    # Rung 3b's ledger read is IGNORANCE when it fails, not absence (Codex
    # 22A-R3-14). Its own reason rather than a borrowed one: a rung that
    # returned `linked_validity_not_accepted` would ASSERT a fact about the
    # broker's answer that it precisely could not read.
    "validity_evidence_unavailable",
    # The envelope carries a value that PYTHON and SQL would read
    # DIFFERENTLY (Codex 22A-R8-01, widened by self-sweep SS-1/SS-4): padded,
    # blank, non-string, or carrying duplicate keys, on EITHER of the two keys
    # both domains read. A value two domains disagree about cannot bind a
    # mandate.  NAMED FOR THE ENVELOPE RATHER THAN THE ORDER ID because the
    # symbol reaches it too, and a reason that says `order_id` while refusing
    # a symbol divergence is the #31 class in a decline code.
    "envelope_not_canonical",
    # The fill's ORIGIN says a broker filled it and its ENVELOPE names nothing
    # -- an INCONSISTENT EVIDENCE PAIR no production writer produces (RD, ruled
    # on 22A-R3-13). Not "untrusted origin", which is a different sentence
    # about a different fill.
    "origin_envelope_inconsistent",
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
        "latch_order_intents cancel rows NAMING THIS broker order "
        "at-or-before the fill session",
        "no cancellation of this broker order at-or-before the fill",
    ),
    AuthorizationClause(
        "rung6_consuming_trade_id", SQL_BOUND, "integer", True,
        "fill_envelope_identity.broker_order_id on OTHER trades",
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
        "fill_envelope_identity.instrument_symbol",
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


# ---------------------------------------------------------------------------
# ``$.probe_guards`` -- THE PROBE'S OWN REFUSAL-CAPABLE CLAUSES (Codex R2-04).
#
# ``$.authorization`` covers the AUTHORIZER's rungs and the envelope guards.
# The PROBE has refusal-capable clauses of its own, and they had no verdict
# slot at all -- so an audit could not distinguish "the guard passed" from "the
# guard never ran" for exactly the three clauses that decide whether the
# delegated derivation is trustworthy.  Same standing rule, same {input,
# verdict} shape, one nested object so the top-level roster grows by ONE key.
#
# THREE ENTRIES, and the boundary is stated rather than left to look complete:
#   * ``fill_session_is_session`` -- an implementation omitting it walks
#     ``session_offset`` from a weekend and shifts the WHOLE probe window.
#   * ``fire_membership`` -- the count of latches whose ``candidate_set``
#     contains the fire.  Exactly ONE is an admission; the reason
#     ``ambiguous_fire_membership`` exists for the other case.
#   * ``decision_ordering`` -- the admissible decisions the as-of rule judged,
#     each as ``[intent_id, recorded_ts]``.  Its SQL twin binds every supplied
#     pair to a real intent row and does NOT prove the set is complete; that
#     limitation is declared in 0037 with its reason, and it is NOT AL-3
#     (Codex 22A-R9-05).  This carries R2-04's "consulted
#     decision IDs/timestamps" AND is the input the ordering verdict was
#     reached over, so the snapshot and the verdict are one entry rather than
#     two halves that could disagree.
#
# THREE CLAUSES ARE DELIBERATELY *NOT* HERE, each for a stated reason -- an
# honest exclusion list, because a roster whose boundary is unstated is the
# hand-enumerated-roster failure again:
#   * the FROZEN-VALUE PRESENCE guard: ``frozen_pivot_raw`` /
#     ``frozen_invalidation_raw`` are already top-level, typed ``real|integer``
#     and BOUND BY IDENTITY to the link's columns, so their presence IS the
#     record of that guard's input and verdict.  A second copy would be two
#     spellings of one fact.
#   * the SNAPSHOT CROSS-CHECK and the COVERAGE guard: recorded already, as
#     ``invalidation_equal_at_dp`` / ``pivot_equal_at_dp`` / ``compare_dp`` and
#     as ``coverage`` / ``archive_status``.
#   * the BROAD ``except Exception`` around the derivation: an implementation
#     omitting it CRASHES rather than admitting, so its absence is loud rather
#     than silent -- it is not the "passed vs never ran" class.
# ---------------------------------------------------------------------------
PROBE_GUARD_CLAUSES: tuple[AuthorizationClause, ...] = (
    AuthorizationClause(
        # SERVICE_VALIDATED, AND THE LABEL WAS FALSE UNTIL NOW (Codex
        # 22A-R6-06). The trigger binds this entry's INPUT to
        # `entry_fill_session_date` -- that part is real -- but it cannot check
        # the VERDICT, because no subquery can enumerate the NYSE calendar. It
        # required only `verdict = 'pass'`, so a weekend or holiday fill could
        # assert `pass` and be admitted while the roster advertised the clause
        # as SQL-bound. The honest options were a registered SQLite calendar
        # function -- which makes every connection lacking it refuse, a new
        # failure mode on every read path -- or truthful reclassification.
        # Reclassified: the same ground as AL-5 one clause over, and the same
        # ground the price-bound guards carry.
        "fill_session_is_session", SERVICE_VALIDATED, "text", False,
        "provenance_corrections.entry_fill_session_date (the INPUT is bound; "
        "the VERDICT is not -- SQL cannot enumerate a session calendar)",
        "the fill session is an NYSE trading session",
    ),
    AuthorizationClause(
        "fire_membership", SERVICE_VALIDATED, "integer", False,
        "-- derivation state; no subquery can walk the fold",
        "exactly ONE latch's candidate_set contains the fire",
    ),
    AuthorizationClause(
        # NOT AL-3, AND THE TWO-VALUED LABEL IS WHY THIS NOTE EXISTS (Codex
        # 22A-R9-05). The binding enum has only SQL_BOUND and
        # SERVICE_VALIDATED, so a PARTIALLY bound clause must pick one -- and
        # picking SERVICE_VALIDATED invited the migration comment to cite
        # AL-3, whose roster is rungs 7, 8 and `fire_membership` and does NOT
        # name this clause. Every pair supplied here IS bound by subquery to a
        # real intent row on both halves, which is strictly more than AL-3's
        # clauses get; what is unbound is the COMPLETENESS of the supply, and
        # that limitation is declared in 0037 beside the clause with its
        # reason and its 22-A2 trigger rather than borrowed from AL-3.
        "decision_ordering", SERVICE_VALIDATED, "array", False,
        "-- pairs BOUND to latch_order_intents; the SET's completeness is not "
        "(a declared limitation, banked to 22-A2 -- NOT AL-3)",
        "every consulted decision is orderable STRICTLY BEFORE the fill",
    ),
)

PROBE_GUARD_KEYS: tuple[str, ...] = tuple(c.key for c in PROBE_GUARD_CLAUSES)

# ---------------------------------------------------------------------------
# THE TOP-LEVEL EVIDENCE ROSTER -- THE INDEPENDENT THIRD PARTY (Codex R2-04).
#
# The predecessor's key-set test derived its expectation FROM migration 0037's
# closure list, so an implementation and a migration omitting the SAME key both
# passed.  Adding keys to a closed object guarded by a circular test leaves the
# new keys equally unguarded, which is why this roster exists BEFORE the keys
# were added rather than after.
#
# BOTH halves are compared against THIS, never against each other: the
# migration's closure list (task-2 module) and the blob the probe actually
# emits (task-6 module).  A key dropped from either fails against the roster; a
# key dropped from both still fails, twice.
# ---------------------------------------------------------------------------
PROBE_EVIDENCE_KEYS: tuple[str, ...] = (
    "evidence_version",
    "fire_candidate_id",
    "ticker",
    "fill_session",
    "horizon_session",
    "bars_through",
    "clear_reason",
    "clear_session",
    "admission_basis",
    "criteria_lapse_forced_off",
    "freeze_tier",
    "archive_status",
    "frozen_invalidation_raw",
    "live_invalidation_raw",
    "frozen_pivot_raw",
    "live_pivot_raw",
    "invalidation_equal_at_dp",
    "pivot_equal_at_dp",
    "compare_dp",
    "coverage",
    "probe_guards",
    # FILLED BY THE AUTHORIZER, not by the probe: `mandate_alive_at` emits
    # every key above and this one is added when the ladder has run.
    "authorization",
)

PROBE_EMITTED_EVIDENCE_KEYS: tuple[str, ...] = tuple(
    k for k in PROBE_EVIDENCE_KEYS if k != "authorization"
)


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
                f"{len(DECLINE_REASONS)}-member roster; a reason no rung can emit "
                f"is a roster "
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
    except Exception:  # noqa: BLE001 -- the TYPE ROSTER is the failure (SS-2)
        # ENUMERATING THE RAISABLE TYPES IS THE HAND-MAINTAINED-ROSTER FAILURE
        # -- 22A-R8-03's own ruling, applied to the readers that fix left
        # behind.  This was `except (ValueError, TypeError)`, and `json.loads`
        # raises `RecursionError`, a `RuntimeError`, on a deeply nested
        # document (MEASURED on this interpreter).  These readers run BEFORE
        # the resolver's containment, and one of them runs before
        # `record_entry` opens a transaction at all, so an escape here rolled
        # a money-bearing entry back over an unreadable audit blob.
        #
        # "Treat it as absent" is safe HERE only because
        # `envelope_is_canonical` answers the SAME document FAIL-CLOSED, so
        # the pair still RECOGNISES it and the row lands honest-unset instead
        # of taking the ordinary chain.
        log.warning(
            "22-A: fill envelope could not be decoded; treating the order id "
            "as absent (the fill still records, cohort bookkeeping degrades)"
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


# ---------------------------------------------------------------------------
# THE ENVELOPE KEYS BOTH DOMAINS READ -- and this roster is CLOSURE-CHECKED,
# never hand-maintained (self-sweep SS-4).
#
# A test parses migration 0037 for every `json_extract(<a fills envelope>,
# '$.KEY')` and asserts each KEY is a member here.  That is the STATIC WALK the
# recipe demands in place of a list: a fix whose shape is "maintain a roster"
# is not the roster, it is the check that walks what the code actually
# references.  Add a third key to the trigger and the walk fails until it is
# added here.
# ---------------------------------------------------------------------------
ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS: tuple[str, ...] = (
    SCHWAB_ORDER_ID_ENVELOPE_KEY,
    SCHWAB_SYMBOL_ENVELOPE_KEY,
)


def envelope_is_canonical(raw: str | None) -> bool:
    """Do PYTHON and SQL read the SAME value for EVERY key both domains read?

    ONE AUTHORITY, APPLIED TO AN IDENTITY (Codex 22A-R8-01; it is AL-7's shape
    one datum over).  The service STRIPS whitespace and ``json.loads`` keeps
    the LAST duplicate key; SQLite's ``json_extract`` strips nothing and keeps
    the FIRST -- both MEASURED.  So a padded or duplicated envelope gives the
    service one value while every SQL scan over the same blob reads another.

    The answer is NOT to canonicalise harder in one domain -- that is the
    two-spellings-agree-today class.  It is to REFUSE an envelope the two
    domains would read differently, so the value is either unambiguous or the
    admission does not happen.  ``False`` becomes a recognised-but-underivable
    refusal, never a fall-through.

    THREE THINGS THE SELF-SWEEP CHANGED, each verified by execution:

    * **THE ROSTER, NOT THE ORDER ID ALONE (SS-4).**  R8-01 stated the class
      and fixed ONE instance.  The citation trigger ALSO binds
      ``$.schwab_instrument_symbol`` by ``json_extract`` while the service
      reads that key through ``instrument_symbol_from_envelope``, which
      strips -- measured: the service admitted ``latch_ladder`` and the trigger
      then ABORTED the correction with the generic citation-graph message, an
      authorize-then-abort delivering an illegible refusal.
    * **A NON-STRING VALUE IS A DISAGREEMENT, NOT AN ABSENCE (SS-1).**  The
      earlier "the reader already returns None" line treated it as harmless.
      It is not: ``json_extract`` yields a non-NULL scalar, and comparing that
      to a TEXT column applies TEXT affinity -- MEASURED, an unquoted
      ``1002937461`` MATCHES a link whose ``broker_order_id`` is the string
      ``1002937461``.  Python reads absence; SQL reads a real mandate.
    * **A BLANK OR PADDED VALUE LIKEWISE.**  Python strips it to nothing while
      SQL returns the string.  Direction is a wrong REFUSAL on a shape that
      names no order, which is the cheap one.

    NEVER RAISES ON A DECODE FAILURE, and the breadth is deliberate: the
    earlier ``except (ValueError, TypeError)`` was the hand-maintained-roster
    failure 22A-R8-03 ruled against, applied to exception TYPES, and
    ``json.loads`` raises ``RecursionError`` (a ``RuntimeError``, caught by
    neither) on a deeply nested document -- MEASURED on this interpreter.

    AND EVERY DECODE FAILURE ANSWERS ``False`` (Codex 22A-R11-01).  A document
    the authority cannot decode is an UNANSWERED question, not an agreement;
    see the handler below for what the split cost and why the mirror-shape
    ground for the old ``True`` died with the mirror.
    """
    if not isinstance(raw, str) or not raw.strip():
        return True                    # no envelope: nothing to disagree about
    # THE COUNT IS THE ROOT OBJECT'S, NOT THE DOCUMENT'S (Codex 22A-R9-06).
    # `object_pairs_hook` fires for EVERY nested object, so a first version
    # counted a legitimate top-level id plus an unrelated nested field of the
    # same name as a duplicate -- a wrong REFUSAL manufactured by the guard.
    # Both readers address `$.<key>` at the ROOT, so the root is the only
    # place the two can disagree. The hook records EVERY object's pairs and
    # the LAST one it returns is the root, because the decoder builds
    # inside-out.
    objects: list[list[tuple]] = []

    def _hook(pairs):
        objects.append(list(pairs))
        return dict(pairs)

    try:
        payload = json.loads(raw, object_pairs_hook=_hook)
    except Exception:  # noqa: BLE001 -- fail-CLOSED on an UNANSWERED question
        # THE TWO DECODE BRANCHES ARE ONE (Codex 22A-R11-01).  This was split:
        # a `ValueError`/`TypeError` returned True on the ground that "a
        # document NEITHER DOMAIN can read agrees with itself -- both read
        # absence", while a `RecursionError` returned False.  The first ground
        # was TRUE OF THE MIRROR SHAPE and died with it.  Under PERSIST-
        # CANONICAL there is no second domain to agree with: SQL never opens
        # the document, so the question is no longer "do the two engines read
        # it alike" but "can the AUTHORITY say what this document names", and
        # for a document it cannot decode it cannot.
        #
        # WHAT THE SPLIT COST, MEASURED: `canonical_envelope_identity('{bad')`
        # stored `state='canonical'` with both ids NULL -- indistinguishable
        # from a decodable document that genuinely names nothing.  Rung 6's
        # consumption scan matches on an order id such a row does not carry,
        # and its unreadable-scan matches on `refused`, which it was not, so an
        # UNREADABLE prior consumer was invisible to both and read as evidence
        # of ABSENCE at the one rung that exists to stop a second consumer of
        # one mandate.  Ignorance fails CLOSED here as it does everywhere else
        # on this ladder.
        #
        # A DECODABLE document that names no order is UNAFFECTED and must be:
        # `[1, 2, 3]` and `{}` are still canonical, because the authority READ
        # them and they name nothing, which is a statement rather than a
        # silence.  That distinction is what keeps the last_word ladder open
        # for every pre-22-A fill.
        log.exception(
            "22-A: the fill envelope could not be DECODED, so the authority "
            "cannot say what it names; the reading is REFUSED and the entry "
            "records with honest-unset cohort keys rather than with the "
            "latest run's candidate")
        return False
    if not isinstance(payload, dict) or not objects:
        return True
    root = objects[-1]
    for key in ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS:
        seen = [k for k, _v in root if k == key]
        if len(seen) > 1:
            log.warning(
                "22-A: fill envelope carries %d %s keys; Python keeps the LAST "
                "and SQLite keeps the FIRST, so the two domains would read "
                "DIFFERENT values", len(seen), key)
            return False
        if key not in payload:
            continue                   # absent in BOTH domains
        value = payload[key]
        if value is None:
            continue                   # JSON null: json_extract reads NULL too
        if not isinstance(value, str):
            log.warning(
                "22-A: fill envelope's %s is a %s rather than a string (%r); "
                "the service treats it as ABSENT while json_extract returns "
                "it, and TEXT affinity can still match a stored identity",
                key, type(value).__name__, value)
            return False
        if value != value.strip() or not value.strip():
            log.warning(
                "22-A: fill envelope's %s is whitespace-padded or blank (%r); "
                "the service strips it and SQL does not, so the two domains "
                "would read DIFFERENT values", key, value)
            return False
    return True


@dataclass(frozen=True)
class EnvelopeIdentity:
    """The authority's ONE reading of one envelope document."""

    state: str                        # ENVELOPE_CANONICAL | ENVELOPE_REFUSED
    broker_order_id: str | None
    instrument_symbol: str | None


def canonical_envelope_identity(raw: str | None) -> EnvelopeIdentity:
    """THE ONE DERIVATION.  Everything downstream compares its STORED OUTPUT.

    PERSIST-CANONICAL (CHARC + RD, 2026-08-26).  Ten review rounds never
    converged because migration 0037 was made to RE-DERIVE this function's
    judgment in SQL, and the two engines disagree in at least three independent
    ways -- ``json.loads`` accepts ``NaN`` where ``json_valid`` rejects the
    document; ``str.strip`` removes tab/newline/NBSP where ``trim()`` removes
    ASCII space only; ``1002937461 == '1002937461'`` is False in Python and
    True in SQL against a TEXT-affinity column.  Three rounds, three
    divergences, each found only after the previous was fixed, and nothing said
    three was the last.  So the mirror is gone: this function decides, its
    answer is PERSISTED against the exact document it read
    (``fill_envelope_identity.envelope_raw``), and SQL compares stored values.

    IT IS COMPOSED OF THE THREE EXISTING READERS AND ADDS NO FOURTH SPELLING.
    ``envelope_is_canonical`` still asks whether the document can be read to a
    single unambiguous value; the two readers still say what it says.  What
    changed is that nothing asks the question TWICE.

    NEVER RAISES: every constituent contains its own decode failure, and
    ``envelope_is_canonical`` answers a document it cannot decode with
    ``False`` -- fail CLOSED, because an unanswerable question is not a pass.
    """
    if not envelope_is_canonical(raw):
        return EnvelopeIdentity(ENVELOPE_REFUSED, None, None)
    return EnvelopeIdentity(
        ENVELOPE_CANONICAL,
        broker_order_id_from_envelope(raw),
        instrument_symbol_from_envelope(raw),
    )


def origin_and_envelope_are_inconsistent(fill_origin, raw) -> bool:
    """A TRUSTED origin whose envelope names NOTHING (RD, ruled on 22A-R3-13).

    THE DISCRIMINATOR IS THE INCONSISTENT EVIDENCE PAIR, NEVER THE ORIGIN.
    A `schwab_auto` fill carries an envelope BY CONSTRUCTION -- established by
    READING both writers, not by grepping:

      * `swing/trades/entry_auto_fill.py` -- the `kind='populated'` branch of
        `EntryAutoFillResult.__post_init__` REQUIRES
        `fill_origin='schwab_auto'`, and the one `populated` return builds
        `schwab_source_value_json` in the same expression that sets it.
      * `swing/web/routes/trades.py` -- a trusted `resolved_fill_origin` is
        stamped ONLY inside the block that also assigns
        `resolved_schwab_source_value_json`, and that block is entered only
        when the submitted envelope parsed to a dict.

    So the pair is a state no production writer produces: the envelope was
    STRIPPED, TAMPERED WITH or CORRUPTED.  Writing TODAY's candidate for such a
    fill would be attribution from a TIMING COINCIDENCE -- gotcha #30's family,
    and the exact misattribution this arc exists to prevent.

    WHY NOT THE ORIGIN ALONE, which is the tempting rule: an envelope-BEARING
    Schwab fill that simply never had a latch is the ORDINARY post-integration
    state, and suppressing it would erase correct pipeline provenance across
    the whole journal.  Both directions are pinned by cases, because the two
    implementations agree on everything except the twin.

    PURE, and query-free by construction: LOCK clause (d) says a request with
    no usable order id costs ZERO additional database queries, and this
    predicate is the reason the answer can be reached without reserving.
    """
    if fill_origin not in TRUSTED_LATCH_FILL_ORIGINS:
        return False
    return not (isinstance(raw, str) and raw.strip())


def envelope_recognises_an_order(raw: str | None) -> bool:
    """THE ONE RECOGNITION TRIGGER, shared by every caller (self-sweep SS-1).

    "Does this request carry a usable broker order id?" was asked at THREE
    sites -- ``record_entry``'s reservation, the entry route's EXT-2 deferral,
    and the resolver -- and all three asked it of the PYTHON reader ALONE.  So
    an envelope Python reads as ABSENT and SQL reads as a REAL LINKED order
    took no reservation, never reached the canonicality guard 22A-R8-01 added
    for exactly that disagreement, and ran the ordinary current-candidate
    chain.  MEASURED end to end on three shapes: the persisted row was
    ``('pipeline_aplus', <today's candidate>)`` for a fill SQL binds to an
    accepted mandate.

    That is 22A-R9-01 one step further back.  R9-01 moved the canonicality
    question above the link LOOKUP; it still sat below the order-id READ, and
    the read is where a disagreeing envelope disappears.

    The question therefore INCLUDES the disagreement: an envelope the two
    domains read differently is RECOGNISED, so it is refused rather than
    silently attributed.  Three spellings became one, which is also what stops
    a fourth caller reintroducing the split.

    PURE STRING READ, ZERO QUERIES -- LOCK clause (d), "a fill with no usable
    broker order id costs ZERO additional database queries", is preserved by
    construction, and its subject is unchanged: an envelope naming no order
    and reading the same in both domains is still not recognised and still
    takes the deferred ``with conn:`` exactly as before.
    """
    return (broker_order_id_from_envelope(raw) is not None
            or not envelope_is_canonical(raw))


def instrument_symbol_from_envelope(raw: str | None) -> str | None:
    """The envelope's instrument symbol, degrading exactly as the order id does."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001 -- the TYPE ROSTER is the failure (SS-2)
        # ENUMERATING THE RAISABLE TYPES IS THE HAND-MAINTAINED-ROSTER FAILURE
        # -- 22A-R8-03's own ruling, applied to the readers that fix left
        # behind.  This was `except (ValueError, TypeError)`, and `json.loads`
        # raises `RecursionError`, a `RuntimeError`, on a deeply nested
        # document (MEASURED on this interpreter).  These readers run BEFORE
        # the resolver's containment, and one of them runs before
        # `record_entry` opens a transaction at all, so an escape here rolled
        # a money-bearing entry back over an unreadable audit blob.
        #
        # "Treat it as absent" is safe HERE only because
        # `envelope_is_canonical` answers the SAME document FAIL-CLOSED, so
        # the pair still RECOGNISES it and the row lands honest-unset instead
        # of taking the ordinary chain.
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
    # AN ABSENT SYMBOL FAILS THE GUARD, IT DOES NOT PASS IT (Codex 22A-R6-05).
    # `envelope_symbol is not None and ...` collapsed a three-valued question to
    # two: UNKNOWN read as PASS, and the evidence blob then recorded a PASSING
    # guard whose input was `null`. It is also an authorize-then-abort: the
    # citation trigger requires that entry's input to be TEXT, so a correction
    # the service admitted aborted at the INSERT. Direction of the change is a
    # wrong REFUSAL, which is the cheap one.
    if envelope_symbol is None or envelope_symbol != ticker:
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

    # NON-FINITE IS UNAVAILABLE, AND POSITIVITY DOES NOT CATCH IT (Codex
    # 22A-R8-03). `inf > 0` is True, so the link CHECK and the model validator
    # both admit `+inf`; `zone_cap_for_pivot` then raises `ValueError` on a
    # non-finite input BY DESIGN, and that exception escaped the whole ladder.
    # Refused HERE, before any arithmetic, under the reason that says what is
    # true: the frozen value cannot be used.
    if (order.frozen_pivot is None
            or not math.isfinite(float(order.frozen_pivot))):
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
# THE LOOKUP -- RAW, AND IT RETURNS A LIST
#
# Two functions, not one, because the declared one-argument signature could not
# implement the rungs assigned to it (plan S5.1, review 22A-R4-08).  This half
# takes a broker order id and returns EVERY matching link; the list is what
# makes S2.4's "cardinality by COUNT, not fetchone()" expressible in the TYPE
# instead of only in prose.  There is deliberately NO UNIQUE on
# ``broker_order_id`` -- a duplicate would abort the LEDGER write, and cohort
# bookkeeping must never block a money-bearing operation -- so the reader
# counts and a ``fetchone()`` signature would silently pick one and look right.
# ---------------------------------------------------------------------------
def find_accepted_latch_order(
    conn, *, broker_order_id: str,
) -> list[AcceptedLatchOrder]:
    """Every link naming this broker order, oldest first.  NO rungs run here.

    ``actual_limit_price`` comes from the validity JOIN this lookup already
    performs, so the envelope guards stay a PURE function over the dataclass
    (plan S5.1) rather than growing a connection argument.
    """
    rows = conn.execute(
        "SELECT l.link_id, l.validity_intent_id, l.place_intent_id, "
        "       l.candidate_id, l.evaluation_run_id, l.ticker, "
        "       l.detection_date, l.broker_order_id, l.frozen_pivot, "
        "       l.frozen_invalidation, l.actual_quantity, l.freeze_tier, "
        "       v.actual_limit_price "
        "  FROM latch_order_mandate_links l "
        "  JOIN latch_order_intents v ON v.intent_id = l.validity_intent_id "
        " WHERE l.broker_order_id = ? "
        " ORDER BY l.link_id",
        (broker_order_id,),
    ).fetchall()
    return [
        AcceptedLatchOrder(
            link_id=int(r[0]), validity_intent_id=int(r[1]),
            place_intent_id=int(r[2]), candidate_id=int(r[3]),
            evaluation_run_id=int(r[4]), ticker=str(r[5]),
            detection_date=str(r[6]), broker_order_id=str(r[7]),
            frozen_pivot=r[8], frozen_invalidation=r[9],
            actual_quantity=None if r[10] is None else int(r[10]),
            freeze_tier=str(r[11]), actual_limit_price=r[12],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# THE AUTHORIZATION LADDER -- ELEVEN RUNGS, EACH A REFUSAL, EACH NAMED
#
# Ten ship HERE (task 4): 1, 2, 3, 3b, 3c, 4, 5, 6, 7 and 9.  **Rung 8 --
# competitor liveness -- is task 6a's**, because it must evaluate each
# competitor through ``mandate_alive_at`` and could not have run at this point
# in the ladder (22A-R7-09).  It is injected through ``competitor_rung`` rather
# than hard-coded here, so task 6a adds a rung without re-opening this function
# and the seam is a parameter rather than a comment promising inheritance (#31).
#
# EVERY RUNG RECORDS THE INPUT IT JUDGED AND THE VERDICT IT REACHED, into the
# ``$.authorization`` object whose roster is ``AUTHORIZATION_CLAUSES`` -- or
# "passed" and "never ran" are indistinguishable at audit (plan S4.3).  The
# block is built by WALKING the roster, so a rung added to the roster without a
# value here raises at emit rather than shipping a silently-absent entry.
# ---------------------------------------------------------------------------
def _refuse(reason: str, order: AcceptedLatchOrder, **fields) -> LatchedProvenance:
    return LatchedProvenance(
        admitted=False, recognised_but_underivable=True,
        decline_reason=reason, order=order, **fields)


def _authorization_block(inputs: dict) -> dict:
    """``{key: {"input": ..., "verdict": "pass"}}`` over the WHOLE roster."""
    missing = sorted(set(AUTHORIZATION_KEYS) - set(inputs))
    extra = sorted(set(inputs) - set(AUTHORIZATION_KEYS))
    if missing or extra:
        raise KeyError(
            f"authorization block does not match AUTHORIZATION_CLAUSES: "
            f"missing {missing}, extra {extra}")
    return {key: {"input": inputs[key], "verdict": "pass"}
            for key in AUTHORIZATION_KEYS}


def _intent_row(conn, intent_id: int | None) -> dict | None:
    if intent_id is None:
        return None
    row = conn.execute(
        "SELECT intent_id, candidate_id, intent_kind, validity_outcome, "
        "       actual_broker_order_id, actual_quantity, actual_limit_price, "
        "       validated_place_intent_id, recorded_ts "
        "  FROM latch_order_intents WHERE intent_id = ?",
        (intent_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "intent_id": row[0], "candidate_id": row[1], "intent_kind": row[2],
        "validity_outcome": row[3], "actual_broker_order_id": row[4],
        "actual_quantity": row[5], "actual_limit_price": row[6],
        "validated_place_intent_id": row[7], "recorded_ts": row[8],
    }


# ---------------------------------------------------------------------------
# RUNG 8 -- COMPETITOR LIVENESS, AND THE POPULATION IS THREE-VALUED
#
# It ships in task 6a rather than task 4 because it must evaluate each
# competitor THROUGH ``mandate_alive_at``, which task 6 delivers (22A-R7-09).
#
# THE RULE: PROVEN-DEAD, PROVEN-LIVE, or UNPROVABLE, and only PROVEN-DEAD is
# DROPPED.  An earlier draft made the evaluation two-valued and EXCLUDED
# anything it could not resolve -- the exact inversion of this arc's posture
# everywhere else, under which an unprovable competitor reads as an absent one
# and the selected order is admitted while two live mandates may have existed.
#
# The refusal NAMES the competitor and WHY it could not be resolved, because a
# guard that says only "ambiguous" cannot be acted on.
# ---------------------------------------------------------------------------
def competitor_liveness_rung(
    conn,
    cfg,
    *,
    order: AcceptedLatchOrder,
    fill_session: date,
    exclude_trade_ids: frozenset[int],
) -> tuple[str | None, list[int]]:
    """``(reason_or_None, competitor_link_ids)`` -- rung 8.

    ``competitor_link_ids`` is the SCANNED population (every link on the ticker
    that survived the authority and consumption filters), not merely the live
    ones: it is the INPUT the rung judged, and the ``$.authorization`` entry
    records the input rather than the conclusion.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.data.repos.latch_order_mandate_links import list_links_for_ticker
    from swing.latches.classification import _order_key

    scanned: list[int] = []
    live: list[int] = []
    for link in list_links_for_ticker(conn, order.ticker):
        if int(link.link_id) == int(order.link_id):
            continue

        # AUTHORITATIVE?  A link whose validity row has been SUPERSEDED -- by a
        # later child of the same place -- is not a competitor: it records what
        # the broker said before the answer was replaced.
        try:
            intents = list_intents_for_latch(conn, candidate_id=link.candidate_id)
        except Exception as exc:  # noqa: BLE001 -- ignorance, not a crash
            # A LEDGER READ THAT FAILS IS IGNORANCE, NOT ABSENCE, and the
            # three-valued rule applies to the AUTHORITY filter exactly as it
            # applies to the liveness verdict: a competitor whose intents could
            # not be read must not be dropped as though it had none.  Letting
            # the exception escape would ALSO block the entry path over cohort
            # bookkeeping (`0036:26-38`).
            log.warning(
                "22-A: the intent ledger for competitor link %s could not be "
                "read (%s: %s); its authority is UNPROVABLE",
                link.link_id, type(exc).__name__, exc)
            scanned.append(int(link.link_id))
            return "competitor_liveness_unverifiable", scanned
        siblings = [
            i for i in intents
            if i.intent_kind == "validity"
            and i.validated_place_intent_id == link.place_intent_id
        ]
        if not siblings:
            # ZERO SIBLINGS IS INCOHERENCE, NOT ABSENCE (Codex 22A-R3-05).
            # This link EXISTS, and a link is minted BY a validity insert, so
            # a place with no validity children contradicts the link's own
            # provenance -- the ledger cannot say whether the linked row is
            # still the latest child because it cannot find the family at all.
            # `continue` read that as "not a competitor" and DROPPED it, which
            # is the two-valued inversion this rung exists to refuse: the
            # selected order is then admitted while a live mandate may have
            # stood beside it. Fail CLOSED, exactly as the unreadable-ledger
            # and un-re-readable-link branches above and below do.
            log.warning(
                "22-A: competitor link %s cites place %s, which has NO "
                "validity children; the link's own authority is UNPROVABLE",
                link.link_id, link.place_intent_id)
            scanned.append(int(link.link_id))
            return "competitor_liveness_unverifiable", scanned
        if max(siblings, key=_order_key).intent_id != link.validity_intent_id:
            continue

        # CONSUMED?  A mandate another trade has already taken is not competing
        # for this one.  Order-linked, exactly as rung 6 is -- AND READING THE
        # SAME STORED REPRESENTATION rung 6 does (PERSIST-CANONICAL).  This
        # scan asked the same question in a second spelling, and the class was
        # re-grepped rather than fixed as an instance: `swing/` now contains
        # ZERO SQL reads INTO a fill envelope (method: grep
        # `json_(extract|valid|each|type)\([^)]*schwab_source_value_json`
        # across swing/*.py and swing/**/*.sql -- the only surviving hits are
        # THIS comment and the AuthorizationClause `source` labels, both prose;
        # a test asserts the same property against migration 0037 directly).
        #
        # NO TRADE IS EXCLUDED HERE, deliberately: this asks whether ANY trade
        # consumed the COMPETITOR's order, and the subject consuming it would
        # equally retire it as a competitor.  `-1` is a sentinel that matches
        # no trade_id (trades.id is a positive rowid).
        from swing.data.repos.fill_envelope_identity import consuming_entry_fills
        if consuming_entry_fills(
                conn, link.broker_order_id, exclude_trade_id=-1):
            continue

        scanned.append(int(link.link_id))
        matches = [
            o for o in find_accepted_latch_order(
                conn, broker_order_id=link.broker_order_id)
            if o.link_id == link.link_id
        ]
        if not matches:
            # The link's validity row vanished from the JOIN -- ignorance, not
            # absence.  Fail CLOSED, exactly as the three-valued rule requires.
            log.warning(
                "22-A: competitor link %s could not be re-read; its liveness "
                "is UNPROVABLE", link.link_id)
            return "competitor_liveness_unverifiable", scanned
        verdict = mandate_alive_at(
            conn, cfg, order=matches[0], fill_session=fill_session,
            exclude_trade_ids=exclude_trade_ids)
        if verdict.admitted:
            live.append(int(link.link_id))
        elif verdict.decline_reason == "mandate_not_alive":
            # PROVEN DEAD IS THE ONLY STATE THAT IS DROPPED -- AND A
            # PRE-BARRIER LINK CANNOT PROVE IT (Codex 22A-R4-05, CHARC ruled
            # 2026-08-25).  `mandate_not_alive` rests on the frozen pivot and
            # stop this link carries, and a `pre_barrier_reconstructed` link's
            # pair was copied from a `candidates` row that was NOT immutable
            # when it was read.  AL-4 says no structural evidence exists for a
            # pre-barrier fire -- so treating one as PROOF of death, and
            # admitting the subject beside it, is a WRONG ACCEPTANCE.
            #
            # NARROW BY RULING: a freeze-tier read on the competitor, three
            # lines, fail-closed.  The reviewer's shared rung-2-to-9 classifier
            # was DECLINED -- rung 8 already recurses through the probe, and a
            # second recursive authority pass is a larger change than the hole.
            if matches[0].freeze_tier != FREEZE_TIER_LIVE_AT_ACCEPTANCE:
                log.warning(
                    "22-A: competitor link %s on %s reads DEAD at %s, but its "
                    "freeze tier is %r -- a pre-barrier link's frozen values "
                    "cannot prove death, so its state is UNPROVABLE",
                    link.link_id, order.ticker, fill_session,
                    matches[0].freeze_tier)
                return "competitor_liveness_unverifiable", scanned
            continue
        else:
            log.warning(
                "22-A: competitor link %s on %s is UNPROVABLE at %s (%s); the "
                "selected order is refused rather than admitted beside a "
                "mandate whose state could not be established",
                link.link_id, order.ticker, fill_session,
                verdict.decline_reason)
            return "competitor_liveness_unverifiable", scanned

    if live:
        log.warning(
            "22-A: %d live accepted order(s) compete on %s (links %s); the "
            "envelope cannot say which one this fill came from",
            len(live), order.ticker, live)
        return "ambiguous_ticker_orders", scanned
    return None, scanned


def authorize_accepted_order(
    conn,
    cfg,
    *,
    order: AcceptedLatchOrder,
    ticker: str,
    fill_session: date,
    price: float,
    shares: float,
    fill_origin: str,
    envelope_symbol: str | None,
    exclude_trade_ids: frozenset[int],
    trade_id: int | None = None,
    competitor_rung=None,
) -> LatchedProvenance:
    """Run the ladder over ONE recognised link, then probe the mandate.

    ``trade_id`` is the SUBJECT trade where one already exists (the correction
    path); on the entry path there is no row yet and ``None`` is correct -- the
    consumption rungs then scan every OTHER trade, which is all of them.

    ``competitor_rung`` is rung 8's seam.  It is a callable
    ``(conn, cfg, order, fill_session, exclude_trade_ids) -> (reason, ids)``;
    ``None`` means the rung does not run, which is exactly true at task 4 and
    is what keeps the two tasks' acceptance sets disjoint rather than
    overlapping (22A-R8-08: rung 8 was once claimed by two tasks and rungs 2
    and 3c by neither).
    """
    validity = _intent_row(conn, order.validity_intent_id)
    place = _intent_row(conn, order.place_intent_id)

    # RUNG 1 -- the link's ticker IS the request's.
    if order.ticker != ticker:
        return _refuse("ticker_mismatch", order)

    # RUNG 2 -- the place parent resolves to a `place` row on the SAME
    # candidate.  A raw link may name a row that is not a place at all, or one
    # belonging to a different mandate; rungs 1 and 3 both pass on either.
    if (place is None or place["intent_kind"] != "place"
            or place["candidate_id"] != order.candidate_id):
        return _refuse("link_parent_incoherent", order)

    # RUNG 3 -- the linked validity row's OWN outcome.  0033 forbids a
    # non-accepted validity row from carrying an actual_broker_order_id, so
    # against the SERVICE this is belt-and-braces with the schema; against a
    # RAW link it is not, and a raw link is reachable throughout this plan.
    if validity is None or validity["intent_kind"] != "validity":
        return _refuse("linked_validity_not_accepted", order)
    if validity["validity_outcome"] != "accepted_by_broker":
        return _refuse("linked_validity_not_accepted", order)

    # RUNG 3b -- and it is still the LATEST validity child of its place, by the
    # classifier's own total order (recorded_ts, intent_id) -- IMPORTED, never
    # re-spelled as max(intent_id), which is a DIFFERENT order whenever a
    # later-inserted row carries an earlier stamp.
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import _order_key

    # AND THE READ IS GUARDED, LIKE EVERY OTHER LEDGER READ ON THIS PATH
    # (Codex 22A-R3-14). The competitor loop and the probe both catch a failed
    # `list_intents_for_latch`; this one did not, so an unreadable ledger
    # ESCAPED and blocked a money-bearing entry over cohort bookkeeping
    # (`0036:26-38`) -- the asymmetry every other rung here honours. A failure
    # is IGNORANCE, so it refuses (fail-closed) and can never admit.
    try:
        intents_for_fire = list_intents_for_latch(
            conn, candidate_id=order.candidate_id)
    except Exception as exc:  # noqa: BLE001 -- ignorance, not a crash
        log.warning(
            "22-A: the intent ledger for fire %s (link %s) could not be read "
            "(%s: %s); whether the linked validity row is still the latest "
            "child is UNPROVABLE",
            order.candidate_id, order.link_id, type(exc).__name__, exc)
        return _refuse("validity_evidence_unavailable", order)
    children = [
        i for i in intents_for_fire
        if i.intent_kind == "validity"
        and i.validated_place_intent_id == order.place_intent_id
    ]
    latest = max(children, key=_order_key) if children else None
    if latest is None or latest.intent_id != order.validity_intent_id:
        return _refuse("validity_superseded", order)

    # RUNG 3c -- EVERY DUPLICATED LINK FIELD IS BOUND BACK TO ITS SOURCE.  The
    # link COPIES five fields that are already held authoritatively elsewhere,
    # and rungs 1-3b checked ticker, parent and outcome while never binding the
    # copies.  So a raw link could cite a GENUINE accepted validity row while
    # substituting a different broker order id or an inflated quantity, and the
    # submitted envelope would then match the forgery rather than the
    # acceptance.
    candidate = conn.execute(
        "SELECT c.ticker, c.evaluation_run_id, e.action_session_date "
        "  FROM candidates c JOIN evaluation_runs e "
        "    ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (order.candidate_id,),
    ).fetchone()
    if candidate is None:
        return _refuse("link_field_unbound", order)
    if order.broker_order_id != validity["actual_broker_order_id"]:
        return _refuse("link_field_unbound", order)
    if order.actual_quantity != validity["actual_quantity"]:
        return _refuse("link_field_unbound", order)
    if (order.ticker != candidate[0]
            or order.evaluation_run_id != candidate[1]
            or order.detection_date != str(candidate[2])):
        return _refuse("link_field_unbound", order)

    # RUNG 4 -- THE GOVERNING PLACE CYCLE AS OF THE FILL.  A later `place`
    # opens a new cycle and RETIRES the earlier order regardless of what the
    # earlier order's own validity children say.  The as-of bound is STRICTLY
    # BEFORE the fill session -- the same date-only clock policy the probe
    # applies, because the entry carries a DATE and inventing a third clock
    # domain to order an intent against a fill is what this arc declines to do.
    governing = conn.execute(
        "SELECT intent_id FROM latch_order_intents "
        " WHERE candidate_id = ? AND intent_kind = 'place' "
        "   AND date(recorded_ts) < ? "
        " ORDER BY recorded_ts DESC, intent_id DESC LIMIT 1",
        (order.candidate_id, fill_session.isoformat()),
    ).fetchone()
    if governing is None or int(governing[0]) != order.place_intent_id:
        log.warning(
            "22-A: link %s cites place %s but the governing place cycle as of "
            "%s is %s; the later place retired the earlier order",
            order.link_id, order.place_intent_id, fill_session,
            None if governing is None else governing[0])
        return _refuse("place_cycle_superseded", order)

    # RUNG 5 -- CANCELLATION HISTORY, AND A CANCEL NAMES ONE BROKER ORDER.
    # Before the fill kills; ON the fill is UNORDERABLE and refuses rather than
    # being counted either way; AFTER the fill is not consulted at all -- an
    # implementation refusing on any cancel fails case 29d.
    #
    # THE SCAN IS ORDER-SCOPED, NOT CANDIDATE-SCOPED (Codex 22A-R4-04).  The
    # model REQUIRES `actual_broker_order_id` on every cancel row -- *"there is
    # no by-ticker cancel path"*, `swing/data/models.py`, and 0033 CHECKs it --
    # so a candidate-wide scan makes the cancellation of an OLDER order on the
    # same fire refuse a NEWER accepted one.  A place cycle can legitimately be
    # placed, cancelled and re-placed; rung 4 already governs WHICH cycle is
    # authoritative, and rung 5 asking a different question about a different
    # order was the one clause too wide.
    #
    # BOTH HALVES MOVED TOGETHER: migration 0037's rung-5 twin carries the same
    # binding.  Diverging them would let the service admit a row the trigger
    # rejects -- a correction that authorizes and then aborts at the INSERT.
    cancel_before = conn.execute(
        "SELECT intent_id FROM latch_order_intents "
        " WHERE candidate_id = ? AND intent_kind = 'cancel' "
        "   AND actual_broker_order_id = ? "
        "   AND date(recorded_ts) < ? ORDER BY intent_id LIMIT 1",
        (order.candidate_id, order.broker_order_id, fill_session.isoformat()),
    ).fetchone()
    if cancel_before is not None:
        return _refuse("order_cancelled", order)
    cancel_same_day = conn.execute(
        "SELECT intent_id FROM latch_order_intents "
        " WHERE candidate_id = ? AND intent_kind = 'cancel' "
        "   AND actual_broker_order_id = ? "
        "   AND date(recorded_ts) = ? ORDER BY intent_id LIMIT 1",
        (order.candidate_id, order.broker_order_id, fill_session.isoformat()),
    ).fetchone()
    if cancel_same_day is not None:
        return _refuse("cancel_ordering_ambiguous", order)

    # RUNG 6 -- CONSUMPTION IS ORDER-LINKED, never COUNT(*) over the candidate.
    # The ordinary entry path assigns candidate_id from pipeline provenance
    # with no accepted order anywhere near it, so a count would let an
    # unrelated ordinary trade falsely block the real order-linked fill.
    #
    # THE SUBJECT IS EXCLUDED BY `trade_id`, NEVER BY `exclude_trade_ids`.
    # The two look interchangeable on the correction path (both name trade 25)
    # and they are NOT: `exclude_trade_ids` is the PROBE's parameter, a set a
    # caller may widen for its own reasons, and honouring it HERE could turn a
    # genuine second consumer into an ACCEPTANCE.  A wrong refusal costs a
    # message; a wrong acceptance contaminates H1.
    # THE SCAN READS ONE STORED READING PER DOCUMENT (PERSIST-CANONICAL,
    # CHARC + RD 2026-08-26; it REPLACES the both-domains union of 22A-R9-02).
    #
    # WHY THE UNION HAD TO GO, and it indicted its own author. The union's "SQL
    # arm" fetched SQLite's `json_extract` result INTO PYTHON and compared it
    # there -- so the arm written to PRESERVE SQL's TEXT affinity was SQL's
    # value judged by PYTHON's rules, and a NUMERIC order id read
    # `1002937461 == '1002937461'` -> False in both arms while the same
    # comparison IN SQL against a TEXT-affinity column is True (Codex
    # 22A-R10-03, reproduced by execution). Two readings of one document is
    # the class; one stored reading is the answer.
    #
    # THE PERSISTED POPULATION IS ESTABLISHED FIRST, and that is not an
    # optimisation. A scan over stored readings can only see documents the
    # authority has READ, so an unread population would be silently treated as
    # EMPTY -- the widest wrong acceptance available here. This call runs
    # inside the reservation, so the set it establishes cannot move under it.
    #
    # THE SUBJECT IS EXCLUDED BY `trade_id`, NEVER BY `exclude_trade_ids`
    # (unchanged): the latter is the PROBE's parameter, a set a caller may
    # widen for its own reasons, and honouring it here could turn a genuine
    # second consumer into an ACCEPTANCE.
    from swing.data.repos.fill_envelope_identity import (
        consuming_entry_fills,
        ensure_entry_fill_identities,
        unreadable_entry_fills,
    )
    ensure_entry_fill_identities(conn)
    subject = trade_id if trade_id is not None else -1
    others = consuming_entry_fills(
        conn, order.broker_order_id, exclude_trade_id=subject)
    if others:
        log.warning(
            "22-A: broker order %s is already consumed by trade(s) %s; one "
            "trade per mandate", order.broker_order_id, others)
        return _refuse("mandate_already_consumed", order)

    # AND A DOCUMENT THE AUTHORITY REFUSED IS IGNORANCE, NOT ABSENCE.
    # A refused envelope stores no order id, so a consumption hiding inside one
    # is invisible to the scan above. The ladder's three-valued rule says an
    # unprovable negative fails CLOSED -- the same shape rung 7 uses for
    # evidence the split handler destroyed, and the same reason. It also keeps
    # the SERVICE at least as strong as the citation trigger's twin, which
    # cannot compensate this way; a service weaker than its twin is the
    # authorize-then-abort shape this arc met four times.
    unreadable = unreadable_entry_fills(conn, exclude_trade_id=subject)
    if unreadable:
        log.warning(
            "22-A: entry fills %s carry an envelope the authority REFUSED to "
            "read, so the consumption scan cannot prove that broker order %s "
            "is unconsumed", unreadable, order.broker_order_id)
        return _refuse("consumption_evidence_unavailable", order)

    # RUNG 7 -- AND THE EVIDENCE FOR RUNG 6 IS DESTRUCTIBLE.  The supported
    # split-into-partials handler REBUILT replacement fills without
    # `fill_origin` or `schwab_source_value_json` (task 11a fixes it FORWARD),
    # so a consumption that began in the supposedly authoritative
    # representation can simply DISAPPEAR.  Rows already rebuilt are already
    # blind, which is why this rung survives the fix.
    scanned = conn.execute(
        "SELECT f.fill_id FROM fills f JOIN trades t ON t.id = f.trade_id "
        " WHERE f.action = 'entry' AND t.ticker = ? ORDER BY f.fill_id",
        (ticker,),
    ).fetchall()
    blinded = conn.execute(
        "SELECT f.fill_id FROM fills f JOIN trades t ON t.id = f.trade_id "
        " WHERE f.action = 'entry' AND t.ticker = ? "
        "   AND f.reconciliation_status = 'reconciled_discrepancy_resolved' "
        "   AND f.schwab_source_value_json IS NULL "
        "   AND t.id <> ? ORDER BY f.fill_id",
        (ticker, trade_id if trade_id is not None else -1),
    ).fetchall()
    if blinded:
        log.warning(
            "22-A: consumption evidence for %s may have been DESTROYED -- "
            "fills %s were rebuilt by the split handler with the envelope "
            "stripped, so the scan cannot prove non-consumption",
            ticker, [int(r[0]) for r in blinded])
        return _refuse("consumption_evidence_unavailable", order)

    # RUNG 8 -- COMPETITOR LIVENESS.  Task 6a owns it; the seam is a parameter.
    competitor_ids: list[int] = []
    if competitor_rung is not None:
        reason, competitor_ids = competitor_rung(
            conn, cfg, order=order, fill_session=fill_session,
            exclude_trade_ids=exclude_trade_ids)
        if reason is not None:
            return _refuse(reason, order)

    # RUNG 9 -- RD'S REFUSE-BY-DEFAULT, and CHARC's read-time existence check.
    #
    # THE BARRIER CHECK COMES FIRST and refuses for EVERY candidate, pre- or
    # post-barrier: "single-state" means armed and VERIFIABLY ARMED WITH THE
    # ACTUAL BARRIER, NOW.  Dropping the triggers mechanically halts structural
    # admission, which is what converts CHARC's CONDITION 3 from something a
    # person must remember into a consequence nobody can avoid.
    from swing.data.repos.candidates_immutability_epoch import (
        freeze_tier_for_candidate,
    )

    read_time_tier, installed = freeze_tier_for_candidate(
        conn, order.candidate_id)
    if not installed:
        log.warning(
            "22-A: the candidates barrier is ABSENT OR ALTERED at read time; "
            "structural admission is refused for link %s regardless of its "
            "stored tier", order.link_id)
        return _refuse("barrier_not_installed", order,
                       freeze_tier=order.freeze_tier)
    # THE STORED TIER IS AN ATTESTATION; THE READ-TIME TIER IS A VERDICT, and
    # BOTH must say live_at_acceptance.  Requiring both can only ever refuse
    # MORE -- the minting CASE and freeze_tier_for_candidate are the same rule
    # in two spellings, so they agree for every truthfully-minted row -- and it
    # closes the one shape a stored-tier-only rung would admit: a RAW link
    # whose freeze_tier column was written by hand.
    if (order.freeze_tier != FREEZE_TIER_LIVE_AT_ACCEPTANCE
            or read_time_tier != FREEZE_TIER_LIVE_AT_ACCEPTANCE):
        return _refuse("pre_barrier_unproven", order,
                       freeze_tier=order.freeze_tier)

    # THE FIVE ENVELOPE GUARDS.  Demoted deliberately to REFUSAL GUARDS rather
    # than identity evidence (plan S2.4.1): fill_origin is computed server-side
    # but FROM the same hidden inputs, so no rung here is independent evidence.
    shape = assert_fill_consistent_with_order(
        order, ticker=ticker, price=price, shares=shares,
        fill_origin=fill_origin, envelope_symbol=envelope_symbol)
    if shape is not None:
        return _refuse(shape, order, freeze_tier=order.freeze_tier)

    verdict = mandate_alive_at(
        conn, cfg, order=order, fill_session=fill_session,
        exclude_trade_ids=exclude_trade_ids)
    if not verdict.admitted:
        return verdict

    evidence = dict(verdict.probe_evidence or {})
    evidence["authorization"] = _authorization_block({
        "rung1_link_ticker": order.ticker,
        "rung2_link_parent": order.place_intent_id,
        "rung3_validity_outcome": validity["validity_outcome"],
        "rung3b_latest_validity_child": order.validity_intent_id,
        "rung3c_link_broker_order_id": order.broker_order_id,
        "rung4_governing_place_intent": order.place_intent_id,
        "rung5_cancel_intent_id": None,
        "rung6_consuming_trade_id": None,
        "rung7_consumption_scan_fill_ids": [int(r[0]) for r in scanned],
        "rung8_competitor_link_ids": [int(i) for i in competitor_ids],
        "rung9_stored_freeze_tier": order.freeze_tier,
        "guard_fill_origin": fill_origin,
        "guard_envelope_symbol": envelope_symbol,
        "guard_quantity": shares,
        "guard_framework_price_bound": price,
        "guard_broker_limit_bound": order.actual_limit_price,
    })
    return LatchedProvenance(
        admitted=True,
        recognised_but_underivable=False,
        decline_reason=None,
        order=order,
        clear_reason=verdict.clear_reason,
        clear_session=verdict.clear_session,
        horizon_session=verdict.horizon_session,
        bars_through=verdict.bars_through,
        window_empty=verdict.window_empty,
        archive_status=verdict.archive_status,
        probe_evidence=evidence,
        freeze_tier=order.freeze_tier,
    )


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
    conn, *, derivation, ticker: str, fill_session: date,
) -> tuple[str | None, list[list]]:
    """``(reason_or_None, consulted)`` -- the ordering verdict AND its INPUT.

    THE CONSULTED LIST IS RETURNED, NOT DISCARDED (Codex R2-04). The guard is
    refusal-capable, so the evidence blob records the input it judged and the
    verdict it reached, or "passed" and "never ran" are indistinguishable at
    audit. Each element is ``[intent_id, recorded_ts]`` for one ADMISSIBLE
    decision -- the rows the as-of rule actually ordered, not every row on the
    ticker.

    ``reason`` is ``None``, or the reason the decision ledger cannot be ordered
    against the fill.

    THE SCAN COVERS EVERY LATCH ON THE TICKER, NOT ONLY THE SELECTED ONE
    (Codex R1, and the scope is what makes the guard reachable at all). The
    fold consumes decisions WITHOUT any `recorded_ts` bound, so an intent that
    post-dates the fill can CHANGE THE TOPOLOGY -- a post-fill decline on fire A
    closes A, and a later same-pivot fire B that would have folded in as A's
    re-confirmation instead opens its OWN latch. Scanning only the selected
    latch's family then never sees the offending decline, because the decline
    lives on the latch it created. Scanning every same-ticker latch does.

    **DETECT-AND-REFUSE IS RATIFIED, AND EXT-1 STAYS AT THREE (CHARC,
    2026-08-25).** This DETECTS the hazard and refuses; it cannot make the
    derivation itself as-of-correct, because that needs the fold to filter
    decisions by `recorded_ts` -- a FOURTH EXT-1 parameter, and EXT-1 is
    approved as exactly THREE. **The ground is the governing asymmetry: a wrong
    REFUSAL costs a legible message, and a wrong ACCEPTANCE contaminates H1.**
    A detected-not-derived as-of world is an HONEST LIMITATION, not a defect --
    and the fourth parameter is not this arc's to take. If 22-A2's proof
    machinery needs the derivation itself, that is 22-A2's envelope question.
    Recorded in the accepted-limitations list so a review measuring against a
    contract that omits it does not re-find it every round.

    THE WINDOW IS THE LADDER'S OWN, IMPORTED. `decision_bounds_for` +
    `admissible_decisions` are the single-sourced filter `_resolve_decline`
    uses, so this helper cannot decide a decision is "about" a latch on
    different terms from the fold that judged it. A hand-written window here
    would refuse on decisions the fold correctly ignores -- naming an
    UNVERIFIABLE where the truth is a PROVEN-DEAD mandate, which matters
    downstream because rung 8 drops proven-dead competitors and blocks on
    unverifiable ones.

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

    THIS IS A SECOND READ OF THE LEDGER, AND MY FIRST JUSTIFICATION FOR IT WAS
    FALSE (Codex R2-03). I wrote that `trg_loi_no_update` / `trg_loi_no_delete`
    make the rows unchangeable between the derivation's read and this one. They
    forbid UPDATE and DELETE; they do NOT forbid an INSERT, and two bare SELECTs
    outside one transaction can therefore see different ledger worlds.

    WHAT ACTUALLY MAKES IT SOUND IS THE CALLER'S TRANSACTION, and it is stated
    as a PRECONDITION rather than assumed: on the production entry path
    `record_entry` opens `BEGIN IMMEDIATE` before resolving, so the derivation
    and this guard run inside ONE snapshot.

    **THE SPLIT-WORLD READ IS AN OBLIGATION ON THE CORRECTION PATH, NOT A
    FOOTNOTE (CHARC, 2026-08-25).** The two ledger reads are one world ONLY
    because the caller holds `BEGIN IMMEDIATE`. **Outside that lock -- the
    CORRECTION path -- a split-world read is possible**, and the correction
    path must ANSWER it rather than inherit it. It is answered where the
    correction path owns its transaction (`correct_cohort_provenance`'s
    `BEGIN IMMEDIATE`), which is the SAME precondition stated once and honoured
    by both callers. **It is NOT answered by owning a transaction inside this
    function**: that violates the project's single-transaction contract (the
    caller MUST own it; auto-detecting an outer tx re-introduces the very race
    the explicit lock closed).

    (Coverage is still computed from `derivation.archive_closes` and never
    re-read: the parquet has no equivalent of the caller's lock at all.)

    A read failure here refuses `decision_evidence_unavailable` -- the same
    reason the strict loader raises -- because the two are the same ignorance.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import (
        admissible_decisions,
        decision_bounds_for,
    )

    post_dates: list[int] = []
    unorderable: list[int] = []
    consulted: list[list] = []
    for latch in derivation.latches:
        if latch.identity.ticker != ticker:
            continue
        intents: list = []
        for candidate_id in sorted(latch.candidate_set):
            try:
                intents.extend(
                    list_intents_for_latch(conn, candidate_id=candidate_id))
            except Exception as exc:  # noqa: BLE001 -- ignorance, not a crash
                log.warning(
                    "22-A: decision-ledger read failed at candidate %s; the "
                    "probe cannot tell an absent decline from an unread one: "
                    "%s", candidate_id, exc)
                return "decision_evidence_unavailable", consulted
        lower, upper, decline_upper = decision_bounds_for(
            latch, fill_bound=fill_session)
        for intent in admissible_decisions(
            intents, candidate_set=latch.candidate_set,
            lower=lower, upper=upper, decline_upper=decline_upper,
        ):
            consulted.append([intent.intent_id or 0, str(intent.recorded_ts)])
            recorded = _as_date(intent.recorded_ts)
            if recorded is None or recorded == fill_session:
                # An UNPARSEABLE stamp is as unorderable as a same-day one.
                unorderable.append(intent.intent_id or 0)
            elif recorded > fill_session:
                post_dates.append(intent.intent_id or 0)
    consulted.sort()
    if post_dates:
        # Named FIRST because it is the DEFINITE fact -- the evidence provably
        # post-dates the fill -- while a same-day stamp is only an ambiguity.
        log.warning(
            "22-A: decision intents %s were recorded AFTER the fill session %s; "
            "the probe refuses rather than judging a mandate on evidence that "
            "had not happened when it filled", post_dates, fill_session)
        return "decision_evidence_post_dates_fill", consulted
    if unorderable:
        return "decision_ordering_ambiguous", consulted
    return None, consulted


def _fill_wins(latch, fill_session: date) -> tuple[bool | None, str | None]:
    """``(alive, admission_basis)`` -- the LADDER's comparison, not a local one.

    TRI-VALUED: ``True`` alive, ``False`` PROVEN dead, ``None`` UNPROVABLE.

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
        # AN UNDATED TERMINAL IS UNPROVABLE, NOT PROVEN-DEAD (Codex R2-02).
        # `Latch.__post_init__` requires a terminal REASON but never a
        # corresponding SESSION, so the shape is representable; the shipped fold
        # does not emit it today, which is exactly why treating it as dead would
        # be an invisible error. It cannot show the mandate died BEFORE the fill,
        # so the honest answer is ignorance -- and the difference is
        # load-bearing downstream, where rung 8 DROPS proven-dead competitors
        # and BLOCKS on unprovable ones.
        return None, None
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


def _probe_guard_block(inputs: dict) -> dict:
    """``{key: {"input": ..., "verdict": "pass"}}`` over the WHOLE roster.

    Built by walking ``PROBE_GUARD_CLAUSES`` rather than by writing a literal,
    so a clause added to the roster without a value here raises at emit. The
    verdict is ``'pass'`` unconditionally and that is not a shortcut: every
    guard REFUSES before reaching this point, so a blob that exists at all is
    one where each of them passed. The migration asserts the same thing from
    the other side.
    """
    missing = sorted(set(PROBE_GUARD_KEYS) - set(inputs))
    extra = sorted(set(inputs) - set(PROBE_GUARD_KEYS))
    if missing or extra:
        raise KeyError(
            f"probe-guard block does not match PROBE_GUARD_CLAUSES: "
            f"missing {missing}, extra {extra}")
    return {key: {"input": inputs[key], "verdict": "pass"}
            for key in PROBE_GUARD_KEYS}


def _snapshot_agrees(order: AcceptedLatchOrder, latch) -> tuple[bool, bool]:
    """``(invalidation_equal, pivot_equal)`` at ``PRICE_DP``.

    THE ARC'S SINGLE ROUNDING AUTHORITY. It happens HERE, in Python, at
    `PRICE_DP`, ONCE. The citation trigger does NOT repeat it: it binds the RAW
    operands to their sources by identity and records this comparison's VERDICT
    as a datum. A SQL-side re-comparison is forbidden in both available forms --
    raw equality refuses truthful sub-cent drift, and SQLite's `round()` is a
    DIFFERENT rounding rule from Python's (half-away-from-zero vs half-to-even),
    measured to diverge on 24 live `candidates` rows.

    The comparison is the link's frozen value against the LATCH's, per RD
    constraint 1: the mandate is frozen at its OPENING fire, so that is the
    number the mandate actually declared. Where an order was placed against a
    re-confirmation whose stop had drifted from the opening fire's, the two
    differ and admission refuses -- the correct, fail-closed answer.
    """
    return (
        round(float(order.frozen_invalidation), PRICE_DP)
        == round(float(latch.latched_initial_stop), PRICE_DP),
        round(float(order.frozen_pivot), PRICE_DP)
        == round(float(latch.latched_pivot), PRICE_DP),
    )


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
    except Exception as exc:  # noqa: BLE001 -- see below; this is DELIBERATE
        # THE ENTRY PATH MUST NEVER BE BLOCKED BY COHORT BOOKKEEPING
        # (`0036:26-38`), and the derivation folds EVERY ticker, so one
        # unrelated corrupt fire can abort a probe about a perfectly good order.
        # MEASURED, not hypothesised: a `bucket='aplus'` candidate whose run is
        # dated on a SATURDAY parses fine (`_validate_fire` checks ISO parsing
        # and price sanity, never the exchange calendar), and the fold's
        # `session_offset(anchor, horizon_sessions)` then raises
        # `exchange_calendars.errors.NotSessionError` -- taking down the probe
        # for a DIFFERENT ticker's order.
        #
        # The catch is BROAD on purpose: enumerating the raisable types is the
        # hand-maintained-roster failure, and every branch here is fail-CLOSED
        # (`aliveness_unverifiable` never admits). The WARNING carries the
        # exception type so a real bug is loud rather than absorbed.
        log.warning(
            "22-A: the latch derivation RAISED for the %s probe at %s (%s: %s); "
            "aliveness is unverifiable, so the entry records with honest-unset "
            "cohort keys rather than being blocked",
            order.ticker, fill_session, type(exc).__name__, exc)
        return _probe_refusal(
            "aliveness_unverifiable", order=order,
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

    ordering, consulted_decisions = _decision_ordering_refusal(
        conn, derivation=derivation, ticker=order.ticker,
        fill_session=fill_session)
    if ordering is not None:
        # BEFORE the verdict is trusted: the as-of rule is about whether the
        # INPUT was admissible, not about what the ladder concluded from it.
        return _probe_refusal(ordering, order=order, **common)

    # THE SNAPSHOT CROSS-CHECK RUNS BEFORE THE TERMINAL IS TRUSTED (Codex
    # R2-01, and the ordering is the whole finding). The probe judges the LIVE
    # candidate row, so a MUTATED stop does not merely fail a later comparison
    # -- it MANUFACTURES a terminal. Frozen stop 14.88, live stop 17.20 and a
    # 17.10 close yields `clear_reason='invalidation'` for a mandate whose OWN
    # frozen value was never breached. Returning `mandate_not_alive` there
    # stamps a live mandate PROVEN DEAD off a number it never declared, and
    # rung 8 drops proven-dead competitors. The drift verdict must therefore be
    # reached BEFORE any terminal is believed.
    invalidation_equal, pivot_equal = _snapshot_agrees(order, latch)
    if not (invalidation_equal and pivot_equal):
        log.warning(
            "22-A: frozen-value DRIFT for %s (link %s): frozen "
            "(pivot=%r, invalidation=%r) vs latched (pivot=%r, invalidation=%r)"
            "; the probe's terminal was derived from the LIVE values and is not "
            "evidence about this mandate",
            order.ticker, order.link_id, order.frozen_pivot,
            order.frozen_invalidation, latch.latched_pivot,
            latch.latched_initial_stop)
        return _probe_refusal("frozen_value_drift", order=order, **common)

    alive, basis = _fill_wins(latch, fill_session)
    if alive is None:
        log.warning(
            "22-A: the %s probe returned terminal %r with NO clear_session at "
            "%s; an undated terminal cannot show the mandate died before the "
            "fill", order.ticker, latch.clear_reason, fill_session)
        return _probe_refusal(
            "aliveness_unverifiable", order=order,
            clear_reason=latch.clear_reason, **common)
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
        # THE PROBE'S OWN REFUSAL-CAPABLE CLAUSES, each with the input it judged
        # and the verdict it reached (Codex R2-04). Built from the roster so a
        # clause added to `PROBE_GUARD_CLAUSES` without a value here raises
        # KeyError at emit rather than shipping a silently-absent guard.
        "probe_guards": _probe_guard_block({
            "fill_session_is_session": fill_session.isoformat(),
            "fire_membership": len(containing),
            "decision_ordering": consulted_decisions,
        }),
    }
    assert set(evidence) == set(PROBE_EMITTED_EVIDENCE_KEYS), (
        "the emitted evidence and PROBE_EVIDENCE_KEYS disagree: "
        f"{sorted(set(evidence) ^ set(PROBE_EMITTED_EVIDENCE_KEYS))}"
    )
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


# ---------------------------------------------------------------------------
# THE RESOLVER -- ONE ENTRY POINT, THREE OUTCOMES
#
# `record_entry` (task 9) and the correction path (task 11) both call THIS, so
# the ladder cannot be honoured at one call site and forgotten at another.
#
# THE THREE OUTCOMES ARE NEVER TWO (plan S2.2):
#   admitted                     -> write the three fire-derived keys
#   recognised_but_underivable   -> a link WAS recognised and admission then
#                                   failed for ANY reason: write the HONEST
#                                   UNSET row and SUPPRESS the ordinary
#                                   candidate/origin chain
#   neither flag                 -> the ORDINARY path, byte-identical to main
#
# WHY SUPPRESSION RATHER THAN FALLBACK (S2.6.4).  For a ticker that is `aplus`
# in today's LATEST run the ordinary chain would write `pipeline_aplus` plus
# TODAY's candidate -- a DIFFERENT candidate from the mandate we know this fill
# came from.  Silent-wrong, not honest-NULL, and exactly what RD's trade-25
# standard forbids.
# ---------------------------------------------------------------------------
def resolve_latched_provenance(
    conn,
    cfg,
    req,
    *,
    trade_id: int | None = None,
    exclude_trade_ids: frozenset[int] | None = None,
) -> LatchedProvenance:
    """The whole ladder for ONE entry request.

    THE FILL SESSION IS `req.entry_date` AND NOTHING ELSE (S2.4.2, case 5c).
    It is the CORRECTED date the operator submitted -- not `trades.entry_date`,
    which on the correction path is the value being corrected, and not the wall
    clock. An implementation reading a different date probes a DIFFERENT WORLD
    and can admit a mandate that was dead when the fill actually happened.

    `exclude_trade_ids` defaults to `None` and is then derived from `trade_id`.
    On the ENTRY path there is no row yet, so the set is empty; on the
    CORRECTION path the subject must be excluded or `_match_fill`'s windowed
    rung returns `clear_reason='fill'` for the very mandate it is being asked
    about (verified against the live DB).
    """
    envelope = getattr(req, "schwab_source_value_json", None)
    # THE INCONSISTENT EVIDENCE PAIR (RD, ruled on 22A-R3-13). See
    # `origin_and_envelope_are_inconsistent` for why this is the pair and never
    # the origin. The ENTRY proceeds; the keys land honest-unset; the warning
    # NAMES the inconsistency, so the operator adjudicates a legible anomaly
    # instead of inheriting a silent wrong label.
    #
    # EVERY NON-TRUSTED PATH IS UNTOUCHED, which is what bounds this: the
    # predicate returns False for `operator_typed`, so an ordinary hand-typed
    # entry with no envelope still returns `no_envelope`, unrecognised, and
    # runs the ordinary chain byte-for-byte.
    if origin_and_envelope_are_inconsistent(
            getattr(req, "fill_origin", "operator_typed"), envelope):
        log.warning(
            "22-A: fill for %s claims origin %r, which carries a Schwab "
            "envelope BY CONSTRUCTION, and its envelope is ABSENT (%r); no "
            "production writer produces that pair, so the envelope was "
            "stripped, tampered with or corrupted. The entry records with "
            "honest-unset cohort keys rather than with the latest run's "
            "candidate -- attributing it from a timing coincidence would be "
            "exactly the misattribution this surface exists to prevent. "
            "WARRANTS INVESTIGATION",
            req.ticker, getattr(req, "fill_origin", None), envelope)
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="origin_envelope_inconsistent")
    if envelope is None:
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_envelope")

    # CANONICALITY IS ASKED OF THE ENVELOPE, BEFORE ANYTHING IS READ OUT OF IT
    # (self-sweep SS-1, a residual of 22A-R8-01 and 22A-R9-01).
    #
    # R9-01 moved this question above the link LOOKUP and left it below the
    # order-id READ. That is where a disagreeing envelope DISAPPEARS: an
    # envelope whose LAST duplicate key is null, numeric or blank gives the
    # Python reader None, and `no_order_id` is NOT recognised -- so the
    # ordinary chain wrote TODAY's candidate while `json_extract`, which keeps
    # the FIRST key, binds a real accepted mandate. MEASURED on three shapes.
    #
    # The guard's own subject is the DOCUMENT, not the identity it happens to
    # yield, so it runs first and it runs unconditionally.
    if not envelope_is_canonical(envelope):
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="envelope_not_canonical")

    broker_order_id = broker_order_id_from_envelope(envelope)
    if broker_order_id is None:
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_order_id")

    fill_session = _as_date(req.entry_date)
    if fill_session is None:
        # An order id WAS supplied, so this is a RECOGNISED request that cannot
        # be resolved -- it must not fall through to the ordinary chain as
        # though no order had been named.
        log.warning(
            "22-A: entry_date %r is not an ISO date; the latch probe cannot "
            "run and the entry records with honest-unset cohort keys",
            req.entry_date)
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="fill_session_not_a_session")

    # THE CONFIG GATE MOVED BELOW THE LINK LOOKUP (Codex 22A-R7-01), and the
    # move is what stops `cfg=None` being a FAIL-OPEN SWITCH.
    #
    # `cfg` is needed to DERIVE the fold, not to RECOGNISE the order -- the
    # envelope read and the link lookup need no configuration at all. Checked
    # FIRST, a caller who simply omitted the config sent an order-bearing fill
    # down the ORDINARY chain, which writes TODAY's candidate for a fill that
    # demonstrably came from an accepted order: the silent misattribution this
    # arc exists to prevent, reachable by leaving one keyword off.
    #
    # "Both production callers pass cfg" is a SERVICE-prevention argument, and
    # the reviewer's answer to it is right: the manifest test that pins those
    # two callers matches a syntactic NAME, so an alias, a wrapper or a future
    # consumer bypasses it while the asserted count stays two. A grep bounds a
    # family from below, and so does an AST walk keyed on a name.
    #
    # So the ladder now RECOGNISES first. No link -> `no_config` is still NOT
    # recognised and the ordinary path is intact, byte-for-byte, which is what
    # the LOCK is about. A link that EXISTS with no config is RECOGNISED and
    # refused, so the row lands honest-unset instead of wrong.
    # THE LOOKUP IS INSIDE THE CONTAINMENT (Codex 22A-R9-04, a residual of my
    # own 22A-R8-03 fix). The broad handler began at `authorize_accepted_order`
    # and `find_accepted_latch_order` ran BEFORE it -- so a SQLite read error
    # or a row-hydration failure escaped `resolve_latched_provenance` entirely
    # and `record_entry` rolled the trade and the fill back. The containment
    # test substituted `authorize_accepted_order` and therefore could not see
    # the hole: a boundary asserted at ONE call site is not a boundary.
    #
    # Fail-CLOSED and RECOGNISED: the request carries a usable order id, so a
    # lookup we could not perform is IGNORANCE about a real order, never
    # licence to write TODAY's candidate.
    try:
        orders = find_accepted_latch_order(
            conn, broker_order_id=broker_order_id)
    except Exception:  # noqa: BLE001 -- ignorance, not a crash
        log.exception(
            "22-A: the link lookup for broker order %s RAISED; the entry "
            "records with honest-unset cohort keys rather than being blocked, "
            "and this WARRANTS INVESTIGATION", broker_order_id)
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="aliveness_unverifiable")
    if orders and cfg is None:
        log.warning(
            "22-A: broker order %s names %d accepted latch link(s) but NO "
            "config was supplied, so the mandate cannot be derived; the entry "
            "records with honest-unset cohort keys rather than with TODAY's "
            "candidate", broker_order_id, len(orders))
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="no_config", order=orders[0])
    if cfg is None:
        # A DISTINCT REASON, NOT A SHARED ONE (case 18). "No config" and "no
        # order id" are different ignorances, and an operator reading the log
        # needs to know which one happened. NOT recognised: no link names this
        # order, so the ordinary chain runs exactly as it does on `main`.
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_config")
    if not orders:
        # NOT recognised: no link names this order, so the ordinary chain runs
        # exactly as it does on `main`. This is the ONLY refusal after an order
        # id was found that leaves the ordinary path intact.
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_accepted_latch_order")
    if len(orders) > 1:
        log.warning(
            "22-A: broker order %s names %d links (%s); cardinality is the "
            "READER's count and two is not one",
            broker_order_id, len(orders), [o.link_id for o in orders])
        return LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="ambiguous_accepted_orders")

    order = orders[0]
    if exclude_trade_ids is not None:
        excluded = frozenset(exclude_trade_ids)
    elif trade_id is not None:
        excluded = frozenset({trade_id})
    else:
        excluded = frozenset()
    # THE INVARIANT FAILURES ARE CONTAINED HERE (Codex 22A-R7-02).
    # `LatchProbeInvariantError` is raised DELIBERATELY at two points inside
    # the probe -- a `criteria_lapsed` terminal the rung was FORCED OFF, and a
    # terminal dated LATER than the fill -- and both sit AFTER the broad
    # fail-soft handler around `build_latch_derivation`. Nothing between here
    # and `record_entry` catches a `RuntimeError`, so the transaction rolled
    # back and NO TRADE AND NO FILL LANDED.
    #
    # The code's own message for those states is that the COHORT PROBE
    # MALFUNCTIONED. Turning a probe malfunction into a blocked broker fill is
    # the `0036:26-38` inversion in its purest form -- and the arc has now met
    # it four times, which is why the containment is placed at the RESOLVER's
    # boundary rather than at each raise site: a fifth invariant added later is
    # contained by construction.
    #
    # THE RAISES ARE NOT REMOVED and their tests are unchanged: they are how a
    # probe defect becomes LOUD at the probe grain. What changes is that the
    # ENTRY does not pay for it. Fail-CLOSED -- `aliveness_unverifiable` can
    # never admit -- and the log carries the exception type and a traceback so
    # a real defect is investigated rather than absorbed.
    try:
        verdict = authorize_accepted_order(
            conn, cfg,
            order=order,
            ticker=req.ticker,
            fill_session=fill_session,
            price=float(req.entry_price),
            shares=float(req.shares),
            fill_origin=getattr(req, "fill_origin", "operator_typed"),
            envelope_symbol=instrument_symbol_from_envelope(envelope),
            exclude_trade_ids=excluded,
            trade_id=trade_id,
            competitor_rung=competitor_liveness_rung,
        )
    except Exception:  # noqa: BLE001 -- see below; this is DELIBERATE
        # BROAD ON PURPOSE, AND THE BREADTH IS THE POINT (Codex 22A-R8-03,
        # generalizing 22A-R7-02). It was `except LatchProbeInvariantError`,
        # and the VERY NEXT ROUND found a different escape: a `+inf` frozen
        # pivot passes the schema's positivity CHECK, reaches
        # `zone_cap_for_pivot`, and raises `ValueError` -- not a
        # LatchProbeInvariantError, so it rolled the money-bearing trade back.
        # Enumerating the raisable types is the hand-maintained-roster failure
        # this project keeps paying for. Every branch here is fail-CLOSED
        # (`aliveness_unverifiable` can never admit) and the log carries a
        # traceback, so a real defect is LOUD rather than absorbed.
        log.exception(
            "22-A: the latch authorization RAISED for %s (order %s, link %s) "
            "at %s; the entry records with honest-unset cohort keys rather "
            "than being blocked, and this WARRANTS INVESTIGATION -- cohort "
            "bookkeeping must never cost a money-bearing entry, and it must "
            "also never fail silently",
            req.ticker, order.broker_order_id, order.link_id, fill_session)
        return _refuse("aliveness_unverifiable", order,
                       horizon_session=fill_session,
                       freeze_tier=order.freeze_tier)
    if not verdict.admitted:
        return verdict

    # THE KEYS COME FROM THE ONE DERIVATION, shared with Demand C (S2.6.1).
    # A refusal here is `keys_not_derivable` and takes the honest-unset path
    # like every other recognised-but-refused outcome -- the three keys move
    # TOGETHER or not at all (S2.6).
    try:
        keys = _cohort_keys_for_fire(conn, order)
    except Exception as exc:  # noqa: BLE001 -- any refusal here is ignorance
        log.warning(
            "22-A: the cohort keys for fire %s (%s, link %s) could not be "
            "derived (%s: %s); the entry records with honest-unset keys rather "
            "than with TODAY's candidate, which would be a different mandate",
            order.candidate_id, order.ticker, order.link_id,
            type(exc).__name__, exc)
        return _refuse(
            "keys_not_derivable", order,
            clear_reason=verdict.clear_reason,
            clear_session=verdict.clear_session,
            horizon_session=verdict.horizon_session,
            bars_through=verdict.bars_through,
            window_empty=verdict.window_empty,
            archive_status=verdict.archive_status,
            probe_evidence=verdict.probe_evidence,
            freeze_tier=order.freeze_tier)

    submitted = getattr(req, "hypothesis_label", None)
    if submitted is not None and submitted != keys.hypothesis_label:
        # THE DERIVED LABEL WINS, AND THE SUBSTITUTION IS LOUD (S2.6.3).
        # Refusing the entry instead would invert the priority `0036:26-38`
        # establishes: cohort bookkeeping must not block a money-bearing
        # operation.
        log.warning(
            "22-A: the operator's submitted hypothesis_label %r is REPLACED by "
            "the framework's derived label %r for %s (trade %s, order %s); the "
            "entry is not refused over a label",
            submitted, keys.hypothesis_label, req.ticker, trade_id,
            order.broker_order_id)

    from dataclasses import replace
    return replace(
        verdict,
        trade_origin=keys.trade_origin,
        candidate_id=keys.candidate_id,
        hypothesis_label=keys.hypothesis_label,
    )


def _cohort_keys_for_fire(conn, order: AcceptedLatchOrder):
    """The fire's three cohort keys, through Demand C's OWN derivation.

    NO SECOND SPELLING (#11, plan S2.6.1).  The alternative -- a local matcher
    call here -- is the comparator-vs-emitter divergence 21-A and 21-B each
    paid for: two derivations that agree on the day they are written and drift
    apart on the day one of them is upgraded.

    NO ``gate``: the latch path has no fill-vs-record ordering question,
    because its authority is an append-only row the broker's acceptance created
    rather than a ranking over the framework's bucket series.

    ``fetch_candidate_by_id`` is used rather than a bare row read because it
    HYDRATES the criteria, and the hypothesis label is built from the non-pass
    criterion set -- an unhydrated row would silently produce a different
    label, which is that repo function's own documented reason for existing.
    """
    from swing.data.repos.candidates import fetch_candidate_by_id
    from swing.trades.cohort_provenance_correction import (
        _require_naive_datetime,
        derive_cohort_keys_for_fire,
    )

    cited = fetch_candidate_by_id(conn, order.candidate_id)
    if cited is None:
        raise ValueError(f"candidate {order.candidate_id} is absent")
    run_ts = conn.execute(
        "SELECT run_ts FROM evaluation_runs WHERE id = ?",
        (order.evaluation_run_id,),
    ).fetchone()
    if run_ts is None:
        raise ValueError(f"evaluation run {order.evaluation_run_id} is absent")
    return derive_cohort_keys_for_fire(
        conn,
        candidate=cited.candidate,
        candidate_id=order.candidate_id,
        evaluation_run_id=order.evaluation_run_id,
        run_ts_parsed=_require_naive_datetime(
            run_ts[0],
            what=f"evaluation run {order.evaluation_run_id}'s run_ts"),
        gate=None,
    )
