"""Orchestrator for the D1 double_bottom_w walk-forward backtest.

Loads cohort from results.csv (or fixture JSON), filters to actionable
RECENT W's, reads each ticker's full OHLCV archive via the V2 Shape A
reader, runs all 3 exit rulesets per pattern, emits CSV + summary +
manifest.

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO V1
persisted-state mutation. L2 LOCK preserved via
research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
)
from research.harness.double_bottom_w_backtest.cohort import (
    PrimaryVerdict,
    extract_primary_verdicts_from_csv,
    filter_recent_patterns,
    load_cohort_fixture,
    merge_adjacent_troughs,
)
from research.harness.double_bottom_w_backtest.io import (
    write_manifest,
    write_results_csv,
    write_summary_markdown,
)
from research.harness.double_bottom_w_backtest.rulesets import all_rulesets
from research.harness.double_bottom_w_backtest.walkforward import Trade, walk_forward


def _sha256_of_file(path: Path) -> str | None:
    """Streaming sha256 hash; None if file missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def run_backtest_for_verdicts(
    verdicts: list[PrimaryVerdict],
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic | None = None,
) -> tuple[list[Trade], dict[str, int]]:
    """For each verdict, read the ticker's full archive then run all 3 rulesets.

    Returns (trades, skipped_counts) where skipped_counts is a dict mapping
    skip-reason class to per-pattern occurrence counts.
    """
    trades: list[Trade] = []
    skipped: dict[str, int] = {"ohlcv_missing": 0, "ohlcv_empty": 0}
    rulesets = all_rulesets()
    # Per-ticker OHLCV cache: read each ticker once even when multiple verdicts
    # share the ticker. Avoids 3x reads (one per ruleset) or N-pattern reads
    # per ticker.
    by_ticker_bars: dict[str, object] = {}
    for v in verdicts:
        if v.ticker not in by_ticker_bars:
            try:
                by_ticker_bars[v.ticker] = read_yfinance_shape_a(
                    v.ticker, cache_dir, diagnostic=diagnostic
                )
            except OhlcvCoverageError:
                by_ticker_bars[v.ticker] = None
                skipped["ohlcv_missing"] += 1
        bars = by_ticker_bars[v.ticker]
        for rs in rulesets:
            if bars is None:
                # Emit untriggered placeholder for visibility per cumulative
                # gotcha #27 (silent-skip-without-audit). Each ruleset emits
                # a row so per-(pattern,ruleset) totals are consistent.
                trades.append(
                    _emit_missing_archive_trade(v, rs.name)
                )
            else:
                trades.append(walk_forward(v, bars, rs))
    return trades, skipped


def _emit_missing_archive_trade(verdict: PrimaryVerdict, ruleset_name: str) -> Trade:
    days_t2_to_asof = (verdict.anchor_asof_date - verdict.trough_2_date).days
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset_name,
        anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
        center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score, initial_stop=verdict.initial_stop,
        entry_date=None, entry_price=None, exit_date=None, exit_price=None,
        exit_reason="ohlcv_missing", r_multiple=None, days_held=None,
        status="untriggered",
        triggered=False, trade_pnl_dollars=None,
        peak_unrealized_R=None, drawdown_to_exit_R=None,
        forward_bars_available=0,
        max_forward_close=None, max_close_pct_of_peak=None,
        days_t2_to_asof=days_t2_to_asof,
    )


