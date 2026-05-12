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
from dataclasses import dataclass, field
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.daily_management import has_update_today_for_trades
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
    # Polish-bundle 2026-05-09 Family A — daily-management "logged?" badge
    # boolean. True iff the trade has at least one ``daily_management_records``
    # row whose ``review_date`` equals the latest-completed-NYSE-session date
    # (per ``has_update_today_for_trades`` predicate, anchored on
    # ``last_completed_session(now)`` post-Codex R1 Major #1 fix). Default
    # False so positional callers (none currently) and tests building VMs
    # without the field aren't broken.
    has_update_today: bool = False
    # Codex R2 Major #1 fix: badge text was "✓ today" / "⚠ not yet" but the
    # predicate is anchored on last_completed_session — Friday's session would
    # render as "today" on Monday morning before market close. Template now
    # shows "✓ logged" / "⚠ pending" + a hover ``title=`` carrying this
    # session-date string so the operator sees the actual session anchor on
    # hover. Default empty string so legacy hand-constructed VMs render an
    # empty title (harmless) without raising.
    update_session_date: str = ""


def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
    state_badge_label: str,
    has_update_today: bool = False,
    update_session_date: str = "",
) -> OpenPositionsRowVM:
    """Pure render-input assembler. NO I/O. Single source of truth for the
    fields an open-positions row consumes from Jinja."""
    return OpenPositionsRowVM(
        trade=trade,
        price_snapshot=price_snapshot,
        remaining_shares=remaining_shares,
        advisories=advisories,
        state_badge_label=state_badge_label,
        has_update_today=has_update_today,
        update_session_date=update_session_date,
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
            # 3e.8 Bundle 3 — per-trade active snapshot for the §4.A.bis
            # maturity_stage advisory. Latest-session-clamped reader; returns
            # None if no snapshot exists (rule no-ops).
            from swing.data.repos.daily_management import (
                select_latest_active_snapshot_for_trade,
            )
            _active_snap = select_latest_active_snapshot_for_trade(
                conn, trade_id=trade.id,
            )
            # Polish-bundle 2026-05-09 Family A — single-row variant of the
            # dashboard's batched call; passes a one-element list. Empty input
            # short-circuits per helper contract, so trade.id=None is also
            # safe (assertion above already excludes that path).
            #
            # Codex R1 Major #1 fix: anchor on ``last_completed_session(now)``
            # (NOT the forward-looking ``action_session``) — see
            # ``swing/data/repos/daily_management.py``
            # ``has_update_today_for_trades`` docstring for the full
            # session-anchor contract.
            from swing.evaluation.dates import last_completed_session
            mgmt_session_date_local = last_completed_session(now).isoformat()
            update_set = has_update_today_for_trades(
                conn, [trade.id], session_date=mgmt_session_date_local,
            )
    finally:
        if own_conn:
            conn.close()
    remaining = trade.initial_shares - sum(
        f.quantity for f in non_entry_fills
    )
    weather_status = weather.status if weather else "STALE"

    advisories: tuple[AdvisorySuggestionVM, ...] = ()
    if snapshot is not None:
        # 3e.8 Bundle 2 — adr_pct from OhlcvBundle; has_been_trimmed from
        # the same non_entry_fills already used for remaining-shares math.
        ctx = AdvisoryContext(
            as_of_date=action_session,
            current_price=snapshot.price,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status,
            config=cfg.stop_advisory,
            adr_pct=bundle.adr_pct if bundle else None,
            has_been_trimmed=bool(non_entry_fills),
            maturity_stage=(
                _active_snap.maturity_stage if _active_snap else None
            ),
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
        has_update_today=(trade.id in update_set),
        update_session_date=mgmt_session_date_local,
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

    3e.8 Bundle 1 (§4.F B.AC.5) — ``advisories`` carries the same per-trade
    ``AdvisorySuggestionVM`` tuple ``OpenPositionsRowVM.advisories`` surfaces
    on the dashboard list view. Default empty tuple keeps existing callers
    green (builder paths that don't pass cache/executor see no advisories).
    """
    trade_id: int
    ticker: str
    data_asof_date: str | None
    chart_reason: str | None
    chart_reason_message: str | None
    # Spec-conformant ``field(default_factory=tuple)`` per brief §0.3 #5
    # (Codex R2 Minor #1 alignment).
    advisories: tuple = field(default_factory=tuple)  # tuple[AdvisorySuggestionVM, ...]


def build_open_positions_expanded(
    *, conn: sqlite3.Connection, cfg: Config, trade_id: int,
    cache: PriceCache | None = None, executor=None, ohlcv_cache=None,
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

    # 3e.8 Bundle 1 (§4.F B.AC.5) — compose advisories via the same path the
    # dashboard list view uses; mirrors ``build_open_positions_row``. Only
    # active trades reach this point (the precondition above returns None for
    # closed/reviewed). When the caller did not thread a ``cache`` (e.g.,
    # pre-Bundle-1 unit tests), advisories remain empty.
    advisories: tuple = ()
    if cache is not None:
        now = datetime.now()
        action_session = action_session_for_run(now).isoformat()
        prices = cache.get_many(
            [trade.ticker],
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )
        snap = prices.get(trade.ticker)
        bundle = None
        if ohlcv_cache is not None:
            bundles = ohlcv_cache.get_many_bundles(
                [trade.ticker],
                deadline_seconds=cfg.web.price_fetch_deadline_seconds,
                executor=executor,
            )
            bundle = bundles.get(trade.ticker)
        # Latest weather — read-only UIs must use get_latest (CLAUDE.md
        # weather lookup gotcha).
        weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
        weather_status = weather.status if weather else "STALE"
        # 3e.8 Bundle 2 — has_been_trimmed from the trade's fills. The
        # expanded-row builder isn't already loading fills (unlike the row
        # builder which loads them for remaining-shares); we query here
        # specifically for the trim-detection predicate. Read happens
        # under the same caller-owned conn so it stays in the request's
        # snapshot.
        fills = list_fills_for_trade(conn, trade.id)
        has_been_trimmed = any(f.action != "entry" for f in fills)
        # 3e.8 Bundle 3 — per-trade active snapshot for §4.A.bis maturity_stage.
        from swing.data.repos.daily_management import (
            select_latest_active_snapshot_for_trade,
        )
        _active_snap = select_latest_active_snapshot_for_trade(
            conn, trade_id=trade.id,
        )
        if snap is not None:
            ctx = AdvisoryContext(
                as_of_date=action_session,
                current_price=snap.price,
                sma10=bundle.sma10 if bundle else None,
                sma20=bundle.sma20 if bundle else None,
                sma50=bundle.sma50 if bundle else None,
                previous_close=bundle.previous_close if bundle else None,
                weather_status=weather_status,
                config=cfg.stop_advisory,
                adr_pct=bundle.adr_pct if bundle else None,
                has_been_trimmed=has_been_trimmed,
                maturity_stage=(
                    _active_snap.maturity_stage if _active_snap else None
                ),
            )
            raw = compute_all_suggestions(trade, ctx)
            advisories = tuple(
                AdvisorySuggestionVM(rule=s.rule, message=s.message)
                for s in raw
            )

    binding = latest_completed_pipeline_run(conn)
    if binding is None:
        # No completed runs — chart unavailable AND data_asof_date is None.
        return OpenPositionsExpandedVM(
            trade_id=trade.id,
            ticker=trade.ticker,
            data_asof_date=None,
            chart_reason="no-run",
            chart_reason_message=CHART_REASON_MESSAGES["no-run"],
            advisories=advisories,
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
        advisories=advisories,
    )
