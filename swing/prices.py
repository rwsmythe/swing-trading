"""yfinance wrapper with on-disk parquet cache."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def _resolve_asof(as_of_date: date | None) -> date:
    """Translate `None` to the most recent completed NYSE session.

    Prevents caching or evaluating partial intraday bars in live mode.
    """
    if as_of_date is not None:
        return as_of_date
    from swing.evaluation.dates import last_completed_session

    return last_completed_session(datetime.now())


@dataclass
class PriceFetcher:
    """Fetches daily OHLCV with parquet cache.

    Cache key includes `as_of_date` so that pinning the end of history for parity
    reproducibility is safe — two runs with different as_of_date cache separately.

    When `as_of_date` is None, it resolves to the last completed NYSE session (never
    today's partial bar), ensuring the cache key maps to a finished daily candle.
    """

    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, ticker: str, lookback_days: int, as_of_date: date) -> Path:
        return self.cache_dir / f"{ticker}_{lookback_days}d_asof-{as_of_date.isoformat()}.parquet"

    def _fetch_from_yf(
        self, ticker: str, lookback_days: int, as_of_date: date
    ) -> pd.DataFrame:
        """Live fetch. Overridden in tests via patch."""
        import yfinance as yf  # imported lazily so tests don't require network

        end = datetime.combine(as_of_date, datetime.min.time()) + timedelta(days=1)
        start = end - timedelta(days=lookback_days + 7)
        df = yf.download(
            ticker, start=start, end=end, progress=False, auto_adjust=False, actions=False
        )
        if df is None or df.empty:
            raise ValueError(f"No data for {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        # Always truncate — never serve bars past the as_of_date (covers live mode too)
        df = df.loc[df.index.date <= as_of_date]
        return df

    def get(
        self, ticker: str, lookback_days: int, *, as_of_date: date | None = None
    ) -> pd.DataFrame:
        """Fetch OHLCV, always pinned to a completed session.

        `as_of_date=None` → resolves to the last completed NYSE session (never today's
        partial bar). `as_of_date=d` → bars <= d.
        """
        effective = _resolve_asof(as_of_date)
        cache_path = self._cache_path(ticker, lookback_days, effective)
        if cache_path.exists():
            return pd.read_parquet(cache_path)
        df = self._fetch_from_yf(ticker, lookback_days, effective)
        df.to_parquet(cache_path)
        return df

    def clear_cache(self) -> int:
        """Delete all cached parquet files. Returns count deleted."""
        count = 0
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
            count += 1
        return count
