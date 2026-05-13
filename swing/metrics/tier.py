"""Spec §3.3 + §3.7 tier-comparison + deviation-outcome computations (Sub-bundle C T-C.1).

Computes the two cross-cohort comparison surfaces consumed by the Sub-bundle
C view-models:

- **§3.3 tier-comparison** (``compute_tier_comparison``): per-cohort
  ``cohort_win_rate_with_CI`` (Wilson) + ``cohort_expectancy_with_CI``
  (bootstrap) + per-non-A+ ``cohort_relative_to_aplus`` (percent-of-A+
  ratio) + ``cohort_ci_overlap_descriptor`` (TEXT only — NOT a boolean
  significance flag per spec §3.3 R1 M3 LOCK).
- **§3.7 deviation-outcome** (``compute_deviation_outcome``): per-cohort
  ``cohort_doctrine_deviation_class`` enum + ``expectancy_relative_to_aplus_pct``
  (percent delta, sign-preserving) + ``decision_criterion_evaluation_text``
  rendered from migration 0008 ``decision_criteria`` seed text verbatim
  (manual-only in V1 per spec §3.7 R1 M4 LOCK; NO automated evaluation).

Per spec §4.3 + §4.7 + dispatch brief §0.5 #4 BINDING: both surfaces are
TAXONOMY-LOCKED to the 4 registered hypothesis_registry cohorts. Orphan-
labeled trades are observational metadata for the trade-process card
(per-cohort EDA), NOT comparison metadata for tier/deviation surfaces.

Per spec §4.3 + §4.7 surface LOCK: individual cohort cells suppress when
the cohort's closed-trade count ``n < COHORT_MINIMUM_N`` (= 5). This is
tighter than honesty.py's Class A/B policy floors (default 3) — the spec
explicitly raises the floor for these surfaces because cohort-comparison
with n<5 produces uninterpretable CIs at our sample size. The
``cohort_ci_overlap_descriptor`` is suppressed until BOTH A+ AND Sub-A+
have n>=5.

Per dispatch brief §0.9 + forward-binding lesson #19: unit-semantic
precision is explicit:

- ``cohort_relative_to_aplus_pct`` (spec §3.3): PERCENT, raw ratio
  ``cohort_expectancy / aplus_expectancy * 100`` (e.g., 75.0 means
  cohort_expectancy is 75% of A+ baseline expectancy). None when:
  cohort is A+ itself / cohort or A+ has n<5 / aplus_expectancy is zero.
- ``cohort_expectancy_relative_to_aplus_pct`` (spec §3.7): PERCENT delta
  ``(cohort_expectancy - aplus_expectancy) / aplus_expectancy * 100``
  (sign-preserving: negative = cohort below baseline). None per same
  suppression rules. The two metrics carry semantically DIFFERENT
  information at the same numeric value (75% of baseline ≠ +75% above
  baseline).

T-C.5 elective integration (per electives amendment §2): the helper
``swing.metrics.cohort.filter_trades_without_unresolved_material_discrepancies``
+ the ``exclude_unresolved_discrepancies`` parameter on
``compute_tier_comparison`` + ``compute_deviation_outcome`` land in
T-C.5; T-C.1 ships the unfiltered baseline.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from swing.data.models import RiskPolicy, Trade
from swing.data.repos.fills import list_fills_for_trade
from swing.metrics.cohort import list_closed_trades_for_cohort
from swing.metrics.honesty import (
    BootstrapCI,
    HonestyBadges,
    SuppressedMetric,
    WilsonCI,
    badges_for_n,
    bootstrap_ci_mean,
    wilson_ci,
)
from swing.metrics.policy import (
    get_trade_policy_id_stamp,
    read_at_trade_time_policy,
    read_live_policy,
)
from swing.trades.derived_metrics import initial_risk_per_share

# Per spec §4.3 + §4.7 LOCK: cohort cells suppress at n<5 (surface-level
# floor; tighter than honesty.py's Class A/B/C policy floors which default
# to 3 for A/B + 5 for C). The cohort-comparison surfaces deliberately
# raise the floor to 5 because Wilson CI bands at n=3-4 are too wide to
# inform a cohort-vs-cohort comparison decision at our sample size.
COHORT_MINIMUM_N: int = 5

# Per spec §4.3 + §4.7 + dispatch brief §0.5 #4 BINDING.
# Cohort order matches hypothesis_registry id assignment in migration 0008
# (A+ at id=1, Near-A+ at id=2, Sub-A+ at id=3, Capital-blocked at id=4).
TAXONOMY_COHORTS: tuple[str, ...] = (
    "A+ baseline",
    "Near-A+ defensible: extension test",
    "Sub-A+ VCP-not-formed",
    "Capital-blocked: smaller-position test",
)

APLUS_COHORT: str = "A+ baseline"
SUB_APLUS_COHORT: str = "Sub-A+ VCP-not-formed"

# Per spec §3.7 ``cohort_doctrine_deviation_class`` enum (4 values).
# Hardcoded by cohort_name to keep the mapping resilient to operator
# free-text edits of hypothesis_registry.statement (the mapping is
# fundamental to the doctrine taxonomy, not a free-text annotation).
DOCTRINE_DEVIATION_CLASS: dict[str, str] = {
    "A+ baseline": "baseline",
    "Near-A+ defensible: extension test": "missing_proximity_20ma",
    "Sub-A+ VCP-not-formed": "missing_tightness_or_vcp_volume_contraction",
    "Capital-blocked: smaller-position test": "smaller_than_standard_position",
}


# ---------------------------------------------------------------------------
# Per-trade classification helper
# ---------------------------------------------------------------------------

def _per_trade_realized_R(  # noqa: N802
    conn: sqlite3.Connection, trade: Trade,
) -> tuple[float | None, str, bool]:
    """Return ``(realized_R, classification, is_legacy_stamp)`` for a closed trade.

    Mirrors :func:`swing.web.view_models.metrics.hypothesis_progress_card.
    _per_trade_net_pnl_and_at_trade_time_policy` (Sub-bundle B precedent) —
    narrow re-implementation here keeps :mod:`swing.metrics.tier`
    self-contained (the heavier :mod:`swing.metrics.process` dataclass
    pipeline is overkill for the 2-output cohort-comparison computation).

    ``classification`` is one of ``{'win', 'loss', 'scratch', 'undefined'}``;
    ``undefined`` covers trades with no exit fills OR invalid
    planned_risk_budget (rps<=0 / initial_shares<=0 / NaN/inf net_pnl).

    Uses AT-TRADE-TIME ``scratch_epsilon_R`` per plan §A.5 split-policy
    (mirrors process.py + hypothesis_progress_card pattern). Legacy trades
    with NULL ``risk_policy_id_at_lock`` fall back to LIVE policy with
    ``is_legacy_stamp=True``.
    """
    assert trade.id is not None
    stamp = get_trade_policy_id_stamp(conn, trade_id=trade.id)
    at_policy, is_legacy = read_at_trade_time_policy(
        conn, policy_id_stamp=stamp,
    )
    fills = list_fills_for_trade(conn, trade.id)

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
        return (None, "undefined", is_legacy)

    net_pnl = (exit_proceeds - entry_cost) - total_fees
    if not math.isfinite(net_pnl):
        return (None, "undefined", is_legacy)

    rps = initial_risk_per_share(
        entry_price=trade.entry_price, initial_stop=trade.initial_stop,
    )
    if rps <= 0 or trade.initial_shares <= 0:
        return (None, "undefined", is_legacy)
    risk_budget = rps * trade.initial_shares
    if risk_budget <= 0:
        return (None, "undefined", is_legacy)
    realized_R = net_pnl / risk_budget  # noqa: N806
    if not math.isfinite(realized_R):
        return (None, "undefined", is_legacy)

    eps = at_policy.scratch_epsilon_R
    if abs(realized_R) < eps:
        cls = "scratch"
    elif realized_R >= eps:
        cls = "win"
    else:
        cls = "loss"
    return (realized_R, cls, is_legacy)


def _cohort_suppression(*, metric_name: str, n: int) -> SuppressedMetric:
    """Build a SuppressedMetric placeholder for cohort-level n<5 suppression.

    Spec §4.3 + §4.7 surface-locked floor uses the same §5.6 italic-
    placeholder text format as the honesty-class suppression dispatcher
    (which keys on the lower per-class policy floor). The text reflects
    the SURFACE floor (5) so the operator sees the correct threshold.
    """
    return SuppressedMetric(
        metric_name=metric_name,
        n=n,
        n_required=COHORT_MINIMUM_N,
        placeholder_text=(
            f"[{metric_name}: n too low (current: {n}, "
            f"need: ≥{COHORT_MINIMUM_N})]"
        ),
    )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CohortStatistics:
    """Per-cohort aggregate consumed by tier-comparison + deviation-outcome.

    ``win_rate`` and ``expectancy`` are SuppressedMetric when
    ``n_closed < COHORT_MINIMUM_N`` (surface-locked floor).
    ``expectancy`` may also be SuppressedMetric when n>=5 but no finite
    realized_R is available (e.g., all trades have invalid risk budget).

    ``badges`` reflect the cohort-aggregate confidence-floor warnings
    (composed at the VM/template layer alongside the value).
    """

    cohort_name: str
    n_closed: int
    n_wins: int
    n_losses: int
    samples_R: tuple[float, ...]  # noqa: N815 — spec field name
    legacy_trades_count: int
    win_rate: WilsonCI | SuppressedMetric
    expectancy: BootstrapCI | SuppressedMetric
    badges: HonestyBadges
    decision_criteria: str
    target_sample_size: int

    def __post_init__(self) -> None:
        # Phase 9 forward-binding lesson #1: validate every new dataclass.
        if not self.cohort_name:
            raise ValueError(
                f"CohortStatistics.cohort_name must be non-empty; got "
                f"{self.cohort_name!r}"
            )
        if self.n_closed < 0:
            raise ValueError(
                f"CohortStatistics.n_closed must be >= 0; got {self.n_closed!r}"
            )
        if self.n_wins < 0:
            raise ValueError(
                f"CohortStatistics.n_wins must be >= 0; got {self.n_wins!r}"
            )
        if self.n_losses < 0:
            raise ValueError(
                f"CohortStatistics.n_losses must be >= 0; got {self.n_losses!r}"
            )
        if self.n_wins + self.n_losses > self.n_closed:
            raise ValueError(
                "CohortStatistics.n_wins + n_losses must be <= n_closed "
                f"(got n_wins={self.n_wins!r}, n_losses={self.n_losses!r}, "
                f"n_closed={self.n_closed!r})"
            )
        if self.legacy_trades_count < 0:
            raise ValueError(
                "CohortStatistics.legacy_trades_count must be >= 0; got "
                f"{self.legacy_trades_count!r}"
            )
        if self.legacy_trades_count > self.n_closed:
            raise ValueError(
                "CohortStatistics.legacy_trades_count must be <= n_closed; "
                f"got {self.legacy_trades_count!r} > {self.n_closed!r}"
            )
        if self.target_sample_size < 1:
            raise ValueError(
                "CohortStatistics.target_sample_size must be >= 1; got "
                f"{self.target_sample_size!r}"
            )
        for i, v in enumerate(self.samples_R):
            if not math.isfinite(v):
                raise ValueError(
                    f"CohortStatistics.samples_R[{i}] must be finite "
                    f"(NaN/inf rejected); got {v!r}"
                )


@dataclass(frozen=True)
class TierComparisonResult:
    """§3.3 tier-comparison aggregate across the 4 registered cohorts.

    ``cohorts`` is in :data:`TAXONOMY_COHORTS` order (A+ baseline first;
    Sub-A+ at index 2).

    ``cohort_relative_to_aplus_pct`` maps cohort_name to percent-of-A+
    ratio per dispatch brief §0.9 LOCK: ``cohort_expectancy /
    aplus_expectancy * 100``. None for: A+ itself (baseline self-
    reference), cohort with n<5, A+ with n<5, or aplus_expectancy==0
    (division-by-zero defense).

    ``cohort_ci_overlap_descriptor`` is TEXT per spec §3.3 R1 M3 LOCK.
    Format when active: ``"A+ CI [a, b] vs Sub-A+ CI [c, d] —
    overlap: yes|no"`` with bounds at 2-decimal precision. Suppressed
    placeholder when either A+ or Sub-A+ has n<5 (the descriptor needs
    both cohorts' Wilson CIs to express the comparison).
    ``overlap_descriptor_suppressed`` is True when the descriptor is the
    suppression placeholder (template-side convenience flag).
    """

    cohorts: tuple[CohortStatistics, ...]
    cohort_relative_to_aplus_pct: dict[str, float | None]
    cohort_ci_overlap_descriptor: str
    overlap_descriptor_suppressed: bool

    def __post_init__(self) -> None:
        if len(self.cohorts) != len(TAXONOMY_COHORTS):
            raise ValueError(
                "TierComparisonResult.cohorts must have exactly "
                f"{len(TAXONOMY_COHORTS)} entries (taxonomy-locked); got "
                f"{len(self.cohorts)}"
            )
        seen = tuple(c.cohort_name for c in self.cohorts)
        if seen != TAXONOMY_COHORTS:
            raise ValueError(
                "TierComparisonResult.cohorts must be in TAXONOMY_COHORTS "
                f"order; got {seen!r}"
            )
        if set(self.cohort_relative_to_aplus_pct.keys()) != set(TAXONOMY_COHORTS):
            raise ValueError(
                "TierComparisonResult.cohort_relative_to_aplus_pct keys must "
                f"equal TAXONOMY_COHORTS; got "
                f"{set(self.cohort_relative_to_aplus_pct.keys())!r}"
            )
        for cohort, v in self.cohort_relative_to_aplus_pct.items():
            if v is not None and not math.isfinite(v):
                raise ValueError(
                    f"TierComparisonResult.cohort_relative_to_aplus_pct"
                    f"[{cohort!r}] must be finite or None; got {v!r}"
                )
        if not self.cohort_ci_overlap_descriptor:
            raise ValueError(
                "TierComparisonResult.cohort_ci_overlap_descriptor must be "
                "non-empty (rendered text always; suppression placeholder "
                "fills the slot when descriptor is suppressed)"
            )


@dataclass(frozen=True)
class DeviationOutcomeRow:
    """One row in the §4.7 deviation-outcome table (one per registered cohort).

    ``decision_criterion_evaluation_text`` is the seed text from
    ``hypothesis_registry.decision_criteria`` (migration 0008) verbatim
    per spec §3.7 R1 M4 LOCK — V1 has NO automated pass/fail evaluation;
    operator reads the seed text + judges manually.

    ``expectancy_relative_to_aplus_pct`` is percent delta
    ``(cohort - aplus) / aplus * 100`` per dispatch brief §0.9 LOCK,
    sign-preserving (negative = cohort below baseline). None for: A+
    itself / cohort with n<5 / A+ with n<5 / aplus_expectancy==0.

    ``row_suppressed`` is True when the cohort's own ``n_closed`` falls
    below :data:`COHORT_MINIMUM_N` — the template renders a "n too low"
    placeholder per spec §4.7 ("do NOT hide the row entirely (operator
    needs to see the registered cohort even at n<5)"; the row stays
    visible with the doctrine_deviation_class + decision-criterion text
    but the relative-expectancy cell is suppressed).
    """

    cohort_name: str
    n_closed: int
    doctrine_deviation_class: str
    decision_criteria: str
    decision_criterion_evaluation_text: str
    expectancy_relative_to_aplus_pct: float | None
    row_suppressed: bool
    target_sample_size: int

    def __post_init__(self) -> None:
        if not self.cohort_name:
            raise ValueError(
                f"DeviationOutcomeRow.cohort_name must be non-empty; got "
                f"{self.cohort_name!r}"
            )
        if self.n_closed < 0:
            raise ValueError(
                f"DeviationOutcomeRow.n_closed must be >= 0; got "
                f"{self.n_closed!r}"
            )
        if not self.doctrine_deviation_class:
            raise ValueError(
                "DeviationOutcomeRow.doctrine_deviation_class must be "
                f"non-empty; got {self.doctrine_deviation_class!r}"
            )
        if (
            self.expectancy_relative_to_aplus_pct is not None
            and not math.isfinite(self.expectancy_relative_to_aplus_pct)
        ):
            raise ValueError(
                "DeviationOutcomeRow.expectancy_relative_to_aplus_pct must be "
                f"finite or None; got {self.expectancy_relative_to_aplus_pct!r}"
            )
        if self.target_sample_size < 1:
            raise ValueError(
                "DeviationOutcomeRow.target_sample_size must be >= 1; got "
                f"{self.target_sample_size!r}"
            )


@dataclass(frozen=True)
class DeviationOutcomeResult:
    """§3.7 deviation-outcome aggregate.

    ``rows`` is in :data:`TAXONOMY_COHORTS` order (A+ first as the
    baseline anchor; the per-row ``expectancy_relative_to_aplus_pct``
    field is None for the A+ row by design — see :class:`DeviationOutcomeRow`).
    """

    rows: tuple[DeviationOutcomeRow, ...]

    def __post_init__(self) -> None:
        if len(self.rows) != len(TAXONOMY_COHORTS):
            raise ValueError(
                "DeviationOutcomeResult.rows must have exactly "
                f"{len(TAXONOMY_COHORTS)} entries (taxonomy-locked); got "
                f"{len(self.rows)}"
            )
        seen = tuple(r.cohort_name for r in self.rows)
        if seen != TAXONOMY_COHORTS:
            raise ValueError(
                "DeviationOutcomeResult.rows must be in TAXONOMY_COHORTS "
                f"order; got {seen!r}"
            )


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _load_cohort_meta(
    conn: sqlite3.Connection,
) -> dict[str, dict[str, object]]:
    """Read ``decision_criteria`` + ``target_sample_size`` from
    ``hypothesis_registry`` keyed on cohort name.

    Spec §3.7 R1 M4 LOCK + dispatch brief §0.11 LOCK: the seed text is
    rendered verbatim on the deviation-outcome surface. Schema-locked
    at migration 0008 (FROZEN per migration header — "CLI mutations may
    flip status (and record the reason) but cannot edit
    target_sample_size, consecutive_loss_tripwire,
    absolute_loss_tripwire_pct, or decision_criteria. A formal amendment
    requires a NEW migration with an explicit version bump.").
    """
    rows = conn.execute(
        "SELECT name, decision_criteria, target_sample_size "
        "FROM hypothesis_registry",
    ).fetchall()
    return {
        str(r[0]): {
            "decision_criteria": str(r[1]),
            "target_sample_size": int(r[2]),
        }
        for r in rows
    }


def _compute_cohort_stats(
    conn: sqlite3.Connection,
    *,
    cohort_name: str,
    decision_criteria: str,
    target_sample_size: int,
    live_policy: RiskPolicy,
    trades: list[Trade],
) -> CohortStatistics:
    """Build :class:`CohortStatistics` for a pre-filtered trade list.

    The caller supplies ``trades`` so the T-C.5 elective filter can run
    BEFORE classification — keeping the filter behavior contained at the
    surface-aggregator level (T-C.5 adds the filter helper and the
    ``exclude_unresolved_discrepancies`` parameter to
    :func:`compute_tier_comparison` / :func:`compute_deviation_outcome`).

    Per spec §4.3 + §4.7 SURFACE LOCK: when ``len(trades) < COHORT_MINIMUM_N``,
    both ``win_rate`` and ``expectancy`` are SuppressedMetric regardless of
    the per-class policy floor (the surfaces deliberately raise the floor
    to 5).
    """
    samples: list[float] = []
    n_wins = 0
    n_losses = 0
    legacy_count = 0
    for t in trades:
        realized_R, cls, is_legacy = _per_trade_realized_R(conn, t)  # noqa: N806
        if is_legacy:
            legacy_count += 1
        if cls == "win":
            n_wins += 1
        elif cls == "loss":
            n_losses += 1
        if realized_R is not None and math.isfinite(realized_R):
            samples.append(realized_R)

    n_closed = len(trades)

    win_rate_value: WilsonCI | SuppressedMetric
    expectancy_value: BootstrapCI | SuppressedMetric

    if n_closed < COHORT_MINIMUM_N:
        win_rate_value = _cohort_suppression(
            metric_name=f"cohort_win_rate ({cohort_name})", n=n_closed,
        )
        expectancy_value = _cohort_suppression(
            metric_name=f"cohort_expectancy ({cohort_name})", n=n_closed,
        )
    else:
        # n>=5 ⇒ Wilson CI is always representable (n_wins in [0, n_closed]).
        win_rate_value = wilson_ci(k=n_wins, n=n_closed)
        if samples:
            expectancy_value = bootstrap_ci_mean(
                samples=samples,
                resample_count=int(live_policy.bootstrap_resample_count),
            )
        else:
            # n>=5 but no finite realized_R available (every trade had
            # invalid risk_budget). Surface as suppressed with explanatory
            # placeholder — n=0 references the missing-samples count, not
            # the cohort closed count.
            expectancy_value = _cohort_suppression(
                metric_name=f"cohort_expectancy ({cohort_name})", n=0,
            )

    return CohortStatistics(
        cohort_name=cohort_name,
        n_closed=n_closed,
        n_wins=n_wins,
        n_losses=n_losses,
        samples_R=tuple(samples),
        legacy_trades_count=legacy_count,
        win_rate=win_rate_value,
        expectancy=expectancy_value,
        badges=badges_for_n(n=n_closed, policy=live_policy),
        decision_criteria=decision_criteria,
        target_sample_size=target_sample_size,
    )


def _format_ci_overlap_descriptor(
    *, aplus: CohortStatistics, sub_aplus: CohortStatistics,
) -> tuple[str, bool]:
    """Per spec §3.3 R1 M3 + dispatch brief §0.10 LOCK: TEXT-only descriptor.

    Suppressed when EITHER A+ or Sub-A+ has Wilson CI rendered as
    SuppressedMetric (which happens iff n<5 per cohort-level
    suppression). The placeholder names both cohorts' current n so the
    operator sees what's missing.

    Active format: ``"A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes|no"``
    with bounds at 2-decimal precision. Overlap is the simple interval-
    intersection test ``max(a, c) <= min(b, d)``.
    """
    if isinstance(aplus.win_rate, SuppressedMetric) or isinstance(
        sub_aplus.win_rate, SuppressedMetric,
    ):
        return (
            f"Insufficient cohort samples (need ≥{COHORT_MINIMUM_N} "
            f"per cohort for CI; current: A+: {aplus.n_closed}, "
            f"Sub-A+: {sub_aplus.n_closed})",
            True,
        )
    # Both Wilson CIs are real WilsonCI at this point.
    a_lo, a_hi = aplus.win_rate.lower, aplus.win_rate.upper
    s_lo, s_hi = sub_aplus.win_rate.lower, sub_aplus.win_rate.upper
    overlap = max(a_lo, s_lo) <= min(a_hi, s_hi)
    overlap_word = "yes" if overlap else "no"
    return (
        f"A+ CI [{a_lo:.2f}, {a_hi:.2f}] vs Sub-A+ CI "
        f"[{s_lo:.2f}, {s_hi:.2f}] — overlap: {overlap_word}",
        False,
    )


def compute_tier_comparison(
    conn: sqlite3.Connection,
) -> TierComparisonResult:
    """Compute the §3.3 tier-comparison aggregate.

    Per dispatch brief §0.5 #4 BINDING: TAXONOMY-LOCKED to the 4
    registered cohorts (orphan-labeled trades EXCLUDED). Cohort columns
    render in :data:`TAXONOMY_COHORTS` order.

    T-C.5 elective extends this signature with
    ``exclude_unresolved_discrepancies: bool = False`` (NOT in T-C.1
    scope — separate task lands the helper + parameter).
    """
    live_policy = read_live_policy(conn)
    cohort_meta = _load_cohort_meta(conn)

    cohorts: list[CohortStatistics] = []
    for name in TAXONOMY_COHORTS:
        trades = list_closed_trades_for_cohort(conn, hypothesis_label=name)
        meta = cohort_meta.get(name)
        if meta is None:
            # Defensive: hypothesis_registry seed missing the cohort name
            # (would indicate a corrupted DB). Surface a placeholder
            # criterion to keep the surface renderable.
            decision_criteria = ""
            target_sample_size = 1
        else:
            decision_criteria = str(meta["decision_criteria"])
            target_sample_size = int(meta["target_sample_size"])
        cohorts.append(
            _compute_cohort_stats(
                conn,
                cohort_name=name,
                decision_criteria=decision_criteria,
                target_sample_size=target_sample_size,
                live_policy=live_policy,
                trades=trades,
            ),
        )

    by_name = {c.cohort_name: c for c in cohorts}
    aplus = by_name[APLUS_COHORT]
    sub_aplus = by_name[SUB_APLUS_COHORT]

    aplus_point: float | None = None
    if isinstance(aplus.expectancy, BootstrapCI):
        aplus_point = aplus.expectancy.point

    # ``cohort_relative_to_aplus_pct`` per dispatch brief §0.9 LOCK:
    # raw ratio rendered as percent. None for: A+ itself; cohort with
    # SuppressedMetric expectancy; A+ with SuppressedMetric expectancy;
    # aplus_point == 0 (division-by-zero defense).
    relative_map: dict[str, float | None] = {}
    for c in cohorts:
        if c.cohort_name == APLUS_COHORT:
            relative_map[c.cohort_name] = None
            continue
        if not isinstance(c.expectancy, BootstrapCI):
            relative_map[c.cohort_name] = None
            continue
        if aplus_point is None:
            relative_map[c.cohort_name] = None
            continue
        if aplus_point == 0.0:
            relative_map[c.cohort_name] = None
            continue
        ratio = (c.expectancy.point / aplus_point) * 100.0
        if not math.isfinite(ratio):
            relative_map[c.cohort_name] = None
        else:
            relative_map[c.cohort_name] = ratio

    descriptor_text, descriptor_suppressed = _format_ci_overlap_descriptor(
        aplus=aplus, sub_aplus=sub_aplus,
    )

    return TierComparisonResult(
        cohorts=tuple(cohorts),
        cohort_relative_to_aplus_pct=relative_map,
        cohort_ci_overlap_descriptor=descriptor_text,
        overlap_descriptor_suppressed=descriptor_suppressed,
    )


def compute_deviation_outcome(
    conn: sqlite3.Connection,
) -> DeviationOutcomeResult:
    """Compute the §3.7 deviation-outcome aggregate.

    Re-uses the :func:`compute_tier_comparison` aggregation so per-cohort
    sample sizes + expectancy CIs are consistent between the two
    surfaces (operator's mental model: A+ row n on tier-comparison ==
    A+ row n on deviation-outcome).

    Per spec §3.7 R1 M4 LOCK: ``decision_criterion_evaluation_text``
    renders ``hypothesis_registry.decision_criteria`` seed text verbatim
    (NO automated pass/fail evaluation in V1).

    Per spec §4.7 SURFACE LOCK: cohort row stays VISIBLE at n<5 (showing
    deviation_class + decision-criterion text) — the relative-expectancy
    cell is suppressed, NOT the whole row.

    T-C.5 elective extends this signature with
    ``exclude_unresolved_discrepancies: bool = False`` (NOT in T-C.1
    scope — separate task lands the helper + parameter).
    """
    tier = compute_tier_comparison(conn)
    by_name = {c.cohort_name: c for c in tier.cohorts}
    aplus = by_name[APLUS_COHORT]
    aplus_point: float | None = None
    if isinstance(aplus.expectancy, BootstrapCI):
        aplus_point = aplus.expectancy.point

    rows: list[DeviationOutcomeRow] = []
    for name in TAXONOMY_COHORTS:
        c = by_name[name]
        deviation_class = DOCTRINE_DEVIATION_CLASS[name]
        row_suppressed = c.n_closed < COHORT_MINIMUM_N

        # ``expectancy_relative_to_aplus_pct`` per dispatch brief §0.9 LOCK:
        # delta-percent ``(cohort - aplus) / aplus * 100``. None when:
        # - cohort is A+ itself (baseline self-reference);
        # - cohort or A+ has SuppressedMetric expectancy (n<5);
        # - aplus_point == 0 (division-by-zero defense).
        rel: float | None
        if (
            name == APLUS_COHORT
            or not isinstance(c.expectancy, BootstrapCI)
            or aplus_point is None
            or aplus_point == 0.0
        ):
            rel = None
        else:
            rel_candidate = (
                (c.expectancy.point - aplus_point) / aplus_point
            ) * 100.0
            rel = rel_candidate if math.isfinite(rel_candidate) else None

        rows.append(
            DeviationOutcomeRow(
                cohort_name=name,
                n_closed=c.n_closed,
                doctrine_deviation_class=deviation_class,
                decision_criteria=c.decision_criteria,
                decision_criterion_evaluation_text=c.decision_criteria,
                expectancy_relative_to_aplus_pct=rel,
                row_suppressed=row_suppressed,
                target_sample_size=c.target_sample_size,
            ),
        )

    return DeviationOutcomeResult(rows=tuple(rows))
