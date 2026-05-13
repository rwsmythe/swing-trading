"""Spec §3.5 maturity-stage metric computations (plan §G Task D.3).

Computes per-open-position maturity-stage rows for the §4.5 dashboard
surface. Consumes Phase 8 ``daily_management_records.list_open_position_active_snapshots``
+ trade ``planned_target_R`` column.

Per spec §3.5 R1 M5 + §6.1: ``trail_MA_candidate_price`` + ``planned_target_R``
shipped at Phase 8; when NULL on a row (legacy / non-target trade), the
field is None and the template renders ``"—"`` placeholder per
spec §4.5 acceptance.

Per spec §3.5: ``trail_MA_eligibility_flag = open_MFE_R_to_date >= +2.0R AND
current_stop < trail_MA_candidate_price``. Returns None (NOT False) when
``trail_MA_candidate_price`` is NULL — operator cannot evaluate eligibility
without the MA reference per plan §G T-D.3 discriminating test acceptance.

Per plan §A.6 + §I.4 BINDING: ``position_capital_utilization_pct`` carries
a dynamic PROVISIONAL/LIVE badge per the row's resolution-asof (the
snapshot's ``data_asof_session`` when present, else
``last_completed_session(now)``). Forward-looking
``action_session_for_run(now)`` MUST NOT be used (plan §A.15).
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from swing.data.repos.daily_management import (
    list_open_position_active_snapshots,
)
from swing.evaluation.dates import last_completed_session
from swing.metrics.equity_resolver import (
    resolve_live_capital_denominator_dollars,
)
from swing.metrics.policy import read_live_policy

# Trail-MA eligibility threshold per spec §3.5 + Tier-3 doctrine.
TRAIL_MA_ELIGIBILITY_MFE_R_THRESHOLD: float = 2.0

# Stage rendering order per spec §4.5 (lower number = earlier in table).
_STAGE_ORDER: dict[str, int] = {
    "pre_+1.5R": 0, "+1.5R_to_+2R": 1, ">=+2R_trail_eligible": 2,
    "closed": 3,
}


@dataclass(frozen=True)
class MaturityStageRow:
    """One per-position row for the §4.5 maturity-stage surface."""

    trade_id: int
    ticker: str
    maturity_stage: str | None  # spec §3.5 enum or None when snapshot absent

    # MFE/MAE since pre_trade_locked_at, in R-multiples (from snapshot).
    open_MFE_R_to_date: float | None  # noqa: N815
    open_MAE_R_to_date: float | None  # noqa: N815

    # Live trade state.
    current_stop: float | None
    planned_target_R: float | None  # noqa: N815  — None for legacy / non-target

    # Trail-MA candidate (Phase 8 capture; None when not yet captured).
    trail_MA_candidate_price: float | None  # noqa: N815
    trail_MA_eligibility_flag: bool | None  # noqa: N815 — None when undefined

    # Capital-utilization (dynamic PROVISIONAL/LIVE per row).
    position_capital_utilization_pct: float | None  # PERCENT
    position_portfolio_heat_contribution_dollars: float | None
    capital_denominator_badge: Literal["PROVISIONAL", "LIVE"]

    def __post_init__(self) -> None:
        if self.trade_id < 1:
            raise ValueError(
                f"trade_id must be >= 1; got {self.trade_id!r}"
            )
        if not self.ticker:
            raise ValueError(f"ticker must be non-empty; got {self.ticker!r}")
        for fname in (
            "open_MFE_R_to_date", "open_MAE_R_to_date",
            "current_stop", "planned_target_R", "trail_MA_candidate_price",
            "position_capital_utilization_pct",
            "position_portfolio_heat_contribution_dollars",
        ):
            val = getattr(self, fname)
            if val is not None and not math.isfinite(val):
                raise ValueError(
                    f"{fname} must be None or finite (NaN/inf rejected); "
                    f"got {val!r}"
                )
        if self.capital_denominator_badge not in ("PROVISIONAL", "LIVE"):
            raise ValueError(
                "capital_denominator_badge must be 'PROVISIONAL' or 'LIVE'; "
                f"got {self.capital_denominator_badge!r}"
            )


@dataclass(frozen=True)
class MaturityStageResult:
    """Result of :func:`compute_maturity_stage` per plan §G T-D.3."""

    asof_date: str  # ISO date — `last_completed_session(now)` page-level
    rows: tuple[MaturityStageRow, ...]
    # Aggregate count of rows by maturity_stage (per spec §4.5).
    count_by_stage: dict[str, int]

    def __post_init__(self) -> None:
        if not self.asof_date:
            raise ValueError(
                f"asof_date must be non-empty; got {self.asof_date!r}"
            )
        for stage, count in self.count_by_stage.items():
            if not isinstance(stage, str):
                raise ValueError(
                    f"count_by_stage key must be str; got {stage!r}"
                )
            if count < 0:
                raise ValueError(
                    f"count_by_stage[{stage!r}] must be >= 0; got {count!r}"
                )


def compute_maturity_stage(
    conn: sqlite3.Connection,
    *,
    asof_date: date | None = None,
) -> MaturityStageResult:
    """Plan §G Task D.3 + spec §3.5.

    ``asof_date`` defaults to ``last_completed_session(datetime.now())``
    (plan §A.15 backward-looking BINDING). Caller may pin it for tests.
    """
    if asof_date is None:
        asof_date = last_completed_session(datetime.now())
    live_policy = read_live_policy(conn)

    # Load per-trade ACTIVE snapshots from Phase 8 helper (clamped to
    # latest session, joined to trades.state IN open-states).
    snapshots = list_open_position_active_snapshots(conn)
    by_trade_id: dict[int, object] = {s.trade_id: s for s in snapshots}

    # Also load every open trade — so the surface still renders rows for
    # trades that have NO active snapshot yet (e.g., entered-no-fill
    # between pipeline runs). Per spec §4.5 empty-state semantics.
    trade_rows = conn.execute(
        "SELECT id, ticker, current_stop, planned_target_R, current_size, "
        "current_avg_cost FROM trades "
        "WHERE state IN ('entered', 'managing', 'partial_exited') "
        "ORDER BY id ASC"
    ).fetchall()

    rows: list[MaturityStageRow] = []
    counts: dict[str, int] = {}
    for trade_id, ticker, t_stop, t_planned_r, t_size, t_avg_cost in trade_rows:
        snap = by_trade_id.get(trade_id)
        # Resolve row's asof_date — snapshot's session if present, else
        # the page's asof_date (backward-looking).
        if snap is not None and snap.data_asof_session:
            try:
                row_asof = date.fromisoformat(snap.data_asof_session)
            except ValueError:
                row_asof = asof_date
        else:
            row_asof = asof_date
        denom_dollars, denom_badge = resolve_live_capital_denominator_dollars(
            conn, asof_date=row_asof, at_trade_time_policy=live_policy,
        )

        if snap is not None:
            stage = snap.maturity_stage
            mfe = snap.open_MFE_R_to_date
            mae = snap.open_MAE_R_to_date
            stop_val = (
                snap.current_stop if snap.current_stop is not None else t_stop
            )
            heat_contrib = snap.position_portfolio_heat_contribution_dollars
            trail_ma_price = snap.trail_MA_candidate_price
            # Prefer Phase 8's stored utilization when present + the row's
            # snapshot was computed against the SAME denominator decision
            # (PROVISIONAL/LIVE). Else recompute live.
            stored_util = snap.position_capital_utilization_pct
            stored_denom = snap.position_capital_denominator_dollars
            if (
                stored_util is not None
                and stored_denom is not None
                and math.isclose(stored_denom, denom_dollars, rel_tol=1e-9)
            ):
                util_pct = stored_util
            else:
                util_pct = _compute_position_util_pct(
                    avg_cost=(t_avg_cost if t_avg_cost is not None else 0.0),
                    size=t_size if t_size is not None else 0.0,
                    denom=denom_dollars,
                )
        else:
            stage = None
            mfe = None
            mae = None
            stop_val = t_stop
            heat_contrib = _compute_heat_contrib(
                avg_cost=t_avg_cost, size=t_size, stop=t_stop,
            )
            trail_ma_price = None
            util_pct = _compute_position_util_pct(
                avg_cost=(t_avg_cost if t_avg_cost is not None else 0.0),
                size=t_size if t_size is not None else 0.0,
                denom=denom_dollars,
            )

        eligibility = _compute_trail_ma_eligibility(
            open_mfe_r=mfe, current_stop=stop_val,
            trail_ma_candidate_price=trail_ma_price,
        )

        rows.append(
            MaturityStageRow(
                trade_id=trade_id,
                ticker=ticker,
                maturity_stage=stage,
                open_MFE_R_to_date=mfe,
                open_MAE_R_to_date=mae,
                current_stop=stop_val,
                planned_target_R=t_planned_r,
                trail_MA_candidate_price=trail_ma_price,
                trail_MA_eligibility_flag=eligibility,
                position_capital_utilization_pct=util_pct,
                position_portfolio_heat_contribution_dollars=heat_contrib,
                capital_denominator_badge=denom_badge,
            )
        )
        key = stage if stage is not None else "(unstaged)"
        counts[key] = counts.get(key, 0) + 1

    # Sort rows by maturity_stage for the §4.5 surface; trades with no
    # stage label go last to avoid mixing into the ordered stage groups.
    rows.sort(
        key=lambda r: (
            _STAGE_ORDER.get(r.maturity_stage or "", 99),
            r.trade_id,
        )
    )

    return MaturityStageResult(
        asof_date=asof_date.isoformat(),
        rows=tuple(rows),
        count_by_stage=counts,
    )


def _compute_position_util_pct(
    *, avg_cost: float, size: float, denom: float,
) -> float | None:
    if denom <= 0 or size <= 0:
        return None
    exposure = avg_cost * size
    if not math.isfinite(exposure):
        return None
    return (exposure / denom) * 100.0


def _compute_heat_contrib(
    *, avg_cost: float | None, size: float | None, stop: float | None,
) -> float | None:
    if avg_cost is None or size is None or stop is None:
        return None
    delta = float(avg_cost) - float(stop)
    if delta <= 0:
        return 0.0
    return delta * float(size)


def _compute_trail_ma_eligibility(
    *,
    open_mfe_r: float | None,
    current_stop: float | None,
    trail_ma_candidate_price: float | None,
) -> bool | None:
    """Per plan §G T-D.3 discriminating-test acceptance: returns None (NOT
    False) when ``trail_MA_candidate_price`` is NULL — operator cannot
    evaluate eligibility without the MA reference."""
    if trail_ma_candidate_price is None:
        return None
    if open_mfe_r is None or current_stop is None:
        return None
    return bool(
        open_mfe_r >= TRAIL_MA_ELIGIBILITY_MFE_R_THRESHOLD
        and current_stop < trail_ma_candidate_price
    )
