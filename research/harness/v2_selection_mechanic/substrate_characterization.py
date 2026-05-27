"""Per-ticker regime metric computation for V2-selection-mechanic investigation.

Computes the 4 per-ticker substrate characterization metrics per
V2-selection-mechanic dispatch brief Sec 1.5:

  - 90-day price return    : pct change between asof - 90 BD and asof close
  - ATR%                   : mean trailing-20-BD ATR / close at asof_date
  - 52w high proximity (%) : (52w_high - close) / 52w_high * 100
  - Sector                 : best-effort from finviz CSV; UNKNOWN if absent

OHLCV reads use `read_legacy_archive` -- pd.read_parquet directly on the
legacy `.parquet` path. Per orchestrator greenlight 2026-05-26 PM:
sidesteps `swing.data.ohlcv_archive.read_or_fetch_archive` V2 reader
Shape A + fetch-on-miss logic; raises `FileNotFoundError` on cache miss
(gotcha #28 OHLCV cache discipline + dispatch brief Sec 6(d) "CLEAR
ERROR + halt rather than fetch").

Per-cohort aggregate metrics (median / IQR / sector mix / unique counts)
are computed by `compute_cohort_characterization` consuming a sequence
of (ticker, asof_date) pairs.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO yfinance imports;
ZERO production swing/ writes. Reads only local legacy parquet OHLCV
archives + (optionally) finviz CSV for sector resolution.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


# Default OHLCV archive cache directory (per D2 baseline manifest +
# CLAUDE.md gotcha #28 V1 operational discipline). Operator can override
# via cache_dir parameter on all public functions.
DEFAULT_CACHE_DIR = Path.home() / "swing-data" / "prices-cache"

# Sentinel for unresolvable sector.
UNKNOWN_SECTOR = "UNKNOWN"


class CacheMissError(FileNotFoundError):
    """Raised when a required legacy OHLCV archive is missing.

    Distinct from FileNotFoundError to enable structural defense per gotcha
    #28 + dispatch brief Sec 6(d): the investigation must NOT silently
    fall through to yfinance fetch when an archive is missing. Operator
    pre-flight refresh is the canonical recovery path.
    """


class AsofDateMissingError(ValueError):
    """Raised when the requested asof_date is NOT present in the OHLCV
    archive's DatetimeIndex.

    Codex R3 MAJOR #3 fix 2026-05-26 PM: prior implementation
    silently substituted the latest prior bar via `_slice_at_or_before`,
    making weekend/holiday/missing-bar asof_dates indistinguishable from
    valid trading-session asof_dates. The V2 cohort CSV asof_dates come
    from V1 eval_run_id snapshots (valid trading sessions); any
    asof_date NOT in the archive index indicates a data-integrity gap
    worth surfacing per gotcha #28 + brief Sec 6(d) "CLEAR ERROR not
    silent fallback" discipline.
    """


@dataclass(frozen=True)
class PerTickerMetrics:
    """Computed regime metrics at a (ticker, asof_date) snapshot."""

    ticker: str
    asof_date: date
    return_90d_pct: float | None
    atr_pct_20d: float | None
    high_52w_proximity_pct: float | None
    sector: str


@dataclass(frozen=True)
class CohortAggregateMetrics:
    """Per-cohort aggregate of per-ticker metrics."""

    cohort_label: str
    unique_ticker_count: int
    unique_ticker_asof_count: int
    return_90d_pct_median: float | None
    return_90d_pct_iqr: float | None
    atr_pct_20d_median: float | None
    atr_pct_20d_iqr: float | None
    high_52w_proximity_pct_median: float | None
    high_52w_proximity_pct_iqr: float | None
    sector_counts: dict[str, int]


# -----------------------------------------------------------------------
# Legacy parquet reader (gotcha #28 + brief Sec 6(d) compliance)
# -----------------------------------------------------------------------


def read_legacy_archive(ticker: str, cache_dir: Path | None = None) -> pd.DataFrame:
    """Read legacy parquet OHLCV archive for `ticker`.

    Raises `CacheMissError` (FileNotFoundError subclass) if the archive
    is missing. Sidesteps the V2 reader's Shape A logic + fetch-on-miss
    path per dispatch brief Sec 6(d).

    Returns a DataFrame indexed by DatetimeIndex named 'Date' with
    columns [Open, High, Low, Close, Volume]. Handles yfinance
    `group_by='column'` MultiIndex defensively.
    """
    cache = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    path = cache / f"{ticker.upper()}.parquet"
    if not path.exists():
        raise CacheMissError(
            f"OHLCV archive missing for {ticker}: {path}. Operator "
            f"pre-flight refresh required (gotcha #28 family + dispatch "
            f"brief Sec 6(d): CLEAR ERROR not yfinance fetch)."
        )
    df = pd.read_parquet(path)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


# -----------------------------------------------------------------------
# Per-ticker metric primitives
# -----------------------------------------------------------------------


def _slice_at_or_before(df: pd.DataFrame, asof: date) -> pd.DataFrame:
    """Slice df to rows with index date <= asof. Returns empty DF on miss."""
    if df.empty:
        return df
    idx_dates = df.index.date if hasattr(df.index, "date") else df.index
    mask = idx_dates <= asof
    return df.loc[mask]


def _require_asof_in_index(df: pd.DataFrame, asof: date, ticker: str) -> None:
    """Codex R3 MAJOR #3 strict-asof guard.

    Raises AsofDateMissingError if asof_date is NOT present in the
    DatetimeIndex. The V2 cohort CSV asof_dates are V1 eval_run snapshots
    (always valid trading sessions); any miss indicates a data-integrity
    gap (archive truncation, weekend/holiday cohort artifact emission
    error, etc.) worth halting per brief Sec 6(d).
    """
    if df.empty:
        raise AsofDateMissingError(
            f"OHLCV archive for {ticker} is empty; cannot resolve asof={asof}"
        )
    idx_dates = df.index.date if hasattr(df.index, "date") else df.index
    if asof not in set(idx_dates):
        raise AsofDateMissingError(
            f"asof_date {asof} not present in OHLCV archive for {ticker}; "
            f"archive ranges from {min(idx_dates)} to {max(idx_dates)}. "
            f"Investigation contract requires asof to be a valid trading "
            f"session present in the archive."
        )


def compute_90d_return_pct(df: pd.DataFrame, asof: date) -> float | None:
    """Pct change between close at (asof - 90 business days) and close at asof.

    Returns None if asof is not in index or insufficient prior history
    (fewer than 90 BD before asof).
    """
    sliced = _slice_at_or_before(df, asof)
    if len(sliced) < 91:  # need asof close + 90 prior business days
        return None
    asof_close = float(sliced["Close"].iloc[-1])
    # 90 business days back -> index position -91 (counting from end)
    prior_close = float(sliced["Close"].iloc[-91])
    if prior_close == 0:
        return None
    return (asof_close - prior_close) / prior_close * 100.0


def compute_atr_pct_20d(df: pd.DataFrame, asof: date) -> float | None:
    """Mean ATR over trailing 20 BD divided by close at asof, expressed as pct.

    ATR (per bar) = max(High - Low, |High - PrevClose|, |Low - PrevClose|).
    The trailing 20 BD window ends AT asof_date inclusive.
    Returns None if fewer than 21 bars available.
    """
    sliced = _slice_at_or_before(df, asof)
    if len(sliced) < 21:  # need 20 ATR-bars + 1 for the prev-close anchor
        return None
    window = sliced.tail(21)
    highs = window["High"].to_numpy()
    lows = window["Low"].to_numpy()
    closes = window["Close"].to_numpy()
    prev_closes = closes[:-1]
    h = highs[1:]
    l = lows[1:]
    range_hl = h - l
    range_hpc = abs(h - prev_closes)
    range_lpc = abs(l - prev_closes)
    tr = [max(a, b, c) for a, b, c in zip(range_hl, range_hpc, range_lpc)]
    atr = sum(tr) / len(tr)
    asof_close = float(closes[-1])
    if asof_close == 0:
        return None
    return float(atr) / asof_close * 100.0


def compute_52w_high_proximity_pct(df: pd.DataFrame, asof: date) -> float | None:
    """`(52w_high - asof_close) / 52w_high * 100`.

    52w_high is the max High over the trailing 252 business days ending
    AT asof inclusive. Returns None on insufficient data: requires at
    least 252 bars at or before asof (Codex R1 MAJOR #1 fix 2026-05-26 PM
    -- prior implementation returned a "trailing-window-max" derived
    value on partial archives, conflating short histories with true
    52-week lookbacks).
    """
    sliced = _slice_at_or_before(df, asof)
    if len(sliced) < 252:
        return None
    window = sliced.tail(252)
    high_52w = float(window["High"].max())
    asof_close = float(sliced["Close"].iloc[-1])
    if high_52w == 0:
        return None
    return (high_52w - asof_close) / high_52w * 100.0


# -----------------------------------------------------------------------
# Sector resolution
# -----------------------------------------------------------------------


def load_sector_map_from_finviz_csv(csv_path: Path) -> dict[str, str]:
    """Parse a finviz CSV; return {ticker: sector} map.

    Finviz CSVs have 13 canonical columns per CLAUDE.md gotcha; the
    `Sector` column is required. Returns empty dict on missing file or
    parse failure (caller must handle UNKNOWN fallback).
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = (row.get("Ticker") or "").strip().upper()
                sector = (row.get("Sector") or "").strip()
                if ticker and sector:
                    out[ticker] = sector
    except (OSError, csv.Error, UnicodeDecodeError):
        return {}
    return out


