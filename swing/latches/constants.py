"""Locked latch-derivation constants (Phase 21 Arc A).

Single source of truth for every value the latch derivation and the
21-A/21-B schema CHECKs mirror (the #11 one-commit multi-mirror discipline).

This module imports NOTHING from `swing` -- it is the domain owner of the
latch state vocabulary, so `swing/data/models.py` can import the frozensets
from here without a cycle.
"""
from __future__ import annotations

from dataclasses import dataclass as _dataclass
from datetime import date as _date
from decimal import ROUND_FLOOR as _ROUND_FLOOR
from decimal import Context as _Context
from decimal import Decimal as _Decimal
from math import isfinite as _isfinite

# Enough precision that `mandate_limit_price` is TOTAL over finite floats --
# `sys.float_info.max` needs 309 integer digits plus the 2 fractional ones, and
# the default 28-digit context raised `InvalidOperation` instead of answering.
# See `mandate_limit_price`'s docstring for why this is the right fix.
_QUANTIZE_CONTEXT = _Context(prec=400)


# RD constraint 2, RULED at the plan-stage gate: the horizon is DERIVED from
# the shadow engine's ENTRY window, never hard-coded. See plan section A.4.
def latch_horizon_sessions(cfg) -> int:
    """The latch entry-mandate horizon in NYSE sessions.

    Bound at the SOURCE so a future change to the observe window cannot
    silently break live-vs-shadow parity. The shadow's entry search runs over
    the temporal log's forward bars, which are bounded by
    observe_max_pending_window_sessions (30). At a shorter latch horizon,
    sessions beyond it become a window where the shadow can enter and live has
    no mandate -- a MANUFACTURED divergence, the FTRE-class defect this arc
    exists to eliminate.

    NOT research/harness/shadow_expectancy/constants.py HORIZON_SESSIONS
    (126) -- that is the TRADE-walk horizon after entry, not the entry window.
    """
    return int(cfg.pipeline.observe_max_pending_window_sessions)


# Mirror of the PipelineConfig default. Used ONLY as the pure derivation's
# signature default; production always passes latch_horizon_sessions(cfg).
# Drift-pinned against PipelineConfig() by a test (the #11 mirror discipline).
DEFAULT_LATCH_HORIZON_SESSIONS = 30

# The settled latch semantics: buy-zone limit cap = pivot x 1.03.
LATCH_ZONE_CAP_PCT = 3.0
# The same quantity as a FRACTION, because that is the shape every consumer
# outside this module actually wants (`Web.chase_factor` is a fraction, and so
# is `zone_cap_for_pivot`'s parameter). Derived rather than typed a second time:
# `0.03` written out anywhere else is the item-6 drift class -- a second
# constant that happens to equal the first.
LATCH_ZONE_CAP_FRACTION = LATCH_ZONE_CAP_PCT / 100.0


def zone_cap_for_pivot(pivot, *, cap_fraction: float = LATCH_ZONE_CAP_FRACTION):
    """THE buy-zone cap for a pivot -- the ONE place the arithmetic is written.

    Extracted from `swing/latches/service.py:_Draft.zone_cap` (which now calls
    it) so the dashboard's hypothesis-recommendation buy limit can derive from
    the SAME expression the frozen latch cap derives from. A private copy in
    each caller agrees today and drifts on the next edit; that is exactly how
    21-A's comparator and 21-B's emitter came to disagree about VSTS.

    THIS IS THE CAP, NOT THE ORDERABLE PRICE. It is a 4-decimal quantity and a
    US equity limit order is penny-priced, so every DISPLAY and every ORDER puts
    it through `mandate_limit_price` (which floors -- a cap that can drift up is
    not a cap). Splitting the two is deliberate: the zone comparison wants the
    true cap, the operator wants the price he can actually type.

    `cap_fraction` exists for `cfg.web.chase_factor`, the operator's editable
    pad. Its DEFAULT is the latch semantics, so an untouched config makes the
    dashboard and the latch panel state one number for one pivot.

    The 4-decimal rounding is 21-A's, preserved verbatim: it clips the binary
    artifact of `pivot * 1.03` without pretending to more precision than the
    inputs carry.

    NON-FINITE INPUT RAISES `ValueError` HERE, at the shared helper (Codex R1
    MAJOR). `cap_fraction` carries `cfg.web.chase_factor`, and
    `config_validation.validate_field` bounds it with ORDERED COMPARISONS ONLY
    -- every comparison against `nan` is False, so `nan` passes both the hard
    refusal and the soft warning; a TOML `chase_factor = inf` bypasses the
    registry altogether through `Web(**raw)`. Downstream,
    `Decimal("Infinity").quantize(...)` raises `decimal.InvalidOperation`, which
    is NOT the `ValueError` the dashboard's degenerate-sizing guard catches, so
    an unguarded non-finite value turned a rendering surface into a 500.
    `ValueError` is the deliberate type: it joins the existing degenerate-input
    contract instead of inventing a second one.
    """
    p = float(pivot)
    f = float(cap_fraction)
    if not _isfinite(p) or not _isfinite(f):
        raise ValueError(
            f"zone_cap_for_pivot requires finite inputs; got pivot={pivot!r}, "
            f"cap_fraction={cap_fraction!r}")
    cap = round(p * (1.0 + f), 4)
    if not _isfinite(cap):
        raise ValueError(
            f"zone_cap_for_pivot overflowed to {cap!r} for pivot={pivot!r}, "
            f"cap_fraction={cap_fraction!r}")
    return cap

