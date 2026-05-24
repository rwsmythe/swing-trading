"""Orchestrator for V2 vcp.tightness_range_factor=1.005 walk-forward backtest.

Reads candidate population from the production DB + the smoke-artifact drill-down;
groups consecutive eval_runs into patterns; reads forward OHLCV bars from the V2
Shape A reader; runs the 3 exit rulesets; emits CSV + summary markdown.

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO V1 persisted-state
mutation. L2 LOCK preserved via research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
)
from research.harness.backtest_v2_tightness.io import (
    write_results_csv,
    write_summary_markdown,
)
from research.harness.backtest_v2_tightness.patterns import (
    CandidateRow,
    Pattern,
    group_consecutive_eval_runs,
)
from research.harness.backtest_v2_tightness.rulesets import all_rulesets
from research.harness.backtest_v2_tightness.walkforward import Trade, walk_forward


def load_flip_rows_from_csv(path: Path) -> list[CandidateRow]:
    """Load the orchestrator-extracted flip rows from CSV (joined with V1 pivot/stop)."""
    rows: list[CandidateRow] = []
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append(
                CandidateRow(
                    ticker=r["ticker"],
                    eval_run_id=int(r["eval_run_id"]),
                    data_asof_date=date.fromisoformat(r["data_asof_date"]),
                    v1_bucket=r["v1_bucket"],
                    pivot=float(r["pivot"]),
                    initial_stop=float(r["initial_stop"]),
                    close=float(r["close"]),
                )
            )
    return rows


def load_baseline_aplus_from_db(db_path: Path) -> list[CandidateRow]:
    """Load V1-production A+ candidates from the swing.db for the control cohort."""
    rows: list[CandidateRow] = []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.ticker, c.evaluation_run_id, er.data_asof_date, c.bucket,
                   c.pivot, c.initial_stop, c.close
            FROM candidates c
            JOIN evaluation_runs er ON er.id = c.evaluation_run_id
            WHERE c.bucket = 'aplus'
            ORDER BY er.id, c.ticker
            """
        )
        for ticker, eval_run_id, asof_str, bucket, pivot, stop, close in cur.fetchall():
            if pivot is None or stop is None:
                continue
            rows.append(
                CandidateRow(
                    ticker=ticker,
                    eval_run_id=eval_run_id,
                    data_asof_date=date.fromisoformat(asof_str),
                    v1_bucket=bucket,
                    pivot=float(pivot),
                    initial_stop=float(stop),
                    close=float(close) if close is not None else 0.0,
                )
            )
    finally:
        conn.close()
    return rows


def _forward_bars_after(
    ticker: str,
    cache_dir: Path,
    first_asof_date: date,
    diagnostic: BothExistDiagnostic | None = None,
):
    """Read the full archive then return bars STRICTLY AFTER first_asof_date."""
    df = read_yfinance_shape_a(ticker, cache_dir, diagnostic=diagnostic)
    return df.loc[df.index.date > first_asof_date]


