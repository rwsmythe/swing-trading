"""DashboardVM + builder."""
from __future__ import annotations

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
from swing.data.repos.weather import get_latest_for_date
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


def build_dashboard(*, cfg: Config, cache: PriceCache, executor) -> DashboardVM:
    """Read state + prices, return a frozen VM. `executor` may be None in
    tests (the cache will fall back to serial `get()` behavior via the
    monkeypatched `get_many`).
    """
    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:  # atomic read snapshot across all queries
            open_trades = list_open_trades(conn)
            recs = list_for_session(conn, action_session)
            watchlist = list_active_watchlist(conn)
            weather = get_latest_for_date(conn, action_session, ticker=cfg.rs.benchmark_ticker)
            # Equity for status strip.
            equity = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=list_all_exits(conn),
                cash_movements=list_cash(conn),
            )
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

    open_trade_last_prices = {t.ticker: prices[t.ticker] for t in open_trades if t.ticker in prices}
    watchlist_last_prices = {w.ticker: prices[w.ticker] for w in top5 if w.ticker in prices}

    # Advisories. Phase 2's compute_all_suggestions expects an
    # AdvisoryContext with (as_of_date, current_price, sma10, sma20,
    # weather_status, config=StopAdvisoryConfig).
    #
    # **3a limitation (R2 Major 1)**: sma10 and sma20 are always passed as
    # None. The 7 advisory rules that depend on MA data (suggest_trail_ma
    # for 10MA/20MA, suggest_exit_close_below_ma for 10MA/20MA) gracefully
    # return None when their ma_value is None — so the advisory list is
    # never wrong, just shorter than the fully-informed version. The
    # remaining rules (breakeven, weather_action, time_stop) fire unchanged
    # with current_price + weather + config alone.
    #
    # SMA-aware advisories require on-demand OHLCV → SMA computation per
    # render, which is Phase 3a.1 or 3b scope. The Phase 2 criterion
    # payloads are NOT a stable data contract we are willing to parse.
    advisories: dict[int, list[AdvisorySuggestionVM]] = {}
    weather_status_str = weather.status if weather else "STALE"
    for t in open_trades:
        # Persisted open trades always have an id (the DB assigns via
        # INSERT). A missing id is a data-integrity bug in
        # list_open_trades and must NOT be silently masked — the
        # dashboard would show mismatched advisories or drop entire
        # rows without explanation. Crash-fast via assertion; the
        # FastAPI exception handler renders a 500 with a request_id
        # the operator can grep in web.log (R4 Major 2). Coercion to
        # 0 (R3 Major 2) and silent skip (also R3 Major 2) are both
        # inferior to crash-fast for a "should never happen" invariant.
        if t.id is None:
            raise RuntimeError(
                f"open trade {t.ticker} has id=None — data-integrity bug in "
                f"list_open_trades; dashboard cannot render advisories reliably"
            )
        snap = open_trade_last_prices.get(t.ticker)
        if snap is None:
            continue
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price,
            sma10=None,
            sma20=None,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv)
        advisories[t.id] = [
            AdvisorySuggestionVM(rule=s.rule, message=s.message)
            for s in raw
        ]

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
        open_trade_advisories=advisories,
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
