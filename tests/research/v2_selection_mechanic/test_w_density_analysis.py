"""W-density analysis primitive tests on synthetic verdict fixtures."""
from __future__ import annotations

from datetime import date

import pytest

from research.harness.v2_selection_mechanic import (
    D2_BASELINE_FILTERED_DENSITY,
    D2_BASELINE_FILTERED_W_COUNT,
    D2_BASELINE_UNIVERSE_SIZE,
)
from research.harness.v2_selection_mechanic.w_density_analysis import (
    WDensityMetrics,
    WPrimaryVerdict,
    apply_canonical_filter,
    baseline_metrics_snapshot,
    compute_w_density,
    merge_adjacency_5bd,
)


def _vp(
    ticker: str,
    anchor: date,
    t1: date,
    t2: date,
    composite: float,
) -> WPrimaryVerdict:
    return WPrimaryVerdict(
        ticker=ticker,
        anchor_asof_date=anchor,
        trough_1_date=t1,
        trough_2_date=t2,
        composite_score=composite,
    )


# ----- D2 baseline constant sanity -----


def test_d2_baseline_constants_lock() -> None:
    """Per __init__.py LOCK: 516 / 71 / 0.1376."""
    assert D2_BASELINE_UNIVERSE_SIZE == 516
    assert D2_BASELINE_FILTERED_W_COUNT == 71
    assert abs(D2_BASELINE_FILTERED_DENSITY - 71 / 516) < 1e-12


def test_baseline_metrics_snapshot_zero_delta() -> None:
    """baseline_metrics_snapshot has delta = 0 by construction."""
    snap = baseline_metrics_snapshot()
    assert snap.substrate_ticker_count == D2_BASELINE_UNIVERSE_SIZE
    assert snap.filtered_w_count == D2_BASELINE_FILTERED_W_COUNT
    assert snap.density_delta_vs_baseline == 0.0


# ----- apply_canonical_filter -----


def test_canonical_filter_drops_low_composite() -> None:
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.45),  # below
        _vp("BBB", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.50),  # at threshold
        _vp("CCC", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.75),  # above
    ]
    filtered = apply_canonical_filter(verdicts)
    survivors = {v.ticker for v in filtered}
    assert survivors == {"BBB", "CCC"}


def test_canonical_filter_drops_stale_recency() -> None:
    """recency_days=365 cutoff on (reference_date - trough_2_date).days gap."""
    verdicts = [
        _vp("RECENT", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.6),
        _vp("STALE", date(2026, 5, 1), date(2024, 1, 1), date(2024, 1, 15), 0.6),  # ~ 470d back
    ]
    filtered = apply_canonical_filter(verdicts)
    survivors = {v.ticker for v in filtered}
    assert survivors == {"RECENT"}


def test_canonical_filter_empty_input() -> None:
    assert apply_canonical_filter([]) == []


def test_canonical_filter_reference_date_auto() -> None:
    """reference_date defaults to max anchor_asof_date in cohort."""
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.6),
        _vp("BBB", date(2026, 3, 1), date(2026, 2, 1), date(2026, 2, 15), 0.6),
    ]
    filtered = apply_canonical_filter(verdicts)
    # Reference should be 2026-05-01; both within 365d
    assert {v.ticker for v in filtered} == {"AAA", "BBB"}


# ----- merge_adjacency_5bd -----


def test_merge_adjacency_dedups_by_ticker_trough1() -> None:
    """Two verdicts on same (ticker, trough_1_date) with different composites -> highest wins."""
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.6),
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 20), 0.8),  # higher
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 25), 0.5),
        _vp("BBB", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.7),
    ]
    merged = merge_adjacency_5bd(verdicts)
    assert len(merged) == 2
    aaa_winner = next(v for v in merged if v.ticker == "AAA")
    assert aaa_winner.composite_score == 0.8
    assert aaa_winner.trough_2_date == date(2026, 4, 20)


def test_merge_adjacency_distinct_trough1_preserved() -> None:
    """Different trough_1_date on same ticker -> 2 distinct primaries."""
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.6),
        _vp("AAA", date(2026, 5, 1), date(2026, 3, 1), date(2026, 3, 15), 0.7),
    ]
    merged = merge_adjacency_5bd(verdicts)
    assert len(merged) == 2