# How far back the PANEL displays cleared latches (display filter only -- the
# derivation always folds every fire so the re-confirmation chain is exact).
LATCH_PANEL_LOOKBACK_SESSIONS = 40

LATCH_STATES = frozenset({
    "armed", "order_resting", "filled", "invalidated", "horizon_expired",
    "superseded",
})
# `superseded`: a re-fire arrived while armed carrying a DIFFERENT frozen
# pivot, so this latch terminated and a new one armed at the new values. It is
# deliberately DISTINCT from `horizon` so 21-B can separate "unfilled because
# the setup re-based" from "unfilled because it went stale"; both still count
# in the ledger denominators. NOT produced by the bar walk -- stamped by the
# section A.2 fold. There is NO zone-escape clear reason: zone escape is a
# RENDER attribute of the armed state (plan section A.7.1).
LATCH_CLEAR_REASONS = frozenset({
    "fill", "invalidation", "horizon", "superseded",
})
LATCH_FILL_LINK_BASES = frozenset({"candidate_id", "windowed"})
LATCH_DEGRADED_REASONS = frozenset({
    "pivot_missing", "stop_missing", "stop_not_below_pivot", "bad_session_date",
})

# Schwab order-status partition (swing/integrations/schwab/models.py
# _SCHWAB_ORDER_STATUSES, the 22-value set).
RESTING_ORDER_STATUSES = frozenset({
    "ACCEPTED", "AWAITING_CONDITION", "AWAITING_PARENT_ORDER",
    "AWAITING_RELEASE_TIME", "AWAITING_STOP_CONDITION", "AWAITING_UR_OUT",
    "NEW", "PENDING_ACKNOWLEDGEMENT", "PENDING_ACTIVATION", "QUEUED",
    "WAIT_TRG", "WORKING",
})
INDETERMINATE_ORDER_STATUSES = frozenset({
    "AWAITING_MANUAL_REVIEW", "PENDING_CANCEL", "PENDING_RECALL",
    "PENDING_REPLACE", "UNKNOWN",
})
BUY_INSTRUCTIONS = frozenset({"BUY", "BUY_TO_OPEN", "BUY_TO_COVER"})

# The MANDATE SHAPE. An order at the right PRICES but the wrong SHAPE does not
# implement the mandate.
#
# RD RULING 2026-07-27: the mandate takes TWO forms, and WHICH one is correct
# depends on where price sits relative to the LATCHED PIVOT.
#
#   price BELOW the latched pivot -> a GTC STOP_LIMIT: stop trigger at the
#     frozen pivot, limit cap at pivot x 1.03. The breakout entry; the
#     canonical form.
#   price AT OR ABOVE the latched pivot -> a GTC LIMIT at the zone cap. The
#     pullback entry. A buy STOP must sit ABOVE the market, so once price has
#     crossed the pivot the broker REJECTS a buy-stop-limit at it -- which is
#     exactly what happened to the operator's FTRE order on 2026-07-23. The
#     correct instrument in that state is a plain resting buy-limit at the cap.
#
# GTC-ness is required of BOTH forms: a DAY order expires tonight and leaves
# the operator uncovered tomorrow, which is how FTRE was lost. A TRAILING stop
# is NEITHER form -- it does not sit at the frozen pivot at all.
MANDATE_ORDER_TYPE_BREAKOUT = "STOP_LIMIT"     # price BELOW the latched pivot
MANDATE_ORDER_TYPE_PULLBACK = "LIMIT"          # price AT OR ABOVE it
MANDATE_ORDER_TYPES = frozenset({
    MANDATE_ORDER_TYPE_BREAKOUT, MANDATE_ORDER_TYPE_PULLBACK,
})
MANDATE_ORDER_DURATIONS = frozenset({"GOOD_TILL_CANCEL"})

LATCH_ORDER_ALARMS = frozenset({
    "LATCH_ARMED_NO_RESTING_ORDER", "ORDER_RESTING_LATCH_CLEARED",
})

