"""yfinance wrapper consuming the per-ticker archive helper."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive


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
    """Fetches daily OHLCV via the per-ticker archive (`swing.data.ohlcv_archive`).

    Public API stable: `get(ticker, lookback_days, *, as_of_date=None)` returns
    a DataFrame indexed by date with OHLCV columns, sliced to the
    `lookback_days` calendar-day window ending at the resolved `as_of_date`
    (or last completed NYSE session if as_of_date is None).

    `cache_dir` is the archive directory (per-ticker `{TICKER}.parquet` +
    `{TICKER}.meta.json` sidecar); `archive_history_days` is the full-history
    fetch depth used by the helper's weekly-refresh / new-ticker paths.
    """

    cache_dir: Path
    archive_history_days: int = 1260

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self, ticker: str, lookback_days: int, *, as_of_date: date | None = None
    ) -> pd.DataFrame:
        """Fetch OHLCV pinned to a completed session, sliced to lookback window.

        `as_of_date=None` → resolves to the last completed NYSE session.
        Raises ValueError when the archive helper has no data for the ticker
        (delisted / invalid / no history) — preserves prior API contract.
        """
        effective = _resolve_asof(as_of_date)
        df = read_or_fetch_archive(
            ticker,
            end_date=effective,
            cache_dir=self.cache_dir,
            archive_history_days=self.archive_history_days,
        )
        if df is None or df.empty:
            raise ValueError(f"No data for {ticker}")
        cutoff = effective - timedelta(days=lookback_days)
        sliced = df.loc[(df.index.date >= cutoff) & (df.index.date <= effective)]
        if sliced.empty:
            raise ValueError(f"No data for {ticker}")
        return sliced

    def clear_cache(self) -> int:
        """Delete archive parquet + meta sidecar + tmp orphan files.
        Returns count deleted."""
        count = 0
        for pattern in ("*.parquet", "*.meta.json", "*.parquet.tmp", "*.meta.json.tmp"):
            for f in self.cache_dir.glob(pattern):
                f.unlink()
                count += 1
        return count
