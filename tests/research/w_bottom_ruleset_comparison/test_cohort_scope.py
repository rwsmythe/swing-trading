"""Cohort scope assertions per dispatch brief Section 5.5.

These tests verify the cohort generation + extraction pipeline yields
counts in the expected ranges. The cohort extractor + dedup pipeline
is reused VERBATIM from D1 (research.harness.double_bottom_w_backtest.cohort)
+ tests at tests/research/double_bottom_w_backtest/test_cohort.py cover
the per-row mechanics; this file asserts the SCOPE expectations specific
to D2 (cohort SIZE not D1's selection-biased N=12).
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from research.harness.double_bottom_w_backtest.cohort import (
    PrimaryVerdict,
    extract_primary_verdicts_from_csv,
    filter_recent_patterns,
    merge_adjacent_troughs,
)


def _write_synthetic_results_csv(
    path: Path,
    rows: list[dict],
) -> None:
    """Write a synthetic pattern_cohort_evaluator results.csv subset.

    Includes the minimum columns the cohort extractor reads:
      pattern_class, composite_score, structural_evidence_json, cohort_entry_id,
      window_index, asof_date, ticker, geometric_score, template_match_score.
    """
    fieldnames = [
        "cohort_entry_id", "ticker", "asof_date", "window_index",
        "pattern_class", "geometric_score", "template_match_score",
        "composite_score", "structural_evidence_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def test_cohort_extractor_filters_to_double_bottom_w_composite_threshold(tmp_path):
    """Verify the extractor admits only pattern_class=double_bottom_w with
    composite_score >= threshold."""
    rows = [
        # Below threshold: skipped
        {
            "cohort_entry_id": "0", "ticker": "TKR1", "asof_date": "2026-04-30",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.5", "template_match_score": "0.4",
            "composite_score": "0.65",
            "structural_evidence_json": '{"trough_1_date":"2026-02-01","trough_1_price":80.0,"center_peak_date":"2026-03-01","center_peak_price":100.0,"trough_2_date":"2026-04-01","trough_2_price":82.0,"pivot_price":99.0}',
        },
        # Above threshold + correct pattern_class: admitted
        {
            "cohort_entry_id": "1", "ticker": "TKR2", "asof_date": "2026-04-30",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.8", "template_match_score": "0.85",
            "composite_score": "0.82",
            "structural_evidence_json": '{"trough_1_date":"2026-02-15","trough_1_price":85.0,"center_peak_date":"2026-03-15","center_peak_price":105.0,"trough_2_date":"2026-04-10","trough_2_price":87.0,"pivot_price":104.0}',
        },
        # Wrong pattern_class: skipped
        {
            "cohort_entry_id": "2", "ticker": "TKR3", "asof_date": "2026-04-30",
            "window_index": "0", "pattern_class": "vcp",
            "geometric_score": "0.9", "template_match_score": "0.9",
            "composite_score": "0.9",
            "structural_evidence_json": "{}",
        },
    ]
    csv_path = tmp_path / "synthetic_results.csv"
    _write_synthetic_results_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path, composite_threshold=0.7)
    assert len(verdicts) == 1
    assert verdicts[0].ticker == "TKR2"
    assert verdicts[0].composite_score == pytest.approx(0.82)


def test_cohort_extractor_dedups_per_ticker_trough_1_date(tmp_path):
    """Multiple windows on the same (ticker, trough_1_date) -> primary =
    highest composite_score."""
    rows = [
        {
            "cohort_entry_id": "0", "ticker": "TKR1", "asof_date": "2026-04-25",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.7", "template_match_score": "0.7",
            "composite_score": "0.70",
            "structural_evidence_json": '{"trough_1_date":"2026-02-15","trough_1_price":85.0,"center_peak_date":"2026-03-15","center_peak_price":105.0,"trough_2_date":"2026-04-10","trough_2_price":87.0,"pivot_price":104.0}',
        },
        {
            "cohort_entry_id": "0", "ticker": "TKR1", "asof_date": "2026-04-25",
            "window_index": "1", "pattern_class": "double_bottom_w",
            "geometric_score": "0.95", "template_match_score": "0.9",
            "composite_score": "0.93",
            "structural_evidence_json": '{"trough_1_date":"2026-02-15","trough_1_price":85.0,"center_peak_date":"2026-03-15","center_peak_price":105.0,"trough_2_date":"2026-04-10","trough_2_price":87.0,"pivot_price":104.0}',
        },
    ]
    csv_path = tmp_path / "synthetic_results.csv"
    _write_synthetic_results_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path, composite_threshold=0.7)
    assert len(verdicts) == 1
    assert verdicts[0].composite_score == pytest.approx(0.93)


def test_recency_filter_uses_max_observed_asof_date(tmp_path):
    """Two observations of same W: highest-composite asof OLDER than
    most-recent asof. Recency uses max_observed_asof per D1 Codex R1 M#3.
    """
    rows = [
        # Older observation: highest composite (becomes primary)
        {
            "cohort_entry_id": "0", "ticker": "TKR1", "asof_date": "2026-04-15",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.95", "template_match_score": "0.9",
            "composite_score": "0.93",
            "structural_evidence_json": '{"trough_1_date":"2026-02-15","trough_1_price":85.0,"center_peak_date":"2026-03-15","center_peak_price":105.0,"trough_2_date":"2026-04-10","trough_2_price":87.0,"pivot_price":104.0}',
        },
        # Newer observation: lower composite; same W structure
        {
            "cohort_entry_id": "1", "ticker": "TKR1", "asof_date": "2026-05-22",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.75", "template_match_score": "0.8",
            "composite_score": "0.77",
            "structural_evidence_json": '{"trough_1_date":"2026-02-15","trough_1_price":85.0,"center_peak_date":"2026-03-15","center_peak_price":105.0,"trough_2_date":"2026-04-10","trough_2_price":87.0,"pivot_price":104.0}',
        },
    ]
    csv_path = tmp_path / "synthetic_results.csv"
    _write_synthetic_results_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path, composite_threshold=0.7)
    assert len(verdicts) == 1
    v = verdicts[0]
    # Primary = highest composite (older observation; asof 2026-04-15)
    assert v.anchor_asof_date == date(2026, 4, 15)
    # max_observed_asof = newest observation (asof 2026-05-22)
    assert v.max_observed_asof_date == date(2026, 5, 22)
    # 2026-05-22 - 2026-04-10 = 42 calendar days; within 60d filter
    filtered = filter_recent_patterns(verdicts, max_calendar_days=60)
    assert len(filtered) == 1
    # ...but a tight 30d filter rejects (42 > 30)
    filtered_30 = filter_recent_patterns(verdicts, max_calendar_days=30)
    assert len(filtered_30) == 0


def test_cohort_pipeline_dedup_through_recency_chain(tmp_path):
    """End-to-end: 3 verdicts with 2 W structures + recency filter -> 2 primaries.

    Plant: TKR1 has 2 windows of one W (dedups to 1 primary); TKR2 has 1 W.
    Both pass composite>=0.7 + recency.
    """
    rows = [
        # TKR1 W1, window 0
        {
            "cohort_entry_id": "0", "ticker": "TKR1", "asof_date": "2026-05-15",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.85", "template_match_score": "0.85",
            "composite_score": "0.85",
            "structural_evidence_json": '{"trough_1_date":"2026-03-01","trough_1_price":80.0,"center_peak_date":"2026-03-20","center_peak_price":100.0,"trough_2_date":"2026-04-15","trough_2_price":82.0,"pivot_price":99.0}',
        },
        # TKR1 W1, window 1 (higher composite; primary)
        {
            "cohort_entry_id": "1", "ticker": "TKR1", "asof_date": "2026-05-15",
            "window_index": "1", "pattern_class": "double_bottom_w",
            "geometric_score": "0.95", "template_match_score": "0.95",
            "composite_score": "0.95",
            "structural_evidence_json": '{"trough_1_date":"2026-03-01","trough_1_price":80.0,"center_peak_date":"2026-03-20","center_peak_price":100.0,"trough_2_date":"2026-04-15","trough_2_price":82.0,"pivot_price":99.0}',
        },
        # TKR2 W2
        {
            "cohort_entry_id": "2", "ticker": "TKR2", "asof_date": "2026-05-22",
            "window_index": "0", "pattern_class": "double_bottom_w",
            "geometric_score": "0.80", "template_match_score": "0.80",
            "composite_score": "0.80",
            "structural_evidence_json": '{"trough_1_date":"2026-03-10","trough_1_price":50.0,"center_peak_date":"2026-04-05","center_peak_price":60.0,"trough_2_date":"2026-04-22","trough_2_price":52.0,"pivot_price":59.0}',
        },
    ]
    csv_path = tmp_path / "synthetic_results.csv"
    _write_synthetic_results_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path, composite_threshold=0.7)
    assert len(verdicts) == 2
    merged = merge_adjacent_troughs(verdicts)
    assert len(merged) == 2  # no adjacency merge fires (different tickers)
    actionable = filter_recent_patterns(merged, max_calendar_days=60)
    assert len(actionable) == 2