# --- Arc 21-G: what the panel may CLAIM about the regime close (gotcha #30) --
#
# `evaluation_runs.data_asof_date` is the MAX bar date across the WHOLE cohort
# while each `candidates.close` comes from that ticker's OWN last bar, so the
# stamp is an UPPER BOUND on the close's date, never a proof of it. The ladder
# below is the read-side treatment of that gap:
#
#   corroborated  -- the archive holds a bar dated EXACTLY the derivation
#                    session whose close IS the recorded close. The only rung
#                    that may ASSERT a match.
#   uncorroborated-- a close exists but is not proven to be that session's. It
#                    may ALARM only under the two conditions in the plan's
#                    section B.2.1 (CHARACTERISABLE + SELF-LIMITING).
#   future_stamp  -- the close belongs to a moment AFTER this page horizon, or
#                    cannot be placed in time at all. Neither direction.
#   absent        -- no usable price. Neither direction.
CLOSE_PROVENANCE_CORROBORATED = "corroborated"
CLOSE_PROVENANCE_UNCORROBORATED = "uncorroborated"
CLOSE_PROVENANCE_FUTURE_STAMP = "future_stamp"
CLOSE_PROVENANCE_ABSENT = "absent"
CLOSE_PROVENANCES = frozenset({
    CLOSE_PROVENANCE_CORROBORATED, CLOSE_PROVENANCE_UNCORROBORATED,
    CLOSE_PROVENANCE_FUTURE_STAMP, CLOSE_PROVENANCE_ABSENT,
})

# Whether the on-disk archive READ COMPLETED, carried SEPARATELY from whether
# it held a bar. `load_bars` swallows every archive exception and returns [],
# so without this "the archive says there is no such bar" and "the archive
# could not be read" collapse into one absence -- and authorizing an alarm in
# the second case would be asserting from a stale price at exactly the moment
# the settling evidence was unreadable.
ARCHIVE_STATUS_OK = "ok"
ARCHIVE_STATUS_UNAVAILABLE = "unavailable"
ARCHIVE_STATUSES = frozenset({ARCHIVE_STATUS_OK, ARCHIVE_STATUS_UNAVAILABLE})

# THE NAMED CATEGORY FOR A DISPLACED PLACE CYCLE THAT CARRIES NO ANSWER
# (RD ruling, 2026-07-30). A failed first attempt that goes permanently
# unmeasured while its ACCEPTED RETRY supplies the scored agreement is not a
# null -- it is a SUBSTITUTION OF A SUCCESS FOR A FAILURE, which is worse than
# silence. So the cycle is REPRESENTED: the panel offers a first-answer form
# while the latch is still rendered, and every cycle that is still unanswered is
# counted under this name in the report AND disclosed beside the agreement rate
# it was excluded from. It is a NAME rather than prose so the report can count
# it and a reader can grep it.
DISPLACED_UNANSWERABLE = "displaced_unanswerable"


# =====================================================================
# THE VIEW-BEACON PAYLOAD CONTRACT -- ONE named object, consumed by BOTH the
# emitter (the panel view model) and the reader (POST /latches/view).
#
# CHARC's ruling, 2026-07-30: a payload contract enforced BY CONVENTION at two
# ends is a drift hazard in a different costume -- the same argument that
# single-sourced the mandate limit price. So the field names live here, the
# emitter BUILDS through `build_beacon_payload`, and the reader PARSES the same
# names and measures coverage with `beacon_coverage_gap`.
#
# RD's binding requirement: SILENT UNDER-REPORTING MUST NOT BE POSSIBLE.
# Under-reporting views pushes latches toward `away`, inflating the number that
# would justify stage-3 auto-place, so the difference between what was RENDERED
# and what was REPORTED must be DETECTABLE rather than assumed equal.
# =====================================================================
BEACON_FIELD_SESSION = "view_session_date"
BEACON_FIELD_ACTIONABLE = "actionable_candidate_ids"
BEACON_FIELD_WITHHELD = "withheld_candidate_ids"
BEACON_ID_FIELDS = (BEACON_FIELD_ACTIONABLE, BEACON_FIELD_WITHHELD)
BEACON_PAYLOAD_FIELDS = (BEACON_FIELD_SESSION, *BEACON_ID_FIELDS)


def build_beacon_payload(*, view_session_date: str, actionable_ids,
                         withheld_ids) -> dict[str, str]:
    """THE payload the panel posts. The ONLY place these names are spelled."""
    return {
        BEACON_FIELD_SESSION: view_session_date,
        BEACON_FIELD_ACTIONABLE: ",".join(str(int(i)) for i in actionable_ids),
        BEACON_FIELD_WITHHELD: ",".join(str(int(i)) for i in withheld_ids),
    }


