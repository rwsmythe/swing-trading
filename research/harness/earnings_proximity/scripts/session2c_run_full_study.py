"""Session 2c — full study run with per-ticker pre-IPO NaN dropna preprocess.

Historical reference script — see ``./README.md``. Not the canonical
interface for the harness; that is ``research.harness.earnings_proximity.run``.

Reproduces the Session 2c full-study run that produced the artifacts in
``research/harness/earnings_proximity/full-run-out/`` (commit ``e5510a8``).
The pipeline is the same as ``run.run_replay`` plus two session-level
additions Session 2c needed:

1. **Per-ticker pre-IPO NaN dropna preprocess.** ``yf.download(group_by='ticker')``
   on the SPX + NDX universe pads tickers that didn't exist at the window
   start with NaN rows back to the window start. Eight Session 2c tickers
   hit this (Q, SNDK, GEV, SOLV, VLTO, ARM, KVUE, FISV); those NaN rows
   crashed ``swing.evaluation.criteria.risk_feasibility`` with
   ``int(budget // NaN)``. The Session 2c workaround dropped any row where
   any of Open/High/Low/Close was NaN per ticker BEFORE the replay loop.
   The permanent harness fix landed in commit C3 of the post-Session-2c
   housekeeping bundle; on the post-fix harness this preprocess is a
   redundant no-op and can be left in for byte-identity.

2. **outcomes.csv and variant_membership.csv emission.** Session 2c's
   evidence summary needs per-trade R-multiples and per-variant filter
   membership; the canonical ``run_replay`` only writes ``metrics.csv``
   and ``run_manifest.json``. This script extends the output to include
   those CSVs (read by ``session2c_compute_cis.py``).

Window
------
Replay window: 2024-04-19 → 2026-04-23, 504 NYSE sessions. Variants:
{0, 3, 5, 7, 10}. Universe: full ``reference/rs-universe.csv``
(version 2026-04-24-1; SHA-256 in ``run_manifest.json``).
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from research.harness.earnings_proximity import fetchers
from research.harness.earnings_proximity.metrics import MetricsRow, aggregate
from research.harness.earnings_proximity.provenance import (
    CacheStats,
    build_manifest,
    write_manifest,
)
from research.harness.earnings_proximity.replay import (
    build_harness_config,
    replay,
)
from research.harness.earnings_proximity.simulator import TradeOutcome, simulate_trade
from research.harness.earnings_proximity.variants import apply_variant
from swing.evaluation.rs import load_universe, universe_version_hash

# Session 2c window (per analysis_summary.json + run_manifest.json).
WINDOW_START = date(2024, 4, 19)
WINDOW_END = date(2026, 4, 23)
WINDOW_DAYS = 504

# Variants pre-registered for Session 2c (per analysis_summary.json).
VARIANT_LIST = (0, 3, 5, 7, 10)

_BENCHMARK_TICKER = "SPY"
_HISTORY_PRIOR_BARS = 220
_FORWARD_BUFFER_BARS = 30
_DEFAULT_UNIVERSE_CSV = Path("reference") / "rs-universe.csv"
_DEFAULT_CACHE_SUBPATH = Path("swing-data") / "research-cache"
_DEFAULT_OUTPUT_DIR = Path("research") / "harness" / "earnings_proximity" / "full-run-out"

_OHLC_COLS = ("Open", "High", "Low", "Close")


def _fetch_window(
    window_start: date,
    window_end: date,
    calendar: xcals.ExchangeCalendar,
) -> tuple[date, date]:
    backward = calendar.sessions_in_range(
        pd.Timestamp(window_start) - pd.Timedelta(days=_HISTORY_PRIOR_BARS * 2 + 30),
        pd.Timestamp(window_start),
    )
    start = backward[0].date()

    forward = calendar.sessions_in_range(
        pd.Timestamp(window_end),
        pd.Timestamp(window_end) + pd.Timedelta(days=_FORWARD_BUFFER_BARS * 2 + 30),
    )
    if len(forward) > _FORWARD_BUFFER_BARS:
        end = forward[_FORWARD_BUFFER_BARS].date()
    else:
        end = forward[-1].date()
    end = end + timedelta(days=1)  # yf.download end-exclusive
    return start, end


def _trading_days(end_date: date, count: int, calendar) -> list[date]:
    end_ts = pd.Timestamp(end_date)
    sessions = calendar.sessions_in_range(
        end_ts - pd.Timedelta(days=count * 2 + 10), end_ts
    )
    return [s.date() for s in sessions[-count:]]


def _drop_pre_ipo_nans(
    ohlcv: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    """Apply per-ticker dropna(subset=OHLC) — Session 2c session-level workaround.

    Returns (cleaned_ohlcv, dropped_row_counts_by_ticker). The harness fix in
    C3 makes this redundant; kept here for byte-identity with Session 2c.
    """
    cleaned: dict[str, pd.DataFrame] = {}
    dropped: dict[str, int] = {}
    for t, df in ohlcv.items():
        if df is None or df.empty:
            cleaned[t] = df
            dropped[t] = 0
            continue
        before = len(df)
        cleaned_df = df.dropna(subset=list(_OHLC_COLS))
        cleaned[t] = cleaned_df
        dropped[t] = before - len(cleaned_df)
    return cleaned, dropped


def _write_outcomes_csv(
    rows: list[tuple[int, TradeOutcome, AplusSignalLike]],
    path: Path,
) -> None:
    """Emit outcomes.csv with the schema observed in commit e5510a8."""
    fieldnames = [
        "outcome_id",
        "ticker",
        "signal_date",
        "entry_target",
        "initial_stop",
        "next_earnings_date",
        "absent_earnings_data",
        "triggered",
        "trigger_date",
        "entry_price",
        "exit_date",
        "exit_price",
        "r_multiple",
        "gap_through",
        "gap_magnitude_r",
        "time_capped",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for outcome_id, outcome, signal in rows:
            writer.writerow(
                {
                    "outcome_id": outcome_id,
                    "ticker": outcome.ticker,
                    "signal_date": outcome.signal_date.isoformat(),
                    "entry_target": signal.entry_target,
                    "initial_stop": signal.initial_stop,
                    "next_earnings_date": (
                        signal.next_earnings_date.isoformat()
                        if signal.next_earnings_date is not None
                        else ""
                    ),
                    "absent_earnings_data": int(bool(signal.absent_earnings_data)),
                    "triggered": int(bool(outcome.triggered)),
                    "trigger_date": (
                        outcome.trigger_date.isoformat()
                        if outcome.trigger_date is not None
                        else ""
                    ),
                    "entry_price": (
                        outcome.entry_price if outcome.entry_price is not None else ""
                    ),
                    "exit_date": (
                        outcome.exit_date.isoformat()
                        if outcome.exit_date is not None
                        else ""
                    ),
                    "exit_price": (
                        outcome.exit_price if outcome.exit_price is not None else ""
                    ),
                    "r_multiple": (
                        outcome.r_multiple if outcome.r_multiple is not None else ""
                    ),
                    "gap_through": int(bool(outcome.gap_through)),
                    "gap_magnitude_r": (
                        outcome.gap_magnitude_r
                        if outcome.gap_magnitude_r is not None
                        else ""
                    ),
                    "time_capped": int(bool(outcome.time_capped)),
                }
            )


def _write_variant_membership_csv(
    membership: list[tuple[int, int]],
    path: Path,
) -> None:
    """Emit variant_membership.csv: (variant_x, outcome_id) pairs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["variant_x", "outcome_id"])
        for x, outcome_id in membership:
            writer.writerow([x, outcome_id])


