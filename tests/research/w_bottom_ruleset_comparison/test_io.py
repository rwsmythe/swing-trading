"""IO tests for D2: CSV schema preservation + cross-ruleset summary."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from research.harness.w_bottom_ruleset_comparison.io import (
    RESULTS_CSV_HEADER,
    aggregate_stats,
    cross_ruleset_comparison,
    write_manifest,
    write_results_csv,
    write_summary_markdown,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import Trade


def _trade(
    *,
    ruleset_name: str = "A_minervini_trail_ma",
    status: str = "closed",
    r_multiple: float | None = -0.5,
    exit_reason: str = "close_below_50d",
    triggered: bool = True,
    days_held: int | None = 3,
    composite: float = 0.85,
    pattern_id: str = "TEST-2026-01-01",
    peak_R: float | None = 0.5,
    dd_R: float | None = 1.0,
) -> Trade:
    return Trade(
        pattern_id=pattern_id, ticker="TEST", ruleset_name=ruleset_name,
        anchor_asof_date=date(2026, 5, 1), trough_1_date=date(2026, 1, 1),
        center_peak_price=100.0, trough_2_price=90.0,
        composite_score=composite, initial_stop=89.1,
        entry_date=date(2026, 5, 5), entry_price=102.0,
        exit_date=date(2026, 5, 8), exit_price=95.0,
        exit_reason=exit_reason, r_multiple=r_multiple,
        days_held=days_held, status=status,
        triggered=triggered, trade_pnl_dollars=-18.75,
        peak_unrealized_R=peak_R, drawdown_to_exit_R=dd_R,
        forward_bars_available=30, max_forward_close=105.0,
        max_close_pct_of_peak=105.0, days_t2_to_asof=20,
        effective_asof_date=date(2026, 5, 1),
        max_observed_asof_date=date(2026, 5, 1),
    )


def test_results_csv_header_has_27_columns():
    """Preserve D1's 27-column schema post-Codex R3 M#2."""
    assert len(RESULTS_CSV_HEADER) == 27


def test_write_results_csv_emits_one_row_per_trade(tmp_path):
    trades = [_trade(ruleset_name=rs) for rs in ("A_minervini_trail_ma", "B_fixed_R_multiple", "C_close_below_50d")]
    csv_path = tmp_path / "results.csv"
    write_results_csv(trades, csv_path)
    lines = csv_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1 + len(trades)  # header + N rows
    header = lines[0].split(",")
    assert header == RESULTS_CSV_HEADER


def test_aggregate_stats_per_ruleset_keyed_by_ruleset_name():
    trades = [
        _trade(ruleset_name="A_minervini_trail_ma", status="closed", r_multiple=0.5),
        _trade(ruleset_name="A_minervini_trail_ma", status="closed", r_multiple=-1.0),
        _trade(ruleset_name="B_fixed_R_multiple", status="closed", r_multiple=2.0),
    ]
    stats = aggregate_stats(trades)
    assert set(stats.keys()) == {"A_minervini_trail_ma", "B_fixed_R_multiple"}
    a = stats["A_minervini_trail_ma"]
    assert a["n_closed"] == 2
    assert a["winners"] == 1
    assert a["losers"] == 1
    assert a["win_rate_closed"] == pytest.approx(0.5)
    assert a["expectancy_R_closed"] == pytest.approx(-0.25)


def test_cross_ruleset_comparison_sorts_by_expectancy_descending():
    """Higher expectancy = better rank (lower rank index)."""
    trades = [
        _trade(ruleset_name="A_minervini_trail_ma", r_multiple=-0.5),
        _trade(ruleset_name="B_fixed_R_multiple", r_multiple=1.5),
        _trade(ruleset_name="C_close_below_50d", r_multiple=0.0),
    ]
    ranked = cross_ruleset_comparison(trades)
    assert ranked[0][0] == "B_fixed_R_multiple"  # best
    assert ranked[1][0] == "C_close_below_50d"
    assert ranked[2][0] == "A_minervini_trail_ma"  # worst


def test_cross_ruleset_comparison_puts_n_closed_zero_rulesets_at_bottom():
    """A ruleset with 0 closed trades has expectancy=None; sorts to bottom."""
    trades = [
        _trade(ruleset_name="A_minervini_trail_ma", r_multiple=0.5),
        _trade(ruleset_name="B_fixed_R_multiple", status="open", r_multiple=0.2),
    ]
    ranked = cross_ruleset_comparison(trades)
    # A has expectancy=0.5; B has None -> A first
    assert ranked[0][0] == "A_minervini_trail_ma"
    assert ranked[1][0] == "B_fixed_R_multiple"


def test_write_summary_markdown_is_ascii_only(tmp_path):
    """Per cumulative gotcha #32 -- ASCII discipline scope across all surfaces."""
    trades = [
        _trade(ruleset_name="A_minervini_trail_ma", r_multiple=0.5),
        _trade(ruleset_name="B_fixed_R_multiple", r_multiple=-0.3),
    ]
    out_path = tmp_path / "summary.md"
    write_summary_markdown(
        trades, out_path,
        n_patterns=2,
        cohort_label="test_cohort",
        population_notes="Synthetic test population.",
    )
    body = out_path.read_text(encoding="utf-8")
    # Must encode as ASCII without errors per gotcha #32
    body.encode("ascii")


def test_write_summary_markdown_contains_cross_ruleset_comparison_section(tmp_path):
    trades = [_trade(ruleset_name=rs) for rs in (
        "A_minervini_trail_ma", "B_fixed_R_multiple", "C_close_below_50d",
    )]
    out_path = tmp_path / "summary.md"
    write_summary_markdown(
        trades, out_path,
        n_patterns=1, cohort_label="test",
    )
    body = out_path.read_text(encoding="utf-8")
    assert "Cross-ruleset comparison" in body
    assert "Per-ruleset aggregate stats" in body
    assert "Exit-reason breakdown" in body


def test_write_manifest_carries_l2_lock_preserved_true(tmp_path):
    out_path = tmp_path / "manifest.json"
    started = datetime.now(timezone.utc)
    finished = started
    write_manifest(
        out_path,
        started_at_utc=started,
        finished_at_utc=finished,
        cohort_csv_path="test.csv",
        cohort_csv_sha256="abc123",
        cache_dir="/tmp/cache",
        n_unique_verdicts_pre_filter=100,
        n_verdicts_after_adjacency_merge=80,
        n_patterns_after_recency_filter=50,
        recency_max_calendar_days=60,
        composite_threshold=0.7,
        max_trigger_search_business_days=60,
        n_trades_emitted=300,
        n_distinct_tickers=40,
        skipped_patterns={"ohlcv_missing": 0, "ohlcv_empty": 0},
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["l2_lock_preserved"] is True
    assert data["rulesets_count"] == 6
    assert len(data["rulesets_enumerated"]) == 6
    assert "F_qullamaggie_momentum_burst" in data["rulesets_enumerated"]
    assert data["harness_name"] == "w_bottom_ruleset_comparison"
