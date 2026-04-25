"""Post-run analysis helper for the S&P 1500 universe expansion study (D4).

Reads a diagnostic run directory produced by :mod:`diagnostic_run`
against ``--universe sp_1500`` and computes the descriptive statistics
the D4 findings writeup requires beyond the generic diagnostic outputs:

- **Sector breakdown** of A+ signals (using the iShares-reported Sector
  column at fetch date; cached as a sidecar JSON via
  :func:`research.harness.earnings_proximity.universe_variants.load_sp_1500_sector_map`).
- **Liquidity distribution** of A+ signals (avg daily $ volume over the
  prior 20 sessions of each A+ date, computed from cached OHLCV).
- **Data-quality summary** (absent_earnings_data fraction; tickers in
  the universe with insufficient history or yfinance fetch failures).

Output: a JSON sidecar ``sp1500_findings.json`` in the run directory.
The D4 writeup quotes this file's contents directly.

Phase isolation
---------------
``swing/*`` is read-only (no production-code mutation). All artifacts
land under ``research/harness/earnings_proximity/diagnostic-out/``.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from research.harness.earnings_proximity.universe_variants import load_sp_1500_sector_map


_BENCHMARK_TICKER = "SPY"


def _load_aplus_signals(run_dir: Path) -> list[dict]:
    path = run_dir / "aplus_signals.csv"
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))


def _ohlcv_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / "ohlcv" / f"{ticker.upper()}.parquet"


def compute_sector_breakdown(
    aplus_rows: list[dict],
    sector_map: dict[str, str],
    *,
    universe_tickers: list[str] | None = None,
) -> dict:
    """Return sector counts + concentration + over/under-indexing over A+ signals.

    Tickers absent from the sector map are bucketed under "Unknown".

    When ``universe_tickers`` is provided, also computes the universe's
    sector composition (denominator) and per-sector index ratio (A+ %
    divided by universe %), so the reader can see whether A+ signals
    over- or under-index any sector vs the universe baseline. The
    universe-composition baseline is required by the dispatch brief
    (docs/sp1500-universe-study-brief.md §7).
    """
    counts: Counter[str] = Counter()
    for row in aplus_rows:
        sector = sector_map.get(row["ticker"].upper(), "Unknown") or "Unknown"
        counts[sector] += 1
    total = sum(counts.values())

    universe_counts: Counter[str] = Counter()
    if universe_tickers is not None:
        for t in universe_tickers:
            sec = sector_map.get(t.upper(), "Unknown") or "Unknown"
            universe_counts[sec] += 1
    universe_total = sum(universe_counts.values())

    sectors_seen = set(counts.keys()) | set(universe_counts.keys())
    breakdown = []
    for sector in sorted(
        sectors_seen,
        key=lambda s: (
            -counts.get(s, 0),
            -universe_counts.get(s, 0),
            s,
        ),
    ):
        a_count = counts.get(sector, 0)
        u_count = universe_counts.get(sector, 0)
        a_frac = (a_count / total) if total else 0.0
        u_frac = (u_count / universe_total) if universe_total else 0.0
        # Index ratio: 1.0 = A+ exactly tracks universe; >1 over-indexes; <1 under-indexes.
        index_ratio = (a_frac / u_frac) if u_frac else None
        breakdown.append(
            {
                "sector": sector,
                "count": a_count,
                "fraction": a_frac,
                "universe_count": u_count,
                "universe_fraction": u_frac,
                "index_ratio": index_ratio,
            }
        )
    largest = next(
        (b for b in breakdown if b["count"] > 0),
        None,
    )
    return {
        "total_aplus": total,
        "universe_total": universe_total,
        "by_sector": breakdown,
        "largest_sector": largest["sector"] if largest else None,
        "largest_sector_fraction": largest["fraction"] if largest else 0.0,
    }


def compute_liquidity_stats(
    aplus_rows: list[dict],
    cache_dir: Path,
    *,
    window_bars: int = 20,
) -> dict:
    """Compute avg daily $ volume distribution for A+ signals.

    For each (ticker, date) A+ row, look up the prior ``window_bars``
    sessions of cached OHLCV and compute mean(Close * Volume).
    Tickers without a usable cached frame are reported as ``unpriced``;
    the distribution is computed over the priced subset.
    """
    dollar_vols: list[float] = []
    unpriced: list[dict] = []

    for row in aplus_rows:
        ticker = row["ticker"].upper()
        d = date.fromisoformat(row["date"])
        path = _ohlcv_path(cache_dir, ticker)
        if not path.exists():
            unpriced.append({"ticker": ticker, "date": d.isoformat(), "reason": "no cache file"})
            continue
        df = pd.read_parquet(path)
        if df.empty or "Close" not in df.columns or "Volume" not in df.columns:
            unpriced.append({"ticker": ticker, "date": d.isoformat(), "reason": "empty frame"})
            continue
        idx_dates = pd.to_datetime(df.index).date
        # Use bars strictly prior to the A+ date (the date row itself is
        # the candidate's evaluation bar; the operator's liquidity check
        # would use trailing 20-day avg as of the prior session).
        mask = idx_dates < d
        prior = df[mask].tail(window_bars)
        if len(prior) < window_bars // 2:
            unpriced.append(
                {"ticker": ticker, "date": d.isoformat(), "reason": f"only {len(prior)} prior bars"}
            )
            continue
        close = prior["Close"]
        volume = prior["Volume"]
        if hasattr(close, "ndim") and close.ndim == 2:
            close = close.iloc[:, 0]
        if hasattr(volume, "ndim") and volume.ndim == 2:
            volume = volume.iloc[:, 0]
        dollar_vol = float((close * volume).mean())
        dollar_vols.append(dollar_vol)

    if not dollar_vols:
        return {
            "priced_count": 0,
            "unpriced_count": len(unpriced),
            "unpriced_examples": unpriced[:10],
            "median": None,
            "p25": None,
            "p75": None,
            "fraction_below_500k": None,
            "fraction_below_1m": None,
        }
    s = pd.Series(dollar_vols)
    return {
        "priced_count": len(dollar_vols),
        "unpriced_count": len(unpriced),
        "unpriced_examples": unpriced[:10],
        "median": float(s.median()),
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "min": float(s.min()),
        "max": float(s.max()),
        "fraction_below_500k": float((s < 500_000).mean()),
        "fraction_below_1m": float((s < 1_000_000).mean()),
    }


def compute_data_quality(aplus_rows: list[dict], manifest: dict) -> dict:
    """Compute data-quality stats from A+ rows + manifest."""
    total_aplus = len(aplus_rows)
    absent = sum(1 for r in aplus_rows if int(r.get("absent_earnings_data", "0") or "0") == 1)
    return {
        "aplus_total": total_aplus,
        "aplus_with_absent_earnings": absent,
        "aplus_absent_earnings_fraction": (absent / total_aplus) if total_aplus else 0.0,
        # Manifest-level data-quality observations
        "ohlcv_hits": manifest.get("ohlcv_hits"),
        "ohlcv_misses": manifest.get("ohlcv_misses"),
        "earnings_hits": manifest.get("earnings_hits"),
        "earnings_misses": manifest.get("earnings_misses"),
        "evaluations_total": manifest.get("evaluations_total"),
        "ticker_days_total": manifest.get("ticker_days_total"),
    }


def _load_universe_tickers_from_snapshot(snapshot_path: Path) -> list[str]:
    """Read the per-ticker snapshot CSV produced by load_universe_variant."""
    tickers: list[str] = []
    with snapshot_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith("ticker,"):
                continue
            ticker = stripped.split(",", 1)[0].strip().strip('"').upper()
            if ticker and ticker != "TICKER":
                tickers.append(ticker)
    return tickers


def _resolve_pinned_sector_map_path(cache_dir: Path, fetched_date: str) -> Path:
    """Pin the sector map to the run's universe_fetched_date.

    The aggregator must NOT silently use a more-recent sector map cached
    after the run; that would diverge sector labels from the universe
    composition the run actually evaluated against. Returns the exact
    expected path; absence is an error.
    """
    return cache_dir / "universe-snapshots" / f"sp_1500_{fetched_date}_sectors.json"


def aggregate_findings(
    run_dir: Path,
    *,
    cache_dir: Path,
    sector_map: dict[str, str] | None = None,
    universe_tickers: list[str] | None = None,
) -> dict:
    aplus_rows = _load_aplus_signals(run_dir)
    manifest = _load_manifest(run_dir)

    # Pin the sector map to the run's universe_fetched_date when not
    # supplied directly. This prevents a later D4 re-aggregation from
    # silently using a fresher iShares sector snapshot than the one
    # corresponding to run_manifest.json's universe_version.
    if sector_map is None:
        fetched_date = manifest.get("universe_fetched_date")
        if fetched_date is None:
            raise ValueError(
                "run_manifest.json missing universe_fetched_date; cannot pin sector map"
            )
        pinned_path = _resolve_pinned_sector_map_path(cache_dir, fetched_date)
        if not pinned_path.exists():
            raise FileNotFoundError(
                f"Pinned sector map not found at {pinned_path}. The aggregator "
                "refuses to fall back to a different snapshot — re-fetch with "
                "research.harness.earnings_proximity.universe_variants."
                "load_sp_1500_sector_map at the matching fetch date."
            )
        sector_map = json.loads(pinned_path.read_text(encoding="utf-8"))

    if universe_tickers is None:
        fetched_date = manifest.get("universe_fetched_date")
        snapshot_path = (
            cache_dir / "universe-snapshots" / f"sp_1500_{fetched_date}.csv"
        )
        if snapshot_path.exists():
            universe_tickers = _load_universe_tickers_from_snapshot(snapshot_path)

    sector = compute_sector_breakdown(
        aplus_rows, sector_map, universe_tickers=universe_tickers
    )
    liquidity = compute_liquidity_stats(aplus_rows, cache_dir)
    quality = compute_data_quality(aplus_rows, manifest)

    aplus_count = quality["aplus_total"]
    eval_count = manifest.get("evaluations_total", 0)
    universe_size = manifest.get("universe_size", 0)
    trading_days = manifest.get("trading_days", 0)
    ticker_days = universe_size * trading_days
    rate_per_ticker_day = (aplus_count / ticker_days) if ticker_days else 0.0

    # Wilson 95 % CI for a proportion (z=1.96).
    # https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval
    def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
        if n <= 0:
            return (0.0, 0.0)
        p = successes / n
        denom = 1 + z * z / n
        centre = p + z * z / (2 * n)
        adj = z * (((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5)
        return ((centre - adj) / denom, (centre + adj) / denom)

    lo, hi = _wilson(aplus_count, ticker_days)

    spx_baseline = 0.00193 / 100  # 0.00193 % per ticker-day from candidate-sparsity diagnostic Run A
    rate_uplift = (rate_per_ticker_day / spx_baseline) if spx_baseline else 0.0

    findings = {
        "run_dir": str(run_dir),
        "harness_git_sha": manifest.get("git_sha"),
        "universe_size_post_dedupe": universe_size,
        "trading_days": trading_days,
        "ticker_days_total": ticker_days,
        "evaluations_total": eval_count,
        "aplus_total": aplus_count,
        "rate_per_ticker_day": rate_per_ticker_day,
        "rate_per_ticker_day_pct": rate_per_ticker_day * 100.0,
        "wilson_95ci_low_pct": lo * 100.0,
        "wilson_95ci_high_pct": hi * 100.0,
        "spx_ndx_1x_baseline_pct": spx_baseline * 100.0,
        "rate_uplift_vs_spx_ndx_1x": rate_uplift,
        "sector_breakdown": sector,
        "liquidity": liquidity,
        "data_quality": quality,
    }
    return findings


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sp1500_findings_aggregate",
        description="Post-run analysis for the S&P 1500 universe expansion study (D4).",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Diagnostic run output directory (e.g. .../run_E_sp1500_1x/).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "swing-data" / "research-cache",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    findings = aggregate_findings(
        args.run_dir, cache_dir=args.cache_dir
    )
    out = args.run_dir / "sp1500_findings.json"
    out.write_text(json.dumps(findings, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {out}")
    print(
        f"  aplus={findings['aplus_total']} "
        f"rate_pct={findings['rate_per_ticker_day_pct']:.5f}% "
        f"uplift={findings['rate_uplift_vs_spx_ndx_1x']:.2f}x "
        f"absent_earnings_pct={findings['data_quality']['aplus_absent_earnings_fraction'] * 100:.1f}%"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
