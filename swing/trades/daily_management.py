"""Phase 8 daily-management service module — public API surface.

This module is the public-API namespace for daily_management consumers
(pipeline runner, web routes, dashboard view-models). It re-exports the
audit-trail invariants from ``swing.data.repos.daily_management`` so callers
have a single canonical import path:

  >>> from swing.trades.daily_management import (
  ...     compute_daily_approximate_snapshot,
  ...     upsert_snapshot,            # re-export from repo
  ...     SupersededRowImmutableException,  # re-export
  ...     OPERATION_REQUIRED_FIELDS,
  ...     validate_for_operation,
  ... )

Layout (per plan §B file map):

  * Pure helpers (compute_*) — see §E for verbatim formulas.
  * Vocabulary constants (DAILY_MGMT_*) — see §D.
  * OPERATION_REQUIRED_FIELDS + validate_for_operation — spec §3.1.1.
  * Service entry-points:
      - compute_daily_approximate_snapshot(...)
      - record_event_log(...)             [stub for T3.2]
      - tier_upgrade_to_intraday(...)     [V2 stub]

CLAUDE.md gotchas observed here:
  * Datetime impedance + lexicographic ordering — `created_at` is canonicalized
    to naive UTC ISO before stamping (Codex R1 Major #5 fix).
  * Per-row policy-versioned value stamping — `trail_MA_period_days` stamped
    only when SMA window is sufficient; coherently NULL together with
    `trail_MA_candidate_price` when archive history is insufficient.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# Re-exports from the repo module so consumers may continue to import the
# audit-trail invariants from the public-API namespace (T2.3 carry-forward).
from swing.data.repos.daily_management import (
    DAILY_MGMT_PRECISION_RANK,
    SupersededRowImmutableException,
    TierOrderingError,
    insert_event_log,
    insert_snapshot,
    list_for_trade_timeline,
    list_open_position_active_snapshots,
    select_active_snapshot,
    select_history,
    tier_upgrade_snapshot,
    upsert_snapshot,
)

__all__ = [
    # Vocabulary constants:
    "DAILY_MGMT_PRECISION_LEVELS",
    "DAILY_MGMT_PRECISION_RANK",
    "DAILY_MGMT_MATURITY_STAGES",
    "DAILY_MGMT_ACTION_TAKEN_VALUES",
    "DAILY_MGMT_THESIS_STATUSES",
    "DAILY_MGMT_THESIS_UNRECORDED_SENTINEL",
    "DAILY_MGMT_EMOTIONAL_STATES",
    "DAILY_MGMT_VOLUME_BEHAVIORS",
    "DAILY_MGMT_RELATIVE_STRENGTH_STATUSES",
    # Validators + exceptions:
    "OPERATION_REQUIRED_FIELDS",
    "validate_for_operation",
    "ValidationException",
    "SupersededRowImmutableException",
    "TierOrderingError",
    # Request models:
    "EventLogRequest",
    # Pure helpers:
    "compute_maturity_stage",
    "compute_trail_MA_eligibility_flag",
    "compute_open_R_effective",
    "compute_position_capital_utilization",
    "compute_position_portfolio_heat",
    "compute_running_extrema_R",
    "resolve_thesis_status",
    # Service entry-points:
    "compute_daily_approximate_snapshot",
    "record_event_log",
    "tier_upgrade_to_intraday",
    # Re-exported repo API:
    "insert_snapshot",
    "insert_event_log",
    "select_active_snapshot",
    "select_history",
    "list_for_trade_timeline",
    "list_open_position_active_snapshots",
    "upsert_snapshot",
    "tier_upgrade_snapshot",
]


# ---------------------------------------------------------------------------
# Vocabulary constants (plan §D)
# ---------------------------------------------------------------------------

DAILY_MGMT_PRECISION_LEVELS: tuple[str, str, str] = (
    "daily_approximate", "intraday_estimated", "intraday_exact",
)

DAILY_MGMT_MATURITY_STAGES: tuple[str, str, str] = (
    "pre_+1.5R", "+1.5R_to_+2R", ">=+2R_trail_eligible",
)

DAILY_MGMT_ACTION_TAKEN_VALUES: tuple[str, ...] = (
    "hold", "trim", "exit", "stop", "move_stop", "no_action",
)

DAILY_MGMT_THESIS_STATUSES: tuple[str, str, str] = (
    "intact", "weakening", "invalidated",
)

# Spec §3.1 + §5.6 R3 Major #4: closed/reviewed trades with no event_log
# thesis update read out as the sentinel "unrecorded" (NOT "intact"). This
# preserves audit-trail veracity — we never claim the operator confirmed a
# closed-trade thesis when no commentary was recorded.
DAILY_MGMT_THESIS_UNRECORDED_SENTINEL: str = "unrecorded"

# Phase 7 entry vocabulary mirror — Phase 7 spec §entry §emotional_state_pre_trade.
DAILY_MGMT_EMOTIONAL_STATES: tuple[str, ...] = (
    "calm", "confident", "anxious", "fomo", "revenge",
    "hopeful", "doubtful", "distracted",
)

DAILY_MGMT_VOLUME_BEHAVIORS: tuple[str, ...] = (
    "confirming", "neutral", "distribution", "fading",
)

DAILY_MGMT_RELATIVE_STRENGTH_STATUSES: tuple[str, ...] = (
    "improving", "flat", "weakening",
)


# ---------------------------------------------------------------------------
# Exceptions (service-layer)
# ---------------------------------------------------------------------------


class ValidationException(Exception):  # noqa: N818  -- shape locked by spec §3.1.1 contract
    """Raised by service-layer entry-points when ``validate_for_operation``
    reports missing required fields. Repo-layer trusts validated input;
    service callers MUST catch this above the upsert/insert call."""


# ---------------------------------------------------------------------------
# Operation-contextual validation (spec §3.1.1)
# ---------------------------------------------------------------------------


OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    # All 14 position-state fields REQUIRED non-null for a snapshot row.
    # ``trail_MA_candidate_price`` and ``trail_MA_period_days`` are NOT in
    # this set: they may be NULL coherently when archive history is
    # insufficient (cross-field constraint enforced separately by the
    # service that emits the snapshot).
    "snapshot_emit": (
        "current_price",
        "current_stop",
        "current_size",
        "current_avg_cost",
        "open_R_effective",
        "open_MFE_R_to_date",
        "open_MAE_R_to_date",
        "intraday_high",
        "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage",
        "trail_MA_eligibility_flag",
    ),
    # event_log decouples from position-state per R1 Critical #1 fix.
    # ``thesis_status`` is OPTIONAL per R2 Major #4 fix.
    # Conditional requirements (stop_change_reason / prior_stop / new_stop /
    # linked_trade_event_id when stop_changed=1; action_reason when
    # action_taken not in ('no_action', NULL)) are enforced by the service
    # layer in T3.2, not by this validator.
    "event_log_emit": (
        "stop_changed",
        "action_taken",
        "rule_violation_suspected",
        "emotional_state",
    ),
    # Tier-upgrade replaces an active snapshot at a higher precision tier;
    # the same 14 position-state fields are required (mirrors snapshot_emit).
    "tier_upgrade": (
        "current_price",
        "current_stop",
        "current_size",
        "current_avg_cost",
        "open_R_effective",
        "open_MFE_R_to_date",
        "open_MAE_R_to_date",
        "intraday_high",
        "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage",
        "trail_MA_eligibility_flag",
    ),
}


def validate_for_operation(
    req: dict[str, Any] | Any,
    *,
    op: Literal["snapshot_emit", "event_log_emit", "tier_upgrade"],
) -> list[str]:
    """Returns missing-field names for the given operation; empty list if valid.

    Treats ``None`` and "key absent" identically as missing. Numeric ``0`` /
    ``0.0`` and empty-string-but-key-present do NOT count as missing — those
    are legitimate position-state values (e.g. ``open_MFE_R_to_date == 0.0``
    is a valid early-trade state, not "we forgot to set it").

    Accepts either a ``dict[str, Any]`` (used by snapshot-emit callers
    constructing the field dict directly) OR an object with attribute-access
    semantics (used by ``record_event_log`` passing an ``EventLogRequest``
    dataclass instance).
    """
    if op not in OPERATION_REQUIRED_FIELDS:
        raise ValueError(
            f"unknown op {op!r}; expected one of "
            f"{tuple(OPERATION_REQUIRED_FIELDS)}"
        )
    required = OPERATION_REQUIRED_FIELDS[op]
    if isinstance(req, dict):
        return [f for f in required if req.get(f) is None]
    return [f for f in required if getattr(req, f, None) is None]


# ---------------------------------------------------------------------------
# Request models (T3.2 — EventLogRequest)
# ---------------------------------------------------------------------------


@dataclass
class EventLogRequest:
    """Operator-emitted event_log request payload (T3.2 + spec §3.1.1).

    Mirrors the daily_management_records ``record_type='event_log'`` row
    shape: position-state OPTIONAL (the operator is logging a free-form
    event, not committing to a fresh snapshot); operator-input fields
    REQUIRED per ``OPERATION_REQUIRED_FIELDS["event_log_emit"]``.

    Carries the four metadata columns required by the table's NOT NULL
    constraints (``review_date``, ``data_asof_session``, ``created_at``,
    ``mfe_mae_precision_level``) so the dataclass round-trips cleanly into
    ``insert_event_log``'s ``event_log_fields`` dict via :meth:`to_dict`.

    The web POST handler (T-web in this phase) constructs an instance from
    the form payload; the CLI is a V2 follow-up per plan §A.2.
    """

    # Identity + metadata (NOT NULL on the underlying table):
    trade_id: int
    review_date: str
    data_asof_session: str
    created_at: str
    mfe_mae_precision_level: str  # CHECK enum at the schema layer

    # Required operator-input (per OPERATION_REQUIRED_FIELDS["event_log_emit"]):
    stop_changed: int = 0
    action_taken: str | None = None
    rule_violation_suspected: int = 0
    emotional_state: str | None = None  # JSON-encoded list per spec §D

    # Conditionally-required when stop_changed=1:
    prior_stop: float | None = None
    new_stop: float | None = None
    stop_change_reason: str | None = None

    # Conditionally-required when action_taken NOT IN ('no_action', None):
    action_reason: str | None = None

    # Optional context columns:
    pipeline_run_id: int | None = None
    thesis_status: str | None = None
    volume_behavior: str | None = None
    relative_strength_status: str | None = None
    market_regime_change: str | None = None
    sector_condition_change: str | None = None
    news_or_event_update: str | None = None
    management_notes: str | None = None
    # Position-state — OPTIONAL per spec §3.1.1 R1 Critical 1:
    current_price: float | None = None
    current_stop: float | None = None
    current_size: float | None = None
    current_avg_cost: float | None = None
    open_R_effective: float | None = None  # noqa: N815  -- name locked by schema column
    open_MFE_R_to_date: float | None = None  # noqa: N815  -- name locked by schema column
    open_MAE_R_to_date: float | None = None  # noqa: N815  -- name locked by schema column
    intraday_high: float | None = None
    intraday_low: float | None = None
    position_capital_utilization_pct: float | None = None
    position_capital_denominator_dollars: float | None = None
    position_portfolio_heat_contribution_dollars: float | None = None
    maturity_stage: str | None = None
    trail_MA_candidate_price: float | None = None  # noqa: N815  -- name locked by schema
    trail_MA_period_days: int | None = None  # noqa: N815  -- name locked by schema
    trail_MA_eligibility_flag: int | None = None  # noqa: N815  -- name locked by schema

    def to_dict(self) -> dict[str, Any]:
        """Return the dataclass as a plain dict suitable for splat into
        ``insert_event_log``'s ``event_log_fields`` argument."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Pure helpers (plan §E — formulas verbatim from spec §1.5 + §6.6)