def resolve_sector(
    ticker: str,
    *,
    finviz_sector_map: dict[str, str] | None = None,
) -> str:
    """Resolve sector for ticker; returns UNKNOWN_SECTOR on miss.

    V1 resolution path: optional finviz_sector_map (caller pre-loads via
    `load_sector_map_from_finviz_csv`). UNKNOWN fallback for any ticker
    not in the map. Operator can extend the map post-hoc; the investigation
    documents the V1 best-effort resolution in the findings doc.
    """
    if not finviz_sector_map:
        return UNKNOWN_SECTOR
    return finviz_sector_map.get(ticker.upper(), UNKNOWN_SECTOR)


# -----------------------------------------------------------------------
# Per-cohort aggregation
# -----------------------------------------------------------------------


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return s[mid]


def _iqr(values: Sequence[float]) -> float | None:
    """Interquartile range (Q3 - Q1) via linear interpolation."""
    if len(values) < 2:
        return None
    s = sorted(values)
    n = len(s)

    def percentile(pct: float) -> float:
        # linear interpolation per numpy default
        k = (n - 1) * pct
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)

    return percentile(0.75) - percentile(0.25)


def compute_per_ticker_metrics(
    ticker: str,
    asof: date,
    *,
    cache_dir: Path | None = None,
    finviz_sector_map: dict[str, str] | None = None,
) -> PerTickerMetrics:
    """Compute the 4 regime metrics for one (ticker, asof) snapshot.

    Reads via `read_legacy_archive` -- raises CacheMissError on missing
    archive (gotcha #28 + brief Sec 6(d)). Raises AsofDateMissingError
    if the asof_date is NOT present in the archive index (Codex R3 MAJOR
    #3 fix; gotcha #28 strict semantic). Individual metric computations
    return None on insufficient HISTORICAL DEPTH (caller surfaces None
    in CSV + aggregates ignore None values).
    """
    df = read_legacy_archive(ticker, cache_dir=cache_dir)
    _require_asof_in_index(df, asof, ticker)
    return PerTickerMetrics(
        ticker=ticker.upper(),
        asof_date=asof,
        return_90d_pct=compute_90d_return_pct(df, asof),
        atr_pct_20d=compute_atr_pct_20d(df, asof),
        high_52w_proximity_pct=compute_52w_high_proximity_pct(df, asof),
        sector=resolve_sector(ticker, finviz_sector_map=finviz_sector_map),
    )


