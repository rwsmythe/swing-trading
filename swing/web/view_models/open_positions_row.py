"""OpenPositionsRowVM + pure assembler + single-row convenience wrapper.

The pure assembler `_open_positions_row_vm` has NO I/O and is called by
`build_dashboard` in its batched path. The convenience wrapper
`build_open_positions_row` does the per-row I/O and is used by POST-success
handlers that need exactly one row (spec §3.4).

Tier-2 #3 also defines `OpenPositionsExpandedVM` and `build_open_positions_expanded`
for the open-positions row click-to-expand chart-display fragment (mirrors
WatchlistExpandedVM's chart_reason / data_asof_date contract).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import get_trade
from swing.data.repos.weather import get_latest
from swing.evaluation.dates import action_session_for_run
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.web.chart_scope import (
    CHART_REASON_MESSAGES,
    latest_completed_pipeline_run,
    resolve_chart_scope,
)
from swing.web.price_cache import PriceCache, PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM
from swing.web.view_models.trades import STATE_BADGE_LABELS

# Phase 7 Sub-C T2 — `STATE_BADGE_LABELS` source-of-truth lives at
# swing/web/view_models/trades.py (declared by C.1); imported above
# rather than re-declared to avoid drift.

# Phase 7 Sub-C T2 — Active-trade lifecycle states (open-positions
# fragment + expanded-row VM preconditions). Mirrors `_ACTIVE_STATES_SQL`
# in repos/trades.py and the `_ACTIVE_STATES` tuple in
# swing/web/view_models/trades.py (kept locally for module independence).
_ACTIVE_STATES = ("entered", "managing", "partial_exited")


@dataclass(frozen=True)
class OpenPositionsRowVM:
    trade: Trade
    price_snapshot: PriceSnapshot | None
    remaining_shares: int
    advisories: tuple[AdvisorySuggestionVM, ...]
    state_badge_label: str


def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
    state_badge_label: str,
) -> OpenPositionsRowVM:
    """Pure render-input assembler. NO I/O. Single source of truth for the
    fields an open-positions row consumes from Jinja."""
    return OpenPositionsRowVM(
        trade=trade,
        price_snapshot=price_snapshot,
        remaining_shares=remaining_shares,
        advisories=advisories,
        state_badge_label=state_badge_label,
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

    Phase 7 Sub-C T2: remaining-shares math now consumes Fill rows
    (action != 'entry') via `list_fills_for_trade`, replacing the legacy
    `Exit.shares` summation. Entry fills must be excluded so the entry-fill
    quantity isn't double-subtracted from `initial_shares`.

    Does: cache.get_many([trade.ticker], deadline=..., executor=...);
          list_fills_for_trade(conn, trade.id) for remaining-shares
            (filtered to action != 'entry');
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
            fills = list_fills_for_trade(conn, trade.id)
            non_entry_fills = [f for f in fills if f.action != "entry"]
            # Latest classification for this ticker — weather is keyed by
            # data_asof_date (last completed session), but `action_session`
            # is forward-looking; querying by action_session silently fails
            # on weekend/holiday gaps.
            weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
    finally:
        if own_conn:
            conn.close()
    remaining = trade.initial_shares - sum(
        f.quantity for f in non_entry_fills
    )
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
        state_badge_label=STATE_BADGE_LABELS.get(trade.state, trade.state),
    )


@dataclass(frozen=True)
class OpenPositionsExpandedVM:
    """Tier-2 #3 — fragment-input VM for the open-positions click-to-expand
    chart-display row. Mirrors WatchlistExpandedVM's chart_reason contract
    so the same chart-unavailable rendering pattern applies.

    `data_asof_date` is the latest completed pipeline run's data_asof_date,
    used to construct the date-prefixed `/charts/<date>/<ticker>.png` URL
    when the chart is available. `chart_reason` and `chart_reason_message`
    are returned verbatim from `swing.web.chart_scope.resolve_chart_scope`.
    """
    trade_id: int
    ticker: str
    data_asof_date: str | None
    chart_reason: str | None
    chart_reason_message: str | None


def build_open_positions_expanded(
    *, conn: sqlite3.Connection, cfg: Config, trade_id: int,
) -> OpenPositionsExpandedVM | None:
    """Resolve the expanded-row VM for an open trade.

    Returns None when:
      - The trade does not exist, OR
      - The trade is not in an active lifecycle state (closed/reviewed
        trades 404 the route — closed-trade ids must not display
        open-positions UI).

    Phase 7 Sub-C T2: precondition migrated from the legacy
    `trade.status != "open"` to `trade.state not in _ACTIVE_STATES`
    (where active = entered|managing|partial_exited).

    Otherwise returns a VM populated with the latest completed pipeline run's
    data_asof_date and the chart_scope-resolved chart-availability tuple.
    Note: when no completed pipeline run exists, data_asof_date is None and
    the resolver returns 'no-run' so the partial renders the chart-unavailable
    message instead of a broken /charts URL.
    """
    trade = get_trade(conn, trade_id)
    if trade is None or trade.state not in _ACTIVE_STATES:
        return None

    binding = latest_completed_pipeline_run(conn)
    if binding is None:
        # No completed runs — chart unavailable AND data_asof_date is None.
        return OpenPositionsExpandedVM(
            trade_id=trade.id,
            ticker=trade.ticker,
            data_asof_date=None,
            chart_reason="no-run",
            chart_reason_message=CHART_REASON_MESSAGES["no-run"],
        )

    chart_reason, chart_reason_message = resolve_chart_scope(
        conn, binding=binding, ticker=trade.ticker,
        charts_dir=cfg.paths.charts_dir,
        chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
    )
    return OpenPositionsExpandedVM(
        trade_id=trade.id,
        ticker=trade.ticker,
        data_asof_date=binding.data_asof_date,
        chart_reason=chart_reason,
        chart_reason_message=chart_reason_message,
    )