def _write_metrics_csv(rows: list[MetricsRow], path: Path) -> None:
    fieldnames = [f.name for f in dataclasses.fields(MetricsRow)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


# ---- Type alias only — the AplusSignal is imported transitively. ----
class AplusSignalLike:  # pragma: no cover — duck-typing placeholder
    ticker: str
    date: date
    entry_target: float
    initial_stop: float
    next_earnings_date: date | None
    absent_earnings_data: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="session2c_run_full_study",
        description="Session 2c full study run (historical reference).",
    )
    repo_root = Path(__file__).resolve().parents[4]
    parser.add_argument(
        "--universe-csv",
        default=str(repo_root / _DEFAULT_UNIVERSE_CSV),
    )
    parser.add_argument(
        "--cache-dir",
        default=str(Path.home() / _DEFAULT_CACHE_SUBPATH),
    )
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / _DEFAULT_OUTPUT_DIR),
    )
    args = parser.parse_args(argv)

    universe_csv_path = Path(args.universe_csv)
    cache_dir = Path(args.cache_dir)
    output_dir = Path(args.output_dir)

    calendar = xcals.get_calendar("XNYS")
    universe = load_universe(universe_csv_path)
    universe_tickers_full = universe.tickers
    universe_version = universe.version
    universe_hash_value = universe_version_hash(universe_csv_path)

    trading_days = _trading_days(WINDOW_END, WINDOW_DAYS, calendar)
    if trading_days[0] != WINDOW_START:
        # Sanity check: 504 sessions back from 2026-04-23 must hit 2024-04-19.
        # Fail loud rather than silently drift.
        raise RuntimeError(
            f"Session 2c window-start mismatch: expected {WINDOW_START}, "
            f"derived {trading_days[0]}."
        )

    fetch_start, fetch_end = _fetch_window(WINDOW_START, WINDOW_END, calendar)
    fetch_tickers = sorted({*universe_tickers_full, _BENCHMARK_TICKER})

    # ---- Fetch (cached). ----
    ohlcv_raw, ohlcv_stats = fetchers.load_ohlcv_with_stats(
        fetch_tickers, start=fetch_start, end=fetch_end, cache_dir=cache_dir
    )
    earnings_tickers = [t for t in fetch_tickers if t != _BENCHMARK_TICKER]
    earnings, earnings_stats = fetchers.load_earnings_with_stats(
        earnings_tickers, cache_dir=cache_dir
    )

    # ---- Session-level workaround: per-ticker pre-IPO NaN dropna. ----
    # Redundant on a post-C3 harness; left in for byte-identity with Session 2c.
    ohlcv, dropped_counts = _drop_pre_ipo_nans(ohlcv_raw)
    nan_dropped_total = sum(dropped_counts.values())

    # ---- Replay → simulate. ----
    cfg = build_harness_config()
    signals = list(
        replay(
            universe_tickers=universe_tickers_full,
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings=earnings,
            cfg=cfg,
            universe_version=universe_version,
            universe_hash=universe_hash_value,
            benchmark_ticker=_BENCHMARK_TICKER,
        )
    )

    outcomes_by_signal: dict[int, TradeOutcome] = {}
    for s in signals:
        t_ohlcv = ohlcv.get(s.ticker)
        if t_ohlcv is None or t_ohlcv.empty:
            continue
        outcomes_by_signal[id(s)] = simulate_trade(s, t_ohlcv)

    # ---- Stable signal/outcome enumeration for outcomes.csv. ----
    # Ordering matches replay's emission order — the canonical run_replay
    # has the same property since dict insertion order is preserved.
    enumerated = list(enumerate(signals))
    outcome_rows: list[tuple[int, TradeOutcome, AplusSignalLike]] = []
    outcome_id_by_signal: dict[int, int] = {}
    for outcome_id, signal in enumerated:
        outcome = outcomes_by_signal.get(id(signal))
        if outcome is None:
            # Signal had no OHLCV (defensive — replay/simulator guard against this).
            continue
        outcome_rows.append((outcome_id, outcome, signal))
        outcome_id_by_signal[id(signal)] = outcome_id

    # ---- Apply each variant; record per-variant filter membership. ----
    rows: list[MetricsRow] = []
    membership: list[tuple[int, int]] = []
    absent_total = sum(1 for s in signals if s.absent_earnings_data)
    dropped_total = sum(1 for o in outcomes_by_signal.values() if not o.triggered)

    for x in VARIANT_LIST:
        filtered = apply_variant(signals, x, calendar)
        variant_outcomes: list[TradeOutcome] = []
        for s in filtered:
            outcome_id = outcome_id_by_signal.get(id(s))
            if outcome_id is None:
                continue
            membership.append((x, outcome_id))
            variant_outcomes.append(outcomes_by_signal[id(s)])

        row = aggregate(
            outcomes=variant_outcomes,
            variant_name=f"X={x}",
            blackout_trading_days=x,
            absent_data_count=sum(1 for s in filtered if s.absent_earnings_data),
        )
        rows.append(row)

    # ---- Write outputs. ----
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_outcomes_csv(outcome_rows, output_dir / "outcomes.csv")
    _write_variant_membership_csv(membership, output_dir / "variant_membership.csv")
    _write_metrics_csv(rows, output_dir / "metrics.csv")

    cache_stats = CacheStats(
        ohlcv_hits=ohlcv_stats.hit_count,
        ohlcv_misses=ohlcv_stats.miss_count,
        earnings_hits=earnings_stats.hit_count,
        earnings_misses=earnings_stats.miss_count,
    )
    notes: list[str] = [
        f"Full-study run: {len(universe_tickers_full)} tickers x "
        f"{len(trading_days)} trading days x {len(VARIANT_LIST)} variants.",
        f"Signal total before variant filtering: {len(signals)}",
        f"Absent-earnings-data signals: {absent_total}",
        f"Outcomes simulated (of signals with OHLCV): {len(outcome_rows)}",
        f"Dropped (never triggered) signals: {dropped_total}",
        f"Pre-IPO NaN rows dropped (session-level workaround): {nan_dropped_total}.",
        "Universe drawn from reference/rs-universe.csv "
        f"v{universe_version} (SPX + NDX; no Finviz pre-filter).",
        "Absent-data rule: signals with no earnings history are KEPT by all "
        "variant filters (method-record mandate).",
    ]
    manifest = build_manifest(
        repo_root=repo_root,
        universe_version_hash=universe_hash_value,
        window_start=trading_days[0],
        window_end=trading_days[-1],
        trading_days=len(trading_days),
        tickers=len(universe_tickers_full),
        variants=tuple(VARIANT_LIST),
        cache_stats=cache_stats,
        absent_data_count=absent_total,
        dropped_signal_count=dropped_total,
        notes=tuple(notes),
    )
    write_manifest(manifest, output_dir / "run_manifest.json")

    print(f"Wrote {len(rows)} variant rows + outcomes/membership to {output_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover — module-level CLI shim
    raise SystemExit(main())
