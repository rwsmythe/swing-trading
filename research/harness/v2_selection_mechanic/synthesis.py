"""Compatibility verdict synthesis for V2-selection-mechanic investigation.

Per V2-selection-mechanic dispatch brief Sec 1.7 BINDING (gotcha #33
third canonical application REINFORCED): the investigation is ANALYTICAL
not verdict-producing. This module emits descriptive narrative + per-
variable signal table; NO "PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE"
verdict terminology is permitted in the OUTPUT.

Categorical compatibility labels per brief Sec 1.7:
  - COMPATIBLE        : V2 selection enriches or matches baseline W-density
  - PARTIALLY-COMPATIBLE : mixed signal across variables
  - INCOMPATIBLE      : consistent thinning across all V2 substrates

Decision rule (brief Sec 1.7 cross-variable consistency):
  - INCOMPATIBLE     when ALL 5 V2 substrates show negative density delta
  - PARTIALLY-COMPATIBLE when 2-4 of 5 show negative deltas
  - COMPATIBLE       when 0-1 show negative deltas

NOTE: a discriminating test asserts the synthesis output does NOT contain
any banned-term substring (case-insensitive; substring match) -- the
banned-term test is BINDING per gotcha #33.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from research.harness.v2_selection_mechanic.substrate_characterization import (
    CohortAggregateMetrics,
)
from research.harness.v2_selection_mechanic.w_density_analysis import (
    WDensityMetrics,
)


# Banned verdict-style terms per gotcha #33 third canonical application
# (operator-paired LOCK at investigation greenlight 2026-05-26 PM). Any
# of these appearing in synthesis output is a discriminating test failure.
# Case-insensitive substring match (per cumulative discipline).
BANNED_VERDICT_TERMS: tuple[str, ...] = (
    "PARTIAL POSITIVE",
    "POSITIVE",
    "NEGATIVE",
    "INSUFFICIENT SAMPLE",  # also reserved -- per brief Sec 1.7 the
                            # analytical synthesis does not classify the
                            # cohort against statistical thresholds
)


@dataclass(frozen=True)
class PerVariableSignal:
    """Per-V2-variable analytical signal row."""

    variable_name: str
    binding_sweep_point: float
    max_delta_aplus: int  # SUMMARY TABLE value
    drill_down_watch_aplus_count: int  # drill-down filter count
    non_watch_transition_gap: int
    non_watch_transition_gap_pct: float
    substrate_ticker_count: int
    substrate_unique_ticker_asof_count: int
    raw_w_count: int  # composite=0 broadest denominator
    raw_w_count_c_0_5: int  # composite>=0.5 R2-A/R2-D narrative-anchor denominator
    filtered_w_count: int  # post-canonical-filter (Sec 1.6 LOCK)
    filtered_density: float | None  # F / T (brief Sec 1.6 LOCK)
    canonical_survival_rate: float | None  # F / R_raw (composite=0)
    canonical_survival_rate_c_0_5: float | None  # F / R_raw_c_0_5 (R2-A/R2-D anchor)
    density_delta_vs_baseline: float | None
    regime_return_90d_median: float | None
    regime_atr_pct_20d_median: float | None
    regime_high_52w_proximity_pct_median: float | None
    dominant_sector: str  # most-common sector or UNKNOWN
    # Brief Amendment 4: per-variable 3-axis profile tags replace single
    # global compatibility label (operator-paired LOCK 2026-05-27 post-Slice-5)
    profile_productivity_tag: str  # ENRICHED / TYPICAL / DEPLETED
    profile_size_tag: str  # SUFFICIENT / MARGINAL / INSUFFICIENT
    profile_survival_tag: str  # COMPARABLE / DEGRADED / SUPPRESSED


@dataclass(frozen=True)
class CompatibilitySynthesis:
    """Cross-variable compatibility narrative + categorical label."""

    categorical_label: str  # COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE
    negative_delta_count: int
    positive_or_zero_delta_count: int
    narrative_markdown: str
    per_variable_signal_table: tuple[PerVariableSignal, ...]


def _dominant_sector(sector_counts: dict[str, int]) -> str:
    """Most-common sector key; ties broken alphabetically; empty -> UNKNOWN."""
    if not sector_counts:
        return "UNKNOWN"
    return max(sorted(sector_counts.keys()), key=lambda k: sector_counts[k])


def _classify_productivity_tag(
    d_filt: float | None, baseline_density: float
) -> str:
    """ENRICHED / TYPICAL / DEPLETED per Brief Amendment 4 thresholds.

    UNKNOWN if D_filt is None (zero-substrate edge; should not occur
    under canonical investigation contract per R3 MAJOR #1 guard).
    """
    if d_filt is None or baseline_density == 0:
        return "UNKNOWN"
    ratio = d_filt / baseline_density
    if ratio >= PRODUCTIVITY_ENRICHED_MIN_MULTIPLIER:
        return "ENRICHED"
    if ratio >= PRODUCTIVITY_TYPICAL_MIN_MULTIPLIER:
        return "TYPICAL"
    return "DEPLETED"


def _classify_size_tag(t_count: int) -> str:
    """SUFFICIENT (T>=20) / MARGINAL (5<=T<20) / INSUFFICIENT (T<5)."""
    if t_count >= SIZE_SUFFICIENT_MIN:
        return "SUFFICIENT"
    if t_count >= SIZE_MARGINAL_MIN:
        return "MARGINAL"
    return "INSUFFICIENT"


def _classify_survival_tag(survival: float | None) -> str:
    """COMPARABLE (>=10%) / DEGRADED (5-10%) / SUPPRESSED (<5%).

    UNKNOWN if survival is None (raw_w_count == 0; should not occur
    under canonical investigation contract).
    """
    if survival is None:
        return "UNKNOWN"
    if survival >= SURVIVAL_COMPARABLE_MIN:
        return "COMPARABLE"
    if survival >= SURVIVAL_DEGRADED_MIN:
        return "DEGRADED"
    return "SUPPRESSED"


def build_per_variable_signal(
    *,
    variable_name: str,
    binding_sweep_point: float,
    max_delta_aplus: int,
    drill_down_watch_aplus_count: int,
    aggregate_metrics: CohortAggregateMetrics,
    w_density: WDensityMetrics,
    baseline_filtered_density: float | None = None,
) -> PerVariableSignal:
    """Assemble a PerVariableSignal row from cohort characterization +
    W-density metrics. Computes 3-axis profile tags per Brief Amendment 4.
    """
    from research.harness.v2_selection_mechanic import D2_BASELINE_FILTERED_DENSITY

    if baseline_filtered_density is None:
        baseline_filtered_density = D2_BASELINE_FILTERED_DENSITY

    gap = max_delta_aplus - drill_down_watch_aplus_count
    gap_pct = (gap / max_delta_aplus * 100.0) if max_delta_aplus != 0 else 0.0
    return PerVariableSignal(
        variable_name=variable_name,
        binding_sweep_point=binding_sweep_point,
        max_delta_aplus=max_delta_aplus,
        drill_down_watch_aplus_count=drill_down_watch_aplus_count,
        non_watch_transition_gap=gap,
        non_watch_transition_gap_pct=gap_pct,
        substrate_ticker_count=aggregate_metrics.unique_ticker_count,
        substrate_unique_ticker_asof_count=aggregate_metrics.unique_ticker_asof_count,
        raw_w_count=w_density.raw_w_count,
        raw_w_count_c_0_5=w_density.raw_w_count_c_0_5,
        filtered_w_count=w_density.filtered_w_count,
        filtered_density=w_density.filtered_density,
        canonical_survival_rate=w_density.canonical_survival_rate,
        canonical_survival_rate_c_0_5=w_density.canonical_survival_rate_c_0_5,
        density_delta_vs_baseline=w_density.density_delta_vs_baseline,
        regime_return_90d_median=aggregate_metrics.return_90d_pct_median,
        regime_atr_pct_20d_median=aggregate_metrics.atr_pct_20d_median,
        regime_high_52w_proximity_pct_median=aggregate_metrics.high_52w_proximity_pct_median,
        dominant_sector=_dominant_sector(aggregate_metrics.sector_counts),
        profile_productivity_tag=_classify_productivity_tag(
            w_density.filtered_density, baseline_filtered_density
        ),
        profile_size_tag=_classify_size_tag(aggregate_metrics.unique_ticker_count),
        profile_survival_tag=_classify_survival_tag(w_density.canonical_survival_rate),
    )


def classify_compatibility(signals: Sequence[PerVariableSignal]) -> tuple[str, int, int]:
    """LEGACY brief Sec 1.7 cross-variable consistency rule (PRE-Amendment 4).

    Returns (label, below_baseline_count, at_or_above_baseline_count) for
    backward compat with existing tests + ad-hoc tooling. The CANONICAL
    output post-Brief Amendment 4 is per-variable 3-axis profile tags
    (see build_per_variable_signal). This helper remains for the headline
    label preserved in the manifest's `compatibility_label` field; the
    study writeup + narrative emit per-variable tags as the dominant
    surface.

    A density_delta_vs_baseline of None (zero-substrate edge case) counts
    as NEUTRAL (at_or_above_baseline side).
    """
    below = 0
    at_or_above = 0
    for s in signals:
        if s.density_delta_vs_baseline is None:
            at_or_above += 1
        elif s.density_delta_vs_baseline < 0:
            below += 1
        else:
            at_or_above += 1
    total = len(signals)
    if total == 0:
        return "COMPATIBLE", 0, 0
    if below == total:
        return "INCOMPATIBLE", below, at_or_above
    if below >= 2:
        return "PARTIALLY-COMPATIBLE", below, at_or_above
    return "COMPATIBLE", below, at_or_above


def _fmt(value: float | None, *, precision: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{precision}f}"


def _render_per_variable_narrative_label(s: PerVariableSignal) -> str:
    """Per-variable narrative label combining the 3-axis profile tags.

    Format: `<productivity> + <size>(T=<N>) + <survival>(<rate>%)`.
    Descriptive substrate-characterization labels per Brief Amendment 4;
    NO banned verdict terms (gotcha #33).
    """
    survival_pct = (
        f"{s.canonical_survival_rate * 100:.1f}%"
        if s.canonical_survival_rate is not None
        else "n/a"
    )
    return (
        f"{s.profile_productivity_tag} + "
        f"{s.profile_size_tag}(T={s.substrate_ticker_count}) + "
        f"{s.profile_survival_tag}({survival_pct})"
    )


def _render_narrative(
    label: str,
    negative_count: int,
    positive_or_zero_count: int,
    signals: Sequence[PerVariableSignal],
) -> str:
    """Emit the cross-variable narrative synthesis markdown.

    Per Brief Amendment 4 (operator-paired LOCK 2026-05-27 post-Slice-5):
    surfaces 3 metric families + per-variable 3-axis profile tags +
    multi-dimensional narrative. The legacy single-label `label` argument
    is preserved in the manifest's `compatibility_label` field for
    backward compat but the dominant narrative surface is per-variable.

    NO banned-verdict-terms (gotcha #33 LOCK; discriminating test).
    """
    lines: list[str] = []
    lines.append("# V2-Selection-Mechanic Compatibility Synthesis")
    lines.append("")
    lines.append("## Per-Variable 3-Axis Profile (Brief Amendment 4)")
    lines.append("")
    lines.append(
        "Per Brief Amendment 4 (operator-paired LOCK 2026-05-27): each V2 "
        "binding variable is profiled along three substrate-characterization "
        "axes -- per-ticker productivity (ENRICHED / TYPICAL / DEPLETED vs "
        "D2 baseline 0.138 W/ticker); substrate size (SUFFICIENT T>=20 / "
        "MARGINAL 5<=T<20 / INSUFFICIENT T<5); canonical survival quality "
        "(COMPARABLE >=10% / DEGRADED 5-10% / SUPPRESSED <5%; composite=0 "
        "denominator). These are descriptive labels, NOT verdict "
        "terminology (gotcha #33 third canonical application LOCK)."
    )
    lines.append("")
    lines.append(
        "| variable | sweep_point | profile | D_filt | survival(c=0) | survival(c>=0.5) |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for s in signals:
        survival_c0_5_str = (
            f"{s.canonical_survival_rate_c_0_5 * 100:.1f}%"
            if s.canonical_survival_rate_c_0_5 is not None
            else "n/a"
        )
        survival_c0_str = (
            f"{s.canonical_survival_rate * 100:.1f}%"
            if s.canonical_survival_rate is not None
            else "n/a"
        )
        lines.append(
            f"| {s.variable_name} | {s.binding_sweep_point} | "
            f"{_render_per_variable_narrative_label(s)} | "
            f"{_fmt(s.filtered_density)} | "
            f"{survival_c0_str} | {survival_c0_5_str} |"
        )
    lines.append("")
    lines.append("## Three Metric Families Surfaced")
    lines.append("")
    lines.append(
        "1. **Per-ticker productivity** (D_filt = F/T; brief Sec 1.6 LOCK): "
        "Given a V2-selected ticker, how many canonical-filtered W primaries "
        "has it produced historically?"
    )
    lines.append(
        "2. **Substrate size + aggregate output** (T and F): How many "
        "actionable W patterns are available from the substrate as a whole?"
    )
    lines.append(
        "3. **Survival quality** (canonical_survival_rate at composite=0 + "
        "composite>=0.5): Of raw W primaries detected on the substrate, "
        "what fraction are recent + high-composite enough to be actionable? "
        "Two denominators: composite=0 (broadest); composite>=0.5 (R2-A/R2-D "
        "findings-doc-anchor framing)."
    )
    lines.append("")
    lines.append("## Per-Variable Detail Table")
    lines.append("")
    lines.append(
        "| variable | T | R_raw(c=0) | R_raw(c>=0.5) | F | D_filt | "
        "regime_90d_ret | regime_atr_pct | regime_52w_prox | dominant_sector |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    for s in signals:
        lines.append(
            f"| {s.variable_name} | {s.substrate_ticker_count} | "
            f"{s.raw_w_count} | {s.raw_w_count_c_0_5} | {s.filtered_w_count} | "
            f"{_fmt(s.filtered_density)} | "
            f"{_fmt(s.regime_return_90d_median, precision=2)} | "
            f"{_fmt(s.regime_atr_pct_20d_median, precision=2)} | "
            f"{_fmt(s.regime_high_52w_proximity_pct_median, precision=2)} | "
            f"{s.dominant_sector} |"
        )
    lines.append("")
    lines.append("## Legacy Single-Label Categorical (Pre-Amendment 4)")
    lines.append("")
    lines.append(
        f"For backward compat the legacy F/T-only categorical label "
        f"under brief Sec 1.7 yields: **{label}**. {negative_count} of "
        f"{len(signals)} substrate(s) showed BELOW-BASELINE F/T; "
        f"{positive_or_zero_count} showed AT-or-ABOVE-BASELINE. NOTE: "
        f"this label is preserved for manifest backward compat ONLY; the "
        f"dominant narrative is the per-variable 3-axis profile above."
    )
    lines.append("")
    lines.append("## Methodological Notes")
    lines.append("")
    lines.append(
        "- Canonical filter held FIXED across all 5 V2 substrates + D2 "
        "EXPANDED baseline: composite >= 0.5 AND recency <= 365d (gotcha "
        "#33 third canonical application REINFORCED)."
    )
    lines.append(
        "- D2 EXPANDED bias-free baseline: 71 filtered W primaries over "
        "516 unique S&P 500 tickers (D_filt = 0.138 W per ticker; "
        "manifest 20260526T000409Z; Brief Amendment 2 corrected universe "
        "size from 88 to 516 at investigation greenlight 2026-05-26 PM)."
    )
    lines.append(
        "- D2 baseline canonical_survival_rate is NOT AVAILABLE in V1 "
        "because the D2 baseline run emitted manifest.json + summary.md "
        "but NOT results.csv (Option B fallback per orchestrator greenlight). "
        "Banked V2 candidate: re-run D2 EXPANDED with results.csv emission "
        "enabled to capture the survival-rate baseline anchor for direct "
        "delta comparison."
    )
    lines.append(
        "- The investigation is ANALYTICAL, not a backtest. Per-ruleset "
        "P&L outcomes were established by R2-A + R2-D + D2 + D1 backtest "
        "arcs and are referenced contextually but NOT recomputed."
    )
    lines.append(
        "- Per-variable SUMMARY-TABLE vs drill-down non-watch-transition "
        "gap is documented as a methodological side-finding: "
        "vcp.tightness_range_factor +75 SUMMARY vs 67 drill-down (gap 8; "
        "~11%); vcp.tightness_days_required +16 vs 15 (gap 1; 6%); other "
        "3 variables show zero gap. The Sensitivity Matrix is the "
        "authoritative source for the binding signal."
    )
    return "\n".join(lines) + "\n"


class SynthesisContractError(ValueError):
    """Raised when synthesis input violates the investigation contract.

    Codex R1 MAJOR #4 fix 2026-05-26 PM: prior implementation accepted
    empty signal lists + returned categorical label COMPATIBLE,
    silently masking upstream orchestration failures (e.g., all 5
    cohort substrates were empty due to detection-run failure -- which
    SHOULD halt the investigation, not classify as COMPATIBLE).
    """


# Canonical 5-variable investigation contract per dispatch brief Q2
# operator-paired LOCK 2026-05-26 AM (all 5 V2 binding variables in scope).
CANONICAL_SIGNAL_COUNT = 5

# -----------------------------------------------------------------------
# Brief Amendment 4 profile-tag thresholds (operator-paired LOCK
# 2026-05-27 post-Slice-5).
# -----------------------------------------------------------------------
# Per-ticker productivity: D_filt relative to baseline filtered density
# (D2 baseline = 0.138). Tags calibrated against operator-prescribed
# example labels:
#   tightness_range_factor   D_filt=9.13 (~66x) -> ENRICHED
#   tightness_days_required  D_filt=9.14 (~66x) -> ENRICHED
#   adr_min_pct              D_filt=1.00 (~7x)  -> TYPICAL
#   proximity_max_pct        D_filt=9.67 (~70x) -> ENRICHED
#   orderliness_max_bar_ratio D_filt=3.00 (~22x) -> ENRICHED
PRODUCTIVITY_ENRICHED_MIN_MULTIPLIER = 10.0  # D_filt >= 10x baseline
PRODUCTIVITY_TYPICAL_MIN_MULTIPLIER = 2.0    # D_filt 2-10x baseline = TYPICAL
# D_filt < 2x baseline = DEPLETED

# Substrate size: T (unique tickers)
SIZE_SUFFICIENT_MIN = 20    # T >= 20 = SUFFICIENT
SIZE_MARGINAL_MIN = 5       # T >= 5 = MARGINAL; T < 5 = INSUFFICIENT

# Survival quality (composite=0 denominator): F / R_raw
SURVIVAL_COMPARABLE_MIN = 0.10  # >=10% = COMPARABLE
SURVIVAL_DEGRADED_MIN = 0.05    # 5-10% = DEGRADED; <5% = SUPPRESSED


def _validate_no_banned_terms_in_input(signals: Sequence[PerVariableSignal]) -> None:
    """Codex R4 MAJOR #2 fix: pre-render contract check that no per-signal
    field carries a banned-verdict-term substring.

    Pre-fix: dominant_sector or variable_name carrying a banned substring
    (e.g., a hypothetical Finviz sector "Positive Services") would
    silently render into the narrative; the post-render banned-terms
    discriminating test would then fail with no clear attribution. This
    pre-render check raises SynthesisContractError with the offending
    field + value identified.
    """
    for s in signals:
        for field_name in ("variable_name", "dominant_sector"):
            value = getattr(s, field_name)
            value_lower = str(value).lower()
            for banned in BANNED_VERDICT_TERMS:
                if banned.lower() in value_lower:
                    raise SynthesisContractError(
                        f"PerVariableSignal {s.variable_name!r} field "
                        f"{field_name}={value!r} contains banned verdict "
                        f"term {banned!r}. The synthesis output contract "
                        f"(gotcha #33 third canonical application) requires "
                        f"NO banned terms in rendered narrative."
                    )


def synthesize(
    signals: Sequence[PerVariableSignal],
    *,
    require_canonical_signal_count: bool = True,
) -> CompatibilitySynthesis:
    """Emit the cross-variable compatibility synthesis.

    Raises SynthesisContractError if:
      - signals is empty
      - (when require_canonical_signal_count is True) signals length
        does not match CANONICAL_SIGNAL_COUNT
      - any per-signal `variable_name` or `dominant_sector` value
        contains a banned-verdict-term substring (Codex R4 MAJOR #2 fix
        2026-05-26 PM)

    Caller can pass require_canonical_signal_count=False for ad-hoc
    analytical use cases against subsets; the V1 canonical run.py
    invocation enforces the 5-variable contract.

    Output narrative markdown MUST NOT contain any BANNED_VERDICT_TERMS
    substring (gotcha #33 third canonical application LOCK).
    """
    if not signals:
        raise SynthesisContractError(
            "synthesize() received empty signals list; the investigation "
            "contract is 5 V2 binding variables (dispatch brief Q2 LOCK). "
            "Pass require_canonical_signal_count=False for ad-hoc "
            "analytical subsets."
        )
    if require_canonical_signal_count and len(signals) != CANONICAL_SIGNAL_COUNT:
        raise SynthesisContractError(
            f"synthesize() received {len(signals)} signals; canonical "
            f"contract requires exactly {CANONICAL_SIGNAL_COUNT} per "
            f"dispatch brief Q2 LOCK. Pass "
            f"require_canonical_signal_count=False for ad-hoc subsets."
        )
    _validate_no_banned_terms_in_input(signals)
    label, neg, pos = classify_compatibility(signals)
    narrative = _render_narrative(label, neg, pos, signals)
    return CompatibilitySynthesis(
        categorical_label=label,
        negative_delta_count=neg,
        positive_or_zero_delta_count=pos,
        narrative_markdown=narrative,
        per_variable_signal_table=tuple(signals),
    )
