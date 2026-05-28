"""Orchestrator for the G2 W-bottom ruleset backtest.

Loads R2-A + D2 EXPANDED substrates (REUSE VERBATIM per brief Sec 1.6);
runs A-F + G + H + I rulesets per substrate (A-F via the existing
walk_forward; G/H/I via walk_forward_with_trigger_predicate for volume
gating); computes the 9-metric scorecard per (ruleset, substrate); emits
the smoke artifact bundle to exports/research/g2-w-bottom-ruleset-backtest-
<TS>/.

Substrate conventions:
  - R2-A (`tests/fixtures/research/r2a_tightness_days_required/cohort.json`):
    consumed VERBATIM (N=65; pre-filtered by the R2-A harness).
  - D2 EXPANDED (`tests/fixtures/research/double_bottom_w_backtest/
    cohort.json`): loaded raw (N=172); filtered to composite>=0.5 +
    recency<=365d + 5-BD adjacency merge per D2 Amendment 5.
    Brief Amendment 1 (post-Codex R1 MAJOR #2): brief Sec 1.3 stated
    'N=71' citing D2 Amendment 5; the SHA-locked fixture + brief-locked
    filter actually yields N=42 at dispatch baseline (cohort drifted
    since Amendment 5 was run). Per gotcha #34, the SHA-locked
    fixture + filter is authoritative; substrate name is
    'd2_expanded' (no embedded count) to avoid label-vs-actual
    confusion in artifacts.

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO yfinance
fetches at backtest time (OHLCV via the existing V2 Shape A reader
inherited from research.harness.aplus_v2_ohlcv_evaluator).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
)
from research.harness.double_bottom_w_backtest.cohort import (
    PrimaryVerdict,
    filter_recent_patterns,
    load_cohort_fixture,
    merge_adjacent_troughs,
)
from research.harness.g2_w_bottom_ruleset_backtest.io import (
    write_manifest,
    write_narrative_synthesis_markdown,
    write_per_trade_detail_csv,
    write_summary_markdown,
)
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.g_bulkowski_double_bottom import (  # noqa: E501
    RulesetG,
    bulkowski_trigger_predicate,
)
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.h_oneil_double_bottom_base import (  # noqa: E501
    RulesetH,
    oneil_trigger_predicate,
)
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.i_edwards_magee_classical import (  # noqa: E501
    RulesetI,
    edwards_magee_trigger_predicate,
)
from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
    R_DOLLAR_SIZE_AT_7500_FLOOR,
    ScorecardRow,
    build_scorecard_row,
    write_scorecard_csv,
)
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    walk_forward_with_trigger_predicate,
)
from research.harness.w_bottom_ruleset_comparison.rulesets import all_rulesets
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    Trade,
    walk_forward,
)


# Substrate filter constants per D2 Amendment 5 (the EXPANDED filter).
D2_EXPANDED_COMPOSITE_THRESHOLD = 0.5
D2_EXPANDED_RECENCY_MAX_CALENDAR_DAYS = 365


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _filter_d2_expanded(
    verdicts: list[PrimaryVerdict],
) -> list[PrimaryVerdict]:
    """Apply the D2 EXPANDED filter (composite>=0.5 + recency<=365d +
    5-BD adjacency merge) per D2 Amendment 5 source-of-truth."""
    filtered = [
        v for v in verdicts
        if v.composite_score >= D2_EXPANDED_COMPOSITE_THRESHOLD
    ]
    merged = merge_adjacent_troughs(filtered)
    actionable = filter_recent_patterns(
        merged, max_calendar_days=D2_EXPANDED_RECENCY_MAX_CALENDAR_DAYS
    )
    return actionable


def _substrate_window_days(verdicts: list[PrimaryVerdict]) -> int:
    """Days from earliest to latest effective_asof_date in the substrate."""
    if not verdicts:
        return 0
    asofs = [v.effective_asof_date for v in verdicts]
    return (max(asofs) - min(asofs)).days


def _new_ruleset_predicate_map() -> dict[str, Callable]:
    """G/H/I rulesets paired with their trigger predicates."""
    return {
        "G_bulkowski_double_bottom": (RulesetG(), bulkowski_trigger_predicate),
        "H_oneil_double_bottom_base": (RulesetH(), oneil_trigger_predicate),
        "I_edwards_magee_classical_double_bottom": (
            RulesetI(), edwards_magee_trigger_predicate,
        ),
    }


def run_backtest_for_substrate(
    verdicts: list[PrimaryVerdict],
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic | None = None,
) -> tuple[list[Trade], dict[str, int]]:
    """For each verdict in the substrate, read OHLCV ONCE per ticker then
    run ALL rulesets (A-F existing + G/H/I new).

    Returns (trades, skipped_counts). Skipped counts surface ohlcv_missing /
    ohlcv_empty for diagnostic-visibility (Codex R2 m#2 + R3 m#1 lessons
    from the existing harness, preserved here).
    """
    trades: list[Trade] = []
    skipped: dict[str, int] = {
        "ohlcv_missing": 0,
        "ohlcv_empty": 0,
        "skipped_tickers_ohlcv_missing": 0,
        "skipped_patterns_ohlcv_missing": 0,
    }
    existing_rulesets = all_rulesets()  # A-F
    new_ruleset_map = _new_ruleset_predicate_map()  # G/H/I + predicates

    by_ticker_bars: dict[str, pd.DataFrame | None] = {}
    for v in verdicts:
        if v.ticker not in by_ticker_bars:
            try:
                by_ticker_bars[v.ticker] = read_yfinance_shape_a(
                    v.ticker, cache_dir, diagnostic=diagnostic
                )
            except OhlcvCoverageError:
                by_ticker_bars[v.ticker] = None
                skipped["ohlcv_missing"] += 1
                skipped["skipped_tickers_ohlcv_missing"] += 1
        bars = by_ticker_bars[v.ticker]
        if bars is None:
            skipped["skipped_patterns_ohlcv_missing"] += 1
        # A-F: existing walk_forward (no volume gate)
        for rs in existing_rulesets:
            if bars is None:
                trades.append(_emit_missing_archive_trade(v, rs.name))
            else:
                trades.append(walk_forward(v, bars, rs))
        # G/H/I: walk_forward_with_trigger_predicate (volume gating)
        for rs_name, (rs, predicate) in new_ruleset_map.items():
            if bars is None:
                trades.append(_emit_missing_archive_trade(v, rs_name))
            else:
                trades.append(
                    walk_forward_with_trigger_predicate(
                        v, bars, rs, trigger_predicate=predicate
                    )
                )

    distinct_ohlcv_empty_patterns = {
        t.pattern_id for t in trades if t.exit_reason == "ohlcv_empty"
    }
    skipped["ohlcv_empty"] = len(distinct_ohlcv_empty_patterns)
    return trades, skipped


def _emit_missing_archive_trade(verdict: PrimaryVerdict, ruleset_name: str) -> Trade:
    days_t2_to_asof = (verdict.effective_asof_date - verdict.trough_2_date).days
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker,
        ruleset_name=ruleset_name,
        anchor_asof_date=verdict.anchor_asof_date,
        trough_1_date=verdict.trough_1_date,
        effective_asof_date=verdict.effective_asof_date,
        max_observed_asof_date=verdict.max_observed_asof_date,
        center_peak_price=verdict.center_peak_price,
        trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score,
        initial_stop=verdict.initial_stop,
        entry_date=None, entry_price=None,
        exit_date=None, exit_price=None,
        exit_reason="ohlcv_missing", r_multiple=None, days_held=None,
        status="untriggered",
        triggered=False,
        trade_pnl_dollars=None,
        peak_unrealized_R=None,
        drawdown_to_exit_R=None,
        forward_bars_available=0,
        max_forward_close=None, max_close_pct_of_peak=None,
        days_t2_to_asof=days_t2_to_asof,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "G2 W-bottom-derived ruleset backtest: 6 existing A-F + 3 new "
            "G/H/I rulesets against R2-A + D2 EXPANDED substrates with the "
            "9-metric scorecard."
        )
    )
    parser.add_argument(
        "--r2a-cohort-fixture", type=Path, required=True,
        help="R2-A cohort.json (N=65; consumed verbatim)",
    )
    parser.add_argument(
        "--d2-cohort-fixture", type=Path, required=True,
        help=(
            "D2 raw cohort.json (N=172; filtered to D2 EXPANDED via "
            "composite>=0.5 + recency<=365d + adjacency merge per D2 "
            "Amendment 5). Brief Sec 1.3 stated N=71 (stale snapshot); "
            "actual dispatch-baseline count is N=42 per Brief Amendment 1."
        ),
    )
    parser.add_argument(
        "--cache-dir", type=Path, required=True,
        help="OHLCV Shape A cache dir (~/swing-data/prices-cache)",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="Output directory; ISO subdir will be created",
    )
    parser.add_argument(
        "--include-d1-cohort", action="store_true",
        help=(
            "Optional: include D1 hand-curated +67 substrate (operator "
            "triage Sec 11 Q2; default OFF). NOT WIRED in V1; raises "
            "NotImplementedError if passed (silent no-op rejected per "
            "Codex R1 MINOR #2 closure)."
        ),
    )
    args = parser.parse_args(argv)

    if args.include_d1_cohort:
        raise NotImplementedError(
            "--include-d1-cohort is not wired in V1; the D1 hand-curated "
            "+67 substrate inclusion was operator triage Sec 11 Q2 "
            "DEFERRED. Re-dispatch with D1 substrate fixture path + "
            "harness wiring to enable. Banked as V2 candidate."
        )

    started_at = datetime.now(timezone.utc)

    # ---- Load R2-A verbatim ----
    r2a_verdicts = load_cohort_fixture(args.r2a_cohort_fixture)
    r2a_n_raw = len(r2a_verdicts)
    r2a_sha = _sha256_of_file(args.r2a_cohort_fixture)
    r2a_window_days = _substrate_window_days(r2a_verdicts)
    print(
        f"R2-A substrate: {r2a_n_raw} verdicts (verbatim); "
        f"window={r2a_window_days}d; SHA={r2a_sha[:12]}..."
    )

    # ---- Load D2 raw + apply EXPANDED filter ----
    d2_verdicts_raw = load_cohort_fixture(args.d2_cohort_fixture)
    d2_n_raw = len(d2_verdicts_raw)
    d2_verdicts = _filter_d2_expanded(d2_verdicts_raw)
    d2_n_filtered = len(d2_verdicts)
    d2_sha = _sha256_of_file(args.d2_cohort_fixture)
    d2_window_days = _substrate_window_days(d2_verdicts)
    print(
        f"D2 EXPANDED substrate: {d2_n_filtered} of {d2_n_raw} verdicts "
        f"(filter composite>={D2_EXPANDED_COMPOSITE_THRESHOLD} + "
        f"recency<={D2_EXPANDED_RECENCY_MAX_CALENDAR_DAYS}d + adjacency "
        f"merge); window={d2_window_days}d; SHA={d2_sha[:12]}..."
    )

    substrates: list[tuple[str, list[PrimaryVerdict], int, dict]] = [
        (
            "r2a_canonical_n65",
            r2a_verdicts,
            r2a_window_days,
            {
                "fixture_path": str(args.r2a_cohort_fixture),
                "cohort_sha256": r2a_sha,
                "n_raw": r2a_n_raw,
                "n_filtered": r2a_n_raw,  # consumed verbatim
                "filter_spec": "verbatim (R2-A pre-filtered)",
                "substrate_window_days": r2a_window_days,
            },
        ),
        (
            "d2_expanded",
            d2_verdicts,
            d2_window_days,
            {
                "fixture_path": str(args.d2_cohort_fixture),
                "cohort_sha256": d2_sha,
                "n_raw": d2_n_raw,
                "n_filtered": d2_n_filtered,
                "filter_spec": (
                    f"composite>={D2_EXPANDED_COMPOSITE_THRESHOLD} + "
                    f"recency<={D2_EXPANDED_RECENCY_MAX_CALENDAR_DAYS}d + "
                    f"5-BD adjacency merge (D2 Amendment 5); Brief "
                    f"Amendment 1: brief Sec 1.3 stated N=71 (stale "
                    f"snapshot); actual yields {d2_n_filtered}"
                ),
                "substrate_window_days": d2_window_days,
            },
        ),
    ]

    # ---- Run backtest per substrate ----
    diagnostic = BothExistDiagnostic()
    trades_by_substrate: dict[str, list[Trade]] = {}
    scorecard_rows: list[ScorecardRow] = []
    substrates_summary: dict[str, dict] = {}

    existing_ruleset_names = [rs.name for rs in all_rulesets()]
    new_ruleset_names = list(_new_ruleset_predicate_map().keys())
    all_ruleset_names = existing_ruleset_names + new_ruleset_names

    for sub_name, verdicts, window_days, meta in substrates:
        print(f"-- Backtesting substrate: {sub_name} (N={len(verdicts)}) --")
        trades, skipped = run_backtest_for_substrate(
            verdicts, args.cache_dir, diagnostic=diagnostic
        )
        trades_by_substrate[sub_name] = trades
        meta["skipped_counts"] = skipped
        meta["n_trades_emitted"] = len(trades)
        substrates_summary[sub_name] = meta
        n_patterns = len(verdicts)
        for rs_name in all_ruleset_names:
            row = build_scorecard_row(
                ruleset_name=rs_name,
                substrate_name=sub_name,
                trades=trades,
                n_patterns=n_patterns,
                substrate_window_days=window_days,
            )
            scorecard_rows.append(row)

    # ---- Emit artifacts ----
    iso_now = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / f"g2-w-bottom-ruleset-backtest-{iso_now}"
    out_dir.mkdir(parents=True, exist_ok=True)

    scorecard_csv = out_dir / "scorecard.csv"
    per_trade_csv = out_dir / "per_trade_detail.csv"
    summary_md = out_dir / "summary.md"
    narrative_md = out_dir / "narrative_synthesis.md"
    manifest_json = out_dir / "manifest.json"

    write_scorecard_csv(scorecard_rows, scorecard_csv)
    write_per_trade_detail_csv(trades_by_substrate, per_trade_csv)
    write_summary_markdown(
        summary_md,
        started_at_utc=started_at,
        scorecard_rows=scorecard_rows,
        substrates_summary=substrates_summary,
        cache_dir=str(args.cache_dir),
    )
    write_narrative_synthesis_markdown(
        narrative_md,
        scorecard_rows=scorecard_rows,
    )

    finished_at = datetime.now(timezone.utc)
    write_manifest(
        manifest_json,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        substrates_summary=substrates_summary,
        rulesets_total=len(all_ruleset_names),
        rulesets_existing_af=len(existing_ruleset_names),
        rulesets_new_ghi=len(new_ruleset_names),
        scorecard_row_count=len(scorecard_rows),
        per_trade_row_count=sum(len(t) for t in trades_by_substrate.values()),
        r_dollar_size_at_7500_floor=R_DOLLAR_SIZE_AT_7500_FLOOR,
        cache_dir=str(args.cache_dir),
    )
    print(f"wrote {scorecard_csv}")
    print(f"wrote {per_trade_csv}")
    print(f"wrote {summary_md}")
    print(f"wrote {narrative_md}")
    print(f"wrote {manifest_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
