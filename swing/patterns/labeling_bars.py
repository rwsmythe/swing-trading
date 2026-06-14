"""Phase 13 T2.SB1 T-A.1.5b Defect 3 (Option B) — auto-fetch the candidate
window's OHLCV bars at the CLI emit path so the operator-paired labeling
session at T-A.1.7 receives a fully-populated dispatch payload (replaces
the V1 placeholder bars=[] that forced the operator to hand-build
enriched_dispatch.json artifacts at T-A.1.7 abort 2026-05-19).

Direct yfinance windowed fetch (NOT routed through OhlcvCache or the
`read_or_fetch_archive` weekly-refresh archive): labeling windows are
historical-window queries with arbitrary start_date / end_date pairs;
the archive's 5-year retention bound and its weekly-refresh semantics
(designed for the daily-bar OhlcvCache) don't fit the labeling use case
(operator's SNAP 2020-07-01 window pre-dates archive_history_days=1260
when run from a 2026 calendar date).

Sandbox short-circuit: this helper uses yfinance ONLY; it MAY NOT invoke
any Schwab API path. Per the existing 'Schwab API integration writes
domain rows ONLY when environment=production' CLAUDE.md gotcha, yfinance
fetches are always-on regardless of `cfg.integrations.schwab.environment`.
Tests assert no Schwab path is invoked.

ASCII-only error messages per CLAUDE.md Windows cp1252 stdout gotcha.
"""
from __future__ import annotations

import logging
from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Any

import click
import pandas as pd
import yfinance as yf

from swing.data.yfinance_audit import _record_yf_download
from swing.data.yfinance_audit_context import get_yfinance_audit_context

log = logging.getLogger(__name__)


def _yf_download_window_for_labeling(
    ticker: str, *, start: date_cls, end: date_cls,
) -> pd.DataFrame:
    """Wrap yf.download with gotcha-resistant kwargs (mirrors
    swing/data/ohlcv_archive.py:_yf_download_window).

    `start` inclusive, `end` exclusive in yfinance - we pass `end + 1 day`
    to make the call site's `end_date` semantics inclusive.
    """
    def _fetch():
        return yf.download(
            ticker,
            start=start,
            end=end + timedelta(days=1),
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
        )
    ctx = get_yfinance_audit_context()
    if ctx is None:
        df = _fetch()
    else:
        df = _record_yf_download(
            ctx=ctx, call_type="download_single", ticker=ticker,
            ticker_count=None, fetch_fn=_fetch,
        )
    if df is None or df.empty:
        return pd.DataFrame()
    # Squeeze MultiIndex columns defensively per CLAUDE.md yfinance gotcha
    # ("yfinance group_by='column' returns a MultiIndex column even for
    # single-ticker calls").
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume")
            if c in df.columns]
    df = df[keep]
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _parse_iso_date(value: str, *, param_label: str) -> date_cls:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise click.ClickException(
            f"{param_label} must be ISO date YYYY-MM-DD; got {value!r}: "
            f"{exc}"
        ) from exc


def autofetch_bars_for_labeling(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    timeframe: str,
) -> list[dict[str, Any]]:
    """Fetch daily OHLCV bars for (ticker, start_date, end_date) via
    yfinance + return list-of-dicts shape matching the operator's bars.json
    fixture (keys: date, open, high, low, close, volume).

    Args:
        ticker: ticker symbol (case preserved; yfinance lookup is
            case-insensitive in practice).
        start_date: ISO date string YYYY-MM-DD (inclusive).
        end_date: ISO date string YYYY-MM-DD (inclusive).
        timeframe: 'daily' (only V1-supported value). 'weekly' raises
            a clear ClickException directing the operator to
            --window-bars-file for fixture-pinned override (V2 may add
            weekly resampling).

    Returns:
        List of bar dicts in chronological order. Empty list if the
        ticker has no bars in the window (e.g. delisted before
        start_date OR yfinance returned empty transiently).

    Raises:
        click.ClickException on bad timeframe / unparseable dates /
        start > end.
    """
    if timeframe != "daily":
        raise click.ClickException(
            f"--timeframe={timeframe!r} not supported by labeling "
            "auto-fetch in V1 (only 'daily' is supported). Use "
            "--window-bars-file to supply a pre-built bars file for "
            "weekly or other timeframes."
        )
    start = _parse_iso_date(start_date, param_label="--start")
    end = _parse_iso_date(end_date, param_label="--end")
    if start > end:
        raise click.ClickException(
            f"--start ({start_date}) must be <= --end ({end_date})."
        )

    df = _yf_download_window_for_labeling(ticker, start=start, end=end)
    if df.empty:
        log.warning(
            "autofetch_bars_for_labeling: empty yfinance response for "
            "%s [%s, %s]; emitting empty bars list. Operator can supply "
            "bars via --window-bars-file as override.",
            ticker, start_date, end_date,
        )
        return []

    bars: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        bar_date = ts.date() if hasattr(ts, "date") else ts
        bars.append({
            "date": bar_date.isoformat(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })
    return bars


__all__ = ["autofetch_bars_for_labeling"]