# ---------------------------------------------------------------------------


def compute_maturity_stage(open_MFE_R_to_date: float | None) -> str | None:  # noqa: N803
    """Spec §1.5 + §3.1 thresholds. NULL passes through (insufficient data)."""
    if open_MFE_R_to_date is None:
        return None
    if open_MFE_R_to_date < 1.5:
        return "pre_+1.5R"
    if open_MFE_R_to_date < 2.0:
        return "+1.5R_to_+2R"
    return ">=+2R_trail_eligible"


def compute_trail_MA_eligibility_flag(  # noqa: N802  -- name preserved for spec §3.1 cross-ref
    *,
    maturity_stage: str | None,
    trail_MA_candidate_price: float | None,  # noqa: N803
    current_stop: float | None,
) -> int | None:
    """Spec §3.1: 1 IFF maturity_stage='>=+2R_trail_eligible' AND
    trail_MA_candidate_price IS NOT NULL AND current_stop < trail_MA_candidate_price.

    Returns NULL when any of the three inputs is NULL (insufficient data —
    operator-actionable signal that the trail-MA suggestion cannot be
    evaluated this session).
    """
    if maturity_stage is None or trail_MA_candidate_price is None or current_stop is None:
        return None
    if maturity_stage != ">=+2R_trail_eligible":
        return 0
    if current_stop < trail_MA_candidate_price:
        return 1
    return 0


