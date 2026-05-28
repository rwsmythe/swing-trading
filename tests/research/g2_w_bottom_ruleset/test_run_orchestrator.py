"""Tests for the G2 run.py orchestrator (Slice 5a).

Verifies:
  - run_backtest_for_substrate emits trades for all 9 rulesets
    (6 A-F + 3 G/H/I) per verdict
  - _filter_d2_expanded applies composite>=0.5 + recency<=365d + adjacency
    merge per D2 Amendment 5
  - Artifact emission writes scorecard.csv + per_trade_detail.csv +
    summary.md + narrative_synthesis.md + manifest.json with correct shapes
  - Manifest carries L2 LOCK assertions (zero schwab/yfinance/swing writes)
  - Narrative + summary are ASCII-only
  - Narrative does NOT emit banned-verdict terms
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
)
from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest import run as g2_run
from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
    R_DOLLAR_SIZE_AT_7500_FLOOR,
    SCORECARD_CSV_HEADER,
)
from research.harness.w_bottom_ruleset_comparison.rulesets import all_rulesets


def _make_verdict(
    ticker: str, *,
    trough_2_date: date = date(2025, 12, 1),
    anchor_asof_date: date = date(2026, 1, 5),
    composite_score: float = 0.75,
) -> PrimaryVerdict:
    return PrimaryVerdict(
        ticker=ticker,
        anchor_asof_date=anchor_asof_date,
        trough_1_date=date(2025, 11, 1),
        trough_1_price=50.0,
        center_peak_date=date(2025, 11, 15),
        center_peak_price=60.0,
        trough_2_date=trough_2_date,
        trough_2_price=52.0,
        pivot_price=60.0,
        composite_score=composite_score,
        geometric_score=composite_score,
        template_match_score=None,
        cohort_entry_ids=(1,),
        aux_window_indices=(0,),
        max_observed_asof_date=anchor_asof_date,
        observed_asof_dates=(anchor_asof_date,),
        window_count=1,
    )


def _make_synthetic_bars_with_breakout() -> pd.DataFrame:
    """Synthetic OHLCV with a clean volume-confirmed breakout that satisfies
    all G/H/I predicates AND the existing A-F entry semantics.

    Pre-window bars MUST span from before the trough_2_date (2025-12-01)
    THROUGH the asof_date (2026-01-05) so the Edwards-Magee predicate has
    rally bars to compute its baseline from. Using ~90 bars from
    2025-09-01 reaches past 2026-01-05 with rally bars in (Dec 1, Jan 6).
    """
    pre_dates = pd.bdate_range(start=date(2025, 9, 1), periods=90)
    pre_closes = [55.0] * 90
    pre_volumes = [1_000_000.0] * 90
    # Trigger bar: first bdate after 2026-01-05 (= 2026-01-06 Mon)
    trigger_date = pd.bdate_range(start=date(2026, 1, 6), periods=1)[0]
    trigger_close = 62.0
    trigger_volume = 5_000_000.0  # 5x baseline; passes 1.3 / 1.4 / 1.5 gates
    n_post = 40
    post_dates = pd.bdate_range(
        start=trigger_date + pd.tseries.offsets.BDay(1), periods=n_post
    )
    post_opens = [trigger_close]
    post_closes = [trigger_close + 0.5]
    for k in range(1, n_post):
        post_opens.append(post_closes[k - 1])
        post_closes.append(min(post_closes[k - 1] + 0.5, 80.0))
    all_dates = list(pre_dates) + [trigger_date] + list(post_dates)
    all_closes = pre_closes + [trigger_close] + post_closes
    all_opens = pre_closes + [trigger_close] + post_opens
    all_volumes = pre_volumes + [trigger_volume] + [1_000_000.0] * n_post
    return pd.DataFrame(
        {
            "Open": all_opens,
            "High": [max(o, c) + 0.10 for o, c in zip(all_opens, all_closes)],
            "Low": [min(o, c) - 0.10 for o, c in zip(all_opens, all_closes)],
            "Close": all_closes,
            "Volume": all_volumes,
        },
        index=all_dates,
    )


def test_run_backtest_for_substrate_emits_9_rulesets_per_verdict(monkeypatch):
    """For a substrate of N verdicts, the orchestrator emits N * 9 trade
    rows (6 existing A-F + 3 new G/H/I)."""
    verdicts = [_make_verdict("TST"), _make_verdict("TST2")]
    synthetic_bars = _make_synthetic_bars_with_breakout()

    def stub_reader(ticker, cache_dir, diagnostic=None):
        return synthetic_bars

    monkeypatch.setattr(
        "research.harness.g2_w_bottom_ruleset_backtest.run.read_yfinance_shape_a",
        stub_reader,
    )
    trades, skipped = g2_run.run_backtest_for_substrate(
        verdicts, Path("/fake/cache"), diagnostic=BothExistDiagnostic()
    )
    # 2 verdicts * 9 rulesets = 18 trades
    assert len(trades) == 18
    ruleset_names = {t.ruleset_name for t in trades}
    expected_ruleset_names = {rs.name for rs in all_rulesets()} | {
        "G_bulkowski_double_bottom",
        "H_oneil_double_bottom_base",
        "I_edwards_magee_classical_double_bottom",
    }
    assert ruleset_names == expected_ruleset_names
    # All trades triggered (synthetic bars satisfy all 9 rulesets' entry rules)
    triggered = [t for t in trades if t.triggered]
    assert len(triggered) == 18


def test_filter_d2_expanded_applies_composite_and_recency():
    """_filter_d2_expanded admits composite>=0.5 + recency<=365d; drops
    composite<0.5 + drops recency>365d."""
    today = date(2026, 1, 1)
    verdicts = [
        _make_verdict("OK1", composite_score=0.6, trough_2_date=date(2025, 6, 1),
                     anchor_asof_date=today),
        _make_verdict("LOW", composite_score=0.4, trough_2_date=date(2025, 6, 1),
                     anchor_asof_date=today),
        _make_verdict("OLD", composite_score=0.6,
                     trough_2_date=date(2024, 1, 1),  # > 365d before today
                     anchor_asof_date=today),
        _make_verdict("OK2", composite_score=0.55,
                     trough_2_date=date(2025, 11, 1),
                     anchor_asof_date=today),
    ]
    filtered = g2_run._filter_d2_expanded(verdicts)
    tickers = {v.ticker for v in filtered}
    assert "OK1" in tickers
    assert "OK2" in tickers
    assert "LOW" not in tickers
    assert "OLD" not in tickers


def test_main_orchestrator_emits_full_artifact_bundle(monkeypatch, tmp_path):
    """End-to-end: invoke main() with a tiny synthetic cohort + verify
    smoke artifact bundle is written with correct shapes + L2 LOCK
    assertions in manifest."""
    # Build tiny R2-A fixture (1 verdict) + tiny D2 raw fixture (1 verdict
    # passing the EXPANDED filter)
    r2a_fixture = tmp_path / "r2a_cohort.json"
    d2_fixture = tmp_path / "d2_cohort.json"
    # Use a recent trough_2_date so recency-filter admits the D2 verdict
    v1 = _make_verdict(
        "AAA",
        trough_2_date=date(2025, 12, 1),
        anchor_asof_date=date(2026, 1, 5),
    )
    v2 = _make_verdict(
        "BBB",
        trough_2_date=date(2025, 12, 1),
        anchor_asof_date=date(2026, 1, 5),
        composite_score=0.55,
    )
    r2a_fixture.write_text(json.dumps([v1.to_dict()]), encoding="utf-8")
    d2_fixture.write_text(json.dumps([v2.to_dict()]), encoding="utf-8")

    synthetic_bars = _make_synthetic_bars_with_breakout()

    def stub_reader(ticker, cache_dir, diagnostic=None):
        return synthetic_bars

    monkeypatch.setattr(
        "research.harness.g2_w_bottom_ruleset_backtest.run.read_yfinance_shape_a",
        stub_reader,
    )

    output_dir = tmp_path / "exports"
    rc = g2_run.main([
        "--r2a-cohort-fixture", str(r2a_fixture),
        "--d2-cohort-fixture", str(d2_fixture),
        "--cache-dir", str(tmp_path / "cache"),
        "--output-dir", str(output_dir),
    ])
    assert rc == 0

    # Locate the timestamped output subdir
    subdirs = list(output_dir.glob("g2-w-bottom-ruleset-backtest-*"))
    assert len(subdirs) == 1
    out = subdirs[0]
    scorecard_csv = out / "scorecard.csv"
    per_trade_csv = out / "per_trade_detail.csv"
    summary_md = out / "summary.md"
    narrative_md = out / "narrative_synthesis.md"
    manifest_json = out / "manifest.json"
    for p in (scorecard_csv, per_trade_csv, summary_md, narrative_md, manifest_json):
        assert p.exists(), f"missing artifact: {p}"

    # Scorecard: 9 rulesets * 2 substrates = 18 rows
    with scorecard_csv.open(encoding="utf-8", newline="") as fp:
        reader = csv.reader(fp)
        header = next(reader)
        rows = list(reader)
    assert header == list(SCORECARD_CSV_HEADER)
    assert len(rows) == 18

    # Per-trade detail: 2 substrates * 1 verdict each * 9 rulesets = 18 rows
    with per_trade_csv.open(encoding="utf-8", newline="") as fp:
        reader = csv.reader(fp)
        next(reader)  # header
        per_trade_rows = list(reader)
    assert len(per_trade_rows) == 18

    # Manifest L2 LOCK assertions
    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    assert manifest["schwab_api_calls"] == 0
    assert manifest["production_swing_writes"] == 0
    assert manifest["yfinance_fetches_at_backtest_time"] == 0
    assert manifest["rulesets_total"] == 9
    assert manifest["rulesets_existing_af"] == 6
    assert manifest["rulesets_new_ghi"] == 3
    assert manifest["r_dollar_size_at_7500_floor"] == R_DOLLAR_SIZE_AT_7500_FLOOR
    assert manifest["g2_version"] == "1.0"

    # All emitted text files are ASCII-only
    for md_path in (summary_md, narrative_md):
        text = md_path.read_text(encoding="utf-8")
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise AssertionError(
                f"{md_path.name} contains non-ASCII characters: {exc}"
            )


def test_narrative_synthesis_does_not_emit_banned_verdict_terms(
    monkeypatch, tmp_path
):
    """Gotcha #33 LOCK: narrative_synthesis.md MUST NOT emit
    PARTIAL POSITIVE / NEGATIVE / POSITIVE."""
    r2a_fixture = tmp_path / "r2a_cohort.json"
    d2_fixture = tmp_path / "d2_cohort.json"
    v = _make_verdict("XXX")
    r2a_fixture.write_text(json.dumps([v.to_dict()]), encoding="utf-8")
    d2_fixture.write_text(json.dumps([v.to_dict()]), encoding="utf-8")

    def stub_reader(ticker, cache_dir, diagnostic=None):
        return _make_synthetic_bars_with_breakout()

    monkeypatch.setattr(
        "research.harness.g2_w_bottom_ruleset_backtest.run.read_yfinance_shape_a",
        stub_reader,
    )
    output_dir = tmp_path / "out"
    g2_run.main([
        "--r2a-cohort-fixture", str(r2a_fixture),
        "--d2-cohort-fixture", str(d2_fixture),
        "--cache-dir", str(tmp_path / "c"),
        "--output-dir", str(output_dir),
    ])
    narrative = next(output_dir.glob("g2-*/narrative_synthesis.md")).read_text(
        encoding="utf-8"
    )
    # Banned verdict terms (case-insensitive word-boundary)
    for pattern in [r"\bPARTIAL\s+POSITIVE\b", r"\bPOSITIVE\b", r"\bNEGATIVE\b"]:
        matches = re.findall(pattern, narrative, flags=re.IGNORECASE)
        assert not matches, (
            f"narrative_synthesis.md contains banned verdict pattern "
            f"{pattern!r}: {matches}"
        )


def test_main_orchestrator_handles_missing_ohlcv_gracefully(
    monkeypatch, tmp_path
):
    """When the OHLCV reader raises OhlcvCoverageError, the trade row is
    emitted with exit_reason='ohlcv_missing' + status='untriggered'; the
    skipped counters reflect the miss."""
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
        OhlcvCoverageError,
    )

    def raising_reader(ticker, cache_dir, diagnostic=None):
        raise OhlcvCoverageError(f"no cache for {ticker}")

    monkeypatch.setattr(
        "research.harness.g2_w_bottom_ruleset_backtest.run.read_yfinance_shape_a",
        raising_reader,
    )
    verdicts = [_make_verdict("MISSING")]
    trades, skipped = g2_run.run_backtest_for_substrate(
        verdicts, Path("/fake/cache"), diagnostic=BothExistDiagnostic()
    )
    assert len(trades) == 9  # 9 rulesets x 1 verdict
    assert all(t.exit_reason == "ohlcv_missing" for t in trades)
    assert all(not t.triggered for t in trades)
    assert skipped["ohlcv_missing"] == 1
    assert skipped["skipped_tickers_ohlcv_missing"] == 1
    assert skipped["skipped_patterns_ohlcv_missing"] == 1
