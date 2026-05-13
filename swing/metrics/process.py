"""§3.1 trade-process metric computations (Sub-bundle B Task T-B.1).

Computes the 22 §3.1 trade-process metrics for a cohort (or "all" closed
trades) per spec §3.1 + plan §E per-metric class matrix. Consumed by
:class:`swing.web.view_models.metrics.trade_process_card.TradeProcessCardVM`.

Per plan §A.5 + §I.3: per-trade win/loss/scratch classification uses
AT-TRADE-TIME ``scratch_epsilon_R`` (each trade carries its at-lock policy
stamp). Legacy trades with NULL stamp fall back to LIVE policy with a
``[legacy: pre-Phase-9 trade]`` annotation surfaced via
:attr:`TradeProcessMetricsResult.legacy_trades_count`.

Per plan §A.11.1: include ALL trades labeled with the cohort regardless
of cohort status at trade-time (operator-intent-at-entry semantics —
paused intervals do NOT cause exclusion).

Per spec §3.1 + §7 + plan §E acceptance: ``mistake_cost_R`` /
``lucky_violation_R`` are per-trade derived via
:func:`swing.trades.review.compute_mistake_cost_R` /
:func:`swing.trades.review.compute_lucky_violation_R` and summed at the
cohort level. The aggregate is rendered both as a Class B mean (cohort
sum / n_reviewed) for honesty-policy purposes AND as a raw cohort sum
total for the dashboard summary (per spec §3.1 "cohort sum"
aggregation).

V1 LIMITATIONS (banked at return report §7):
- MFE_R / MAE_R / capture_ratio / giveback_R_winner /
  giveback_R_winner_to_loser require ``daily_management_records``
  snapshots (Phase 8 capture); when absent for a trade, that trade is
  excluded from the metric's contribution (NOT zeroed). Cohorts with
  zero MFE-bearing trades render as suppressed.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from swing.data.models import Fill, RiskPolicy, Trade
from swing.data.repos.fills import list_fills_for_trade
from swing.metrics.cohort import list_closed_trades_for_cohort
from swing.metrics.honesty import (
    BootstrapCI,
    HonestyBadges,
    SuppressedMetric,
    WilsonCI,
    badges_for_n,
    render_class_a,
    render_class_b,
    render_class_c,
)
from swing.metrics.policy import (
    get_trade_policy_id_stamp,
    read_at_trade_time_policy,
    read_live_policy,
)
from swing.trades.derived_metrics import initial_risk_per_share
from swing.trades.review import (
    compute_lucky_violation_R,
    compute_mistake_cost_R,
)

_ONE_DAY = timedelta(days=1)


# ---------------------------------------------------------------------------
# Per-trade classification & derivation helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _TradeMetricInputs:
    """Per-trade pre-computed inputs threaded into the cohort aggregator.

    Each field is finite (NaN/inf rejected at constructor time) and the
    classification + risk_budget are precomputed so the aggregator does
    NOT loop more than once per metric.
    """

    trade: Trade
    realized_R: float | None  # noqa: N815 — None when planned_risk_budget invalid
    gross_realized_R: float | None  # noqa: N815
    planned_risk_budget_dollars: float | None
    risk_per_share: float | None  # for slippage computation
    net_pnl_dollars: float | None
    gross_pnl_dollars: float | None
    fills: tuple[Fill, ...]
    vwap_entry: float | None
    classification: str  # 'win' | 'loss' | 'scratch' | 'undefined'
    scratch_epsilon_R: float  # noqa: N815  # at-trade-time stamp
    is_legacy_stamp: bool  # True if fallback to LIVE policy applied
    holding_period_days: int | None


def _classify(realized_R: float | None, scratch_epsilon: float) -> str:  # noqa: N803
    """Per spec §2 + plan §A.5: win / loss / scratch classification.

    Uses AT-TRADE-TIME ``scratch_epsilon_R``. Returns 'undefined' when
    ``realized_R`` is None (invalid planned_risk_budget — entry==stop or
    inverted).
    """
    if realized_R is None:
        return "undefined"
    if abs(realized_R) < scratch_epsilon:
        return "scratch"
    if realized_R >= scratch_epsilon:
        return "win"
    return "loss"


def _compute_vwap_entry(fills: tuple[Fill, ...]) -> float | None:
    """Per spec §2: ``sum(price * quantity) / sum(quantity)`` over entry fills."""
    entry_fills = [f for f in fills if f.action == "entry"]
    if not entry_fills:
        return None
    total_qty = sum(f.quantity for f in entry_fills)
    if total_qty <= 0:
        return None
    weighted = sum(f.price * f.quantity for f in entry_fills)
    return weighted / total_qty


def _compute_pnl_components(
    trade: Trade, fills: tuple[Fill, ...],
) -> tuple[float | None, float | None]:
    """Per spec §2: derive net_pnl_dollars + gross_pnl_dollars.

    Long-only convention: gross = sum(exit_proceeds) - sum(entry_cost);
    net = gross - sum(fees) over ALL fills.

    Returns ``(net, gross)`` or ``(None, None)`` when no exit fills (open
    trade / mis-stated input).
    """
    entry_cost = 0.0
    exit_proceeds = 0.0
    total_fees = 0.0
    has_exit = False
    for f in fills:
        fee_contribution = f.fees if f.fees is not None else 0.0
        total_fees += fee_contribution
        if f.action == "entry":
            entry_cost += f.price * f.quantity
        else:
            exit_proceeds += f.price * f.quantity
            has_exit = True
    if not has_exit:
        return (None, None)
    gross = exit_proceeds - entry_cost
    net = gross - total_fees
    return (net, gross)


def _holding_period_trading_days(trade: Trade) -> int | None:
    """Trading-day delta between ``pre_trade_locked_at`` and ``last_fill_at``.

    V1 implementation: simple calendar-day difference + weekend exclusion
    (no exchange-calendar dependency). Returns None when either timestamp
    is absent/malformed (legacy trades without lock_at; not-yet-closed
    trades).
    """
    if not trade.pre_trade_locked_at or not trade.last_fill_at:
        return None
    try:
        start = date.fromisoformat(trade.pre_trade_locked_at[:10])
        end = date.fromisoformat(trade.last_fill_at[:10])
    except (ValueError, TypeError):
        return None
    if end < start:
        return None
    # Trading-day count: Mon-Fri inclusive between start and end.
    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            days += 1
        d += _ONE_DAY
    return days


def _prepare_trade_inputs(
    conn: sqlite3.Connection,
    trade: Trade,
    live_policy: RiskPolicy,
) -> _TradeMetricInputs:
    """Build the per-trade computation inputs for cohort aggregation.

    Resolves AT-TRADE-TIME policy via the
    :func:`swing.metrics.policy.get_trade_policy_id_stamp` accessor +
    :func:`swing.metrics.policy.read_at_trade_time_policy` resolver per
    plan §A.5 binding interface.
    """
    assert trade.id is not None, "trade.id must be set for cohort aggregation"
    stamp = get_trade_policy_id_stamp(conn, trade_id=trade.id)
    at_policy, is_legacy = read_at_trade_time_policy(
        conn, policy_id_stamp=stamp,
    )
    fills = tuple(list_fills_for_trade(conn, trade.id))

    rps_raw = initial_risk_per_share(
        entry_price=trade.entry_price, initial_stop=trade.initial_stop,
    )
    # Per plan §A.0 edge case: clamp negative risk_per_share to 0 (inverted
    # stop ⇒ planned_risk_budget invalid; realized_R becomes undefined).
    if rps_raw <= 0 or trade.initial_shares <= 0:
        risk_budget: float | None = None
        rps: float | None = None
    else:
        risk_budget = rps_raw * trade.initial_shares
        rps = rps_raw

    net_pnl, gross_pnl = _compute_pnl_components(trade, fills)
    if (
        risk_budget is not None and risk_budget > 0
        and net_pnl is not None
        and math.isfinite(net_pnl)
    ):
        realized_R = net_pnl / risk_budget  # noqa: N806
    else:
        realized_R = None  # noqa: N806
    if (
        risk_budget is not None and risk_budget > 0
        and gross_pnl is not None
        and math.isfinite(gross_pnl)
    ):
        gross_realized_R = gross_pnl / risk_budget  # noqa: N806
    else:
        gross_realized_R = None  # noqa: N806

    vwap = _compute_vwap_entry(fills)
    cls = _classify(realized_R, at_policy.scratch_epsilon_R)
    holding = _holding_period_trading_days(trade)

    return _TradeMetricInputs(
        trade=trade,
        realized_R=realized_R,
        gross_realized_R=gross_realized_R,
        planned_risk_budget_dollars=risk_budget,
        risk_per_share=rps,
        net_pnl_dollars=net_pnl,
        gross_pnl_dollars=gross_pnl,
        fills=fills,
        vwap_entry=vwap,
        classification=cls,
        scratch_epsilon_R=at_policy.scratch_epsilon_R,
        is_legacy_stamp=is_legacy,
        holding_period_days=holding,
    )


def _read_latest_mfe_mae(
    conn: sqlite3.Connection, trade_id: int,
) -> tuple[float | None, float | None]:
    """Read latest ``open_MFE_R_to_date`` + ``open_MAE_R_to_date`` from
    Phase 8 ``daily_management_records`` (V1: latest active snapshot).

    Returns ``(mfe_R, mae_R)`` — either may be None when Phase 8 capture
    is absent for the trade.
    """
    row = conn.execute(
        "SELECT open_MFE_R_to_date, open_MAE_R_to_date "
        "FROM daily_management_records "
        "WHERE trade_id = ? AND record_type = 'daily_snapshot' "
        "  AND (is_superseded = 0 OR is_superseded IS NULL) "
        "ORDER BY review_date DESC, management_record_id DESC LIMIT 1",
        (trade_id,),
    ).fetchone()
    if row is None:
        return (None, None)
    mfe, mae = row[0], row[1]
    if mfe is not None and not math.isfinite(float(mfe)):
        mfe = None
    if mae is not None and not math.isfinite(float(mae)):
        mae = None
    return (mfe, mae)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricCellA:
    """Class A rate-metric cell (Wilson CI or suppression)."""

    name: str
    value: WilsonCI | SuppressedMetric
    badges: HonestyBadges
    sample_n: int
    events_k: int

    def __post_init__(self) -> None:
        if self.sample_n < 0:
            raise ValueError(
                f"MetricCellA.sample_n must be >= 0; got {self.sample_n!r}"
            )
        if self.events_k < 0:
            raise ValueError(
                f"MetricCellA.events_k must be >= 0; got {self.events_k!r}"
            )


@dataclass(frozen=True)
class MetricCellB:
    """Class B mean-metric cell (bootstrap CI or suppression)."""

    name: str
    value: BootstrapCI | SuppressedMetric
    badges: HonestyBadges
    sample_n: int

    def __post_init__(self) -> None:
        if self.sample_n < 0:
            raise ValueError(
                f"MetricCellB.sample_n must be >= 0; got {self.sample_n!r}"
            )


@dataclass(frozen=True)
class MetricCellC:
    """Class C ratio-metric cell (point estimate or suppression)."""

    name: str
    value: float | None | SuppressedMetric
    badges: HonestyBadges
    sample_n: int
    n_wins: int
    n_losses: int

    def __post_init__(self) -> None:
        if self.sample_n < 0:
            raise ValueError(
                f"MetricCellC.sample_n must be >= 0; got {self.sample_n!r}"
            )
        if (
            self.value is not None
            and not isinstance(self.value, SuppressedMetric)
            and not math.isfinite(float(self.value))
        ):
            raise ValueError(
                f"MetricCellC.value must be finite; got {self.value!r}"
            )


@dataclass(frozen=True)
class PointMetricCell:
    """Plain point value (cohort sum / count / etc.; no CI rendering)."""

    name: str
    value: float | int | None

    def __post_init__(self) -> None:
        if (
            self.value is not None
            and isinstance(self.value, float)
            and not math.isfinite(self.value)
        ):
            raise ValueError(
                f"PointMetricCell.value must be finite; got {self.value!r}"
            )


@dataclass(frozen=True)
class TradeProcessMetricsResult:
    """Per-cohort §3.1 trade-process metric aggregate.

    Per plan §E + §A.5 + §A.5.1 + §A.11.1 — all 22 §3.1 metrics
    surfaced with their honesty-class rendering.
    """

    cohort_label: str | None  # None = "all closed trades"
    n_closed: int
    n_wins: int
    n_losses: int
    n_scratches: int
    n_reviewed: int  # closed AND reviewed (mistake_tags / process_grade scope)
    legacy_trades_count: int  # trades with NULL risk_policy_id_at_lock

    # Class B (mean) metrics
    realized_R: MetricCellB  # noqa: N815  # spec §3.1 row 1
    gross_realized_R: MetricCellB  # noqa: N815  # row 2
    expectancy_R: MetricCellB  # noqa: N815  # row 3 — alias for cohort mean of realized_R
    avg_win_R: MetricCellB  # noqa: N815  # row 7
    avg_loss_R: MetricCellB  # noqa: N815  # row 8
    mfe_R: MetricCellB  # noqa: N815  # row 11
    mae_R: MetricCellB  # noqa: N815  # row 12
    capture_ratio: MetricCellB  # row 13 (winners only)
    giveback_R_winner: MetricCellB  # noqa: N815  # row 14
    giveback_R_winner_to_loser: MetricCellB  # noqa: N815  # row 15
    entry_adverse_slippage_R: MetricCellB  # noqa: N815  # row 16
    holding_period_days: MetricCellB  # row 21 (cohort mean)
    mistake_cost_R_per_trade: MetricCellB  # noqa: N815  # row 17 (cohort mean)
    lucky_violation_R_per_trade: MetricCellB  # noqa: N815  # row 18 (cohort mean)

    # Class A (rate) metrics
    win_rate: MetricCellA  # row 4
    loss_rate: MetricCellA  # row 5
    scratch_rate: MetricCellA  # row 6
    disqualifying_process_violation_rate: MetricCellA  # row 20

    # Class C (ratio) metrics
    profit_factor: MetricCellC  # row 9
    payoff_ratio: MetricCellC  # row 10

    # Per spec §3.1: cohort SUM of mistake_cost_R + lucky_violation_R
    # surfaced as point totals (Class B mean above is the CI-bearing view).
    mistake_cost_R_total: PointMetricCell  # noqa: N815
    lucky_violation_R_total: PointMetricCell  # noqa: N815

    # process_grade row 19 — distribution across A/B/C/D/F (5 Class A rates).
    process_grade_distribution: dict[str, MetricCellA] = field(
        default_factory=dict,
    )

    # mistake_tag_frequency row 22 — per-tag Class A rates over reviewed trades.
    mistake_tag_frequency: dict[str, MetricCellA] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        for fname in (
            "n_closed", "n_wins", "n_losses", "n_scratches", "n_reviewed",
            "legacy_trades_count",
        ):
            v = getattr(self, fname)
            if not isinstance(v, int) or v < 0:
                raise ValueError(
                    f"TradeProcessMetricsResult.{fname} must be int >= 0; "
                    f"got {v!r}"
                )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

# Sentinel HonestyBadges for suppressed cells (badges are "no warning"
# when the metric is fully suppressed — caller renders only the placeholder).
_NO_BADGES = HonestyBadges(
    confidence_floor_warning=False, low_confidence_warning=False,
)


def _render_class_b_cell(
    *,
    name: str,
    samples: list[float],
    policy: RiskPolicy,
) -> MetricCellB:
    n = len(samples)
    rendered = render_class_b(
        samples=samples, policy=policy, metric_name=name,
    )
    if isinstance(rendered, SuppressedMetric):
        return MetricCellB(name=name, value=rendered, badges=_NO_BADGES, sample_n=n)
    return MetricCellB(
        name=name, value=rendered, badges=badges_for_n(n=n, policy=policy),
        sample_n=n,
    )


def _render_class_a_cell(
    *,
    name: str,
    k: int,
    n: int,
    policy: RiskPolicy,
) -> MetricCellA:
    rendered = render_class_a(k=k, n=n, policy=policy, metric_name=name)
    if isinstance(rendered, SuppressedMetric):
        return MetricCellA(
            name=name, value=rendered, badges=_NO_BADGES,
            sample_n=n, events_k=k,
        )
    return MetricCellA(
        name=name, value=rendered,
        badges=badges_for_n(n=n, policy=policy),
        sample_n=n, events_k=k,
    )


def _render_class_c_cell(
    *,
    name: str,
    value: float | None,
    n: int,
    n_wins: int,
    n_losses: int,
    policy: RiskPolicy,
) -> MetricCellC:
    rendered = render_class_c(
        value=value, n=n, n_wins=n_wins, n_losses=n_losses,
        policy=policy, metric_name=name,
    )
    if isinstance(rendered, SuppressedMetric):
        return MetricCellC(
            name=name, value=rendered, badges=_NO_BADGES,
            sample_n=n, n_wins=n_wins, n_losses=n_losses,
        )
    point_value, badges = rendered
    return MetricCellC(
        name=name, value=point_value, badges=badges,
        sample_n=n, n_wins=n_wins, n_losses=n_losses,
    )


def compute_trade_process_metrics(  # noqa: PLR0915 — orchestrator function over 22 metrics
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
) -> TradeProcessMetricsResult:
    """Compute the §3.1 trade-process metric aggregate for ``hypothesis_label``.

    ``hypothesis_label`` of ``None`` aggregates over ALL closed trades
    (the "all" toggle per spec §4.1 + plan §E Task B.2).

    Per plan §A.5: per-trade win/loss/scratch classification uses the
    AT-TRADE-TIME ``scratch_epsilon_R`` stamp. LIVE policy is used for
    suppression-floor + confidence-floor decisions per §A.7 decoupling.
    """
    live_policy = read_live_policy(conn)
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=hypothesis_label,
    )

    inputs: list[_TradeMetricInputs] = [
        _prepare_trade_inputs(conn, t, live_policy) for t in trades
    ]
    n_closed = len(inputs)
    legacy_count = sum(1 for x in inputs if x.is_legacy_stamp)

    # Classification counts (per spec §3.1).
    n_wins = sum(1 for x in inputs if x.classification == "win")
    n_losses = sum(1 for x in inputs if x.classification == "loss")
    n_scratches = sum(1 for x in inputs if x.classification == "scratch")

    reviewed_trades = [x for x in inputs if x.trade.reviewed_at is not None]
    n_reviewed = len(reviewed_trades)

    # --------- Class B (mean) samples ---------
    realized_R_samples = [  # noqa: N806
        x.realized_R for x in inputs if x.realized_R is not None
    ]
    gross_R_samples = [  # noqa: N806
        x.gross_realized_R for x in inputs if x.gross_realized_R is not None
    ]
    avg_win_samples = [
        x.realized_R for x in inputs
        if x.classification == "win" and x.realized_R is not None
    ]
    avg_loss_samples = [
        x.realized_R for x in inputs
        if x.classification == "loss" and x.realized_R is not None
    ]

    # MFE / MAE per-trade (Phase 8 capture).
    mfe_samples: list[float] = []
    mae_samples: list[float] = []
    capture_samples: list[float] = []
    giveback_winner_samples: list[float] = []
    giveback_winner_to_loser_samples: list[float] = []
    for x in inputs:
        if x.trade.id is None:
            continue
        mfe, mae = _read_latest_mfe_mae(conn, x.trade.id)
        if mfe is not None:
            mfe_samples.append(float(mfe))
        if mae is not None:
            mae_samples.append(float(mae))
        # capture_ratio: realized_R / MFE_R for winners with MFE>0.
        if (
            x.classification == "win"
            and x.realized_R is not None
            and mfe is not None
            and mfe > 0
        ):
            capture_samples.append(x.realized_R / float(mfe))
        # giveback_R_winner: MFE_R - realized_R for winners with MFE>0.
        if (
            x.classification == "win"
            and x.realized_R is not None
            and mfe is not None
            and mfe > 0
        ):
            giveback_winner_samples.append(float(mfe) - x.realized_R)
        # giveback_R_winner_to_loser: losers with MFE>0.
        if (
            x.classification == "loss"
            and x.realized_R is not None
            and mfe is not None
            and mfe > 0
        ):
            giveback_winner_to_loser_samples.append(float(mfe) - x.realized_R)

    # entry_adverse_slippage_R: (vwap_entry - planned_entry) / risk_per_share.
    slippage_samples: list[float] = []
    for x in inputs:
        if x.vwap_entry is None or x.risk_per_share is None or x.risk_per_share <= 0:
            continue
        slippage = (x.vwap_entry - x.trade.entry_price) / x.risk_per_share
        if math.isfinite(slippage):
            slippage_samples.append(slippage)

    # holding_period_days: integer trading-day samples.
    holding_samples = [
        float(x.holding_period_days) for x in inputs
        if x.holding_period_days is not None
    ]

    # mistake_cost / lucky_violation per-trade values (cohort SUM + cohort MEAN).
    mistake_costs = [
        compute_mistake_cost_R(
            realized_R_if_plan_followed=x.trade.realized_R_if_plan_followed,
            actual_realized_R_effective=x.realized_R
            if x.realized_R is not None else 0.0,
        )
        for x in inputs
    ]
    lucky_violations = [
        compute_lucky_violation_R(
            realized_R_if_plan_followed=x.trade.realized_R_if_plan_followed,
            actual_realized_R_effective=x.realized_R
            if x.realized_R is not None else 0.0,
        )
        for x in inputs
    ]
    mistake_cost_total = float(sum(mistake_costs))
    lucky_violation_total = float(sum(lucky_violations))

    # --------- Class C (ratio) ---------
    sum_pos = sum(x.realized_R for x in inputs
                  if x.realized_R is not None and x.realized_R > 0)
    sum_neg = sum(x.realized_R for x in inputs
                  if x.realized_R is not None and x.realized_R < 0)
    profit_factor_value: float | None = (
        None if sum_neg == 0 else sum_pos / abs(sum_neg)
    )

    payoff_ratio_value: float | None
    if n_wins >= 1 and n_losses >= 1 and avg_loss_samples and avg_win_samples:
        mean_win = sum(avg_win_samples) / len(avg_win_samples)
        mean_loss = sum(avg_loss_samples) / len(avg_loss_samples)
        payoff_ratio_value = (
            None if mean_loss == 0 else mean_win / abs(mean_loss)
        )
    else:
        payoff_ratio_value = None

    # --------- Class A (rate) ---------
    win_rate_cell = _render_class_a_cell(
        name="win_rate", k=n_wins, n=n_closed, policy=live_policy,
    )
    loss_rate_cell = _render_class_a_cell(
        name="loss_rate", k=n_losses, n=n_closed, policy=live_policy,
    )
    scratch_rate_cell = _render_class_a_cell(
        name="scratch_rate", k=n_scratches, n=n_closed, policy=live_policy,
    )
    disq_count = sum(
        1 for x in reviewed_trades
        if x.trade.disqualifying_process_violation
    )
    disqualifying_rate_cell = _render_class_a_cell(
        name="disqualifying_process_violation_rate",
        k=disq_count, n=n_reviewed, policy=live_policy,
    )

    # process_grade distribution — 5 Class A rates (A/B/C/D/F).
    grade_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for x in reviewed_trades:
        g = x.trade.process_grade
        if g in grade_counts:
            grade_counts[g] += 1
    process_grade_distribution = {
        grade: _render_class_a_cell(
            name=f"process_grade_{grade}_rate",
            k=count, n=n_reviewed, policy=live_policy,
        )
        for grade, count in grade_counts.items()
    }

    # mistake_tag_frequency — per-tag Class A rates over REVIEWED trades.
    tag_counts: dict[str, int] = {}
    for x in reviewed_trades:
        if not x.trade.mistake_tags:
            continue
        try:
            tags = json.loads(x.trade.mistake_tags)
        except (ValueError, TypeError):
            continue
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, str) or not tag:
                continue
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    mistake_tag_frequency = {
        tag: _render_class_a_cell(
            name=f"mistake_tag_frequency_{tag}",
            k=count, n=n_reviewed, policy=live_policy,
        )
        for tag, count in sorted(tag_counts.items())
    }

    # --------- Class B (mean) cell construction ---------
    realized_R_cell = _render_class_b_cell(  # noqa: N806
        name="realized_R", samples=list(realized_R_samples), policy=live_policy,
    )
    gross_R_cell = _render_class_b_cell(  # noqa: N806
        name="gross_realized_R",
        samples=list(gross_R_samples), policy=live_policy,
    )
    # expectancy_R is the same cohort mean as realized_R per spec §3.1 row 3.
    expectancy_cell = _render_class_b_cell(
        name="expectancy_R",
        samples=list(realized_R_samples), policy=live_policy,
    )
    avg_win_cell = _render_class_b_cell(
        name="avg_win_R", samples=list(avg_win_samples), policy=live_policy,
    )
    avg_loss_cell = _render_class_b_cell(
        name="avg_loss_R", samples=list(avg_loss_samples), policy=live_policy,
    )
    mfe_cell = _render_class_b_cell(
        name="MFE_R", samples=list(mfe_samples), policy=live_policy,
    )
    mae_cell = _render_class_b_cell(
        name="MAE_R", samples=list(mae_samples), policy=live_policy,
    )
    capture_cell = _render_class_b_cell(
        name="capture_ratio",
        samples=list(capture_samples), policy=live_policy,
    )
    giveback_winner_cell = _render_class_b_cell(
        name="giveback_R_winner",
        samples=list(giveback_winner_samples), policy=live_policy,
    )
    giveback_winner_to_loser_cell = _render_class_b_cell(
        name="giveback_R_winner_to_loser",
        samples=list(giveback_winner_to_loser_samples),
        policy=live_policy,
    )
    slippage_cell = _render_class_b_cell(
        name="entry_adverse_slippage_R",
        samples=list(slippage_samples), policy=live_policy,
    )
    holding_cell = _render_class_b_cell(
        name="holding_period_days",
        samples=list(holding_samples), policy=live_policy,
    )
    mistake_cost_per_trade_cell = _render_class_b_cell(
        name="mistake_cost_R_per_trade",
        samples=[float(v) for v in mistake_costs], policy=live_policy,
    )
    lucky_violation_per_trade_cell = _render_class_b_cell(
        name="lucky_violation_R_per_trade",
        samples=[float(v) for v in lucky_violations], policy=live_policy,
    )

    # --------- Class C (ratio) cells ---------
    profit_factor_cell = _render_class_c_cell(
        name="profit_factor", value=profit_factor_value,
        n=n_closed, n_wins=n_wins, n_losses=n_losses, policy=live_policy,
    )
    payoff_ratio_cell = _render_class_c_cell(
        name="payoff_ratio", value=payoff_ratio_value,
        n=n_closed, n_wins=n_wins, n_losses=n_losses, policy=live_policy,
    )

    return TradeProcessMetricsResult(
        cohort_label=hypothesis_label,
        n_closed=n_closed,
        n_wins=n_wins,
        n_losses=n_losses,
        n_scratches=n_scratches,
        n_reviewed=n_reviewed,
        legacy_trades_count=legacy_count,
        realized_R=realized_R_cell,
        gross_realized_R=gross_R_cell,
        expectancy_R=expectancy_cell,
        avg_win_R=avg_win_cell,
        avg_loss_R=avg_loss_cell,
        mfe_R=mfe_cell,
        mae_R=mae_cell,
        capture_ratio=capture_cell,
        giveback_R_winner=giveback_winner_cell,
        giveback_R_winner_to_loser=giveback_winner_to_loser_cell,
        entry_adverse_slippage_R=slippage_cell,
        holding_period_days=holding_cell,
        mistake_cost_R_per_trade=mistake_cost_per_trade_cell,
        lucky_violation_R_per_trade=lucky_violation_per_trade_cell,
        win_rate=win_rate_cell,
        loss_rate=loss_rate_cell,
        scratch_rate=scratch_rate_cell,
        disqualifying_process_violation_rate=disqualifying_rate_cell,
        profit_factor=profit_factor_cell,
        payoff_ratio=payoff_ratio_cell,
        mistake_cost_R_total=PointMetricCell(
            name="mistake_cost_R_total", value=mistake_cost_total,
        ),
        lucky_violation_R_total=PointMetricCell(
            name="lucky_violation_R_total", value=lucky_violation_total,
        ),
        process_grade_distribution=process_grade_distribution,
        mistake_tag_frequency=mistake_tag_frequency,
    )


# Convenience re-exports for VM layer consumption (callers should import
# from this module; ``swing.metrics.__init__`` does not currently re-export).
__all__ = [
    "MetricCellA",
    "MetricCellB",
    "MetricCellC",
    "PointMetricCell",
    "TradeProcessMetricsResult",
    "compute_trade_process_metrics",
]
