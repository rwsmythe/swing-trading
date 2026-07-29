"""Locked latch-derivation constants (Phase 21 Arc A).

Single source of truth for every value the latch derivation and the
21-A/21-B schema CHECKs mirror (the #11 one-commit multi-mirror discipline).

This module imports NOTHING from `swing` -- it is the domain owner of the
latch state vocabulary, so `swing/data/models.py` can import the frozensets
from here without a cycle.
"""
from __future__ import annotations


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
