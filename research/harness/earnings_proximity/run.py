"""CLI entrypoint + orchestration for the earnings-proximity replay harness.

Smoke invocation::

    python -m research.harness.earnings_proximity.run \
        --tickers AAPL,SOFI \
        --window-days 10 \
        --variants 0,3,5,7,10 \
        --output-dir research/harness/earnings_proximity/smoke-out/

Full-study invocation (Session 2c's job, not Session 2b's) would drop
``--window-days`` in favor of an explicit ``--window-years`` and use the
full RS universe CSV.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta
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

_DEFAULT_CACHE_SUBPATH = Path("swing-data") / "research-cache"
_BENCHMARK_TICKER = "SPY"
# Trend-template SMA-200 requires 200 prior bars. Buffer for weekends/holidays
# brings worst-case calendar-days lookback to ~300.
_HISTORY_PRIOR_BARS = 220
# Simulator time cap — how many bars forward we need after the last signal day.
_FORWARD_BUFFER_BARS = 30


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="research.harness.earnings_proximity.run",
        description="Earnings-proximity replay harness (smoke or full study).",
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated ticker list (e.g., AAPL,SOFI).",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=10,
        help="Number of NYSE trading days to replay (default: 10).",
    )
    parser.add_argument(
        "--variants",
        default="0,3,5,7,10",
        help="Comma-separated blackout_trading_days values.",
    )
    parser.add_argument("--output-dir", required=True, help="Where to write metrics + manifest.")
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Override cache dir. Default: $USERPROFILE/swing-data/research-cache/.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="ISO date of the last trading day in the replay window. Default: yesterday-ish.",
    )
    return parser.parse_args(argv)


def _resolve_cache_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # Anchored under %USERPROFILE% per CLAUDE.md Drive-sync invariant.
    return Path.home() / _DEFAULT_CACHE_SUBPATH


def _session_days_through(
    end_date: date,
    count: int,
    calendar: xcals.ExchangeCalendar,
) -> list[date]:
    """Last ``count`` NYSE sessions up to and including ``end_date``."""
    # Walk backward from end_date, picking sessions.
    end_ts = pd.Timestamp(end_date)
    sessions = calendar.sessions_in_range(
        end_ts - pd.Timedelta(days=count * 2 + 10), end_ts
    )
    return [s.date() for s in sessions[-count:]]


def _fetch_window(
    trading_days: list[date],
    calendar: xcals.ExchangeCalendar,
) -> tuple[date, date]:
    """Bounds for yfinance fetch: 220 sessions prior, 30 sessions forward.

    ``yf.download`` uses end-exclusive semantics, so the returned ``end`` is
    the first session strictly AFTER the forward buffer.
    """
    first_day = trading_days[0]
    last_day = trading_days[-1]

    # Walk back 220 sessions.
    backward = calendar.sessions_in_range(
        pd.Timestamp(first_day) - pd.Timedelta(days=_HISTORY_PRIOR_BARS * 2 + 30),
        pd.Timestamp(first_day),
    )
    start = backward[0].date() if len(backward) > _HISTORY_PRIOR_BARS else backward[0].date()

    # Walk forward 30 sessions + a couple of days for exclusivity.
    forward = calendar.sessions_in_range(
        pd.Timestamp(last_day),
        pd.Timestamp(last_day) + pd.Timedelta(days=_FORWARD_BUFFER_BARS * 2 + 30),
    )
    if len(forward) > _FORWARD_BUFFER_BARS:
        end = forward[_FORWARD_BUFFER_BARS].date()
    else:
        end = forward[-1].date()
    end = end + timedelta(days=1)  # yf.download end is exclusive
    return start, end


def _universe_hash(tickers: tuple[str, ...]) -> str:
    """SHA-256 of a canonical "ticker\\n" rendering — stable for the same set."""
    canonical = "\n".join(sorted(tickers)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _variant_name(x: int) -> str:
    return f"X={x}"


def _write_metrics_csv(rows: list[MetricsRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f.name for f in dataclasses.fields(MetricsRow)]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def run_replay(
    *,
    tickers: list[str],
    window_days: int,
    variant_list: list[int],
    output_dir: Path,
    cache_dir: Path,
    end_date: date | None = None,
) -> list[MetricsRow]:
    """End-to-end: fetch, replay, variant-filter, simulate, aggregate, write.

    Exposed separately from the ``main`` CLI entry so tests can mock the
    ``fetchers`` module and drive the pipeline without real yfinance traffic.
    """
    calendar = xcals.get_calendar("XNYS")
    if end_date is None:
        today = datetime.now().date()
        # Last completed NYSE session on or before today - 1 (conservative).
        sessions = calendar.sessions_in_range(
            pd.Timestamp(today) - pd.Timedelta(days=15),
            pd.Timestamp(today) - pd.Timedelta(days=1),
        )
        end_date = sessions[-1].date()

    trading_days = _session_days_through(end_date, window_days, calendar)
    if not trading_days:
        raise RuntimeError(f"No NYSE trading days found ending {end_date}")

    fetch_start, fetch_end = _fetch_window(trading_days, calendar)
    ticker_set = sorted(set(tickers + [_BENCHMARK_TICKER]))

    # --- Fetch OHLCV + earnings (cached). ---
    cache_stats = CacheStats(
        ohlcv_hits=sum((cache_dir / "ohlcv" / f"{t}.parquet").exists() for t in ticker_set),
        earnings_hits=sum((cache_dir / "earnings" / f"{t}.json").exists() for t in ticker_set),
    )
    ohlcv = fetchers.load_ohlcv(ticker_set, start=fetch_start, end=fetch_end, cache_dir=cache_dir)
    earnings = fetchers.load_earnings(
        [t for t in ticker_set if t != _BENCHMARK_TICKER],
        cache_dir=cache_dir,
    )
    # Recompute after the fetch to capture final state.
    ohlcv_existing = sum((cache_dir / "ohlcv" / f"{t}.parquet").exists() for t in ticker_set)
    earnings_existing = sum(
        (cache_dir / "earnings" / f"{t}.json").exists()
        for t in ticker_set
        if t != _BENCHMARK_TICKER
    )
    cache_stats = CacheStats(
        ohlcv_hits=cache_stats.ohlcv_hits,
        ohlcv_misses=max(0, ohlcv_existing - cache_stats.ohlcv_hits),
        earnings_hits=cache_stats.earnings_hits,
        earnings_misses=max(0, earnings_existing - cache_stats.earnings_hits),
    )

    # --- Run replay (one iteration over all trading days). ---
    cfg = build_harness_config()
    universe_tickers = tuple(tickers)
    signals = list(
        replay(
            universe_tickers=universe_tickers,
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings=earnings,
            cfg=cfg,
            universe_version="harness-smoke",
            universe_hash=_universe_hash(universe_tickers),
            benchmark_ticker=_BENCHMARK_TICKER,
        )
    )

    # --- Apply each variant, simulate, aggregate. ---
    rows: list[MetricsRow] = []
    absent_total = sum(1 for s in signals if s.absent_earnings_data)
    dropped_total = 0

    for x in variant_list:
        filtered = apply_variant(signals, x, calendar)
        outcomes: list[TradeOutcome] = []
        for s in filtered:
            t_ohlcv = ohlcv.get(s.ticker)
            if t_ohlcv is None or t_ohlcv.empty:
                continue
            outcome = simulate_trade(s, t_ohlcv)
            outcomes.append(outcome)
            if not outcome.triggered:
                dropped_total += 1
        row = aggregate(
            outcomes=outcomes,
            variant_name=_variant_name(x),
            blackout_trading_days=x,
            absent_data_count=sum(1 for s in filtered if s.absent_earnings_data),
        )
        rows.append(row)

    # --- Write outputs. ---
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_metrics_csv(rows, output_dir / "metrics.csv")

    manifest = build_manifest(
        repo_root=Path(__file__).resolve().parents[3],
        universe_version_hash=_universe_hash(universe_tickers),
        window_start=trading_days[0],
        window_end=trading_days[-1],
        trading_days=len(trading_days),
        tickers=len(universe_tickers),
        variants=tuple(variant_list),
        cache_stats=cache_stats,
        absent_data_count=absent_total,
        dropped_signal_count=dropped_total,
        notes=(
            "Smoke run — shape check only; not the full study.",
            f"Signal total before variant filtering: {len(signals)}",
        ),
    )
    write_manifest(manifest, output_dir / "run_manifest.json")

    return rows


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    variant_list = [int(x.strip()) for x in args.variants.split(",") if x.strip()]
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    cache_dir = _resolve_cache_dir(args.cache_dir)
    output_dir = Path(args.output_dir)

    rows = run_replay(
        tickers=tickers,
        window_days=args.window_days,
        variant_list=variant_list,
        output_dir=output_dir,
        cache_dir=cache_dir,
        end_date=end_date,
    )
    print(f"Wrote {len(rows)} variant rows to {output_dir}/metrics.csv")
    print(f"Manifest: {output_dir}/run_manifest.json")
    return 0


if __name__ == "__main__":  # pragma: no cover — module-level CLI shim
    sys.exit(main())
