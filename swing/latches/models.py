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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class LatchDerivation:
    """The whole read-only picture at one (horizon_session, derivation_session)."""

    latches: tuple[Latch, ...]
    degraded: tuple[DegradedFire, ...]
    derivation_session: date
    horizon_session: date
    horizon_sessions: int


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


@dataclass(frozen=True)
class OrderAlarm:
    """One of the two tier-1 order alarms (plan A.9)."""

    kind: str
    ticker: str
    latch_candidate_id: int | None
    detail: str
    severity: str

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
