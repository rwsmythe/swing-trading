"""Tests for io.py: CSV header shape + aggregate_stats + manifest fields."""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from research.harness.double_bottom_w_backtest.io import (
    RESULTS_CSV_HEADER,
    aggregate_stats,
    write_manifest,
    write_results_csv,
    write_summary_markdown,
)
from research.harness.double_bottom_w_backtest.walkforward import Trade


def _trade(
    *,
    pattern_id: str = "ABC-2026-04-01",
    ticker: str = "ABC",
    ruleset_name: str = "A_minervini_trail_ma",
    status: str = "closed",
    exit_reason: str = "stop_hit",
    r_multiple: float | None = -1.0,
    days_held: int | None = 5,
    entry_date: date | None = date(2026, 5, 4),
    exit_date: date | None = date(2026, 5, 11),
    composite: float = 0.85,
) -> Trade:
    return Trade(
        pattern_id=pattern_id,
        ticker=ticker,
        ruleset_name=ruleset_name,
        anchor_asof_date=date(2026, 5, 1),
        trough_1_date=date(2026, 4, 1),
        center_peak_price=100.0,
        trough_2_price=92.0,
        composite_score=composite,
        initial_stop=92 * 0.99,
        entry_date=entry_date,
        entry_price=101.9 if entry_date else None,
        exit_date=exit_date,
        exit_price=88.0 if exit_date else None,
        exit_reason=exit_reason,
        r_multiple=r_multiple,
        days_held=days_held,
        status=status,
        forward_bars_available=40,
        max_forward_close=95.0,
        max_close_pct_of_peak=95.0,
        days_t2_to_asof=11,
    )


def test_csv_header_has_21_columns() -> None:
    assert len(RESULTS_CSV_HEADER) == 21
    assert "pattern_id" in RESULTS_CSV_HEADER
    assert "r_multiple" in RESULTS_CSV_HEADER
    assert "days_t2_to_asof" in RESULTS_CSV_HEADER


def test_write_results_csv_emits_one_row_per_trade(tmp_path: Path) -> None:
    trades = [
        _trade(pattern_id="ABC-2026-04-01", ruleset_name="A_minervini_trail_ma"),
        _trade(pattern_id="ABC-2026-04-01", ruleset_name="B_fixed_R_multiple"),
        _trade(pattern_id="DEF-2026-04-10", ruleset_name="C_close_below_50d", r_multiple=2.5,
               exit_reason="target_3R"),
    ]
    out = tmp_path / "results.csv"
    write_results_csv(trades, out)
    with out.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    # header round-trip
    assert set(rows[0].keys()) == set(RESULTS_CSV_HEADER)


def test_aggregate_stats_excludes_untriggered_from_win_rate_denominator() -> None:
    trades = [
        _trade(status="closed", r_multiple=2.0, exit_reason="target_3R"),
        _trade(status="closed", r_multiple=-1.0, exit_reason="stop_hit"),
        _trade(status="untriggered", r_multiple=None, days_held=None,
               entry_date=None, exit_date=None, exit_reason="untriggered"),
    ]
    stats = aggregate_stats(trades)
    rs = stats["A_minervini_trail_ma"]
    assert rs["n_closed"] == 2
    assert rs["untriggered"] == 1
    assert rs["winners"] == 1
    assert rs["losers"] == 1
    assert rs["win_rate_closed"] == pytest.approx(0.5)


def test_aggregate_stats_distinguishes_status_open_from_closed() -> None:
    trades = [
        _trade(status="closed", r_multiple=2.0),
        _trade(status="open", r_multiple=0.5, exit_reason="open_at_data_tail", days_held=10),
    ]
    stats = aggregate_stats(trades)
    rs = stats["A_minervini_trail_ma"]
    assert rs["n_closed"] == 1
    assert rs["open_positions"] == 1
    assert rs["n_triggered"] == 2


def test_write_summary_markdown_emits_ascii_only(tmp_path: Path) -> None:
    """ASCII-only on findings.md surfaces per dispatch brief §6.2(b) + cumulative
    gotcha re: PowerShell cp1252 encoder."""
    trades = [_trade()]
    out = tmp_path / "summary.md"
    write_summary_markdown(trades, out, n_patterns=1, cohort_label="test")
    body = out.read_text(encoding="utf-8")
    body.encode("ascii")  # Raises UnicodeEncodeError if non-ASCII present


def test_write_manifest_records_l2_lock_preserved(tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    write_manifest(
        out,
        started_at_utc=datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc),
        finished_at_utc=datetime(2026, 5, 25, 10, 5, 0, tzinfo=timezone.utc),
        cohort_csv_path="exports/research/pattern-cohort-detection-20260525T201617Z/results.csv",
        cohort_csv_sha256="abc123",
        cache_dir="C:\\Users\\rwsmy\\swing-data\\prices-cache",
        n_unique_verdicts_pre_filter=172,
        n_verdicts_after_adjacency_merge=172,
        n_patterns_after_recency_filter=13,
        recency_max_calendar_days=60,
        composite_threshold=0.7,
        max_trigger_search_business_days=60,
        n_trades_emitted=39,
        n_distinct_tickers=11,
        skipped_patterns={"ohlcv_missing": 0},
    )
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["l2_lock_preserved"] is True
    assert manifest["n_patterns_after_recency_filter"] == 13
    assert manifest["recency_max_calendar_days"] == 60
    assert manifest["composite_threshold"] == 0.7
    assert manifest["runtime_seconds"] == 300.0