def beacon_coverage_gap(*, reported_ids, live_ids) -> tuple[int, ...]:
    """Live latches the payload did NOT report -- the SILENT UNDER-REPORT.

    Measured against the handler's OWN re-derivation of the live set, never
    against a total the client also supplies: the emitter builds all three
    fields from one source, so a client-supplied total could only ever agree
    with itself -- a tautology dressed as a check.

    AN EXTRA id is NOT a shortfall. The existence gate already ignores an id
    that is not live, and treating one as a defect would reject a
    stale-but-honest render in the direction that loses views.
    """
    return tuple(sorted(set(live_ids) - set(reported_ids)))


def mandate_limit_price(zone_cap: float) -> float:
    """THE mandate's limit price: the LARGEST WHOLE-CENT PRICE THAT DOES NOT
    EXCEED THE CAP, evaluated against the cap's DECIMAL value rather than its
    BINARY representation (RD ruling, 2026-07-30).

    IT IS SINGLE-SOURCED AND THAT IS THE POINT (CHARC ruling, 2026-07-30). This
    function is called by BOTH 21-B's emitter (`compute_prepared_order`) and
    21-A's comparator (`swing/latches/orders.py`, at every site that judges a
    resting order's limit against a latch). It lives here, in the module that
    imports nothing from `swing`, so both layers can reach it without a cycle.

    THE SECOND DEFINITION IS DELETED, NOT TAUGHT TO FLOOR. 21-A's comparator
    used to derive the mandate limit itself, as `round(zone_cap, 2)` -- a second
    independently-plausible rounding of one quantity, which is the D6 class: a
    parallel copy that agrees most of the time and drifts in production. On the
    live VSTS geometry (cap 17.407) it emitted 17.40 and expected 17.41, so the
    framework attributed the operator's CORRECT order to no latch at all. 49.5%
    of two-decimal pivots produce a cap whose third decimal is non-zero, so the
    disagreement was the ordinary case. The comparator must compare a resting
    order against THE VALUE THE FRAMEWORK ACTUALLY EMITTED.

    AND `round` WAS WRONG ON ITS OWN TERMS: `round(17.407, 2)` is 17.41, which
    EXCEEDS the cap of 17.407 -- the comparator was blessing a price OUTSIDE the
    buy zone, which is exactly what the floor ruling exists to prevent.

    WHOLE CENTS because that is the only price the order could actually be: a US
    equity limit order is penny-priced, 18.8902 is not a price the operator could
    enter, and this arc exists to put *the order he would place* in front of him.

    FLOOR, not round-half-up, and the reason is the CAP SEMANTIC: the zone cap is
    a MAXIMUM (pivot x 1.03 is the top of the buy zone), so a quantization that
    can move the price UP can push the order ABOVE the zone. Round-half-up does
    that whenever the cap's third decimal is >= 5 -- a cap of 18.8952 becomes
    18.90 > 18.8952. RD: a cap that can drift up under rounding is not a cap.

    AND NOT `math.floor(cap * 100) / 100` EITHER, which was the originally
    shipped form: a cap that IS an exact cent in decimal can be represented just
    BELOW it in binary, so the multiply-and-floor drops a cent that the decimal
    value plainly contains. `round(141.00 * 1.03, 4)` is `145.23`, but
    `145.23 * 100` evaluates to `14522.999999999998` and the naive floor emits
    **145.22**. Incidence through the production path
    (`zone_cap = round(pivot * 1.03, 4)`): 43 of the 100,000 two-decimal pivots
    up to $1000.

    `Decimal(str(cap))` is the mandated form rather than an epsilon or a
    `floor(round(cap * 100, 6))`: both of those work, and both need a precision
    constant nobody can justify to the next reader. `str()` yields the shortest
    decimal that round-trips the double, which IS "the cap's decimal value", and
    `ROUND_FLOOR` then states the cap semantic directly.

    FTRE does NOT exhibit either defect (18.8902 floors to 18.89 under every
    implementation), which is exactly why both rules have to be STATED rather
    than inferred from the worked example -- and why the two pinning tests are
    each marked NOT DROPPABLE: the round-half-up case passes under the naive
    floor, and the representation case passes under round-half-up.

    AND IT IS TOTAL OVER FINITE FLOATS (Codex R2 MAJOR + codex-auto-review,
    2026-08-03). `quantize` raises `InvalidOperation` when the RESULT needs more
    digits than the ambient context carries -- 28 by default -- so
    `mandate_limit_price(1e26)` used to RAISE. Harmless while every caller was
    latch-internal with a validated price; NOT harmless once the display fix
    routed the dashboard's buy limit and every cap render through here, because
    `candidates.pivot` carries no schema CHECK (migration 0001) and
    `cfg.web.chase_factor` reaches `Web(**raw)` unvalidated from TOML. A
    rendering surface must not 500 on a number.

    THE PRECISION CONTEXT IS THE FIX, NOT A `try/except` AT EACH CALLER: the
    contract is "the largest whole-cent price that does not exceed the cap", and
    for 1e26 that answer plainly exists -- the default context was the only
    thing refusing to compute it. 400 digits covers `sys.float_info.max` (309
    integer digits + 2 fractional) with room, and the widening is EXACTLY
    output-preserving on every value that already worked: a larger precision
    cannot change a result that already fit.
    """
    return float(
        _Decimal(str(float(zone_cap))).quantize(
            _Decimal("0.01"), rounding=_ROUND_FLOOR, context=_QUANTIZE_CONTEXT))


