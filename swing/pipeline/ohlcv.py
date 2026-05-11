"""Daily-bar fetch + pure SMA math for Phase 3d advisories.

`fetch_daily_bars` is now a thin adapter over `swing.data.ohlcv_archive.read_or_fetch_archive`
(per OHLCV archive consolidation plan Task 5). The session-anchored
partial-bar strip (CLAUDE.md yfinance gotcha) is preserved as belt-and-suspenders.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.evaluation.dates import action_session_for_run


def fetch_daily_bars(
    ticker: str,
    *,
    n_bars: int = 60,
    as_of_date: date | None = None,
    cache_dir: Path,
    archive_history_days: int,
) -> pd.DataFrame | None:
    """Fetch up to `n_bars` completed daily bars <= as_of_date / session.

    Now archive-aware: consults `swing.data.ohlcv_archive.read_or_fetch_archive`
    instead of calling yfinance directly. `cache_dir` and `archive_history_days`
    come from config (typically `cfg.paths.prices_cache_dir` +
    `cfg.archive.archive_history_days`).

    Strip rule (CLAUDE.md gotcha + spec §3.1): drops the last row iff
    `last_bar.date() >= session`. Defends against in-progress intraday bar
    leak even if the helper's archive happens to contain it.

    Returns None on empty result (delisted / bad ticker / no data) — the
    cache layer distinguishes this from raised exceptions (source-level
    failures, breaker-relevant).
    """
    session = as_of_date or action_session_for_run(datetime.now())
    df = read_or_fetch_archive(
        ticker,
        end_date=session,
        cache_dir=cache_dir,
        archive_history_days=archive_history_days,
    )
    if df is None or df.empty:
        return None
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


def compute_adr_pct(
    bars: pd.DataFrame | None, lookback: int = 20,
) -> float | None:
    """ADR% over the trailing ``lookback`` bars from a daily-bar DataFrame.

    ADR% = mean((High - Low) / Close * 100) across the trailing window.

    Returns None when bars is None/empty, when High/Low/Close columns are
    missing, or when fewer than ``lookback`` bars are available. Mirrors
    ``compute_smas``'s "insufficient bars → None" contract so callers can
    surface ``adr_pct=None`` uniformly when OHLCV history is short — the
    §4.D parabolic-trim rule then silently no-ops.

    Bundle 2 add (3e.8) — same formula as
    ``swing.evaluation.criteria._base.adr_pct`` but with explicit
    insufficient-bars handling so the cache surface matches its
    SMA-companion contract.
    """
    if bars is None or bars.empty:
        return None
    for col in ("High", "Low", "Close"):
        if col not in bars.columns:
            return None
    if len(bars) < lookback:
        return None
    tail = bars.tail(lookback)
    # Codex R1 Minor #1 — guard against NaN High/Low/Close rows inside the
    # trailing window. pandas would silently skip NaNs and compute a mean
    # over fewer than `lookback` valid bars, breaking the "≥ lookback bars"
    # invariant compute_smas enforces. Treat ANY missing OHLC in the window
    # as insufficient data and no-op.
    if tail[["High", "Low", "Close"]].isna().any().any():
        return None
    # Defend against zero/negative close (corrupted bar) — would yield
    # inf/-inf in the per-bar percent.
    if (tail["Close"] <= 0).any():
        return None
    ranges_pct = (tail["High"] - tail["Low"]) / tail["Close"] * 100
    val = ranges_pct.mean()
    if pd.isna(val):
        return None
    return float(val)


def previous_close(bars: pd.DataFrame) -> float | None:
    """Last daily bar's Close, or None if unavailable."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return None
    closes = bars["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])