def compute_open_R_effective(  # noqa: N802  -- name preserved for spec §3.1 cross-ref
    *,
    current_price: float,
    current_avg_cost: float,
    current_size: float,
    planned_risk_budget_dollars: float,
) -> float:
    """Spec §2 risk-denominator + §3.1 column definition.

    open_R_effective = (current_price - current_avg_cost) * current_size
                      / planned_risk_budget_dollars

    Caller resolves planned_risk_budget_dollars via Phase 7's pre-trade-locked
    derivation: (entry_price - initial_stop) * initial_shares.
    """
    if planned_risk_budget_dollars == 0:
        # Should be impossible per Phase 7 invariants; defensive.
        raise ValueError("planned_risk_budget_dollars cannot be zero")
    return (
        (current_price - current_avg_cost) * current_size
        / planned_risk_budget_dollars
    )


def compute_position_capital_utilization(
    *,
    current_size: float,
    current_price: float,
    denominator_dollars: float,
) -> float:
    """Spec §3.1 + §10.5: V1 denominator = capital_floor_constant_dollars (7500.0).

    Returned as a proportion (0.0 to 1.0+; values >1 indicate over-utilization
    against the floor, which is the operator-actionable signal).
    """
    if denominator_dollars <= 0:
        raise ValueError("denominator_dollars must be > 0")
    return (current_size * current_price) / denominator_dollars


