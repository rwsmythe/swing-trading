"""Tests for cohort.py: extraction, dedup, recency filter, fixture roundtrip."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from research.harness.double_bottom_w_backtest.cohort import (
    PrimaryVerdict,
    extract_primary_verdicts_from_csv,
    filter_recent_patterns,
    load_cohort_fixture,
    merge_adjacent_troughs,
    write_cohort_fixture,
)


# ---- Fixture-building helpers ------------------------------------------


def _evidence(
    *,
    trough_1_date: str = "2026-04-10",
    trough_1_price: float = 10.0,
    center_peak_date: str = "2026-04-15",
    center_peak_price: float = 12.5,
    trough_2_date: str = "2026-04-25",
    trough_2_price: float = 9.9,
    pivot_price: float = 12.0,
    geometric_score: float = 0.9333,
) -> dict:
    return {
        "trough_1_date": trough_1_date,
        "trough_1_price": trough_1_price,
        "center_peak_date": center_peak_date,
        "center_peak_price": center_peak_price,
        "trough_2_date": trough_2_date,
        "trough_2_price": trough_2_price,
        "pivot_price": pivot_price,
        "geometric_score": geometric_score,
        "stage": "stage_2",
        "recent_stage": "undefined",
        "trough_1_drawdown_pct": 0.10,
        "trough_1_avg_volume": 100000.0,
        "trough_2_avg_volume": 90000.0,
        "center_peak_retracement_pct": 0.50,
        "undercut": True,
        "trough_1_to_center_duration_days": 5,
        "center_to_trough_2_duration_days": 10,
        "criteria_pass": {f"criterion_{i}": True for i in range(1, 9)},
    }


_CSV_HEADER = [
    "cohort_entry_id",
    "cohort_label",
    "ticker",
    "asof_date",
    "candidate_id",
    "eval_run_id",
    "persisted_bucket",
    "persisted_pivot",
    "persisted_initial_stop",
    "window_index",
    "window_start_date",
    "window_end_date",
    "anchor_date",
    "anchor_reason",
    "pattern_class",
    "detector_version",
    "stage_observed",
    "geometric_score",
    "template_match_score",
    "composite_score",
    "template_match_nearest_exemplar_ids_json",
    "criteria_pass_json",
    "structural_evidence_json",
    "skip_reason",
]


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_HEADER)
        w.writeheader()
        for r in rows:
            full = {k: "" for k in _CSV_HEADER}
            full.update(r)
            w.writerow(full)


def _row(
    *,
    cohort_entry_id: int,
    ticker: str,
    asof: str,
    window_index: int,
    pattern_class: str,
    composite: float,
    geometric: float,
    template: float | None,
    evidence_dict: dict,
) -> dict:
    return {
        "cohort_entry_id": cohort_entry_id,
        "cohort_label": "test_cohort",
        "ticker": ticker,
        "asof_date": asof,
        "window_index": window_index,
        "window_start_date": "2021-01-01",
        "window_end_date": asof,
        "anchor_date": evidence_dict["trough_1_date"],
        "anchor_reason": "zigzag_pivot:swing_1_down",
        "pattern_class": pattern_class,
        "detector_version": "double_bottom_w@v1.0.0",
        "stage_observed": "stage_2",
        "geometric_score": f"{geometric:.6f}",
        "template_match_score": "" if template is None else f"{template:.6f}",
        "composite_score": f"{composite:.6f}",
        "criteria_pass_json": json.dumps(evidence_dict["criteria_pass"]),
        "structural_evidence_json": json.dumps(evidence_dict),
    }


# ---- Tests --------------------------------------------------------------


def test_extract_filters_to_double_bottom_w_only(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    rows = [
        _row(
            cohort_entry_id=1, ticker="ABC", asof="2026-05-01", window_index=0,
            pattern_class="vcp", composite=0.85, geometric=0.85, template=None,
            evidence_dict=_evidence(),
        ),
        _row(
            cohort_entry_id=1, ticker="ABC", asof="2026-05-01", window_index=1,
            pattern_class="double_bottom_w", composite=0.92, geometric=0.92, template=None,
            evidence_dict=_evidence(),
        ),
    ]
    _write_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path)
    assert len(verdicts) == 1
    assert verdicts[0].ticker == "ABC"
    assert verdicts[0].composite_score == pytest.approx(0.92)


def test_extract_filters_below_composite_threshold(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    rows = [
        _row(
            cohort_entry_id=1, ticker="ABC", asof="2026-05-01", window_index=0,
            pattern_class="double_bottom_w", composite=0.50, geometric=0.50, template=None,
            evidence_dict=_evidence(),
        ),
        _row(
            cohort_entry_id=2, ticker="DEF", asof="2026-05-01", window_index=0,
            pattern_class="double_bottom_w", composite=0.75, geometric=0.75, template=None,
            evidence_dict=_evidence(),
        ),
    ]
    _write_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path)
    assert len(verdicts) == 1
    assert verdicts[0].ticker == "DEF"


def test_extract_per_key_highest_composite_wins(tmp_path: Path) -> None:
    """Two verdicts with same (ticker, trough_1_date) collapse to one; higher composite wins."""
    csv_path = tmp_path / "results.csv"
    ev = _evidence(trough_1_date="2026-04-10")
    rows = [
        _row(
            cohort_entry_id=1, ticker="ABC", asof="2026-05-01", window_index=10,
            pattern_class="double_bottom_w", composite=0.75, geometric=0.75, template=None,
            evidence_dict=ev,
        ),
        _row(
            cohort_entry_id=2, ticker="ABC", asof="2026-05-01", window_index=11,
            pattern_class="double_bottom_w", composite=0.93, geometric=0.93, template=None,
            evidence_dict=ev,
        ),
        _row(
            cohort_entry_id=3, ticker="ABC", asof="2026-05-01", window_index=12,
            pattern_class="double_bottom_w", composite=0.85, geometric=0.85, template=None,
            evidence_dict=ev,
        ),
    ]
    _write_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.composite_score == pytest.approx(0.93)
    # All three cohort_entry_ids + window_indices preserved for audit
    assert v.cohort_entry_ids == (1, 2, 3)
    assert v.aux_window_indices == (10, 11, 12)


def test_extract_different_trough_dates_yield_distinct_verdicts(tmp_path: Path) -> None:
    """Same ticker, different trough_1_date => separate W patterns."""
    csv_path = tmp_path / "results.csv"
    rows = [
        _row(
            cohort_entry_id=1, ticker="YOU", asof="2026-05-22", window_index=0,
            pattern_class="double_bottom_w", composite=0.93, geometric=0.93, template=None,
            evidence_dict=_evidence(trough_1_date="2021-07-07"),
        ),
        _row(
            cohort_entry_id=2, ticker="YOU", asof="2026-05-22", window_index=124,
            pattern_class="double_bottom_w", composite=0.83, geometric=0.83, template=None,
            evidence_dict=_evidence(trough_1_date="2026-04-29"),
        ),
    ]
    _write_csv(csv_path, rows)
    verdicts = extract_primary_verdicts_from_csv(csv_path)
    assert len(verdicts) == 2
    t1_dates = sorted(v.trough_1_date.isoformat() for v in verdicts)
    assert t1_dates == ["2021-07-07", "2026-04-29"]


def test_merge_adjacent_troughs_collapses_within_5_business_days() -> None:
    """Two verdicts on same ticker with trough_1_date 3 BD apart merge into one."""
    a = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 6),
        trough_1_price=10.0, center_peak_date=date(2026, 4, 10), center_peak_price=12.0,
        trough_2_date=date(2026, 4, 20), trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
        cohort_entry_ids=(1,), aux_window_indices=(0,),
    )
    b = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 9),  # 3 BD later
        trough_1_price=10.1, center_peak_date=date(2026, 4, 12), center_peak_price=12.1,
        trough_2_date=date(2026, 4, 23), trough_2_price=10.0, pivot_price=11.7,
        composite_score=0.92, geometric_score=0.92, template_match_score=None,
        cohort_entry_ids=(2,), aux_window_indices=(1,),
    )
    merged = merge_adjacent_troughs([a, b])
    assert len(merged) == 1
    m = merged[0]
    # Higher-composite verdict (b) wins
    assert m.composite_score == pytest.approx(0.92)
    assert m.trough_1_date == date(2026, 4, 9)
    # All cohort_entry_ids + aux_window_indices preserved (union)
    assert m.cohort_entry_ids == (1, 2)
    assert m.aux_window_indices == (0, 1)


def test_merge_adjacent_troughs_keeps_separated_clusters_separate() -> None:
    """7-BD gap exceeds 5-BD threshold => verdicts stay separate."""
    a = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 1),
        trough_1_price=10.0, center_peak_date=date(2026, 4, 5), center_peak_price=12.0,
        trough_2_date=date(2026, 4, 15), trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
    )
    b = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 13),  # 8 calendar days = 8 BD; >= 5
        trough_1_price=10.1, center_peak_date=date(2026, 4, 17), center_peak_price=12.1,
        trough_2_date=date(2026, 4, 27), trough_2_price=10.0, pivot_price=11.7,
        composite_score=0.92, geometric_score=0.92, template_match_score=None,
    )
    merged = merge_adjacent_troughs([a, b])
    assert len(merged) == 2


def test_filter_recent_patterns_60_calendar_days() -> None:
    """Pattern with trough_2 60d before asof => included; 61d => excluded."""
    recent = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 3, 1),
        trough_1_price=10.0, center_peak_date=date(2026, 3, 5), center_peak_price=12.0,
        trough_2_date=date(2026, 3, 23),  # 60 days before 2026-05-22
        trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
    )
    old = PrimaryVerdict(
        ticker="DEF", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2021, 7, 7),
        trough_1_price=10.0, center_peak_date=date(2021, 7, 12), center_peak_price=12.0,
        trough_2_date=date(2021, 7, 19),
        trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.93, geometric_score=0.93, template_match_score=None,
    )
    filtered = filter_recent_patterns([recent, old], max_calendar_days=60)
    assert len(filtered) == 1
    assert filtered[0].ticker == "ABC"


def test_pattern_id_is_ticker_dash_trough_1_iso() -> None:
    v = PrimaryVerdict(
        ticker="YOU", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 29),
        trough_1_price=55.5, center_peak_date=date(2026, 5, 6), center_peak_price=60.94,
        trough_2_date=date(2026, 5, 13), trough_2_price=55.54, pivot_price=60.06,
        composite_score=0.83, geometric_score=0.83, template_match_score=None,
    )
    assert v.pattern_id == "YOU-2026-04-29"


def test_initial_stop_is_trough_2_times_0_99() -> None:
    v = PrimaryVerdict(
        ticker="YOU", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 29),
        trough_1_price=55.5, center_peak_date=date(2026, 5, 6), center_peak_price=60.94,
        trough_2_date=date(2026, 5, 13), trough_2_price=55.54, pivot_price=60.06,
        composite_score=0.83, geometric_score=0.83, template_match_score=None,
    )
    assert v.initial_stop == pytest.approx(55.54 * 0.99)


def test_trigger_threshold_is_center_peak_price() -> None:
    """W-bottom neckline = center_peak_price (NOT pivot_price); the dispatch
    brief Section 10 explicitly bans pivot_price as the trigger reference."""
    v = PrimaryVerdict(
        ticker="YOU", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 29),
        trough_1_price=55.5, center_peak_date=date(2026, 5, 6), center_peak_price=60.94,
        trough_2_date=date(2026, 5, 13), trough_2_price=55.54, pivot_price=60.06,
        composite_score=0.83, geometric_score=0.83, template_match_score=None,
    )
    assert v.trigger_threshold == 60.94
    assert v.trigger_threshold != v.pivot_price


def test_trigger_lower_bound_is_max_of_three_anchors() -> None:
    """Lower bound = max(trough_1, trough_2, asof). For RECENT W's where
    trough_2 is BEFORE asof, asof wins; for in-progress W's where trough_2 is
    AFTER asof, trough_2 wins."""
    asof_wins = PrimaryVerdict(
        ticker="ABC", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 1),
        trough_1_price=10.0, center_peak_date=date(2026, 4, 8), center_peak_price=12.0,
        trough_2_date=date(2026, 4, 20),  # before asof
        trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
    )
    assert asof_wins.trigger_lower_bound_date == date(2026, 5, 22)
    t2_wins = PrimaryVerdict(
        ticker="DEF", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 5, 10),
        trough_1_price=10.0, center_peak_date=date(2026, 5, 15), center_peak_price=12.0,
        trough_2_date=date(2026, 5, 28),  # AFTER asof
        trough_2_price=9.9, pivot_price=11.5,
        composite_score=0.75, geometric_score=0.75, template_match_score=None,
    )
    assert t2_wins.trigger_lower_bound_date == date(2026, 5, 28)


def test_fixture_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    v = PrimaryVerdict(
        ticker="YOU", anchor_asof_date=date(2026, 5, 22),
        trough_1_date=date(2026, 4, 29),
        trough_1_price=55.5, center_peak_date=date(2026, 5, 6), center_peak_price=60.94,
        trough_2_date=date(2026, 5, 13), trough_2_price=55.54, pivot_price=60.06,
        composite_score=0.83, geometric_score=0.83, template_match_score=0.91,
        cohort_entry_ids=(0, 1, 2), aux_window_indices=(124, 125, 126),
    )
    out_path = tmp_path / "cohort.json"
    write_cohort_fixture([v], out_path)
    loaded = load_cohort_fixture(out_path)
    assert len(loaded) == 1
    lv = loaded[0]
    assert lv.ticker == v.ticker
    assert lv.anchor_asof_date == v.anchor_asof_date
    assert lv.trough_1_date == v.trough_1_date
    assert lv.trough_1_price == v.trough_1_price
    assert lv.center_peak_price == v.center_peak_price
    assert lv.trough_2_price == v.trough_2_price
    assert lv.composite_score == v.composite_score
    assert lv.template_match_score == v.template_match_score
    assert lv.cohort_entry_ids == v.cohort_entry_ids
    assert lv.aux_window_indices == v.aux_window_indices
