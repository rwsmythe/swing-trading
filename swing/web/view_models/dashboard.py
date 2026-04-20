"""DashboardVM + builder."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, Trade, WatchlistEntry, WeatherRun
from swing.data.repos.cash import list_cash
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.recommendations import list_for_session
from swing.data.repos.trades import list_all_exits, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.data.repos.weather import get_latest
from swing.evaluation.dates import action_session_for_run
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.trades.equity import current_equity
from swing.web.price_cache import PriceCache, PriceSnapshot


@dataclass(frozen=True)
class StatusStripVM:
    weather_status: str       # "Bullish" | "Caution" | "Bearish" | "STALE"
    weather_rationale: str
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int
    last_pipeline_ts: str | None
    last_pipeline_state: str | None


@dataclass(frozen=True)
class DecisionVM:
    ticker: str
    action_text: str
    narrative: str | None


@dataclass(frozen=True)
class AdvisorySuggestionVM:
    rule: str
    message: str   # matches Phase 2 AdvisorySuggestion.message — do not rename


@dataclass(frozen=True)
class DashboardVM:
    generated_at: str
    session_date: str
    stale_banner: str | None
    status_strip: StatusStripVM
    today_decisions: list[DecisionVM]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]]
    open_trade_last_prices: Mapping[str, PriceSnapshot]
    watchlist_top5: list[WatchlistEntry]
    watchlist_remaining_count: int
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
    # Additive field — populated by Task 6 refactor. Default preserves backward
    # compat for any caller that constructs DashboardVM without this argument.
    open_trade_rows: Mapping[int, object] = field(default_factory=dict)


def build_dashboard(
    *, cfg: Config, cache: PriceCache, executor, ohlcv_cache=None,
) -> DashboardVM:
    """Read state + prices + OHLCV bundles, return a frozen VM.

    When `ohlcv_cache=None` (transitional — wired in T14/15), the OHLCV fetch
    is skipped and all SMA fields fall through to None, so the dashboard
    renders without SMA advisories. `executor` may be None in tests.
    """
    from swing.web.view_models.open_positions_row import (
        OpenPositionsRowVM,
        _open_positions_row_vm,
    )

    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:  # atomic read snapshot across all queries
            open_trades = list_open_trades(conn)
            recs = list_for_session(conn, action_session)
            watchlist = list_active_watchlist(conn)
            # Weather is keyed by data_asof_date (last completed session);
            # action_session is forward-looking (next session). Query by
            # ticker only — the latest classification for that ticker is the
            # right answer, regardless of its asof date. Prevents weekend/
            # holiday gaps from silently rendering STALE.
            weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
            # Equity for status strip — fetch all exits once; also used for
            # per-trade remaining-shares grouping below (no N+1 queries).
            all_exits = list_all_exits(conn)
            equity = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=all_exits,
                cash_movements=list_cash(conn),
            )
            # Group exits by trade_id in Python — avoids per-row DB queries.
            exits_by_trade: dict[int, list] = defaultdict(list)
            for e in all_exits:
                exits_by_trade[e.trade_id].append(e)
            # Latest pipeline run.
            row = conn.execute(
                """SELECT finished_ts, state FROM pipeline_runs
                   ORDER BY started_ts DESC LIMIT 1"""
            ).fetchone()
            last_pipeline_ts, last_pipeline_state = (row[0], row[1]) if row else (None, None)
            # Stale banner: most recent complete run's action_session < today's action_session.
            row = conn.execute(
                """SELECT action_session_date FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            stale_banner = None
            if row is not None and row[0] < action_session:
                stale_banner = (
                    f"Last pipeline session: {row[0]} — decisions below are for session "
                    f"{action_session}. Run pipeline for the current session."
                )
            # Latest candidates for flag_tags + narrative.
            row = conn.execute("SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1").fetchone()
            candidates: list[Candidate] = []
            if row is not None:
                candidates = fetch_candidates_for_run(conn, row[0])
    finally:
        conn.close()

    candidates_by_ticker = {c.ticker: c for c in candidates}

    # Prices — batch fetch all tickers we need.
    active_tickers = {t.ticker for t in open_trades}
    watch_sorted = _sort_by_proximity(watchlist)
    top5 = watch_sorted[:5]
    active_tickers.update(w.ticker for w in top5)
    prices = cache.get_many(
        sorted(active_tickers),
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )

    bundles: dict = {}
    if ohlcv_cache is not None:
        bundles = ohlcv_cache.get_many_bundles(
            sorted(active_tickers),
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )

    watchlist_last_prices = {w.ticker: prices[w.ticker] for w in top5 if w.ticker in prices}

    # Build per-row VMs via the pure assembler. No I/O here — all I/O already
    # happened under the `with conn:` snapshot above. Matches spec §3.4.
    weather_status_str = weather.status if weather else "STALE"

    open_trade_last_prices: dict[str, PriceSnapshot] = {}
    open_trade_advisories: dict[int, list[AdvisorySuggestionVM]] = {}
    open_trade_rows: dict[int, OpenPositionsRowVM] = {}
    for t in open_trades:
        assert t.id is not None, (
            f"open trade {t.ticker} has id=None — data-integrity bug in "
            f"list_open_trades; dashboard cannot render advisories reliably"
        )
        snap = prices.get(t.ticker)
        remaining = t.initial_shares - sum(e.shares for e in exits_by_trade.get(t.id, []))
        bundle = bundles.get(t.ticker)        # may be None or all-None
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv) if snap else []
        advisories_tuple = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )
        row_vm = _open_positions_row_vm(
            trade=t,
            price_snapshot=snap,
            remaining_shares=remaining,
            advisories=advisories_tuple,
        )
        open_trade_rows[t.id] = row_vm
        # Legacy mappings — kept for backward compat with any external consumer.
        if snap is not None:
            open_trade_last_prices[t.ticker] = snap
        open_trade_advisories[t.id] = list(advisories_tuple)

    flag_tags = _flag_tags(candidates_by_ticker)

    # Status strip.
    status_strip = StatusStripVM(
        weather_status=(weather.status if weather else "STALE"),
        weather_rationale=(weather.rationale if weather and weather.rationale else ""),
        equity=equity,
        open_count=len(open_trades),
        soft_warn=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        last_pipeline_ts=last_pipeline_ts,
        last_pipeline_state=last_pipeline_state,
    )

    today_decisions = [
        DecisionVM(
            ticker=r.ticker, action_text=r.action_text or "",
            narrative=r.rationale,
        ) for r in recs if r.recommendation == "today_decision"
    ]

    degraded_until = cache.degraded_until()
    return DashboardVM(
        generated_at=now.isoformat(timespec="seconds"),
        session_date=action_session,
        stale_banner=stale_banner,
        status_strip=status_strip,
        today_decisions=today_decisions,
        open_trades=list(open_trades),
        open_trade_advisories=open_trade_advisories,
        open_trade_last_prices=open_trade_last_prices,
        watchlist_top5=list(top5),
        watchlist_remaining_count=max(0, len(watchlist) - 5),
        watchlist_last_prices=watchlist_last_prices,
        flag_tags=flag_tags,
        candidates_by_ticker=candidates_by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
        ohlcv_source_degraded=(
            ohlcv_cache.is_degraded() if ohlcv_cache is not None else False
        ),
        open_trade_rows=open_trade_rows,
    )


def _sort_by_proximity(watchlist: list[WatchlistEntry]) -> list[WatchlistEntry]:
    def key(w: WatchlistEntry) -> float:
        if w.entry_target is None or w.last_close is None:
            return float("inf")
        return abs(w.last_close - w.entry_target) / max(w.entry_target, 1e-6)
    return sorted(watchlist, key=key)


def _flag_tags(candidates_by_ticker: Mapping[str, Candidate]) -> Mapping[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {}
    for ticker, c in candidates_by_ticker.items():
        row_tags: list[str] = []
        tt_pass = sum(1 for cr in c.criteria if cr.layer == "trend_template" and cr.result == "pass")
        if tt_pass >= 7:
            row_tags.append("TT\u2713")
        vcp_pass = sum(1 for cr in c.criteria if cr.layer == "vcp" and cr.result == "pass")
        vcp_total = sum(1 for cr in c.criteria if cr.layer == "vcp")
        if vcp_total and vcp_pass == vcp_total:
            row_tags.append("VCP\u2713")
        if c.bucket == "aplus":
            row_tags.append("A+")
        if row_tags:
            tags[ticker] = tuple(row_tags)
    return tags
