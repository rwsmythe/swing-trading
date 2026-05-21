"""Phase 13 T3.SB3 — Review auto-fill helpers (MFE/MAE source-ladder).

This module implements the spec §6.3 + plan §E.3 LOCK source ladder for
maximum-favorable-excursion (MFE) and maximum-adverse-excursion (MAE) over
a trade's post-entry window. Two sources, ordered:

  1. ``daily_management_records`` (Phase 8) — when the operator's daily-
     management coverage exists for the trade, scan the active (non-
     superseded) ``daily_snapshot`` rows for ``intraday_high`` /
     ``intraday_low`` and compute pct against ``trade.entry_price``.

  2. ``OhlcvCache`` (T1.SB0 substrate) — when Phase 8 coverage is absent,
     fall through to ``OhlcvCache.get_or_fetch`` and compute pct from the
     post-entry slice of daily High/Low bars.

Both sources yield uniform ``mfe_pct`` / ``mae_pct`` per spec §6.3:

    mfe_pct = max(daily highs since entry) / entry_price - 1
    mae_pct = min(daily lows  since entry) / entry_price - 1

Per-row failure isolation honors T2.SB5 R1 M#1 forward-binding lesson #2:
malformed rows (NULL highs / lows) skip rather than poison the aggregate.
Helper-level no-data fall-through returns ``(0.0, 0.0)`` so the form-
render path stays robust even on tickers with no data anywhere (e.g., a
just-opened trade with no Phase 8 snapshot yet AND a cache-miss).

ZERO Schwab API calls (spec §6.3 LOCK + L2 LOCK).
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import date
from typing import Any, Protocol

from swing.data.models import Trade

log = logging.getLogger(__name__)


class _OhlcvCacheLike(Protocol):
    """Structural duck-type of ``swing.web.ohlcv_cache.OhlcvCache.get_or_fetch``.

    Accept any object that exposes the ``get_or_fetch`` surface; lets tests
    inject a stub without instantiating the full TTL cache.
    """

    def get_or_fetch(self, *, ticker: str, window_days: int = ...) -> Any: ...


def _phase8_mfe_mae(
    conn: sqlite3.Connection, trade: Trade,
) -> tuple[float, float] | None:
    """Compute (mfe_pct, mae_pct) from Phase 8 daily_management_records.

    Returns ``None`` when no usable Phase 8 coverage exists for the trade
    (caller falls through to OhlcvCache source). The "usable" predicate
    requires at least one active (non-superseded) ``daily_snapshot`` row
    with a non-NULL ``intraday_high`` OR ``intraday_low`` value.
    """
    try:
        rows = conn.execute(
            "SELECT intraday_high, intraday_low "
            "FROM daily_management_records "
            "WHERE trade_id = ? "
            "  AND record_type = 'daily_snapshot' "
            "  AND is_superseded = 0",
            (trade.id,),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        log.warning(
            "compute_mfe_mae: daily_management_records query failed for "
            "trade %s: %s", trade.id, exc,
        )
        return None

    highs: list[float] = []
    lows: list[float] = []
    for row in rows:
        # Per-row failure isolation (T2.SB5 R1 M#1 lesson #2): skip rows
        # with NULL / non-numeric / NaN values rather than raising.
        try:
            high = row[0]
            if high is not None and isinstance(high, (int, float)):
                hv = float(high)
                if math.isfinite(hv):
                    highs.append(hv)
            low = row[1]
            if low is not None and isinstance(low, (int, float)):
                lv = float(low)
                if math.isfinite(lv):
                    lows.append(lv)
        except (TypeError, ValueError) as exc:
            log.debug(
                "compute_mfe_mae: skipping malformed Phase 8 row for "
                "trade %s: %s", trade.id, exc,
            )
            continue

    if not highs and not lows:
        return None

    entry_price = trade.entry_price
    if entry_price is None or entry_price <= 0:
        # Defensive: an entry price of 0 (or non-positive) would divide-
        # by-zero; treat as no Phase 8 coverage and let the caller fall
        # through.
        return None

    mfe_pct = (max(highs) / entry_price - 1.0) if highs else 0.0
    mae_pct = (min(lows) / entry_price - 1.0) if lows else 0.0
    return mfe_pct, mae_pct


def _ohlcv_mfe_mae(
    trade: Trade, cache: _OhlcvCacheLike,
) -> tuple[float, float]:
    """Compute (mfe_pct, mae_pct) from OhlcvCache.get_or_fetch.

    Returns ``(0.0, 0.0)`` when the cache raises (no data) OR when no bars
    fall on/after the trade's entry_date. Caller is expected to surface
    this as a graceful "no MFE/MAE data" UI state.
    """
    entry_price = trade.entry_price
    if entry_price is None or entry_price <= 0:
        return (0.0, 0.0)

    try:
        entry_dt = date.fromisoformat(trade.entry_date)
    except (TypeError, ValueError):
        log.warning(
            "compute_mfe_mae: trade %s has unparseable entry_date %r",
            trade.id, trade.entry_date,
        )
        return (0.0, 0.0)

    # Calendar-day window covering the trade's post-entry duration plus a
    # buffer (so the OhlcvCache returns enough history). The cache's hook-
    # fallback discipline (T1.SB0 R3 M#1 — "shared-infrastructure cache
    # hooks return FULL archive; consumers slice") means we ask for a
    # generous window and slice locally to the entry_date.
    today = date.today()
    days_since_entry = max(1, (today - entry_dt).days + 30)

    try:
        df = cache.get_or_fetch(
            ticker=trade.ticker, window_days=days_since_entry,
        )
    except Exception as exc:  # noqa: BLE001 — safety boundary
        log.info(
            "compute_mfe_mae: OhlcvCache.get_or_fetch fell through for "
            "trade %s ticker %s: %s",
            trade.id, trade.ticker, exc,
        )
        return (0.0, 0.0)

    if df is None or len(df) == 0:
        return (0.0, 0.0)

    # Per CLAUDE.md OhlcvCache contract: DatetimeIndex + capitalized
    # Open/High/Low/Close/Volume columns. Slice to entry_date onward.
    try:
        index_dates = [ts.date() for ts in df.index]
    except AttributeError:
        # Defensive: a non-DatetimeIndex frame (e.g., stubs returning a
        # plain RangeIndex) gets treated as no-data.
        log.warning(
            "compute_mfe_mae: OhlcvCache returned non-DatetimeIndex frame "
            "for trade %s ticker %s", trade.id, trade.ticker,
        )
        return (0.0, 0.0)

    highs: list[float] = []
    lows: list[float] = []
    high_col = df["High"] if "High" in df.columns else None
    low_col = df["Low"] if "Low" in df.columns else None
    for i, d in enumerate(index_dates):
        if d < entry_dt:
            continue
        # Per-row failure isolation: skip a bar that yields a non-finite
        # high / low rather than poisoning the cohort.
        try:
            if high_col is not None:
                hv = float(high_col.iloc[i])
                if math.isfinite(hv):
                    highs.append(hv)
            if low_col is not None:
                lv = float(low_col.iloc[i])
                if math.isfinite(lv):
                    lows.append(lv)
        except (TypeError, ValueError) as exc:
            log.debug(
                "compute_mfe_mae: skipping malformed OhlcvCache bar for "
                "trade %s ticker %s on %s: %s",
                trade.id, trade.ticker, d, exc,
            )
            continue

    if not highs and not lows:
        return (0.0, 0.0)
    mfe_pct = (max(highs) / entry_price - 1.0) if highs else 0.0
    mae_pct = (min(lows) / entry_price - 1.0) if lows else 0.0
    return mfe_pct, mae_pct


def compute_mfe_mae_from_ohlcv_cache(
    conn: sqlite3.Connection,
    trade: Trade,
    ohlcv_cache: _OhlcvCacheLike | None,
) -> tuple[float, float]:
    """Return ``(mfe_pct, mae_pct)`` for the trade's post-entry window.

    Source ladder per spec §6.3 + plan §E.3 LOCK:

      1. Phase 8 ``daily_management_records`` — when at least one active
         (non-superseded) daily_snapshot row carries a non-NULL intraday
         high OR low. Operator-curated coverage wins.

      2. ``OhlcvCache.get_or_fetch`` — only invoked when Phase 8 coverage
         is absent. Falls through to ``(0.0, 0.0)`` if the cache raises
         (no data) or the post-entry slice is empty.

    Both branches yield uniform pct semantics:

        mfe_pct = max(daily highs since entry) / entry_price - 1
        mae_pct = min(daily lows  since entry) / entry_price - 1

    Helper-level no-data fall-through returns ``(0.0, 0.0)`` so the form-
    render path stays robust on tickers with no data anywhere (just-opened
    trade with no Phase 8 snapshot yet AND a cache-miss).
    """
    phase8 = _phase8_mfe_mae(conn, trade)
    if phase8 is not None:
        return phase8
    if ohlcv_cache is None:
        return (0.0, 0.0)
    return _ohlcv_mfe_mae(trade, ohlcv_cache)
