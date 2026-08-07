"""Value types for the Arc 21-A latch derivation.

All frozen; all validating in `__post_init__` (a `Literal[...]` hint is NOT
runtime-enforced). Deliberately NOT validated here: `FireRow.pivot` /
`initial_stop` finiteness. Those are DATA-QUALITY facts about a row the
derivation must DEGRADE on (A6 / plan A.10), not construction errors -- a
NULL-pivot `bucket='aplus'` row genuinely exists in the schema's reachable
space, so the reader must be able to build a FireRow for it and let
`derive_latches` emit a visible `DegradedFire`.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from swing.latches.constants import (
    INDETERMINATE_ORDER_STATUSES,
    LATCH_CLEAR_REASONS,
    LATCH_DEGRADED_REASONS,
    LATCH_FILL_LINK_BASES,
    LATCH_ORDER_ALARMS,
    LATCH_STATES,
    RESTING_ORDER_STATUSES,
)
from swing.latches.identity import LatchIdentity

_LIVE_STATES = frozenset({"armed", "order_resting"})


def _require_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be int (not bool); got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}")


def _require_finite_number(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number; got {type(value).__name__}")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite; got {value!r}")


@dataclass(frozen=True)
class FireRow:
    """One `candidates` row with `bucket='aplus'`, joined to its run.

    `action_session_date` is kept as the raw TEXT column value (NOT a `date`)
    precisely so a malformed value can reach `derive_latches` and degrade
    visibly rather than exploding at the reader boundary.
    """

    candidate_id: int
    evaluation_run_id: int
    ticker: str
    pivot: float | None
    initial_stop: float | None
    action_session_date: str
    run_ts: str
    pipeline_run_id: int | None = None
    # The FIRE's OWN `candidates.adr_pct` (item 3b) -- a PER-ROW value, so
    # reading it here carries no gotcha-#30 exposure the way an
    # `evaluation_runs` stamp would. It scales the `criteria_lapsed`
    # materiality floor.
    #
    # RAW, NOT COERCED, exactly like `pivot`/`initial_stop` above and for the
    # identical reason: SQLite will hold TEXT in a REAL column, and an eager
    # float() at the reader would raise and DROP the whole fire, contradicting
    # the reader's degrade-don't-drop contract. An unusable value makes the
    # latch DIRECTIONALLY UNVERIFIABLE -- which never clears anything -- rather
    # than substituting a constant.
    adr_pct: float | None = None

    def __post_init__(self) -> None:
        _require_positive_int("candidate_id", self.candidate_id)
        _require_positive_int("evaluation_run_id", self.evaluation_run_id)
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError(f"ticker must be a non-blank str; got {self.ticker!r}")
        if not isinstance(self.action_session_date, str):
            raise ValueError(
                "action_session_date must be str; got "
                f"{type(self.action_session_date).__name__}")
        if not isinstance(self.run_ts, str):
            raise ValueError(f"run_ts must be str; got {type(self.run_ts).__name__}")
        if self.pipeline_run_id is not None:
            _require_positive_int("pipeline_run_id", self.pipeline_run_id)

    @property
    def sort_key(self) -> tuple[str, str, int]:
        return (self.action_session_date, self.run_ts, self.candidate_id)


# The three ways one action session can answer "did this name still pass the A+
# STRUCTURAL gate?". Named here rather than as bare strings so the resolver, the
# reader and the render cannot drift on the spelling.
VERDICT_PASSED = "PASSED"
VERDICT_FAILED = "FAILED"
VERDICT_UNVERIFIABLE = "UNVERIFIABLE"
STRUCTURAL_VERDICTS = frozenset({
    VERDICT_PASSED, VERDICT_FAILED, VERDICT_UNVERIFIABLE})
# Why a session could not be verified. One CLASS to the operator ("we could not
# check this"), because splitting them on the card would imply a distinction he
# cannot act on -- the cause belongs in the detail line.
UNVERIFIABLE_CAUSES = frozenset({
    "absent", "sentinel_row", "incomplete_roster", "malformed_result"})


@dataclass(frozen=True)
class SessionStructuralVerdict:
    """What ONE evaluated action session says about ONE ticker's A+ structure.

    `conflicted` is RD's OQ-15 addition and is NOT a tiebreak record: two runs
    for one session disagreeing on the STRUCTURAL verdict is a fact about the
    pipeline, not an ambiguity to be quietly resolved. It is surfaced and
    counted; the resolution itself is generous (a session in which the
    framework at any point judged the setup sound is not evidence of decay).
    """

    action_session: date
    classification: str
    cause: str | None = None
    conflicted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.action_session, date):
            raise ValueError("action_session must be a date")
        if self.classification not in STRUCTURAL_VERDICTS:
            raise ValueError(
                f"classification must be in {sorted(STRUCTURAL_VERDICTS)}; "
                f"got {self.classification!r}")
        if self.cause is not None and self.cause not in UNVERIFIABLE_CAUSES:
            raise ValueError(
                f"cause must be None or in {sorted(UNVERIFIABLE_CAUSES)}; "
                f"got {self.cause!r}")
        # A cause explains an UNVERIFIABLE and nothing else; a verified verdict
        # carrying one would let the detail line state a reason for a session
        # the framework actually checked.
        if (self.classification == VERDICT_UNVERIFIABLE) != (self.cause is not None):
            raise ValueError(
                "a cause is required for UNVERIFIABLE and forbidden otherwise; "
                f"got {self.classification!r}/{self.cause!r}")


@dataclass(frozen=True)
class DailyBar:
    """One completed daily bar from the on-disk OHLCV archive."""

    session: date
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if not isinstance(self.session, date):
            raise ValueError(
                f"session must be a date; got {type(self.session).__name__}")
        for name in ("open", "high", "low", "close"):
            _require_finite_number(name, getattr(self, name))


@dataclass(frozen=True)
class EntryRecord:
    """One `trades` entry, reduced to what latch fill-matching needs."""

    trade_id: int
    ticker: str
    entry_date: date
    candidate_id: int | None
    entry_price: float | None = None
    shares: float | None = None

    def __post_init__(self) -> None:
        _require_positive_int("trade_id", self.trade_id)
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError(f"ticker must be a non-blank str; got {self.ticker!r}")
        if not isinstance(self.entry_date, date):
            raise ValueError(
                f"entry_date must be a date; got {type(self.entry_date).__name__}")
        if self.candidate_id is not None:
            _require_positive_int("candidate_id", self.candidate_id)


@dataclass(frozen=True)
class DegradedFire:
    """An A+ fire whose own `candidates` row is unusable (plan A.10).

    Rendered as a visibly-degraded row so the operator sees that a fire EXISTED
    and why it produced no latch -- never silently dropped.
    """

    candidate_id: int
    evaluation_run_id: int
    ticker: str
    action_session_date: str
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int("candidate_id", self.candidate_id)
        _require_positive_int("evaluation_run_id", self.evaluation_run_id)
        if self.reason not in LATCH_DEGRADED_REASONS:
            raise ValueError(
                f"reason must be in {sorted(LATCH_DEGRADED_REASONS)}; "
                f"got {self.reason!r}")


@dataclass(frozen=True)
class Latch:
    """One entry mandate, frozen at its opening fire (RD constraint 1)."""

    identity: LatchIdentity
    latched_pivot: float
    latched_initial_stop: float
    zone_cap: float
    anchor: date
    horizon_expiry: date
    sessions_elapsed: int
    sessions_to_horizon: int
    state: str
    clear_reason: str | None = None
    clear_session: date | None = None
    clear_trade_id: int | None = None
    fill_link_basis: str | None = None
    fill_link_anomaly: bool = False
    bars_available: bool = False
    bars_through: date | None = None
    reconfirmation_candidate_ids: tuple[int, ...] = ()
    reconfirmation_sessions: tuple[str, ...] = ()
    # ---- THE `criteria_lapsed` DIAGNOSTICS (item 3b) -----------------------
    # Trailing + defaulted, so every existing `Latch(...)` construction and
    # every fixture stays valid -- the shape `bars_available`/`bars_through`
    # already have.
    #
    # THEY TRAVEL ON THE LATCH; the view model READS them and never re-derives
    # them. Recomputing the streak in the VM would be a SECOND implementation
    # of the resolver, which is the drift class this arc single-sources the
    # gate to avoid.
    #
    # TWO SCOPES, NAMED APART, because one set of tuples cannot serve both
    # contracts (see `LATCH_LAPSE_DIAGNOSTIC_FIELDS`).
    lapse_failed_sessions: tuple[date, ...] = ()
    lapse_unverifiable_sessions: tuple[date, ...] = ()
    lapse_unverifiable_causes: tuple[str, ...] = ()
    lapse_conflicted_sessions: tuple[date, ...] = ()
    lapse_failed_count: int = 0
    lapse_unchecked_count: int = 0
    lapse_unverifiable_tail: int = 0
    directional_evaluable: bool = True
    directional_block_reason: str | None = None
    lapse_qualifying_session: date | None = None
    lapse_would_clear_session: date | None = None

    def __post_init__(self) -> None:
        if self.state not in LATCH_STATES:
            raise ValueError(
                f"state must be in {sorted(LATCH_STATES)}; got {self.state!r}")
        if self.clear_reason is not None and self.clear_reason not in LATCH_CLEAR_REASONS:
            raise ValueError(
                f"clear_reason must be None or in {sorted(LATCH_CLEAR_REASONS)}; "
                f"got {self.clear_reason!r}")
        if (self.fill_link_basis is not None
                and self.fill_link_basis not in LATCH_FILL_LINK_BASES):
            raise ValueError(
                f"fill_link_basis must be None or in {sorted(LATCH_FILL_LINK_BASES)}; "
                f"got {self.fill_link_basis!r}")
        for name in ("latched_pivot", "latched_initial_stop", "zone_cap"):
            _require_finite_number(name, getattr(self, name))
        if self.latched_initial_stop >= self.latched_pivot:
            raise ValueError("latched_initial_stop must be below latched_pivot")
        if not isinstance(self.anchor, date):
            raise ValueError("anchor must be a date")
        if len(self.reconfirmation_candidate_ids) != len(self.reconfirmation_sessions):
            raise ValueError(
                "reconfirmation_candidate_ids and reconfirmation_sessions must "
                "be parallel")
        # A live state must NOT carry a terminal record, and vice versa. This
        # is the invariant the panel + the order alarms both read.
        if self.state in _LIVE_STATES and self.clear_reason is not None:
            raise ValueError(f"state {self.state!r} cannot carry a clear_reason")
        if self.state not in _LIVE_STATES and self.clear_reason is None:
            raise ValueError(f"state {self.state!r} requires a clear_reason")
        self._validate_lapse_diagnostics()

    def _validate_lapse_diagnostics(self) -> None:
        """THE TUPLES ARE AUTHORITATIVE AND EVERY COUNT IS DERIVED FROM THEM.

        A count is REJECTED when it disagrees with its tuple rather than
        silently overwritten -- the raise-don't-absorb posture the rest of this
        module takes. Without it a `Latch` could carry "4 failures" while naming
        two sessions, and the card would state a false fact with nothing to
        catch it: two independent representations of one quantity is the drift
        class this arc keeps closing elsewhere.
        """
        for name in ("lapse_failed_sessions", "lapse_unverifiable_sessions",
                     "lapse_conflicted_sessions"):
            sessions = getattr(self, name)
            for s in sessions:
                if not isinstance(s, date):
                    raise ValueError(f"{name} must hold dates; got {s!r}")
            # STRICTLY ascending, hence unique: without it a card can name one
            # session twice and claim evidence it does not have.
            if any(a >= b for a, b in zip(sessions, sessions[1:], strict=False)):
                raise ValueError(f"{name} must be strictly ascending")
        if len(self.lapse_unverifiable_causes) != len(
                self.lapse_unverifiable_sessions):
            raise ValueError(
                "lapse_unverifiable_causes must be parallel to "
                "lapse_unverifiable_sessions")
        for cause in self.lapse_unverifiable_causes:
            if cause not in UNVERIFIABLE_CAUSES:
                raise ValueError(
                    f"cause must be in {sorted(UNVERIFIABLE_CAUSES)}; "
                    f"got {cause!r}")
        # A session is FAILED or UNVERIFIABLE, never both.
        if set(self.lapse_failed_sessions) & set(self.lapse_unverifiable_sessions):
            raise ValueError(
                "lapse_failed_sessions and lapse_unverifiable_sessions must be "
                "disjoint")
        if self.lapse_failed_count != len(self.lapse_failed_sessions):
            raise ValueError(
                "lapse_failed_count must equal len(lapse_failed_sessions); got "
                f"{self.lapse_failed_count} vs "
                f"{len(self.lapse_failed_sessions)}")
        if self.lapse_unchecked_count != len(self.lapse_unverifiable_sessions):
            raise ValueError(
                "lapse_unchecked_count must equal "
                "len(lapse_unverifiable_sessions); got "
                f"{self.lapse_unchecked_count} vs "
                f"{len(self.lapse_unverifiable_sessions)}")
        # THE TAIL INVARIANT IS NARROWED HONESTLY. The strong form -- that the
        # tail equals the UNVERIFIABLE suffix of the actual verdict sequence --
        # is UNCHECKABLE here: `Latch` carries the failed and unverifiable
        # sessions but NEVER the PASSED ones, so a caller supplying a tail of 1
        # while omitting a later PASSED session is undetectable at the
        # constructor. Claiming the stronger check would be a guard that cannot
        # fire, so the RESOLVER owns the suffix computation and a resolver test
        # pins it.
        if not isinstance(self.lapse_unverifiable_tail, int) or isinstance(
                self.lapse_unverifiable_tail, bool):
            raise ValueError("lapse_unverifiable_tail must be an int")
        if not 0 <= self.lapse_unverifiable_tail <= self.lapse_unchecked_count:
            raise ValueError(
                "lapse_unverifiable_tail must be within "
                f"[0, {self.lapse_unchecked_count}]; got "
                f"{self.lapse_unverifiable_tail}")
        if (self.directional_evaluable
                and self.directional_block_reason is not None):
            raise ValueError(
                "directional_block_reason is only meaningful when "
                "directional_evaluable is False")

    @property
    def is_live(self) -> bool:
        return self.state in _LIVE_STATES

    @property
    def reconfirmation_count(self) -> int:
        return len(self.reconfirmation_candidate_ids)

    @property
    def candidate_set(self) -> frozenset[int]:
        """The opening fire PLUS every re-confirmation (RD constraint 4)."""
        return frozenset(
            {self.identity.candidate_id, *self.reconfirmation_candidate_ids})


# THE DIAGNOSTIC ROSTER, NAMED ONCE (item 3b). The armed/unarmed equivalence
# test and the production-path test both WALK this rather than enumerating their
# own subsets -- an iteration over a roster that can itself omit a field proves
# nothing, which is how the newest field goes missing from the dataclass, the
# roster and the comparison at the same time. A test asserts this equals the
# exact eleven-name literal set AND that every name is a real `Latch` field.
#
# TWO SCOPES LIVE IN HERE AND THEY ARE DIFFERENT QUESTIONS:
#
#   CURRENT-STREAK evidence -- the interval AFTER the last PASSED session.
#   These drive the CARD, which is a claim about the mandate's state NOW:
#     lapse_failed_sessions / lapse_unverifiable_sessions /
#     lapse_unverifiable_causes and their two counts.
#
#   ANALYSIS-WINDOW evidence -- `[anchor, min(bar_bound, horizon_expiry)]`,
#   the same window the hypothetical ladder walks:
#     lapse_conflicted_sessions (a conflict RESOLVES to PASS, so a
#       streak-scoped tuple would DELETE the ambiguity RD required to be
#       surfaced the instant it was conservatively resolved),
#     lapse_qualifying_session and lapse_would_clear_session (the
#       counterfactual deliberately scans PAST the actual terminal).
#
# The consequence a reader must not be surprised by: a terminal card's ANALYSIS
# figures describe the analysis window, not the mandate's live life, so a filled
# latch can carry a would-clear session dated AFTER its fill. That is correct
# for calibration -- it is what the armed rule would have seen -- and the card
# labels it as analysis rather than history.
LATCH_LAPSE_DIAGNOSTIC_FIELDS = (
    "lapse_failed_sessions",
    "lapse_unverifiable_sessions",
    "lapse_unverifiable_causes",
    "lapse_conflicted_sessions",
    "lapse_failed_count",
    "lapse_unchecked_count",
    "lapse_unverifiable_tail",
    "directional_evaluable",
    "directional_block_reason",
    "lapse_qualifying_session",
    "lapse_would_clear_session",
)


@dataclass(frozen=True)
class LatchDerivation:
    """The whole read-only picture at one (horizon_session, derivation_session)."""

    latches: tuple[Latch, ...]
    degraded: tuple[DegradedFire, ...]
    derivation_session: date
    horizon_session: date
    horizon_sessions: int
    # Arc 21-G: the per-ticker `{session -> close}` map read from the on-disk
    # OHLCV archive -- the ONLY read-side source that DATES a close per row,
    # and one the derivation already loads for the invalidation walk.
    #
    # DELIBERATELY ANCHOR-INDEPENDENT, and that is load-bearing. The
    # invalidation walk's ELIGIBLE set is `[anchor, derivation_session]`, which
    # is EMPTY for a latch that fired tonight for tomorrow -- so a witness taken
    # from it could never corroborate the newest latch in the system, the one
    # the operator is about to act on. This map is keyed off the LOAD window
    # instead, which reaches back to `min(anchor, derivation_session)`.
    #
    # It DATES the persisted close; it never REPLACES it. The number the check
    # judges stays the number the cards render (21-A shown-equals-judged).
    archive_closes: Mapping[str, Mapping[date, float]] = field(
        default_factory=dict)
    # Per ticker, one of ARCHIVE_STATUSES. `unavailable` = the read RAISED (our
    # ignorance); `ok` = it completed, so an empty map is a FACT about the data.
    archive_status: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RestingOrder:
    """A live broker order reduced to what the latch join needs."""

    order_id: str
    ticker: str
    instruction: str
    quantity: float
    order_type: str
    limit_price: float | None
    stop_price: float | None
    status: str
    duration: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id:
            raise ValueError("order_id must be a non-empty str")
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError(f"ticker must be a non-blank str; got {self.ticker!r}")
        for name in ("limit_price", "stop_price"):
            val = getattr(self, name)
            if val is not None:
                _require_finite_number(name, val)

    @property
    def is_resting(self) -> bool:
        return self.status in RESTING_ORDER_STATUSES

    @property
    def is_indeterminate(self) -> bool:
        return self.status in INDETERMINATE_ORDER_STATUSES


@dataclass(frozen=True)
class LatchOrderJoin:
    """What the broker order book says about ONE latch."""

    latch_candidate_id: int
    orders: tuple[RestingOrder, ...] = ()
    order_stop_agrees: bool | None = None
    order_limit_agrees: bool | None = None
    indeterminate: bool = False
    # Resting BUY orders on this latch's ticker that match NO latch's frozen
    # prices. Carried SEPARATELY because a correctly-priced order must not be
    # able to hide a stray one: the agreement flags describe the MATCHED order,
    # so without this an extra mispriced order would render as all-clear.
    unmatched_orders: tuple[RestingOrder, ...] = ()
    # How many resting BUY orders were attributed to THIS latch (RD ruling
    # 2026-07-27, the multiplicity guard). The agreement flags above describe
    # ONE reference order, so above 1 the consumer must WITHHOLD the affirmative
    # all-clear: two stop-limits sharing the correct stop trigger but carrying
    # different caps BOTH match, so neither is `unmatched_orders`, and the
    # wrong-cap one rests at the broker completely uninspected. This is a COUNT,
    # deliberately: reporting per-order legs/agreement/alarms is a different
    # reporting model and is OUT of 21-A.
    matched_order_count: int = 0


@dataclass(frozen=True)
class OrderAlarm:
    """One of the two tier-1 order alarms (plan A.9)."""

    kind: str
    ticker: str
    latch_candidate_id: int | None
    detail: str
    severity: str
    # THE BROKER ORDER THIS ALARM IS ABOUT, STRUCTURALLY (auto-review MAJOR).
    # The stale-order alarm names an order id in its PROSE, and prose is not a
    # field: without this the panel cannot offer the per-order Cancel control the
    # plan's file manifest requires, so a `cancel` intent -- the row that carries
    # section G.4's EXACT linkage -- is unreachable in a browser and cancellation
    # decisions never enter the measurement ledger at all.
    #
    # `None` on LATCH_ARMED_NO_RESTING_ORDER, which is an alarm about the ABSENCE
    # of an order and has no id to carry.
    broker_order_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in LATCH_ORDER_ALARMS:
            raise ValueError(
                f"kind must be in {sorted(LATCH_ORDER_ALARMS)}; got {self.kind!r}")
        if self.severity not in {"critical", "warning"}:
            raise ValueError(
                f"severity must be critical|warning; got {self.severity!r}")


@dataclass(frozen=True)
class OrdersResolution:
    """The outcome of trying to read the live broker order book."""

    kind: str                      # ok | sandbox | not_configured | unavailable | error
    orders: tuple[RestingOrder, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        allowed = {"ok", "sandbox", "not_configured", "unavailable", "error"}
        if self.kind not in allowed:
            raise ValueError(f"kind must be in {sorted(allowed)}; got {self.kind!r}")
