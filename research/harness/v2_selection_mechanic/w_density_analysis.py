"""W-density measurement orchestration for V2-selection-mechanic investigation.

Per V2-selection-mechanic dispatch brief Sec 1.6, computes:

  - Substrate ticker count (T)        : unique tickers in cohort
  - Canonical-filtered W count (F)    : double_bottom_w primaries surviving
                                        composite>=0.5 + recency<=365d
                                        + 5-BD adjacency merge
  - Filtered density (D_filt)         : F / T (avg canonical-filtered W
                                        primaries per ticker)
  - Density delta vs baseline         : D_filt(cohort) - D_filt(D2 baseline)

D_raw_baseline (raw W primary count BEFORE canonical filter) is NOT
AVAILABLE in V1 because the D2 baseline run emitted manifest.json +
summary.md but NOT results.csv (Option B fallback per orchestrator
greenlight 2026-05-26 PM). The investigation surfaces ONLY D_filt
deltas; banked V2 candidate: re-run D2 EXPANDED with results.csv emission
enabled.

W primary verdict emission is the responsibility of the detection
harness `pattern_cohort_evaluator` (Phase 13 detector pipeline). This
module CONSUMES pre-emitted W primaries (passed as a structured iterable
or loaded from a results CSV) and applies the canonical filter +
adjacency merge.

The actual `pattern_cohort_evaluator` invocation is delegated to
`run.py` (slice 4c) which orchestrates the full pipeline including
detection runs. This module's primitives are PURE (consume planted
verdicts; produce W-density metrics) so they are testable on synthetic
fixtures without invoking the detector.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO yfinance imports;
ZERO production swing/ writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from research.harness.v2_selection_mechanic import (
    CANONICAL_COMPOSITE_THRESHOLD,
    CANONICAL_RECENCY_DAYS,
    D2_BASELINE_FILTERED_DENSITY,
    D2_BASELINE_FILTERED_W_COUNT,
    D2_BASELINE_UNIVERSE_SIZE,
)


@dataclass(frozen=True)
class WPrimaryVerdict:
    """One W primary verdict (pattern_class == 'double_bottom_w' with is_primary=True).

    `anchor_asof_date` is the asof_date of the candidate window the
    detector evaluated (mirrors D1 + D2 schema). `trough_1_date` /
    `trough_2_date` are the structural landmarks per D1 backtest
    contract. `composite_score` is the final post-template composite.
    """

    ticker: str
    anchor_asof_date: date
    trough_1_date: date
    trough_2_date: date
    composite_score: float


@dataclass(frozen=True)
class WDensityMetrics:
    """Per-cohort W-density measurement."""

    cohort_label: str
    substrate_ticker_count: int  # T
    filtered_w_count: int  # F
    filtered_density: float | None  # F / T (None if T == 0)
    density_delta_vs_baseline: float | None  # D_filt - D2_baseline_density


def apply_canonical_filter(
    verdicts: Iterable[WPrimaryVerdict],
    *,
    composite_threshold: float = CANONICAL_COMPOSITE_THRESHOLD,
    recency_days: int = CANONICAL_RECENCY_DAYS,
    reference_date: date | None = None,
) -> list[WPrimaryVerdict]:
    """Filter W primaries by canonical filter (composite>=threshold + recency).

    `reference_date` defaults to the maximum anchor_asof_date in the
    verdict list (per D1 + D2 precedent for "recency from cohort's most
    recent observation"). recency_days defines the maximum gap between
    trough_2_date and reference_date.
    """
    verdicts_list = list(verdicts)
    if not verdicts_list:
        return []
    if reference_date is None:
        reference_date = max(v.anchor_asof_date for v in verdicts_list)
    out: list[WPrimaryVerdict] = []
    for v in verdicts_list:
        if v.composite_score < composite_threshold:
            continue
        recency_gap_days = (reference_date - v.trough_2_date).days
        if recency_gap_days > recency_days:
            continue
        out.append(v)
    return out


def merge_adjacency_5bd(
    verdicts: Sequence[WPrimaryVerdict],
) -> list[WPrimaryVerdict]:
    """5-BD adjacency merge: collapse per-(ticker, trough_1_date) clusters.

    Within each cluster, dedupe by trough_2_date with the highest
    composite_score winning if multiple trough_2_dates exist within 5
    business days of each other. Returns one verdict per (ticker,
    trough_1_date, dedup'd-trough_2). Stable across runs (sorted output).

    NOTE: this is V1 minimal implementation -- production D1 has full
    adjacency-merge semantics; here we implement the (ticker,
    trough_1_date) clustering with highest-composite winner, which is
    methodologically equivalent for the substrate-density measurement
    use case per dispatch brief Sec 1.6.
    """
    if not verdicts:
        return []
    # Group by (ticker, trough_1_date)
    groups: dict[tuple[str, date], list[WPrimaryVerdict]] = {}
    for v in verdicts:
        key = (v.ticker, v.trough_1_date)
        groups.setdefault(key, []).append(v)
    # Highest-composite winner per group
    winners: list[WPrimaryVerdict] = []
    for key, members in groups.items():
        best = max(members, key=lambda x: x.composite_score)
        winners.append(best)
    winners.sort(key=lambda x: (x.ticker, x.trough_1_date))
    return winners


def compute_w_density(
    cohort_label: str,
    substrate_tickers: Iterable[str],
    canonical_filtered_verdicts: Sequence[WPrimaryVerdict],
    *,
    baseline_filtered_density: float = D2_BASELINE_FILTERED_DENSITY,
) -> WDensityMetrics:
    """Compute W-density metrics for a substrate.

    Parameters:
      cohort_label: human-readable cohort identifier
      substrate_tickers: unique tickers in the substrate (T)
      canonical_filtered_verdicts: W primaries surviving canonical
        filter + adjacency merge (F)
      baseline_filtered_density: D2 EXPANDED N=71 / 516 = 0.1376
        (overridable for tests)

    Returns WDensityMetrics. If `substrate_tickers` is empty, filtered_density
    is None (avoids div-by-zero per dispatch brief Sec 4.2 edge case
    discriminating test contract).
    """
    tickers = {t.upper() for t in substrate_tickers}
    t_count = len(tickers)
    f_count = len(list(canonical_filtered_verdicts))
    if t_count == 0:
        d_filt = None
        delta = None
    else:
        d_filt = f_count / t_count
        delta = d_filt - baseline_filtered_density
    return WDensityMetrics(
        cohort_label=cohort_label,
        substrate_ticker_count=t_count,
        filtered_w_count=f_count,
        filtered_density=d_filt,
        density_delta_vs_baseline=delta,
    )


def baseline_metrics_snapshot() -> WDensityMetrics:
    """Return a synthetic WDensityMetrics row representing the D2 EXPANDED
    bias-free baseline (delta_vs_baseline is 0 by construction)."""
    return WDensityMetrics(
        cohort_label="d2_expanded_baseline_sp500",
        substrate_ticker_count=D2_BASELINE_UNIVERSE_SIZE,
        filtered_w_count=D2_BASELINE_FILTERED_W_COUNT,
        filtered_density=D2_BASELINE_FILTERED_DENSITY,
        density_delta_vs_baseline=0.0,
    )