def aggregate_cohort_metrics(
    cohort_label: str,
    per_ticker: Iterable[PerTickerMetrics],
) -> CohortAggregateMetrics:
    """Aggregate per-ticker metrics into cohort-level medians + IQRs + sector mix."""
    rows = list(per_ticker)
    returns = [r.return_90d_pct for r in rows if r.return_90d_pct is not None]
    atrs = [r.atr_pct_20d for r in rows if r.atr_pct_20d is not None]
    proxs = [r.high_52w_proximity_pct for r in rows if r.high_52w_proximity_pct is not None]
    sector_counts: dict[str, int] = {}
    for r in rows:
        sector_counts[r.sector] = sector_counts.get(r.sector, 0) + 1
    unique_tickers = {r.ticker for r in rows}
    unique_pairs = {(r.ticker, r.asof_date) for r in rows}
    return CohortAggregateMetrics(
        cohort_label=cohort_label,
        unique_ticker_count=len(unique_tickers),
        unique_ticker_asof_count=len(unique_pairs),
        return_90d_pct_median=_median(returns),
        return_90d_pct_iqr=_iqr(returns),
        atr_pct_20d_median=_median(atrs),
        atr_pct_20d_iqr=_iqr(atrs),
        high_52w_proximity_pct_median=_median(proxs),
        high_52w_proximity_pct_iqr=_iqr(proxs),
        sector_counts=sector_counts,
    )


def compute_cohort_characterization(
    cohort_label: str,
    ticker_asof_pairs: Iterable[tuple[str, date]],
    *,
    cache_dir: Path | None = None,
    finviz_sector_map: dict[str, str] | None = None,
) -> tuple[list[PerTickerMetrics], CohortAggregateMetrics]:
    """Compute per-ticker metrics for all (ticker, asof) pairs + aggregate.

    Returns (per_ticker_rows, aggregate). Per-ticker rows preserve input
    order. Raises CacheMissError on first missing archive (gotcha #28
    structural enforcement).
    """
    per_ticker: list[PerTickerMetrics] = []
    for ticker, asof in ticker_asof_pairs:
        per_ticker.append(
            compute_per_ticker_metrics(
                ticker,
                asof,
                cache_dir=cache_dir,
                finviz_sector_map=finviz_sector_map,
            )
        )
    aggregate = aggregate_cohort_metrics(cohort_label, per_ticker)
    return per_ticker, aggregate