# =====================================================================
# Phase 21 Arc 21-B -- the prepared-order form + the execution-parity ledger.
#
# EVERY schema enum migration 0033 declares has its ONE authority here; the
# dataclass validators in swing/data/models.py IMPORT these frozensets rather
# than re-declaring them (the #11 one-commit multi-mirror discipline, pinned by
# `is`-identity tests), and tests/data/test_migration_0033.py parses the
# migration SQL and asserts exact set equality.
#
# NO SITE STATES A CARDINALITY. Every set has ONE authority; every other site
# refers to it by NAME and every test ITERATES it, so a set that grows gains its
# cases automatically instead of needing a bullet edited.
# =====================================================================

# THE TELEMETRY EPOCH -- the first action session for which a latch_view_events
# row could exist. Migration 0032 applied to the live DB at 2026-07-28T11:14:53
# (backup swing-20260728T111453.db) and the beacon writes
# action_session_for_run(now), which at that instant was 2026-07-29.
#
# A HISTORICAL FACT, not a derived quantity, and deliberately NOT
# MIN(view_session_date): with zero rows that is undefined, and once rows exist
# it would drift FORWARD every time the operator goes quiet -- so a genuinely
# away fire would be re-labelled "uninstrumented" precisely BECAUSE he was away.
# That is the flattering direction. In-tree precedent: the 18-D research monitor
# baselines check #1 on the hard-coded date(2026, 6, 13) 18-A boundary.
LATCH_TELEMETRY_EPOCH_SESSION = _date(2026, 7, 29)

# The schema CHECK enum for `surface` on BOTH 0033 tables.
LATCH_VIEW_SURFACES = frozenset({"latch_panel"})
# Which surfaces COUNT as a view for MEASUREMENT purposes.
#
# DELIBERATELY SEPARATE FROM, AND DELIBERATELY EQUAL TO, LATCH_VIEW_SURFACES
# TODAY. Adding a surface to the CHECK enum is a SCHEMA decision; adding it here
# is a MEASUREMENT decision and RD's (it is exactly the 21-F question -- does a
# dashboard glance count evidentially as a view?). Keeping them separate means a
# future surface cannot change the away/lapse math as a side effect of being
# added. A test asserts ACTIONABLE_VIEW_SURFACES <= LATCH_VIEW_SURFACES: an
# uncounted-but-unwritable surface is a typo, not a design.
ACTIONABLE_VIEW_SURFACES = frozenset({"latch_panel"})

