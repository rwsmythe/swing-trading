"""WatchlistVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, WatchlistEntry
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.watchlist import list_active_watchlist
from swing.evaluation.dates import action_session_for_run
from swing.web.chart_scope import resolve_chart_scope
from swing.web.price_cache import PriceCache, PriceSnapshot
from swing.web.view_models.dashboard import _flag_tags, _sort_by_proximity


@dataclass(frozen=True)
class WatchlistVM:
    session_date: str
    rows: list[WatchlistEntry]
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    stale_banner: str | None = None   # placeholder — populated only on the main dashboard
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)


@dataclass(frozen=True)
class WatchlistExpandedVM:
    ticker: str
    entry: WatchlistEntry
    candidate: Candidate | None
    last_price: PriceSnapshot | None
    data_asof_date: str | None   # for /charts/<date>/<ticker>.png
    chart_reason: str | None = None         # None when chart is available
    chart_reason_message: str | None = None


def build_watchlist(*, cfg: Config, cache: PriceCache, executor) -> WatchlistVM:
    now = datetime.now()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            rows = _sort_by_proximity(list_active_watchlist(conn))
            row = conn.execute("SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1").fetchone()
            candidates: list[Candidate] = []
            if row is not None:
                candidates = fetch_candidates_for_run(conn, row[0])
    finally:
        conn.close()
    by_ticker = {c.ticker: c for c in candidates}
    prices = cache.get_many(
        [r.ticker for r in rows],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    degraded_until = cache.degraded_until()
    return WatchlistVM(
        session_date=action_session_for_run(now).isoformat(),
        rows=list(rows),
        watchlist_last_prices={r.ticker: prices[r.ticker] for r in rows if r.ticker in prices},
        flag_tags=_flag_tags(by_ticker),
        candidates_by_ticker=by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
    )


def build_watchlist_expanded(
    *, cfg: Config, cache: PriceCache, ticker: str, executor,
) -> WatchlistExpandedVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            rows = list_active_watchlist(conn)
            row = next((r for r in rows if r.ticker == ticker), None)
            if row is None:
                return None
            # Candidate (for trend-template / VCP criteria panel) comes from
            # the latest eval run; this is independent of the chart-source
            # binding below.
            eval_row = conn.execute(
                "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
            ).fetchone()
            candidate = None
            if eval_row is not None:
                for c in fetch_candidates_for_run(conn, eval_row[0]):
                    if c.ticker == ticker:
                        candidate = c
                        break
            # Chart URL binds to the LATEST COMPLETED PIPELINE RUN's
            # data_asof_date (per spec §4) — using the latest eval's asof
            # would pick up post-pipeline standalone eval rows and point the
            # <img> at a date the pipeline never charted.
            pipe_row = conn.execute(
                """SELECT data_asof_date FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1""",
            ).fetchone()
            data_asof = pipe_row[0] if pipe_row else None
            chart_reason, chart_reason_message = resolve_chart_scope(
                conn, ticker=ticker, charts_dir=cfg.paths.charts_dir,
                chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
            )
    finally:
        conn.close()
    snaps = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = snaps.get(ticker)
    return WatchlistExpandedVM(
        ticker=ticker, entry=row, candidate=candidate,
        last_price=snap, data_asof_date=data_asof,
        chart_reason=chart_reason, chart_reason_message=chart_reason_message,
    )
