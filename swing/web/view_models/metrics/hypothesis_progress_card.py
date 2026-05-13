"""View-model for spec §4.2 hypothesis-progress card (Sub-bundle B T-B.4).

Per-cohort governance surface — ALWAYS rendered (no n<3 suppression);
tripwire indicators visible from n=1.

Per plan §A.11: full transition timeline (last 5 entries, newest-first)
supersedes spec §3.2 V1-limitation note (Phase 9 Sub-bundle C closed the
audit-table capture gap).

Per plan §A.5.1: cohort-aggregate ``cumulative_R_pct_of_capital`` is
PER-TRADE-DIVIDE-THEN-SUM with EACH trade's AT-TRADE-TIME
``capital_floor_constant_dollars`` (NOT live policy, NOT averaged across
policies). Discriminating regression test pins multi-policy semantics.

Per plan §A.11.1: cohort metrics include ALL trades labeled with the
cohort regardless of cohort.status at trade-time (paused intervals do NOT
cause exclusion).
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import HypothesisStatusHistory
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.hypothesis_status_history import (
    list_history_for_hypothesis,
)
from swing.evaluation.dates import action_session_for_run
from swing.metrics.cohort import list_closed_trades_for_cohort
from swing.metrics.discrepancies import count_unresolved_material
from swing.metrics.policy import (
    get_trade_policy_id_stamp,
    read_at_trade_time_policy,
)
from swing.trades.derived_metrics import initial_risk_per_share
from swing.web.view_models.metrics.shared import BaseLayoutVM

# Per plan §A.11: hypothesis-progress card cap on transition timeline.
# Newest-first; V1 UI brevity. Prior transitions remain in the audit
# table for V2 drill-down.
TRANSITION_TIMELINE_CAP: int = 5


@dataclass(frozen=True)
class TransitionEntry:
    """Single transition row for timeline rendering."""

    status: str
    effective_from: str
    effective_to: str | None
    change_reason: str | None

    @classmethod
    def from_history(cls, h: HypothesisStatusHistory) -> TransitionEntry:
        return cls(
            status=h.status,
            effective_from=h.effective_from,
            effective_to=h.effective_to,
            change_reason=h.change_reason,
        )


@dataclass(frozen=True)
class CohortProgressVM:
    """Per-cohort governance metrics + transition timeline."""

    hypothesis_id: int
    cohort_name: str
    statement: str
    decision_criteria: str
    target_sample_size: int
    consecutive_loss_tripwire: int
    absolute_loss_tripwire_pct: float
    status: str

    n_closed: int
    progress_pct: float  # n_closed / target_sample_size (>=0; uncapped)
    consecutive_loss_run: int
    distance_to_loss_tripwire: int  # tripwire - run (clamped >=0)
    cumulative_R_pct_of_capital: float  # noqa: N815 per spec §3.2
    distance_to_absolute_loss_tripwire: float  # noqa: E501  # >=0

    legacy_trades_count: int  # NULL risk_policy_id_at_lock count

    transition_timeline: tuple[TransitionEntry, ...]
    # Latest-only fields (for the prior single-transition-V1 display in
    # case the timeline cap=5 doesn't include the most recent). Always
    # populated when at least one row exists in hypothesis_status_history.
    latest_status_changed_at: str | None
    latest_status_change_reason: str | None

    def __post_init__(self) -> None:
        if self.n_closed < 0:
            raise ValueError(
                f"CohortProgressVM.n_closed must be >= 0; got {self.n_closed!r}"
            )
        if self.target_sample_size <= 0:
            raise ValueError(
                f"CohortProgressVM.target_sample_size must be > 0; got "
                f"{self.target_sample_size!r}"
            )
        if self.consecutive_loss_tripwire <= 0:
            raise ValueError(
                f"CohortProgressVM.consecutive_loss_tripwire must be > 0; "
                f"got {self.consecutive_loss_tripwire!r}"
            )
        if self.consecutive_loss_run < 0:
            raise ValueError(
                f"CohortProgressVM.consecutive_loss_run must be >= 0; got "
                f"{self.consecutive_loss_run!r}"
            )
        if self.distance_to_loss_tripwire < 0:
            raise ValueError(
                f"CohortProgressVM.distance_to_loss_tripwire must be >= 0; "
                f"got {self.distance_to_loss_tripwire!r}"
            )
        if self.absolute_loss_tripwire_pct <= 0:
            raise ValueError(
                f"CohortProgressVM.absolute_loss_tripwire_pct must be > 0; "
                f"got {self.absolute_loss_tripwire_pct!r}"
            )
        if self.distance_to_absolute_loss_tripwire < 0:
            raise ValueError(
                f"CohortProgressVM.distance_to_absolute_loss_tripwire must be "
                f">= 0; got {self.distance_to_absolute_loss_tripwire!r}"
            )
        if self.progress_pct < 0:
            raise ValueError(
                f"CohortProgressVM.progress_pct must be >= 0; got "
                f"{self.progress_pct!r}"
            )
        for fname in (
            "progress_pct", "cumulative_R_pct_of_capital",
            "distance_to_absolute_loss_tripwire",
        ):
            v = getattr(self, fname)
            if not math.isfinite(v):
                raise ValueError(
                    f"CohortProgressVM.{fname} must be finite; got {v!r}"
                )
        if len(self.transition_timeline) > TRANSITION_TIMELINE_CAP:
            raise ValueError(
                f"CohortProgressVM.transition_timeline must have at most "
                f"{TRANSITION_TIMELINE_CAP} entries; got "
                f"{len(self.transition_timeline)}"
            )


@dataclass(frozen=True)
class HypothesisProgressCardVM(BaseLayoutVM):
    """VM for ``GET /metrics/hypothesis-progress`` per plan §E Task B.4 +
    §A.11 supersession.
    """

    cohorts: tuple[CohortProgressVM, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Per-trade R + classification helpers — narrow-scope re-implementation
# (the swing/metrics/process.py helpers are a heavier dependency for this
# governance surface which only needs net_pnl_dollars + at-trade-time
# capital_floor + scratch_epsilon).
# ---------------------------------------------------------------------------

def _per_trade_net_pnl_and_at_trade_time_policy(
    conn: sqlite3.Connection,
    trade_id: int,
    entry_price: float,
    initial_stop: float,
    initial_shares: int,
) -> tuple[float | None, float | None, str, float, float, bool]:
    """Return (net_pnl_dollars, realized_R, classification, scratch_epsilon,
    capital_floor, is_legacy_stamp).

    classification ∈ {'win', 'loss', 'scratch', 'undefined'}.

    Returns ``(None, None, 'undefined', ...)`` when fills missing / invalid
    risk_budget. The capital_floor + scratch_epsilon fields are always
    populated (AT-TRADE-TIME stamp resolution + LIVE fallback).
    """
    stamp = get_trade_policy_id_stamp(conn, trade_id=trade_id)
    at_policy, is_legacy = read_at_trade_time_policy(conn, policy_id_stamp=stamp)
    fills = list_fills_for_trade(conn, trade_id)

    entry_cost = 0.0
    exit_proceeds = 0.0
    total_fees = 0.0
    has_exit = False
    for f in fills:
        fee = f.fees if f.fees is not None else 0.0
        total_fees += fee
        if f.action == "entry":
            entry_cost += f.price * f.quantity
        else:
            exit_proceeds += f.price * f.quantity
            has_exit = True
    if not has_exit:
        return (
            None, None, "undefined",
            at_policy.scratch_epsilon_R,
            at_policy.capital_floor_constant_dollars,
            is_legacy,
        )
    net_pnl = (exit_proceeds - entry_cost) - total_fees

    rps = initial_risk_per_share(
        entry_price=entry_price, initial_stop=initial_stop,
    )
    if rps <= 0 or initial_shares <= 0:
        return (
            net_pnl, None, "undefined",
            at_policy.scratch_epsilon_R,
            at_policy.capital_floor_constant_dollars,
            is_legacy,
        )
    risk_budget = rps * initial_shares
    realized_R = net_pnl / risk_budget if risk_budget > 0 else None  # noqa: N806
    if realized_R is None or not math.isfinite(realized_R):
        cls = "undefined"
    elif abs(realized_R) < at_policy.scratch_epsilon_R:
        cls = "scratch"
    elif realized_R >= at_policy.scratch_epsilon_R:
        cls = "win"
    else:
        cls = "loss"
    return (
        net_pnl, realized_R, cls,
        at_policy.scratch_epsilon_R,
        at_policy.capital_floor_constant_dollars,
        is_legacy,
    )


def _compute_consecutive_loss_run(
    classifications: list[str],
) -> int:
    """Length of the current consecutive-loss streak ending on the most-
    recent closed trade.

    Per spec §3.2: scratches reset the streak (NOT carry-through);
    classifier output of 'win' / 'scratch' / 'undefined' all break the run.
    """
    run = 0
    for cls in reversed(classifications):
        if cls == "loss":
            run += 1
        else:
            break
    return run


def _list_cohort_trades_sorted(
    conn: sqlite3.Connection,
    cohort_name: str,
) -> list:
    """Closed-state trades for the cohort ordered by close-time (oldest first).

    Ordering uses ``last_fill_at ASC, id ASC`` so the consecutive-loss-run
    + cumulative_R series reflect chronological close order. Falls back
    to ``entry_date, ticker, id`` (cohort.list_closed_trades_for_cohort
    ordering) when last_fill_at is NULL.
    """
    trades = list_closed_trades_for_cohort(conn, hypothesis_label=cohort_name)
    return sorted(
        trades,
        key=lambda t: (t.last_fill_at or "9999", t.id or 0),
    )


def _build_cohort_vm(
    conn: sqlite3.Connection,
    *,
    row: tuple,
) -> CohortProgressVM:
    """Construct a CohortProgressVM from a hypothesis_registry row tuple."""
    (
        hyp_id, name, statement, target_sample_size, decision_criteria,
        status, consecutive_loss_tripwire, absolute_loss_tripwire_pct,
        status_changed_at, status_change_reason,
    ) = row

    trades = _list_cohort_trades_sorted(conn, name)
    classifications: list[str] = []
    legacy_count = 0
    cumulative_R_pct = 0.0  # noqa: N806 spec column name (per spec §3.2)
    for t in trades:
        assert t.id is not None
        net_pnl, _realized_R, cls, _eps, floor, is_legacy = (  # noqa: N806
            _per_trade_net_pnl_and_at_trade_time_policy(
                conn, t.id, t.entry_price, t.initial_stop, t.initial_shares,
            )
        )
        classifications.append(cls)
        if is_legacy:
            legacy_count += 1
        # §A.5.1 BINDING: per-trade contribution = net_pnl / at_trade_time_floor.
        if net_pnl is not None and floor > 0:
            cumulative_R_pct += net_pnl / floor  # noqa: N806

    n_closed = len(trades)
    progress_pct = (
        n_closed / target_sample_size if target_sample_size > 0 else 0.0
    )
    consecutive_loss_run = _compute_consecutive_loss_run(classifications)
    distance_to_loss_tripwire = max(
        0, consecutive_loss_tripwire - consecutive_loss_run,
    )

    # spec §3.2: distance_to_absolute = abs_tripwire_pct - abs(min(0, cum)).
    # absolute_loss_tripwire_pct is in PERCENT (e.g., 5.0 means 5%);
    # cumulative_R_pct_of_capital here is the SUM of dimensionless ratios
    # (e.g., -0.01 = -1%). Convert sum to percent (multiply by 100) before
    # comparing — preserves spec's percent-vs-percent comparison.
    cum_in_pct_units = cumulative_R_pct * 100.0
    abs_drawdown_pct = abs(min(0.0, cum_in_pct_units))
    distance_to_absolute = max(
        0.0, absolute_loss_tripwire_pct - abs_drawdown_pct,
    )

    # Transition timeline: ASC from repo; reverse + cap at 5.
    history = list_history_for_hypothesis(conn, hyp_id)
    history_newest_first = list(reversed(history))
    timeline = tuple(
        TransitionEntry.from_history(h)
        for h in history_newest_first[:TRANSITION_TIMELINE_CAP]
    )

    return CohortProgressVM(
        hypothesis_id=hyp_id,
        cohort_name=name,
        statement=statement,
        decision_criteria=decision_criteria,
        target_sample_size=target_sample_size,
        consecutive_loss_tripwire=consecutive_loss_tripwire,
        absolute_loss_tripwire_pct=absolute_loss_tripwire_pct,
        status=status,
        n_closed=n_closed,
        progress_pct=progress_pct,
        consecutive_loss_run=consecutive_loss_run,
        distance_to_loss_tripwire=distance_to_loss_tripwire,
        cumulative_R_pct_of_capital=cum_in_pct_units,
        distance_to_absolute_loss_tripwire=distance_to_absolute,
        legacy_trades_count=legacy_count,
        transition_timeline=timeline,
        latest_status_changed_at=status_changed_at,
        latest_status_change_reason=status_change_reason,
    )


def build_hypothesis_progress_card_vm(
    *, cfg: Config, conn: sqlite3.Connection | None = None,
) -> HypothesisProgressCardVM:
    """Build the per-cohort governance VM eagerly populating discrepancies
    field per §A.18."""
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        unresolved = count_unresolved_material(conn)
        rows = conn.execute(
            "SELECT id, name, statement, target_sample_size, "
            "decision_criteria, status, consecutive_loss_tripwire, "
            "absolute_loss_tripwire_pct, status_changed_at, "
            "status_change_reason FROM hypothesis_registry ORDER BY id",
        ).fetchall()
        cohorts = tuple(_build_cohort_vm(conn, row=r) for r in rows)
    finally:
        if own_conn:
            conn.close()
    return HypothesisProgressCardVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        cohorts=cohorts,
    )
