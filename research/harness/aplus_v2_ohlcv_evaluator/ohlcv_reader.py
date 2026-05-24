"""Read-only Shape A parquet wrapper for the V2 OHLCV harness.

NEVER opens {ticker}.schwab_api.parquet (L2 LOCK preservation per OQ-12 + OQ-16).
NO fetch path. NO writes. NO archive mutation. Reads only:
  - {cache_dir}/{TICKER}.yfinance.parquet  (Shape A primary)
  - {cache_dir}/{TICKER}.parquet            (legacy fallback)

Both-exist policy: Shape A wins unconditionally (per OQ-18 LOCK; caveat
in study writeup Limitations section).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError

_OHLCV_LOWER = ("open", "high", "low", "close", "volume")
_OHLCV_CAPITAL = ("Open", "High", "Low", "Close", "Volume")
_LOWER_TO_CAPITAL = dict(zip(_OHLCV_LOWER, _OHLCV_CAPITAL, strict=True))

# Cap affected_tickers list at 50 per spec §F.1 R4.M1 (avoids unbounded growth on large runs)
_BOTH_EXIST_TICKERS_CAP = 50


@dataclass
class BothExistDiagnostic:
    """Tracks per-V2-invocation both-exist diagnostic surface (Codex R4.M1).

    Populated by repeated read_yfinance_shape_a invocations during a single
    V2 run. Emitted to manifest + markdown warning banner by output.py.

    Note: count accumulates accurately for all tickers; affected_tickers
    is capped at _BOTH_EXIST_TICKERS_CAP=50 to avoid unbounded memory growth.
    """
    count: int = 0
    affected_tickers: list[str] = field(default_factory=list)


def read_yfinance_shape_a(
    ticker: str,
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    """Read the per-ticker yfinance Shape A parquet (with legacy fallback).

    Returns: DataFrame indexed by datetime (ascending; tz-naive) with
    capitalized OHLCV columns (Open/High/Low/Close/Volume) per
    swing/evaluation/criteria expectations.

    Behavior:
      - Primary: read {cache_dir}/{TICKER}.yfinance.parquet (Shape A).
        Columns are lowercase (open/high/low/close/volume) per Shape A
        convention at swing/data/ohlcv_archive.py:449+521-522.
      - Legacy fallback: if primary absent, read {cache_dir}/{TICKER}.parquet
        (capitalized OHLCV; DatetimeIndex).
      - Both-exist case: Shape A wins; if `diagnostic` is provided, increment
        count + append ticker to affected_tickers (capped at 50).
      - Column-case normalization: lowercase OHLCV are renamed to capitalized
        AT THE READ BOUNDARY so downstream evaluate_one(ctx) sees production-
        expected column names (per Codex R2.C1).
      - asof_date handling: Shape A files carry an explicit `asof_date` ISO
        string column; this reader converts to a DatetimeIndex (UTC-naive,
        ascending) and DROPS the asof_date column.
      - NEVER reads {TICKER}.schwab_api.parquet under any branch.

    Raises:
      OhlcvCoverageError: when neither yfinance Shape A nor legacy file exists.
    """
    cache_dir = Path(cache_dir)
    ticker_u = ticker.upper()
    yfinance_path = cache_dir / f"{ticker_u}.yfinance.parquet"
    legacy_path = cache_dir / f"{ticker_u}.parquet"
    yfinance_exists = yfinance_path.exists()
    legacy_exists = legacy_path.exists()

    # Both-exist diagnostic: fires when yfinance Shape A AND legacy coexist
    # (per OQ-18 LOCK + Codex R4.M1 note in §F.3: NOT for yfinance vs schwab_api)
    if yfinance_exists and legacy_exists and diagnostic is not None:
        diagnostic.count += 1
        if len(diagnostic.affected_tickers) < _BOTH_EXIST_TICKERS_CAP:
            diagnostic.affected_tickers.append(ticker_u)

    if yfinance_exists:
        df = pd.read_parquet(yfinance_path)
        return _normalize_shape_a(df)
    elif legacy_exists:
        df = pd.read_parquet(legacy_path)
        return _normalize_legacy(df)
    else:
        raise OhlcvCoverageError(
            f"OHLCV archive missing for ticker={ticker_u!r}: neither "
            f"{yfinance_path.name} nor {legacy_path.name} exists at {cache_dir}"
        )


def read_yfinance_shape_a_sliced(
    ticker: str,
    cache_dir: Path,
    *,
    asof_date: date,
    min_bars: int = 200,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    """Read + slice the per-ticker yfinance Shape A parquet to bars
    <= asof_date (inclusive).

    Raises:
      OhlcvCoverageError: when the sliced frame has fewer than `min_bars` rows
        (per spec §F.2 + cumulative gotcha "yfinance history strip" backward-
        looking inequality discipline -- `data_asof_date` is BACKWARD-looking,
        so `<=` (inclusive) is correct per the existing weather lookup +
        Phase 13 T1.SB0 R3 gotcha precedent).
    """
    df = read_yfinance_shape_a(ticker, cache_dir, diagnostic=diagnostic)
    # Backward-looking anchor: use <= (inclusive) per cumulative gotcha
    sliced = df.loc[df.index.date <= asof_date]
    if len(sliced) < min_bars:
        raise OhlcvCoverageError(
            f"OHLCV insufficient for ticker={ticker!r} at asof_date={asof_date}: "
            f"sliced={len(sliced)} < min_bars={min_bars}"
        )
    return sliced


def _normalize_shape_a(df: pd.DataFrame) -> pd.DataFrame:
    """Shape A (lowercase OHLCV + asof_date column) -> capitalized OHLCV +
    DatetimeIndex.
    """
    if "asof_date" not in df.columns:
        raise ValueError("Shape A parquet missing asof_date column")
    df = df.rename(columns=_LOWER_TO_CAPITAL)
    df["__dt__"] = pd.to_datetime(df["asof_date"])
    df = df.drop(columns=["asof_date"]).set_index("__dt__").sort_index()
    df.index.name = None
    return df[list(_OHLCV_CAPITAL)]


def _normalize_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy (capitalized OHLCV + DatetimeIndex) -> already-canonical shape."""
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        for col in ("Date", "date", "index"):
            if col in df.columns:
                df["__dt__"] = pd.to_datetime(df[col])
                df = df.drop(columns=[col]).set_index("__dt__")
                df.index.name = None
                break
    df = df.sort_index()
    return df[[c for c in _OHLCV_CAPITAL if c in df.columns]]