def compute_position_portfolio_heat(
    *,
    current_avg_cost: float,
    current_stop: float,
    current_size: float,
) -> float:
    """Spec §3.1: max(0, (current_avg_cost - current_stop) * current_size).

    Non-negative magnitude per the spec convention (slippage convention).
    """
    return max(0.0, (current_avg_cost - current_stop) * current_size)


def compute_running_extrema_R(  # noqa: N802  -- name preserved for spec §1.5 cross-ref
    ohlcv_df: pd.DataFrame,
    *,
    anchor_session: date,
    asof_session: date,
    entry_price: float,
    initial_stop: float,
) -> tuple[float, float]:
    """Spec §1.5 daily_approximate formulas. Returns (MFE_R, MAE_R) over
    sessions [anchor_session, asof_session] inclusive; both clamped to
    non-negative per spec §2 adverse-positive convention.

    MFE_R = max((High - entry_price) / risk_per_share) over window; min 0.
    MAE_R = max((entry_price - Low)  / risk_per_share) over window; min 0.

    Both default to 0.0 when the window is empty.
    """
    risk_per_share = entry_price - initial_stop
    if risk_per_share == 0:
        raise ValueError("risk_per_share cannot be zero")
    mask = (
        (ohlcv_df.index.date >= anchor_session)
        & (ohlcv_df.index.date <= asof_session)
    )
    window = ohlcv_df.loc[mask]
    if window.empty:
        return 0.0, 0.0
    mfe = max(0.0, float((window["High"].max() - entry_price) / risk_per_share))
    mae = max(0.0, float((entry_price - window["Low"].min()) / risk_per_share))
    return mfe, mae


def resolve_thesis_status(
    *,
    trade_state: str,
    latest_thesis_in_event_log: str | None,
) -> str:
    """Spec §3.1 + §5.6 R3 Major 4 fix: closed/reviewed trades with no
    event_log thesis update return sentinel ``unrecorded``; open trades
    default to ``intact``. If event_log has a non-NULL value, that overrides
    defaults.
    """
    if latest_thesis_in_event_log is not None:
        return latest_thesis_in_event_log
    if trade_state in ("closed", "reviewed"):
        return DAILY_MGMT_THESIS_UNRECORDED_SENTINEL
    # 'entered' / 'managing' / 'partial_exited':
    return "intact"


# ---------------------------------------------------------------------------
# Service entry-point: compute_daily_approximate_snapshot
# ---------------------------------------------------------------------------


