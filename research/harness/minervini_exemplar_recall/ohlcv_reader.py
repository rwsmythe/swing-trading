# research/harness/minervini_exemplar_recall/ohlcv_reader.py
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .exceptions import TiingoArchiveMissingError, TiingoCoverageError

SYMBOL_OVERRIDE = {"EMEX": "ELX", "HOOK": "BREW"}

_ADJ_TO_CAPITAL = {
    "adjOpen": "Open",
    "adjHigh": "High",
    "adjLow": "Low",
    "adjClose": "Close",
    "adjVolume": "Volume",
}


def tiingo_symbol(book_ticker: str) -> str:
    up = book_ticker.upper()
    return SYMBOL_OVERRIDE.get(up, up)


def read_full(symbol: str, *, tiingo_dir: Path) -> pd.DataFrame:
    """Read research/data/tiingo/<symbol>.csv -> capitalized adjusted OHLCV,
    ascending DatetimeIndex (tz-naive)."""
    path = Path(tiingo_dir) / f"{symbol}.csv"
    if not path.exists():
        raise TiingoArchiveMissingError(f"Tiingo archive missing for symbol={symbol!r} at {path}")
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    df = pd.DataFrame({cap: raw[adj] for adj, cap in _ADJ_TO_CAPITAL.items()})
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def slice_to(bars: pd.DataFrame, asof_date: date) -> pd.DataFrame:
    """In-memory <= asof inclusive slice (backward-looking anchor)."""
    return bars.loc[bars.index.date <= asof_date]


def read_sliced(symbol: str, asof_date: date, *, tiingo_dir: Path, min_bars: int) -> pd.DataFrame:
    sliced = slice_to(read_full(symbol, tiingo_dir=tiingo_dir), asof_date)
    if len(sliced) < min_bars:
        raise TiingoCoverageError(
            f"Tiingo insufficient for symbol={symbol!r} at asof={asof_date}: "
            f"sliced={len(sliced)} < min_bars={min_bars}"
        )
    return sliced