def _read_upstream_provenance(
    source_artifact_dir: Path | None,
) -> tuple[str | None, str | None, str | None]:
    """Read upstream pattern_cohort_evaluator manifest for provenance fields.

    Returns (manifest_path, manifest_sha256, cohort_input_sha256).
    Returns all-None when source_artifact_dir is None / manifest missing.
    """
    if source_artifact_dir is None:
        return None, None, None
    manifest_path = source_artifact_dir / "manifest.json"
    if not manifest_path.exists():
        return None, None, None
    manifest_sha = _sha256_of_file(manifest_path)
    try:
        import json

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        cohort_input_sha = data.get("cohort_input_sha256")
    except (OSError, ValueError):
        cohort_input_sha = None
    return str(manifest_path), manifest_sha, cohort_input_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="D1 double_bottom_w walk-forward backtest"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--results-csv", type=Path,
        help="Path to pattern_cohort_evaluator results.csv (will stream-parse + dedup)",
    )
    src.add_argument(
        "--cohort-fixture", type=Path,
        help="Path to pre-extracted cohort.json (skips results.csv parsing)",
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
        "--composite-threshold", type=float, default=0.7,
        help="Minimum composite_score to admit a verdict (default 0.7)",
    )
    parser.add_argument(
        "--recency-max-calendar-days", type=int, default=60,
        help="Restrict to W's with trough_2 within N calendar days of asof (default 60)",
    )
    parser.add_argument(
        "--no-recency-filter", action="store_true",
        help="Skip recency filter; backtest ALL unique W primary verdicts (typically ~172)",
    )
    parser.add_argument(
        "--source-artifact-dir", type=Path, default=None,
        help="Upstream pattern_cohort_evaluator run directory (for provenance "
             "manifest fields per Codex R1 M#5)",
    )
    args = parser.parse_args(argv)

    started_at = datetime.now(timezone.utc)

    # Load cohort
    if args.results_csv:
        verdicts = extract_primary_verdicts_from_csv(
            args.results_csv, composite_threshold=args.composite_threshold
        )
        cohort_source_path = str(args.results_csv)
        cohort_csv_sha = _sha256_of_file(args.results_csv)
    else:
        verdicts = load_cohort_fixture(args.cohort_fixture)
        # Re-apply composite filter (fixture may have been written at a
        # different threshold).
        verdicts = [v for v in verdicts if v.composite_score >= args.composite_threshold]
        cohort_source_path = str(args.cohort_fixture)
        cohort_csv_sha = _sha256_of_file(args.cohort_fixture)

    n_unique_pre = len(verdicts)
    print(f"Loaded {n_unique_pre} unique (ticker, trough_1) primary verdicts")

    merged = merge_adjacent_troughs(verdicts)
    n_after_merge = len(merged)
    print(f"After 5-BD adjacency merge: {n_after_merge}")

    if args.no_recency_filter:
        actionable = merged
    else:
        actionable = filter_recent_patterns(
            merged, max_calendar_days=args.recency_max_calendar_days
        )
    n_actionable = len(actionable)
    print(
        f"After recency filter ({args.recency_max_calendar_days} cal days): "
        f"{n_actionable} actionable patterns"
    )

    # Backtest
    diagnostic = BothExistDiagnostic()
    trades, skipped = run_backtest_for_verdicts(
        actionable, args.cache_dir, diagnostic=diagnostic
    )
    n_distinct_tickers = len({v.ticker for v in actionable})
    print(
        f"Emitted {len(trades)} trade rows ({n_actionable} patterns x 3 rulesets); "
        f"distinct tickers: {n_distinct_tickers}"
    )
    if skipped["ohlcv_missing"]:
        print(f"Skipped (ohlcv_missing): {skipped['ohlcv_missing']}")

    # Build output dir
    iso_now = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / f"double-bottom-w-backtest-{iso_now}"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_out = out_dir / "results.csv"
    summary_out = out_dir / "summary.md"
    manifest_out = out_dir / "manifest.json"

    write_results_csv(trades, csv_out)
    pop_notes = (
        f"**Cohort source:** {cohort_source_path}\n"
        f"**Recency filter:** trough_2 within {args.recency_max_calendar_days} calendar days of asof "
        f"({n_actionable} of {n_after_merge} verdicts passed).\n"
        f"**Both-exist diagnostic:** {diagnostic.count} ticker-reads hit Shape A + legacy (Shape A wins per OQ-18)."
    )
    if args.no_recency_filter:
        cohort_label = (
            f"composite>={args.composite_threshold} double_bottom_w; "
            f"NO RECENCY FILTER (all unique W primaries)"
        )
    else:
        cohort_label = (
            f"composite>={args.composite_threshold} double_bottom_w; "
            f"recency<={args.recency_max_calendar_days}d (max_observed_asof)"
        )
    write_summary_markdown(
        trades, summary_out,
        n_patterns=n_actionable,
        cohort_label=cohort_label,
        population_notes=pop_notes,
    )
    finished_at = datetime.now(timezone.utc)
    src_manifest_path, src_manifest_sha, src_cohort_input_sha = _read_upstream_provenance(
        args.source_artifact_dir
    )
    # When --results-csv is the input, that IS the source-of-truth results.csv;
    # surface its sha in source_results_csv_sha256 too for downstream tooling.
    source_results_csv_sha = (
        cohort_csv_sha if args.results_csv is not None else None
    )
    write_manifest(
        manifest_out,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        cohort_csv_path=cohort_source_path,
        cohort_csv_sha256=cohort_csv_sha,
        cache_dir=str(args.cache_dir),
        n_unique_verdicts_pre_filter=n_unique_pre,
        n_verdicts_after_adjacency_merge=n_after_merge,
        n_patterns_after_recency_filter=n_actionable,
        recency_max_calendar_days=args.recency_max_calendar_days,
        composite_threshold=args.composite_threshold,
        max_trigger_search_business_days=60,
        n_trades_emitted=len(trades),
        n_distinct_tickers=n_distinct_tickers,
        skipped_patterns=skipped,
        source_artifact_manifest_path=src_manifest_path,
        source_artifact_manifest_sha256=src_manifest_sha,
        source_results_csv_sha256=source_results_csv_sha,
        source_cohort_input_sha256=src_cohort_input_sha,
        recency_filter_active=(not args.no_recency_filter),
    )
    print(f"wrote {csv_out}")
    print(f"wrote {summary_out}")
    print(f"wrote {manifest_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