def run_backtest_for_patterns(
    patterns: list[Pattern],
    cache_dir: Path,
    diagnostic: BothExistDiagnostic | None = None,
) -> tuple[list[Trade], dict[str, str]]:
    """Run walk-forward for every (pattern, ruleset). Returns (trades, errors)."""
    trades: list[Trade] = []
    errors: dict[str, str] = {}
    rulesets = all_rulesets()
    for p in patterns:
        try:
            fwd_bars = _forward_bars_after(p.ticker, cache_dir, p.first_data_asof_date, diagnostic)
        except OhlcvCoverageError as exc:
            errors[p.pattern_id] = f"OHLCV missing: {exc}"
            # Emit untriggered placeholder per ruleset so the CSV reports the gap.
            for rs in rulesets:
                trades.append(
                    Trade(
                        pattern_id=p.pattern_id,
                        ticker=p.ticker,
                        ruleset_name=rs.name,
                        pivot=p.pivot,
                        initial_stop=p.initial_stop,
                        entry_date=None,
                        entry_price=None,
                        exit_date=None,
                        exit_price=None,
                        exit_reason="ohlcv_missing",
                        r_multiple=None,
                        days_held=None,
                        status="untriggered",
                        n_eval_runs_in_pattern=p.n_runs,
                    )
                )
            continue
        if fwd_bars.empty:
            errors[p.pattern_id] = "no forward bars after asof"
            for rs in rulesets:
                trades.append(
                    Trade(
                        pattern_id=p.pattern_id,
                        ticker=p.ticker,
                        ruleset_name=rs.name,
                        pivot=p.pivot,
                        initial_stop=p.initial_stop,
                        entry_date=None,
                        entry_price=None,
                        exit_date=None,
                        exit_price=None,
                        exit_reason="no_forward_bars",
                        r_multiple=None,
                        days_held=None,
                        status="untriggered",
                        n_eval_runs_in_pattern=p.n_runs,
                    )
                )
            continue
        for rs in rulesets:
            trades.append(walk_forward(p, fwd_bars, rs))
    return trades, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V2 vcp.tightness_range_factor=1.005 walk-forward backtest"
    )
    parser.add_argument(
        "--flip-rows-csv",
        type=Path,
        required=True,
        help="CSV path with ticker,eval_run_id,data_asof_date,v1_bucket,pivot,initial_stop,close",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to swing.db for baseline A+ control cohort",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="OHLCV Shape A cache dir (~/swing-data/prices-cache)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory; ISO subdir will be created",
    )
    args = parser.parse_args(argv)

    iso_now = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / f"tightness-range-factor-backtest-{iso_now}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cohort: 67 flip candidates -> deduped patterns
    cohort_rows = load_flip_rows_from_csv(args.flip_rows_csv)
    cohort_patterns = group_consecutive_eval_runs(cohort_rows)
    print(
        f"cohort: {len(cohort_rows)} candidates -> {len(cohort_patterns)} unique patterns"
    )

    # Control: V1 baseline A+ candidates from DB
    control_rows = load_baseline_aplus_from_db(args.db_path)
    control_patterns = group_consecutive_eval_runs(control_rows)
    print(
        f"control: {len(control_rows)} candidates -> {len(control_patterns)} unique patterns"
    )

    diagnostic = BothExistDiagnostic()

    cohort_trades, cohort_errors = run_backtest_for_patterns(
        cohort_patterns, args.cache_dir, diagnostic=diagnostic
    )
    control_trades, control_errors = run_backtest_for_patterns(
        control_patterns, args.cache_dir, diagnostic=diagnostic
    )

    print(f"cohort: {len(cohort_trades)} trades emitted")
    print(f"control: {len(control_trades)} trades emitted")
    if cohort_errors:
        print(f"cohort errors: {cohort_errors}")
    if control_errors:
        print(f"control errors: {control_errors}")

    # Combine for CSV (one row per (pattern, ruleset)).
    all_trades = cohort_trades + control_trades
    # Tag cohort vs control via pattern_id naming. To distinguish we add a 'cohort' column;
    # write two CSV files instead to keep clarity.
    cohort_csv = out_dir / "results_cohort.csv"
    control_csv = out_dir / "results_control.csv"
    write_results_csv(cohort_trades, cohort_csv)
    write_results_csv(control_trades, control_csv)
    print(f"wrote {cohort_csv}")
    print(f"wrote {control_csv}")

    # Combined results.csv per dispatch brief §5 deliverable 1
    combined_csv = out_dir / "results.csv"
    write_results_csv(cohort_trades + control_trades, combined_csv)
    print(f"wrote {combined_csv}")

    pop_notes = (
        f"**Both-exist diagnostic:** {diagnostic.count} ticker-reads hit both Shape A "
        f"+ legacy parquet (Shape A wins per OQ-18; first 50 listed in V2 manifest)."
    )

    summary_md = out_dir / "summary.md"
    write_summary_markdown(
        cohort_trades=cohort_trades,
        cohort_label="vcp.tightness_range_factor=1.005 flips (67 watch->aplus)",
        control_trades=control_trades,
        control_label="V1 baseline aplus (sweep_point=0.67)",
        output_path=summary_md,
        n_patterns=len(cohort_patterns),
        n_control_patterns=len(control_patterns),
        population_notes=pop_notes,
    )
    print(f"wrote {summary_md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
