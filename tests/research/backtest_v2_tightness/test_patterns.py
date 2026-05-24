"""Tests for pattern-group dedup."""
from __future__ import annotations

from datetime import date

from research.harness.backtest_v2_tightness.patterns import (
    CandidateRow,
    group_consecutive_eval_runs,
)


def _row(ticker: str, eval_run_id: int, asof: str, pivot: float = 100.0, stop: float = 90.0) -> CandidateRow:
    return CandidateRow(
        ticker=ticker,
        eval_run_id=eval_run_id,
        data_asof_date=date.fromisoformat(asof),
        v1_bucket="watch",
        pivot=pivot,
        initial_stop=stop,
        close=95.0,
    )


def test_single_ticker_consecutive_runs_collapse_to_one_pattern() -> None:
    rows = [
        _row("YOU", 55, "2026-05-18"),
        _row("YOU", 56, "2026-05-18"),
        _row("YOU", 57, "2026-05-18"),
    ]
    patterns = group_consecutive_eval_runs(rows)
    assert len(patterns) == 1
    p = patterns[0]
    assert p.ticker == "YOU"
    assert p.first_eval_run_id == 55
    assert p.pattern_id == "YOU-r55"
    assert p.eval_run_ids == (55, 56, 57)
    assert p.n_runs == 3


def test_separated_clusters_per_ticker_create_separate_patterns() -> None:
    rows = [
        _row("RLMD", 13, "2026-04-23"),
        _row("RLMD", 14, "2026-04-23"),
        _row("RLMD", 33, "2026-05-04"),
        _row("RLMD", 42, "2026-05-11"),
        _row("RLMD", 43, "2026-05-11"),
        _row("RLMD", 44, "2026-05-12"),
    ]
    patterns = group_consecutive_eval_runs(rows)
    # 3 clusters: (13,14) at 2026-04-23, (33) at 2026-05-04, (42,43,44) at 2026-05-11..12
    assert len(patterns) == 3
    pat_ids = [p.pattern_id for p in patterns]
    assert "RLMD-r13" in pat_ids
    assert "RLMD-r33" in pat_ids
    assert "RLMD-r42" in pat_ids


def test_first_eval_run_provides_pivot_and_stop() -> None:
    rows = [
        _row("KOD", 25, "2026-04-30", pivot=10.0, stop=8.0),
        _row("KOD", 26, "2026-04-30", pivot=11.0, stop=8.5),
        _row("KOD", 27, "2026-04-30", pivot=12.0, stop=9.0),
    ]
    patterns = group_consecutive_eval_runs(rows)
    assert len(patterns) == 1
    assert patterns[0].pivot == 10.0
    assert patterns[0].initial_stop == 8.0


def test_multiple_tickers_grouped_independently() -> None:
    rows = [
        _row("YOU", 55, "2026-05-18"),
        _row("DK", 53, "2026-05-15"),
        _row("YOU", 56, "2026-05-18"),
        _row("DK", 54, "2026-05-15"),
    ]
    patterns = group_consecutive_eval_runs(rows)
    pat_ids = sorted(p.pattern_id for p in patterns)
    assert pat_ids == ["DK-r53", "YOU-r55"]


def test_empty_input_returns_empty() -> None:
    assert group_consecutive_eval_runs([]) == []