LATCH_INTENT_KINDS = frozenset({
    "place", "decline", "cancel", "attest", "validity",
})
# WHICH KINDS MAY CARRY AN OBSERVED BROKER ORDER ID. DERIVED BY SUBTRACTION,
# mirroring the migration's own EXCLUSION shape verbatim
# (`intent_kind NOT IN ('place','decline') OR actual_broker_order_id IS NULL`):
# a broker order id is an OBSERVATION, and `place`/`decline` are DECISIONS about
# a prepared order that have observed nothing.
#
# DERIVED rather than re-listed so a kind added to the enum joins this set
# automatically. The CLI's distinguishability query reads it: the shipped query
# hand-listed `validity` and `cancel`, which silently dropped every `attest`
# row's broker order -- and the attestation path is the ONE path that exists for
# orders the framework did not prepare (Codex exec R5 MAJOR 5).
LATCH_BROKER_ORDER_ID_KINDS = LATCH_INTENT_KINDS - {"place", "decline"}
LATCH_ATTESTED_DISPOSITIONS = frozenset({
    "acted_manually", "chose_not_to_act", "was_away",
})
LATCH_VALIDITY_OUTCOMES = frozenset({
    "accepted_by_broker", "rejected_by_broker", "not_submitted", "unknown",
})
LATCH_SIZING_BASES = frozenset({"limit_price", "pivot"})
# The tri-state stop-leg comparison result (plan section D.4). `both_absent` is
# the pullback regime's RIGHT answer and is a MATCH; with a bare `float | None`
# it would collapse into `unknown`, and unknown is never agreement, so the
# CORRECT order would score as a non-match.
# THE STOP-LEG CELL OF THE PER-FIELD DELTA. FOUR states, not three (RD ruling,
# 2026-07-30):
#   both_absent -- neither side carries a stop leg. The pullback regime's RIGHT
#                  answer, and a determinable AGREEMENT.
#   compared    -- both carry one; the signed delta is set.
#   one_sided   -- EXACTLY ONE carries one, and BOTH SIDES WERE OBSERVED. A
#                  framework STOP_LIMIT against an actual LIMIT is NOT unknown:
#                  we can see both sides, so it is a fully observed
#                  DISAGREEMENT. RD's consistency check: `both_absent` is
#                  already ruled a determinable agreement, so the symmetric
#                  one-present-one-absent case is the determinable
#                  DISAGREEMENT. Scoring one and calling the other unknown is
#                  exactly the asymmetry that produces a flattering metric --
#                  it deleted a real disagreement from the agreement rate.
#   unknown     -- the INSTRUMENT COULD NOT OBSERVE (no actual side at all).
#                  That is what `unknown` means and it keeps meaning it.
LATCH_STOP_LEG_STATES = frozenset({
    "both_absent", "compared", "one_sided", "unknown",
})
LATCH_ORDER_WITHHELD_REASONS = frozenset({
    "regime_undeterminable", "sizing_infeasible", "sizing_degenerate",
})
# The `actual_order_type` / `actual_duration` vocabularies. The framework side
# reuses 21-A's MANDATE_ORDER_TYPES / MANDATE_ORDER_DURATIONS unchanged; the
# ACTUAL side additionally admits UNKNOWN, because an unmapped broker rendering
# must canonicalise to something that compares as UNKNOWN rather than as
# agreement.
LATCH_ACTUAL_ORDER_TYPES = MANDATE_ORDER_TYPES | {"UNKNOWN"}
LATCH_ACTUAL_DURATIONS = frozenset({
    "GOOD_TILL_CANCEL", "DAY", "FILL_OR_KILL", "IMMEDIATE_OR_CANCEL",
    "END_OF_WEEK", "END_OF_MONTH", "NEXT_END_OF_MONTH", "UNKNOWN",
})

# The DECISION axis. `partial_telemetry_unresolved` was drafted and DELETED by
# RD's ruling 2: partial-coverage-with-no-observation collapses into
# `pre_telemetry`, because the REASON is the same in both cases -- the
# instrument was not there -- and a second name would imply a distinction the
# evidence does not support. A `pending_attestation` state was ALSO drafted and
# deleted: it required a persisted prompt-shown bit nothing writes, so it was
# uncomputable from the classifier's pure inputs, AND it made the pessimistic
# default depend on the instrument having rendered a prompt (the instrument
# flattering its subject through inaction).
LATCH_DISPOSITIONS = frozenset({
    "pre_telemetry", "telemetry_unhealthy",
    "away_unseen", "accepted", "declined", "attested_acted_manually",
    "attested_chose_not_to_act", "attested_was_away", "discipline_lapse",
    "pending_live", "never_actionable",
})
# The EXECUTION axis -- a SECOND, independent question. Collapsing the two would
# let a broker-REJECTED placement classify as a clean `accepted` and contribute
# to the agreement rate, which is the FTRE failure mode itself.
LATCH_EXECUTION_OUTCOMES = LATCH_VALIDITY_OUTCOMES | {"not_applicable"}

# How many DARK instrumented sessions make the beacon `broken`. Named so a
# genuinely quiet week does not trip it.
LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD = 5
# How old a broker-book snapshot may be and still answer a validity prompt.
LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS = 900

# The broker-snapshot envelope persisted VERBATIM into
# latch_order_intents.validity_detail. THE ROSTER IS THE MIGRATION'S OWN
# `json_remove(...)` PATH LIST -- that call is the machine-readable source of
# truth and this frozenset mirrors it under #11 (a test parses the path list out
# of the migration and asserts exact set equality). No site states the count: an
# earlier round added broker_snapshot_session to the CHECK while three other
# sites still said "six keys", so the fragment's emitted set and the row's
# required set disagreed by one -- which makes the audit row unwritable.
#
# `broker_snapshot_digest` is itself one of the roster keys and is computed over
# the broker-book STATE, NOT over the other keys; the two are separate facts and
# conflating them is how the count drifted.
LATCH_BROKER_SNAPSHOT_KEYS = frozenset({
    "broker_snapshot_ts", "broker_snapshot_branch", "broker_snapshot_digest",
    "broker_snapshot_session", "attributable_order_count",
    "exact_framework_match_count", "indeterminate",
})
# TWO VOCABULARIES, because the render status and the persisted answer are
# MEASURED DIFFERENTLY and do not share one enum (the governing principle). The
# FRAGMENT emits from the RENDER set; the handler and the dataclass validate
# against the PERSISTED set; the migration CHECK mirrors the PERSISTED set. A
# test asserts PERSISTED < RENDER as a STRICT subset -- equality would mean the
# narrowing had been silently undone.
#
# An `unavailable` book renders NO validity prompt in either direction, so an
# append-only row asserting an outcome against an unknown book must be
# UNWRITABLE rather than merely unreachable.
LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES = frozenset({
    "presence", "absence", "unavailable",
})
LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES = frozenset({"presence", "absence"})


