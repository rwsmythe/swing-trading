"""OpenPositionsRowVM + pure assembler + single-row convenience wrapper.

The pure assembler `_open_positions_row_vm` has NO I/O and is called by
`build_dashboard` in its batched path. The convenience wrapper
`build_open_positions_row` does the per-row I/O and is used by POST-success
handlers that need exactly one row (spec §3.4).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import list_exits_for_trade
from swing.data.repos.weather import get_latest
from swing.evaluation.dates import action_session_for_run
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.web.price_cache import PriceCache, PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


@dataclass(frozen=True)
class OpenPositionsRowVM:
    trade: Trade
    price_snapshot: PriceSnapshot | None
    remaining_shares: int
    advisories: tuple[AdvisorySuggestionVM, ...]


def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
) -> OpenPositionsRowVM:
    """Pure render-input assembler. NO I/O. Single source of truth for the
    fields an open-positions row consumes from Jinja."""
    return OpenPositionsRowVM(
        trade=trade,
        price_snapshot=price_snapshot,
        remaining_shares=remaining_shares,
        advisories=advisories,
    )


def build_open_positions_row(
    *, trade: Trade, cfg: Config, cache: PriceCache, executor,
    ohlcv_cache=None,
    conn: sqlite3.Connection | None = None,
) -> OpenPositionsRowVM:
    """Single-row convenience wrapper for POST-success handlers.

    Shares advisory inputs with build_dashboard (R2 Major 3 fix): fetches the
    same `action_session_for_run(now)` date and the same latest-weather row
    the dashboard loop uses, so POST-success rows render the SAME advisory
    set the dashboard would for bullish/caution/bearish or session-boundary
    days.

    Does: cache.get_many([trade.ticker], deadline=..., executor=...);
          list_exits_for_trade(conn, trade.id) for remaining-shares;
          get_latest_for_date(conn, action_session, ticker=benchmark) for weather;
          ohlcv_cache.get_many_bundles([trade.ticker], ...) when ohlcv_cache is
          provided (None default keeps existing call sites green until T15);
          compute_all_suggestions(trade, AdvisoryContext(...)) with SMA fields
          populated from bundle when available.

    Opens its own read-snapshot `with conn:` if `conn` is None.
    Callers that have batch context (dashboard.py) should use `_open_positions_row_vm`
    directly with precomputed snapshots + exits + advisories.
    """
    assert trade.id is not None, f"trade.id=None for {trade.ticker} — data integrity bug"

    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snapshot = prices.get(trade.ticker)

    bundle = None
    if ohlcv_cache is not None:
        bundles = ohlcv_cache.get_many_bundles(
            [trade.ticker],
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )
        bundle = bundles.get(trade.ticker)

    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    try:
        with conn:
            exits = list_exits_for_trade(conn, trade.id)
            # Latest classification for this ticker — weather is keyed by
            # data_asof_date (last completed session), but `action_session`
            # is forward-looking; querying by action_session silently fails
            # on weekend/holiday gaps.
            weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
    finally:
        if own_conn:
            conn.close()
    remaining = trade.initial_shares - sum(e.shares for e in exits)
    weather_status = weather.status if weather else "STALE"

    advisories: tuple[AdvisorySuggestionVM, ...] = ()
    if snapshot is not None:
        ctx = AdvisoryContext(
            as_of_date=action_session,
            current_price=snapshot.price,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(trade, ctx)
        advisories = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )

    return _open_positions_row_vm(
        trade=trade,
        price_snapshot=snapshot,
        remaining_shares=remaining,
        advisories=advisories,
    )
