"""Session 2c — bulk OHLCV + earnings cache warm-up.

Historical reference script — see ``./README.md``. Not the canonical
interface for the harness; that is ``research.harness.earnings_proximity.run``.

This script primes ``~/swing-data/research-cache/`` for Session 2c's full
study by issuing one ``load_ohlcv_with_stats`` call (batched yfinance
download) over the full SPX + NDX RS universe + the SPY benchmark across
the Session 2c replay window. It does not perform any analysis; the
follow-on script ``session2c_run_full_study.py`` runs the replay against
the warmed cache.

Window
------
Session 2c's replay window: 2024-04-19 → 2026-04-23 (504 NYSE sessions).
The fetch window extends 220 trading-day-equivalents BEFORE the window
start (for SMA-200 history) and ~30 trading-day-equivalents AFTER the
window end (for the simulator's forward time-cap buffer). The
``run_replay`` orchestration in ``run.py`` derives the same bounds from
its own constants; this script reproduces that arithmetic to make the
warm-up step a self-contained operation.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from research.harness.earnings_proximity import fetchers
from swing.evaluation.rs import load_universe

# Session 2c window (per analysis_summary.json + run_manifest.json).
WINDOW_START = date(2024, 4, 19)
WINDOW_END = date(2026, 4, 23)

# Match run.py's _HISTORY_PRIOR_BARS / _FORWARD_BUFFER_BARS.
_HISTORY_PRIOR_BARS = 220
_FORWARD_BUFFER_BARS = 30

_BENCHMARK_TICKER = "SPY"
_DEFAULT_UNIVERSE_CSV = Path("reference") / "rs-universe.csv"
_DEFAULT_CACHE_SUBPATH = Path("swing-data") / "research-cache"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="session2c_warm_cache",
        description="Session 2c cache warm-up (historical reference).",
    )
    repo_root = Path(__file__).resolve().parents[4]
    parser.add_argument(
        "--universe-csv",
        default=str(repo_root / _DEFAULT_UNIVERSE_CSV),
        help="Path to RS universe CSV (default: reference/rs-universe.csv).",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(Path.home() / _DEFAULT_CACHE_SUBPATH),
        help="Cache directory (default: $USERPROFILE/swing-data/research-cache/).",
    )
    args = parser.parse_args(argv)

    universe = load_universe(Path(args.universe_csv))
    cache_dir = Path(args.cache_dir)
    calendar = xcals.get_calendar("XNYS")
    fetch_start, fetch_end = _fetch_window(WINDOW_START, WINDOW_END, calendar)

    fetch_tickers = sorted({*universe.tickers, _BENCHMARK_TICKER})
    print(
        f"Warming OHLCV cache for {len(fetch_tickers)} tickers, "
        f"window {fetch_start} → {fetch_end}…"
    )
    _, ohlcv_stats = fetchers.load_ohlcv_with_stats(
        fetch_tickers, start=fetch_start, end=fetch_end, cache_dir=cache_dir
    )
    print(
        f"OHLCV: hits={ohlcv_stats.hit_count} misses={ohlcv_stats.miss_count}"
    )

    # Earnings cache is per-ticker yfinance.Ticker.get_earnings_dates;
    # benchmark SPY is a price-only series and is excluded.
    earnings_tickers = [t for t in fetch_tickers if t != _BENCHMARK_TICKER]
    print(f"Warming earnings cache for {len(earnings_tickers)} tickers…")
    _, earnings_stats = fetchers.load_earnings_with_stats(
        earnings_tickers, cache_dir=cache_dir
    )
    print(
        f"Earnings: hits={earnings_stats.hit_count} misses={earnings_stats.miss_count}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — module-level CLI shim
    raise SystemExit(main())