# ---------------------------------------------------------------------
# THE FIVE R BUCKETS (plan section F.3). `r_bucket_for` validates membership
# against the UNION of these five, NOT against LATCH_DISPOSITIONS: the enum says
# only that the CLASSIFIER may emit a value, not that anyone RULED its bucket,
# so a disposition added to the enum without a ruling would pass a
# LATCH_DISPOSITIONS check and fall through the terminality gate into
# `pending_r` -- silently scored as "not an observation yet" rather than raising.
# ---------------------------------------------------------------------
_ALL_EXCLUDED_DISPOSITIONS = frozenset({
    "away_unseen", "pre_telemetry",
    "never_actionable", "telemetry_unhealthy",
})
PENDING_DISPOSITIONS = frozenset({"pending_live"})
# RD ruling 2 (2026-07-28): testimony is not telemetry, so a self-declared away
# does NOT belong in the same number as a telemetry-derived one. Merging it into
# away_r would reintroduce, through the attestation door, the flattering path
# closed at the default door.
ATTESTED_AWAY_DISPOSITIONS = frozenset({"attested_was_away"})
# FIXED at the closed gate (plan section A.1.5): the objective away rate counts
# `away_unseen` and nothing else.
AWAY_RATE_COUNTED_DISPOSITIONS = frozenset({"away_unseen"})
# WRITTEN OUT EXPLICITLY, never derived by subtraction -- ON PURPOSE.
# `decision_r` is the bucket a missing ruling would silently fall into, so it
# must be the one set that can only grow by someone TYPING a disposition into
# it.
DECISION_DISPOSITIONS = frozenset({
    "accepted", "declined",
    "attested_acted_manually", "attested_chose_not_to_act",
    "discipline_lapse",
})
# DERIVED by set subtraction, never hand-written -- that is what makes an
# overlap between the buckets UNREPRESENTABLE rather than merely tested-against.
# ATTESTED_AWAY_DISPOSITIONS is subtracted too, or away_unseen's sibling would
# fall into unattributable_r as well as its own bucket.
UNATTRIBUTABLE_DISPOSITIONS = (
    _ALL_EXCLUDED_DISPOSITIONS
    - AWAY_RATE_COUNTED_DISPOSITIONS
    - ATTESTED_AWAY_DISPOSITIONS
)
# THE RULED UNION -- what `r_bucket_for` validates membership against, and the
# reason the terminality gate can no longer absorb an unruled disposition.
# `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS` is a CONCLUSION with its own test,
# never the CHECK.
_RULED_DISPOSITIONS = (
    AWAY_RATE_COUNTED_DISPOSITIONS | ATTESTED_AWAY_DISPOSITIONS
    | UNATTRIBUTABLE_DISPOSITIONS | DECISION_DISPOSITIONS
    | PENDING_DISPOSITIONS
)
# The closed set of values `r_bucket_for` can RETURN, named so no site has to
# say "the five buckets". ExecutionParityReport builds its per-bucket fields by
# ITERATING this, the partition test iterates it, and the CLI report prints it --
# so a sixth bucket added to the resolver cannot be silently omitted from any of
# the three.
R_BUCKETS = frozenset({
    "decision_r", "away_r", "attested_away_r", "unattributable_r", "pending_r",
})


