"""Read-only trade-window chart helpers (CR.1 + journal drill-down/thumbnails).

Render-direct over a trade-window archive slice using the SB3 renderers; NEVER
writes chart_renders (closed-trade charts are neither run-bound nor safely
ticker-keyed -- spec section 1.2). No candlestick re-implementation.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.evaluation.dates import last_completed_session
from swing.web.charts import (
    _serialized_render,
    render_position_detail_svg,
)

if TYPE_CHECKING:
    from swing.config import Config
    from swing.data.models import Trade

PAD_BEFORE_DAYS = 30  # OQ-1: operator-tunable
PAD_AFTER_DAYS = 10   # OQ-1: operator-tunable


def _today() -> date:
    return last_completed_session(datetime.now())


def _exit_date_for(trade: "Trade", fills) -> date | None:
    """Last non-entry fill's date, or None (open trade / no reducing fill)."""
    reducing = [f for f in fills if f.action != "entry"]
    if not reducing:
        return None
    last = sorted(reducing, key=lambda f: f.fill_datetime)[-1]
    return date.fromisoformat(last.fill_datetime[:10])


def _trade_window_bars(*, ticker, entry_date: date, exit_date: date | None,
                       cfg: "Config",
                       pad_before_days: int = PAD_BEFORE_DAYS,
                       pad_after_days: int = PAD_AFTER_DAYS) -> pd.DataFrame | None:
    """Archive slice [entry-pad_before .. (exit or today)+pad_after].

    Returns FULL archive rows <= window_end (read_or_fetch_archive semantics)
    sliced locally to >= window_start. None when the archive lacks coverage of
    the entry (older than archive depth) or yfinance is empty (F6 -> None).
    """
    window_end = (exit_date or _today()) + timedelta(days=pad_after_days)
    window_start = entry_date - timedelta(days=pad_before_days)
    df = read_or_fetch_archive(
        ticker, end_date=window_end,
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days)
    if df is None or df.empty:
        return None
    sliced = df[df.index.date >= window_start]
    if sliced.empty:
        return None
    if sliced.index.min().date() > entry_date:  # #29: entry must be visible
        return None
    return sliced