def compute_daily_approximate_snapshot(  # noqa: PLR0913  -- spec-locked signature
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    asof_session: date,
    run_now: datetime,
    ohlcv_archive_dir: Path,
    archive_history_days: int,
    pipeline_run_id: int | None,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,  # noqa: N803  -- name locked by spec §6.6
) -> dict[str, Any] | None:
    """Spec §4.1 step body — emit a daily_approximate snapshot row's field dict.

    Returns a dict suitable for ``upsert_snapshot``, OR ``None`` if the
    OHLCV archive returns no data for this ticker (operator-actionable
    signal that the ticker is delisted/invalid; pipeline runner logs and
    skips per the cadence-step semantics).

    Caller responsibilities:
      * Pass ``run_now`` from a session-anchored helper. Both naive and
        aware datetimes are accepted — aware inputs are canonicalized to
        naive UTC before stamping ``created_at`` (preserves the
        lexicographic-ordering invariant on the TEXT column per spec §8.4
        + Codex R1 Major #5 fix).
      * Run service-layer ``validate_for_operation`` is performed BY this
        function before returning. Repo-layer ``upsert_snapshot`` re-runs
        validation defensively, but failing-fast here gives the caller a
        clean ValidationException without an in-flight transaction.

    Raises:
        ValueError: if the trade does not exist.
        ValidationException: if the constructed field dict is missing any
            ``snapshot_emit`` required field (should be impossible given the
            full-path computation; defensive guard for refactor-time
            regressions).
    """
    # Lazy imports to avoid circular references at module load time:
    from swing.data.ohlcv_archive import read_or_fetch_archive
    from swing.data.repos.trades import get_trade

    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")

    df = read_or_fetch_archive(
        trade.ticker,
        end_date=asof_session,
        cache_dir=ohlcv_archive_dir,
        archive_history_days=archive_history_days,
    )
    if df is None or df.empty:
        return None

    # Slice to >= pre_trade_locked_at_session (the anchor for MFE/MAE running
    # extrema) AND <= asof_session.
    anchor = date.fromisoformat(trade.pre_trade_locked_at[:10])
    window_mask = (df.index.date >= anchor) & (df.index.date <= asof_session)
    window = df.loc[window_mask]
    if window.empty:
        return None

    asof_mask = df.index.date == asof_session
    asof_rows = df.loc[asof_mask]
    if asof_rows.empty:
        return None

    current_price = float(asof_rows["Close"].iloc[-1])
    intraday_high = float(asof_rows["High"].iloc[-1])
    intraday_low = float(asof_rows["Low"].iloc[-1])

    open_MFE_R, open_MAE_R = compute_running_extrema_R(  # noqa: N806
        df,
        anchor_session=anchor,
        asof_session=asof_session,
        entry_price=trade.entry_price,
        initial_stop=trade.initial_stop,
    )

    planned_risk_budget = (
        (trade.entry_price - trade.initial_stop) * trade.initial_shares
    )
    open_R_effective = compute_open_R_effective(  # noqa: N806
        current_price=current_price,
        current_avg_cost=trade.current_avg_cost
            if trade.current_avg_cost is not None
            else trade.entry_price,
        current_size=trade.current_size,
        planned_risk_budget_dollars=planned_risk_budget,
    )
    cap_util = compute_position_capital_utilization(
        current_size=trade.current_size,
        current_price=current_price,
        denominator_dollars=capital_floor_dollars,
    )
    heat = compute_position_portfolio_heat(
        current_avg_cost=trade.current_avg_cost
            if trade.current_avg_cost is not None
            else trade.entry_price,
        current_stop=trade.current_stop,
        current_size=trade.current_size,
    )
    maturity_stage = compute_maturity_stage(open_MFE_R)

    # 21-day SMA of close at asof_session. Slice to all sessions <= asof_session
    # so we have the full SMA window available; tail() takes the most recent
    # ``trail_MA_period_days_default`` rows. Coherent NULL pair when the
    # archive history is insufficient (per-row stamp follows: spec §6.6).
    sma_slice = df.loc[df.index.date <= asof_session].tail(
        trail_MA_period_days_default,
    )
    if len(sma_slice) < trail_MA_period_days_default:
        trail_MA_candidate_price: float | None = None  # noqa: N806
        trail_MA_period_days_stamp: int | None = None  # noqa: N806
    else:
        trail_MA_candidate_price = float(sma_slice["Close"].mean())  # noqa: N806
        trail_MA_period_days_stamp = trail_MA_period_days_default  # noqa: N806

    trail_MA_eligibility_flag = compute_trail_MA_eligibility_flag(  # noqa: N806
        maturity_stage=maturity_stage,
        trail_MA_candidate_price=trail_MA_candidate_price,
        current_stop=trade.current_stop,
    )

    # Naive UTC ISO datetime per spec §8.4 + Codex R1 Major #5 fix.
    # Aware inputs (any tz) are canonicalized to naive UTC; naive inputs
    # pass through as-is (microseconds stripped for stable comparison).
    if run_now.tzinfo is not None:
        run_now_naive_utc = (
            run_now.astimezone(UTC).replace(tzinfo=None, microsecond=0)
        )
    else:
        run_now_naive_utc = run_now.replace(microsecond=0)
    created_at = run_now_naive_utc.isoformat()
    # Defensive assertion — fail fast if canonicalization didn't strip tz.
    # CHECK constraint at the schema doesn't enforce naive-only on TEXT;
    # the validator does. Failing here is preferable to silent persistence
    # of an offset-suffixed timestamp that breaks lexicographic ordering.
    assert "+" not in created_at and "Z" not in created_at, (
        f"created_at must be naive (no offset): got {created_at!r}"
    )

    fields: dict[str, Any] = {
        "review_date": asof_session.isoformat(),
        "data_asof_session": asof_session.isoformat(),
        "created_at": created_at,
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": pipeline_run_id,
        "current_price": current_price,
        "current_stop": trade.current_stop,
        "current_size": trade.current_size,
        "current_avg_cost": (
            trade.current_avg_cost
            if trade.current_avg_cost is not None
            else trade.entry_price
        ),
        "open_R_effective": open_R_effective,
        "open_MFE_R_to_date": open_MFE_R,
        "open_MAE_R_to_date": open_MAE_R,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,
        "position_capital_utilization_pct": cap_util,
        "position_capital_denominator_dollars": capital_floor_dollars,
        "position_portfolio_heat_contribution_dollars": heat,
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": trail_MA_candidate_price,
        "trail_MA_period_days": trail_MA_period_days_stamp,
        "trail_MA_eligibility_flag": trail_MA_eligibility_flag,
    }

    # Defensive validator pass — service callers see a clean
    # ValidationException above the upsert/insert call rather than discovering
    # a missing field deep inside the repo's INSERT.
    #
    # Coherent-NULL exception per spec §3.1.1: when ``trail_MA_candidate_price``
    # is NULL (archive history insufficient), the eligibility flag is
    # coherently NULL too. Both are legitimately absent for the early life of
    # a position; the validator must NOT flag this as missing.
    missing = validate_for_operation(fields, op="snapshot_emit")
    if (
        trail_MA_candidate_price is None
        and "trail_MA_eligibility_flag" in missing
    ):
        missing = [m for m in missing if m != "trail_MA_eligibility_flag"]
    if missing:
        raise ValidationException(
            f"compute_daily_approximate_snapshot missing required fields: {missing}"
        )

    return fields