# ---------------------------------------------------------------------
# THE DERIVATION-FIELD MANIFEST (plan section A.4) -- the ONLY place the
# DB-column <-> OrderDerivation-attribute <-> encoding mapping exists.
#
# The rule it carries: EVERY value the card presents INSIDE the prepared-order
# derivation block is hidden-anchored, compared at POST, and stored. Anything
# not anchored MUST NOT be rendered inside that block. The two are ONE decision:
# a number is either part of the audited derivation, or it is not shown as part
# of it.
#
# As PROSE that rule cannot execute -- an implementer would have to invent the
# column-to-attribute mapping, which is exactly the hand-kept list the roster
# rule forbids, re-created one layer down. So it is a manifest, and four
# assertions make it the AUTHORITY rather than a fourth copy:
#   1. {f.column} EQUALS the derivation_* columns in PRAGMA table_info
#   2. {f.column if f.nullable} EQUALS DERIVATION_NULLABLE_ON_DECISION, and
#      every nullable row carries a non-empty null_reason
#   3. {f.column if f.rendered} EQUALS the derivation values the card renders
#      as audited (the section A.4 closure, checkable instead of aspirational)
#   4. the form's hidden inputs, anchor_digest's components and the POST-time
#      comparison are all GENERATED by walking the manifest and applying
#      `encode`, so the three cannot drift and no site re-lists the columns
#
# `encode` is what makes the digest REPRODUCIBLE across render and POST:
# `price2` is the whole-cent form, `pct6` fixes the policy-rate precision,
# `session` is ISO YYYY-MM-DD, and a NULL encodes as the EMPTY STRING --
# distinct from "0", which a float field could legitimately produce.
#
# `pct6` IS SIX DECIMALS OF FRACTION AND IT REPLACED A FOUR-DECIMAL `pct4`
# (auto-review CRITICAL 3): the card renders a policy rate as `{rate*100:.3f}%`,
# which is FIVE decimals of fraction, so a four-decimal anchor was COARSER THAN
# THE DISPLAY -- 0.00504 and 0.00505 render 0.504% and 0.505% and both encoded
# `0.0050`. Two consequences, both real: the POST-time comparison could not
# detect a changed VISIBLE derivation, and `_stored_anchor_values` decodes the
# SUBMITTED text, so the ledger persisted a provenance different from the card
# the operator was shown -- on the ledger whose entire claim is that those two
# are identical. The rule is DIRECTIONAL: the anchor must be at least as fine as
# the display, never the reverse.
# ---------------------------------------------------------------------
DERIVATION_ENCODINGS = frozenset({"price2", "pct6", "int", "session", "text"})


@_dataclass(frozen=True)
class DerivationField:
    column: str          # the latch_order_intents column
    attr: str            # the OrderDerivation attribute it comes from
    encode: str          # canonical hidden-input / digest encoding
    nullable: bool       # legitimately NULL on a place/decline row?
    null_reason: str     # REQUIRED iff nullable -- why, in one line
    rendered: bool       # does the card present it INSIDE the derivation block?

    def __post_init__(self) -> None:
        if self.encode not in DERIVATION_ENCODINGS:
            raise ValueError(
                f"{self.column}: encode must be in {sorted(DERIVATION_ENCODINGS)}, "
                f"got {self.encode!r}")
        if self.nullable and not self.null_reason.strip():
            raise ValueError(
                f"{self.column}: a nullable derivation field REQUIRES a "
                "null_reason -- an unexplained exemption is the hand-kept list "
                "this manifest replaces")
        if not self.nullable and self.null_reason:
            raise ValueError(
                f"{self.column}: a non-nullable field must carry NO null_reason")


DERIVATION_FIELD_MANIFEST: tuple[DerivationField, ...] = (
    DerivationField("derivation_zone_cap_pct", "zone_cap_pct", "pct6",
                    False, "", True),
    DerivationField("derivation_sizing_equity", "sizing_equity", "price2",
                    False, "", True),
    DerivationField("derivation_max_risk_pct", "max_risk_pct", "pct6",
                    False, "", True),
    DerivationField("derivation_position_pct_cap", "position_pct_cap", "pct6",
                    False, "", True),
    DerivationField(
        "derivation_risk_policy_id", "risk_policy_id", "int", True,
        "the sizing RATE comes from cfg.risk.max_risk_pct, NOT from the policy "
        "row, so a prepared order is fully computable with no active policy row "
        "and the form is NOT withheld for one; the id is PROVENANCE, and the "
        "card renders an explicit 'no active risk_policy row' line rather than "
        "a blank",
        True),
    DerivationField("derivation_sizing_basis", "sizing_basis", "text",
                    False, "", True),
    DerivationField("derivation_regime_close", "regime_close", "price2",
                    False, "", True),
    DerivationField("derivation_regime_close_session", "regime_close_session",
                    "session", False, "", True),
    DerivationField("derivation_real_equity", "real_equity", "price2",
                    False, "", True),
    DerivationField("derivation_equity_floor", "equity_floor", "price2",
                    False, "", True),
    DerivationField(
        "derivation_nightly_recommendation_shares",
        "nightly_recommendation_shares", "int", True,
        "a fire with no daily_recommendations row has none, and the card "
        "renders no sizing-divergence note for it",
        True),
)

# The ROSTER of derivation columns legitimately NULL on a place/decline row.
# DERIVED from the manifest so it cannot disagree with it; the migration's
# required-block CHECK mirrors the complement, and the tests derive the required
# set as {every derivation_* column in PRAGMA table_info} - this set, stating no
# cardinality. Adding a derivation column extends the required set
# automatically; adding an EXEMPTION is a deliberate edit with a reviewer.
DERIVATION_NULLABLE_ON_DECISION = frozenset(
    f.column for f in DERIVATION_FIELD_MANIFEST if f.nullable
)
