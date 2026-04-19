"""Daily-bar fetch + pure SMA math for Phase 3d advisories.

Spec §3.1. `fetch_daily_bars` does the network IO; `compute_smas` and
`previous_close` are pure transformations over pandas DataFrames and are
unit-testable without yfinance.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from swing.evaluation.dates import action_session_for_run


def fetch_daily_bars(
    ticker: str, *, n_bars: int = 60, as_of_date: date | None = None,
) -> pd.DataFrame | None:
    """Fetch completed daily bars for `ticker` (spec §3.1).

    Returns up to `n_bars` rows of FULLY-COMPLETED daily bars, ending with
    the most recent completed session. Returns None on empty result or
    exception.

    Session-boundary semantics: yfinance's `history(interval='1d')` includes
    the IN-PROGRESS bar during market hours. We strip it — otherwise
    `previous_close` would reflect the partial close, turning the
    "close below MA" rule back into an intraday rule.

    `as_of_date` resolves against the EXCHANGE SESSION, not the app-local
    timezone (HST lags ET by 5h). Defaults to
    `action_session_for_run(datetime.now())` — the project's single source
    of truth for session-date resolution. Injectable for deterministic tests.

    Strip rule: drop the last row iff `last_bar.date() >= session`.

    Implementation notes:
      - `period='6mo'` (~126 trading bars) is ample for SMA50 with holiday buffer.
      - `auto_adjust=False` returns raw bars (see spec §6 for split handling).
      - `threads=False` per the yfinance rate-limit gotcha (CLAUDE.md).
    """
    try:
        df = yf.Ticker(ticker).history(
            period="6mo",
            interval="1d",
            auto_adjust=False,
            threads=False,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    session = as_of_date or action_session_for_run(datetime.now())
    # yfinance index is timezone-aware Timestamps; compare by .date().
    last_date = df.index[-1].date()
    if last_date >= session:
        df = df.iloc[:-1]
    if df.empty:
        return None
    return df.tail(n_bars)


def compute_smas(
    bars: pd.DataFrame, periods: Sequence[int],
) -> dict[int, float | None]:
    """Return {period: float|None} from the last row of a rolling-mean over
    the 'Close' column. None if fewer bars than `period` (or 'Close' missing)."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return {p: None for p in periods}
    closes = bars["Close"].dropna()
    out: dict[int, float | None] = {}
    for p in periods:
        if len(closes) < p:
            out[p] = None
        else:
            sma = closes.rolling(p, min_periods=p).mean()
            last = sma.iloc[-1]
            out[p] = float(last) if pd.notna(last) else None
    return out


def previous_close(bars: pd.DataFrame) -> float | None:
    """Last daily bar's Close, or None if unavailable."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return None
    closes = bars["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])