def test_merge_adjacency_empty() -> None:
    assert merge_adjacency_5bd([]) == []


def test_merge_adjacency_stable_sort() -> None:
    """Output is sorted by (ticker, trough_1_date) deterministically."""
    verdicts = [
        _vp("BBB", date(2026, 5, 1), date(2026, 4, 5), date(2026, 4, 15), 0.7),
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.6),
        _vp("AAA", date(2026, 5, 1), date(2026, 3, 1), date(2026, 3, 15), 0.5),
    ]
    merged = merge_adjacency_5bd(verdicts)
    assert merged[0].ticker == "AAA"
    assert merged[0].trough_1_date == date(2026, 3, 1)
    assert merged[1].ticker == "AAA"
    assert merged[1].trough_1_date == date(2026, 4, 1)
    assert merged[2].ticker == "BBB"


# ----- compute_w_density -----


def test_compute_w_density_known_counts() -> None:
    """Plant 3 tickers + 2 filtered W primaries -> D_filt = 2/3."""
    tickers = ["AAA", "BBB", "CCC"]
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.7),
        _vp("BBB", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.7),
    ]
    m = compute_w_density("test", tickers, verdicts)
    assert m.substrate_ticker_count == 3
    assert m.filtered_w_count == 2
    assert m.filtered_density is not None
    assert abs(m.filtered_density - 2 / 3) < 1e-9
    # Delta vs baseline 0.1376; 0.6667 - 0.1376 ~ +0.529
    assert m.density_delta_vs_baseline is not None
    assert abs(m.density_delta_vs_baseline - (2 / 3 - D2_BASELINE_FILTERED_DENSITY)) < 1e-9


def test_compute_w_density_zero_tickers_returns_none_density() -> None:
    """Zero tickers -> filtered_density is None (no div-by-zero per brief 4.2)."""
    m = compute_w_density("empty", [], [])
    assert m.substrate_ticker_count == 0
    assert m.filtered_density is None
    assert m.density_delta_vs_baseline is None


def test_compute_w_density_zero_filtered_yields_zero_density() -> None:
    """Tickers present + zero filtered W -> D_filt = 0 (thin substrate)."""
    m = compute_w_density("thin", ["AAA", "BBB"], [])
    assert m.substrate_ticker_count == 2
    assert m.filtered_w_count == 0
    assert m.filtered_density == 0.0
    # Delta = 0 - 0.1376 = -0.1376
    assert m.density_delta_vs_baseline is not None
    assert abs(m.density_delta_vs_baseline - (-D2_BASELINE_FILTERED_DENSITY)) < 1e-9


def test_compute_w_density_dedupes_tickers() -> None:
    """Substrate_ticker_count counts UNIQUE tickers (case-insens)."""
    m = compute_w_density("dups", ["AAA", "aaa", "BBB"], [])
    assert m.substrate_ticker_count == 2


def test_compute_w_density_distinguishes_correct_vs_buggy_arithmetic() -> None:
    """Per cumulative `feedback_verify_regression_test_arithmetic`:

    The discriminating test asserts D_filt = F/T (correct) rather than
    D_filt = F/F or D_filt = T/F (common arithmetic bugs).
    """
    tickers = ["AAA"] * 1 + ["BBB"] * 1 + ["CCC"] * 1  # 3 unique tickers
    verdicts = [
        _vp("AAA", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.7),
        _vp("BBB", date(2026, 5, 1), date(2026, 4, 1), date(2026, 4, 15), 0.7),
    ]
    m = compute_w_density("test", tickers, verdicts)
    correct_density = 2 / 3
    buggy_density_self = 2 / 2  # F/F = 1.0
    buggy_density_inverse = 3 / 2  # T/F = 1.5
    assert abs(m.filtered_density - correct_density) < 1e-9
    assert abs(m.filtered_density - buggy_density_self) > 0.3
    assert abs(m.filtered_density - buggy_density_inverse) > 0.8
