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
    filtered_w_count: int
    filtered_density: float | None
    density_delta_vs_baseline: float | None
    regime_return_90d_median: float | None
    regime_atr_pct_20d_median: float | None
    regime_high_52w_proximity_pct_median: float | None
    dominant_sector: str  # most-common sector or UNKNOWN


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


def build_per_variable_signal(
    *,
    variable_name: str,
    binding_sweep_point: float,
    max_delta_aplus: int,
    drill_down_watch_aplus_count: int,
    aggregate_metrics: CohortAggregateMetrics,
    w_density: WDensityMetrics,
) -> PerVariableSignal:
    """Assemble a PerVariableSignal row from cohort characterization +
    W-density metrics."""
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
        filtered_w_count=w_density.filtered_w_count,
        filtered_density=w_density.filtered_density,
        density_delta_vs_baseline=w_density.density_delta_vs_baseline,
        regime_return_90d_median=aggregate_metrics.return_90d_pct_median,
        regime_atr_pct_20d_median=aggregate_metrics.atr_pct_20d_median,
        regime_high_52w_proximity_pct_median=aggregate_metrics.high_52w_proximity_pct_median,
        dominant_sector=_dominant_sector(aggregate_metrics.sector_counts),
    )


def classify_compatibility(signals: Sequence[PerVariableSignal]) -> tuple[str, int, int]:
    """Apply the brief Sec 1.7 cross-variable consistency rule.

    Returns (label, negative_count, positive_or_zero_count).
    A density_delta_vs_baseline of None (e.g., zero-substrate edge case)
    counts as NEUTRAL (positive_or_zero side).
    """
    negative = 0
    positive_or_zero = 0
    for s in signals:
        if s.density_delta_vs_baseline is None:
            positive_or_zero += 1
        elif s.density_delta_vs_baseline < 0:
            negative += 1
        else:
            positive_or_zero += 1
    total = len(signals)
    if total == 0:
        return "COMPATIBLE", 0, 0
    if negative == total:
        return "INCOMPATIBLE", negative, positive_or_zero
    if negative >= 2:
        return "PARTIALLY-COMPATIBLE", negative, positive_or_zero
    return "COMPATIBLE", negative, positive_or_zero


def _fmt(value: float | None, *, precision: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{precision}f}"


def _render_narrative(
    label: str,
    negative_count: int,
    positive_or_zero_count: int,
    signals: Sequence[PerVariableSignal],
) -> str:
    """Emit the cross-variable narrative synthesis markdown.

    NO banned-verdict-terms (gotcha #33 LOCK). Discriminating test
    asserts the output text does not contain any BANNED_VERDICT_TERMS
    substring (case-insensitive).
    """
    lines: list[str] = []
    lines.append("# V2-Selection-Mechanic Compatibility Synthesis")
    lines.append("")
    lines.append(f"## Categorical Compatibility: {label}")
    lines.append("")
    lines.append(
        f"Across {len(signals)} V2 binding variables analyzed, "
        f"{negative_count} substrate(s) showed BELOW-BASELINE filtered "
        f"W-density delta vs the D2 EXPANDED bias-free reference; "
        f"{positive_or_zero_count} substrate(s) showed AT-or-ABOVE-BASELINE "
        f"density relative to that reference."
    )
    lines.append("")
    lines.append("## Per-Variable Signal Table")
    lines.append("")
    lines.append(
        "| variable | sweep_point | T (tickers) | F (filtered W) | "
        "D_filt | delta_vs_baseline | regime_90d_return_median | "
        "regime_atr_pct_median | regime_52w_prox_median | dominant_sector |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    for s in signals:
        lines.append(
            f"| {s.variable_name} | {s.binding_sweep_point} | "
            f"{s.substrate_ticker_count} | {s.filtered_w_count} | "
            f"{_fmt(s.filtered_density)} | "
            f"{_fmt(s.density_delta_vs_baseline)} | "
            f"{_fmt(s.regime_return_90d_median, precision=2)} | "
            f"{_fmt(s.regime_atr_pct_20d_median, precision=2)} | "
            f"{_fmt(s.regime_high_52w_proximity_pct_median, precision=2)} | "
            f"{s.dominant_sector} |"
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
        "516 unique S&P 500 tickers (density = 0.1376 W per ticker; "
        "manifest 20260526T000409Z; Brief Amendment 2 corrected universe "
        "size from 88 to 516 at investigation greenlight 2026-05-26 PM)."
    )
    lines.append(
        "- Raw W-density (D_raw) is NOT AVAILABLE in V1 because D2 baseline "
        "results.csv was not emitted at baseline-run time; Option B "
        "fallback per orchestrator greenlight emits only D_filt. Banked "
        "V2 candidate: re-run D2 EXPANDED with results.csv emission "
        "enabled to capture raw-density anchor."
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