# ---------------------------------------------------------------------------
# Service entry-point: record_event_log (T3.2 — single-transaction §A.1)
# ---------------------------------------------------------------------------


def record_event_log(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    req: EventLogRequest,
) -> int:
    """Single-transaction contract per spec §4.4 + plan §A.1.

    All side-effects in one ``with conn:`` deferred-mode transaction. If ANY
    step fails, ALL roll back (no partial state where Phase 7 stop_adjust
    event exists without Phase 8 event_log row, OR vice versa).

    Steps:

      0. Validate ``req`` against ``OPERATION_REQUIRED_FIELDS["event_log_emit"]``
         AND conditional validators (stop_changed=1 implies prior_stop +
         new_stop + stop_change_reason; action_taken NOT IN ('no_action',
         None) implies action_reason).
      1. Open deferred-mode transaction (``with conn:``).
      2. If ``req.stop_changed=1``: re-read trade state inside transaction;
         reject no-op stops (``new_stop == current_stop``); reject stale
         forms (``prior_stop != current_stop``); call REPO-LEVEL
         :func:`swing.data.repos.trades.update_stop_with_event` (NOT the
         service-level wrapper at :mod:`swing.trades.stop_adjust`, which
         opens its own ``with conn:`` block and would prematurely commit
         the outer transaction — see plan §A.1); resolve
         ``linked_trade_event_id`` via TRADE-SCOPED max-id-after-insert.
      3. INSERT event_log row via :func:`insert_event_log`.
      4. If ``trade.state == 'entered'``: call
         :func:`swing.trades.state.state_transition` to flip → 'managing'.

    Returns:
        ``management_record_id`` of the inserted event_log row.

    Raises:
        ValidationException — missing required fields per spec §3.1.1, or
            no-op stop (Codex R1 M4), or stale prior_stop (Codex R4 M2).
        ValueError — Phase 7 service rejects (e.g., trade not found,
            terminal state).

    §A.1 binding contract: this function calls the REPO-LEVEL update_stop
    function (``swing.data.repos.trades:update_stop_with_event``), NOT the
    service-level one (``swing.trades.stop_adjust:update_stop_with_event``).
    The service-level wrapper opens its own ``with conn:`` block which
    would commit prematurely inside the outer single-transaction. Future
    maintainers MUST NOT consolidate the two call paths — the asymmetry
    is intentional. (See plan §A.1 + spec §4.4.)

    Transaction contract (Codex R3 Major #1 + R4 Major #1; spec §4.4):
    the function opens a ``BEGIN IMMEDIATE`` transaction up front so the
    validation read of ``trades.current_stop`` is taken under a RESERVED
    lock — no concurrent writer can mutate the row between the stale-form
    check and the ``repo_update_stop_with_event`` write. The function
    ALWAYS owns its transaction boundary (BEGIN IMMEDIATE / COMMIT on
    success / ROLLBACK on exception); callers MUST NOT pass a connection
    with an open transaction (no wrapping ``with conn:`` block, no prior
    ``conn.execute('BEGIN ...')``). Entry guard raises ``RuntimeError`` if
    ``conn.in_transaction`` is True at entry — the earlier "nested-call
    safety" branch (R3 Major #1) was speculative and re-introduced the
    DEFERRED-caller race the IMMEDIATE-mode fix was meant to close (R4
    Major #1; chose Option A — reject — over Option B — SAVEPOINT — because
    no real caller needs the nested form).
    """
    # Lazy imports to avoid module-load circulars + give monkeypatch surface:
    from swing.data.repos.trades import get_trade
    from swing.data.repos.trades import (
        update_stop_with_event as repo_update_stop_with_event,
    )
    from swing.trades.state import state_transition

    # Step 0 — validate required fields:
    missing = validate_for_operation(req, op="event_log_emit")
    if missing:
        raise ValidationException(
            f"missing required fields: {missing}"
        )
    # Conditional validators:
    if req.stop_changed and (
        not req.stop_change_reason
        or not req.stop_change_reason.strip()
        or req.prior_stop is None
        or req.new_stop is None
    ):
        raise ValidationException(
            "stop_changed=1 requires prior_stop, new_stop, stop_change_reason"
        )
    # action_reason required only for STATE-CHANGING actions (move_stop /
    # trim / exit / stop). 'hold' and 'no_action' are inert observations
    # that do not require operator justification — matches the plan's
    # discriminating regression test (test_record_event_log_no_stop_change
    # passes action_taken='hold' with action_reason=None).
    action_reason_exempt = (None, "no_action", "hold")
    if req.action_taken not in action_reason_exempt and (
        not req.action_reason or not req.action_reason.strip()
    ):
        raise ValidationException(
            "action_taken NOT IN ('no_action', 'hold', None) requires action_reason"
        )

    # Step 1 — open IMMEDIATE-mode transaction (Codex R3 Major #1 + R4 Major
    # #1 fix; spec §4.4: "BEGIN IMMEDIATE / COMMIT"). The default sqlite3
    # ``with conn:`` block opens a DEFERRED transaction — locks are not
    # acquired until the first WRITE statement, so the validation read of
    # ``trades.current_stop`` below could pass while another writer mutates
    # the row before our ``repo_update_stop_with_event`` call reaches the
    # lock manager. BEGIN IMMEDIATE acquires the RESERVED lock up front,
    # blocking concurrent writers for the full validation+write sequence.
    #
    # Codex R4 Major #1 fix (Option A — reject caller-held transactions):
    # the earlier ``in_transaction``-aware branch (R3 Major #1's "nested-call
    # safety" guard) re-introduced the very race the BEGIN-IMMEDIATE fix was
    # meant to close — a DEFERRED caller transaction would let the validation
    # read above happen without a write lock, and a late failure inside this
    # function could leak partial state out via the caller's later commit.
    # Refuse the unsafe contract outright: callers MUST NOT pass a connection
    # with an open transaction. The single production caller
    # (``swing.web.routes.trades.daily_management_event_post``) opens a fresh
    # connection without a wrapping ``with conn:`` block; the cadence-step
    # service (``compute_daily_approximate_snapshot``) doesn't call this
    # function at all.
    if conn.in_transaction:
        raise RuntimeError(
            "record_event_log requires a connection with no open transaction; "
            "the caller MUST NOT wrap the call in `with conn:` or otherwise "
            "issue BEGIN before calling. The function manages its own "
            "BEGIN IMMEDIATE / COMMIT / ROLLBACK boundary (Codex R4 Major #1)."
        )
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read trade state for the entered→managing decision (per §5.2):
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise ValueError(f"trade {trade_id} not found")

        # Codex R2 Major #1 fix: write-path active-state guard. The UI hides
        # the form for closed/reviewed trades (R1 Major #2 fix) but a direct
        # POST or future programmatic caller can otherwise reach the
        # ``stop_changed=0`` branch and pollute closed-trade timelines (the
        # repo-level ``update_stop_with_event`` guard only fires on the
        # ``stop_changed=1`` path). Reject here BEFORE branching so both
        # paths share the same active-state contract that mirrors
        # ``swing.trades.exit._ACTIVE_STATES``.
        _active_states = frozenset({"entered", "managing", "partial_exited"})
        if trade.state not in _active_states:
            raise ValidationException(
                f"trade {trade_id} not active (state={trade.state!r}); "
                f"event_log emission only permitted from "
                f"{sorted(_active_states)}"
            )

        # Step 2 — Phase 7 stop-adjust (REPO-LEVEL per §A.1):
        linked_event_id: int | None = None
        if req.stop_changed:
            # Codex R1 Major #4 fix: reject no-op stops at the validator
            # boundary BEFORE invoking the repo call. The repo-level
            # update_stop_with_event returns EARLY without inserting when
            # trade.current_stop == new_stop; a subsequent
            # last_insert_rowid() / max-id capture would mis-link to a
            # stale prior trade_events row.
            if req.new_stop == trade.current_stop:
                raise ValidationException(
                    f"stop_changed=1 but new_stop={req.new_stop!r} equals "
                    f"current trades.current_stop={trade.current_stop!r}; "
                    "no-op stop change is invalid for event_log emission"
                )
            # Codex R4 Major #2 fix: stale-form guard. The web form
            # pre-fills `prior_stop` from a snapshot or trades-row reading
            # PRIOR to the POST. If another stop_adjust raced ahead between
            # form-render and POST, the form's prior_stop is STALE and
            # persisting it would diverge from Phase 7's
            # trade_events.payload_json (which records the actual
            # at-time-of-mutation old_stop). Re-read inside the transaction
            # and reject mismatches:
            if req.prior_stop != trade.current_stop:
                raise ValidationException(
                    f"req.prior_stop={req.prior_stop!r} does not match "
                    f"current trades.current_stop={trade.current_stop!r} — "
                    "stale form (a stop_adjust raced between render and "
                    "POST); operator should reload + re-submit"
                )
            # Capture trade_events.id BEFORE invoking — we use the
            # TRADE-SCOPED max-id-after-insert technique (Codex R2 Major #3
            # fix: globally-scoped MAX(id) compared against trade-scoped
            # MAX(id) would mis-fire when another trade has a higher prior
            # event id). Both queries scope to (trade_id = ?) so the
            # comparison is arithmetically valid:
            pre_max_event_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM trade_events "
                "WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()[0]
            repo_update_stop_with_event(
                conn,
                trade_id=trade_id,
                new_stop=req.new_stop,
                event_ts=req.created_at,  # naive UTC ISO datetime
                rationale=req.stop_change_reason,
            )
            # Resolve the freshly-inserted trade_events row by querying for
            # the max id NEW since pre-call (same trade_id scope). Both
            # queries run inside the outer transaction so the max value is
            # consistent. The repo-level update_stop_with_event ALWAYS
            # inserts when new != current (the no-op pre-validation above
            # guarantees the non-no-op path):
            new_max = conn.execute(
                "SELECT MAX(id) FROM trade_events WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()[0]
            assert new_max is not None and new_max > pre_max_event_id, (
                f"expected trade_events INSERT for trade_id={trade_id!r} "
                f"but got new_max={new_max!r}, "
                f"pre_max={pre_max_event_id!r} — repo-level "
                "update_stop_with_event did not insert as expected; "
                "investigate Phase 7 contract."
            )
            linked_event_id = int(new_max)

        # Step 3 — INSERT event_log row:
        event_log_fields: dict[str, Any] = {
            **req.to_dict(),
            "linked_trade_event_id": linked_event_id,
        }
        management_record_id = insert_event_log(
            conn, trade_id=trade_id, event_log_fields=event_log_fields,
        )

        # Step 4 — entered→managing transition (per spec §5.2):
        if trade.state == "entered":
            state_transition(
                conn,
                trade_id=trade_id,
                new_state="managing",
                event_ts=req.created_at,
                rationale="first_daily_management_record",
            )
    except Exception:
        # On ANY exception roll back the transaction we opened. Codex R4
        # Major #1: we ALWAYS own the boundary (the entry guard above
        # rejects caller-held transactions outright).
        conn.rollback()
        raise
    else:
        conn.commit()

    return management_record_id


# ---------------------------------------------------------------------------
# Service entry-point: tier_upgrade_to_intraday (V2 stub)
# ---------------------------------------------------------------------------


def tier_upgrade_to_intraday(*args: Any, **kwargs: Any) -> int:
    """V2 entry point — gated on intraday data source per spec §10.7.

    V1 ships ``daily_approximate`` only; the schema reserves ``intraday_estimated``
    and ``intraday_exact`` enum values plus the 6-step transactional
    tier-upgrade path (exercised at V1 via direct repo-level
    ``tier_upgrade_snapshot`` calls — see T2.3 tests). This service-layer
    facade is a placeholder that surfaces a clear NotImplementedError until
    Phase B (Schwab API intraday ingestion) wires real intraday tier emitters.
    """
    raise NotImplementedError("V2: gated on Schwab API Phase B intraday ingestion")
