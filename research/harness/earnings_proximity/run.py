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
import warnings
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
from swing.evaluation.rs import load_universe, universe_version_hash

_DEFAULT_CACHE_SUBPATH = Path("swing-data") / "research-cache"
_BENCHMARK_TICKER = "SPY"
# Trend-template SMA-200 requires 200 prior bars. Buffer for weekends/holidays
# brings worst-case calendar-days lookback to ~300.
_HISTORY_PRIOR_BARS = 220
# Simulator time cap — how many bars forward we need after the last signal day.
_FORWARD_BUFFER_BARS = 30
# Default RS universe path, relative to the repo root. The brief mandates the
# manifest's universe_version_hash reflect the repo's current RS universe CSV
# rather than whatever ad-hoc smoke-ticker subset --tickers happens to specify.
_DEFAULT_UNIVERSE_CSV = Path("reference") / "rs-universe.csv"


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
    parser.add_argument(
        "--universe-csv",
        default=None,
        help=(
            "Path to the RS universe CSV (default: reference/rs-universe.csv "
            "relative to the repo root). Determines the BatchContext universe "
            "and the manifest's universe_version_hash."
        ),
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


def _resolve_universe_csv(explicit: str | None, repo_root: Path) -> Path:
    if explicit:
        return Path(explicit)
    return repo_root / _DEFAULT_UNIVERSE_CSV


def _ticker_set_hash(tickers: tuple[str, ...]) -> str:
    """SHA-256 of the canonical sorted ticker list — fallback when no
    universe CSV is available (e.g., test scenarios)."""
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
    universe_csv: Path | None = None,
) -> list[MetricsRow]:
    """End-to-end: fetch, replay, variant-filter, simulate, aggregate, write.

    Exposed separately from the ``main`` CLI entry so tests can mock the
    ``fetchers`` module and drive the pipeline without real yfinance traffic.

    ``tickers`` is the smoke FILTER — the subset of the RS universe whose
    OHLCV is fetched and which is therefore eligible to emit signals. The
    BatchContext universe is the full RS universe loaded from
    ``universe_csv`` (default: ``reference/rs-universe.csv`` relative to the
    repo root); this keeps the manifest's universe_version_hash provenance
    accurate per the brief §2.3.
    """
    calendar = xcals.get_calendar("XNYS")
    repo_root = Path(__file__).resolve().parents[3]

    # --- Load RS universe (provenance-faithful BatchContext universe). ---
    universe_csv_path = (
        universe_csv if universe_csv is not None else repo_root / _DEFAULT_UNIVERSE_CSV
    )
    if not universe_csv_path.exists():
        # Strict — silent subset-fallback would reintroduce the original
        # adversarial-review issue (Round 1 #1) in a quieter form. Force
        # the operator to be explicit about the universe.
        raise FileNotFoundError(
            f"RS universe CSV not found: {universe_csv_path}. "
            f"Pass --universe-csv explicitly, or ensure the default "
            f"({_DEFAULT_UNIVERSE_CSV}) exists relative to the repo root."
        )
    universe = load_universe(universe_csv_path)
    universe_tickers_full = universe.tickers
    universe_version = universe.version
    universe_hash_value = universe_version_hash(universe_csv_path)

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
    smoke_tickers = sorted({t.upper() for t in tickers})

    # Validate smoke ticker subset is fully in the universe. Tickers outside
    # the universe are silently ignored downstream (replay iterates the
    # universe, not the smoke set), which would be a confusing UX bug.
    # Round 3 review minor: ALSO drop out-of-universe tickers from the fetch
    # list — they would burn yfinance quota for nothing.
    universe_set = set(universe_tickers_full)
    out_of_universe = sorted(t for t in smoke_tickers if t not in universe_set)
    in_universe_smoke = [t for t in smoke_tickers if t in universe_set]
    if out_of_universe:
        warnings.warn(
            f"Smoke ticker(s) not in RS universe: {out_of_universe}. "
            f"They will not be evaluated (replay iterates the universe). "
            f"Add them to the universe CSV or remove from --tickers.",
            stacklevel=2,
        )

    fetch_tickers = sorted({*in_universe_smoke, _BENCHMARK_TICKER})

    # --- Fetch OHLCV + earnings (cached). Real per-ticker hit/miss telemetry. ---
    ohlcv, ohlcv_stats = fetchers.load_ohlcv_with_stats(
        fetch_tickers, start=fetch_start, end=fetch_end, cache_dir=cache_dir
    )
    # Earnings are NOT fetched for the benchmark — it's a price-only series.
    earnings_tickers = [t for t in fetch_tickers if t != _BENCHMARK_TICKER]
    earnings, earnings_stats = fetchers.load_earnings_with_stats(
        earnings_tickers, cache_dir=cache_dir
    )
    cache_stats = CacheStats(
        ohlcv_hits=ohlcv_stats.hit_count,
        ohlcv_misses=ohlcv_stats.miss_count,
        earnings_hits=earnings_stats.hit_count,
        earnings_misses=earnings_stats.miss_count,
    )

    # --- Run replay over the full RS universe; only smoke tickers carry OHLCV. ---
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

    # --- Simulate each signal once; reuse outcomes across variants. ---
    outcomes_by_signal: dict[int, TradeOutcome] = {}
    for s in signals:
        t_ohlcv = ohlcv.get(s.ticker)
        if t_ohlcv is None or t_ohlcv.empty:
            continue
        outcomes_by_signal[id(s)] = simulate_trade(s, t_ohlcv)

    # Run-level counters (NOT multiplied across variants — each signal counted once).
    absent_total = sum(1 for s in signals if s.absent_earnings_data)
    dropped_total = sum(1 for o in outcomes_by_signal.values() if not o.triggered)

    # --- Apply each variant, aggregate per-variant metrics from cached outcomes. ---
    rows: list[MetricsRow] = []
    for x in variant_list:
        filtered = apply_variant(signals, x, calendar)
        variant_outcomes = [
            outcomes_by_signal[id(s)] for s in filtered if id(s) in outcomes_by_signal
        ]
        row = aggregate(
            outcomes=variant_outcomes,
            variant_name=_variant_name(x),
            blackout_trading_days=x,
            absent_data_count=sum(1 for s in filtered if s.absent_earnings_data),
        )
        rows.append(row)

    # --- Write outputs. ---
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_metrics_csv(rows, output_dir / "metrics.csv")

    # Disclose subset-driven RS for the smoke (faithful note for Session 2c).
    # When the smoke evaluates only a few tickers of the larger universe,
    # cross-sectional RS ranking inside compute_rs effectively collapses to
    # the fetched-OHLCV subset (it skips universe tickers without a return
    # in returns_12w_by_ticker). The manifest's universe_version_hash
    # reflects the FULL universe, so provenance is faithful, but readers
    # need to know the RS math is subset-driven on smoke runs.
    notes = [
        "Smoke run — shape check only; not the full study.",
        f"Signal total before variant filtering: {len(signals)}",
        (
            f"Requested smoke tickers: {','.join(smoke_tickers)}; "
            f"evaluated subset of universe: {','.join(in_universe_smoke)}."
        ),
    ]
    if len(smoke_tickers) < len(universe_tickers_full):
        notes.append(
            "RS ranking is subset-driven on smoke runs — only universe tickers "
            "with fetched OHLCV participate in the rank denominator. "
            "Session 2c's full study fetches OHLCV for the full universe."
        )
    if out_of_universe:
        notes.append(f"Excluded out-of-universe smoke tickers: {','.join(out_of_universe)}.")

    manifest = build_manifest(
        repo_root=repo_root,
        universe_version_hash=universe_hash_value,
        window_start=trading_days[0],
        window_end=trading_days[-1],
        trading_days=len(trading_days),
        tickers=len(universe_tickers_full),
        variants=tuple(variant_list),
        cache_stats=cache_stats,
        absent_data_count=absent_total,
        dropped_signal_count=dropped_total,
        notes=tuple(notes),
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
    universe_csv = (
        Path(args.universe_csv)
        if args.universe_csv
        else _resolve_universe_csv(None, Path(__file__).resolve().parents[3])
    )

    rows = run_replay(
        tickers=tickers,
        window_days=args.window_days,
        variant_list=variant_list,
        output_dir=output_dir,
        cache_dir=cache_dir,
        end_date=end_date,
        universe_csv=universe_csv,
    )
    print(f"Wrote {len(rows)} variant rows to {output_dir}/metrics.csv")
    print(f"Manifest: {output_dir}/run_manifest.json")
    return 0


if __name__ == "__main__":  # pragma: no cover — module-level CLI shim
    sys.exit(main())
