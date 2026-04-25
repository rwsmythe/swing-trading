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
            # Mixed-anchor fix (closes the last surface from the Bug 7 family):
            # bind candidates_by_ticker (and the flag_tags it feeds) to the
            # pipeline's OWN eval via pipeline_runs.evaluation_run_id when
            # populated. Otherwise a post-pipeline standalone `swing eval`
            # could silently win the MAX(run_ts) race and seed flag tags
            # from an eval the pipeline did not chart — the same anchor
            # inconsistency the dashboard fix (commit 1cfc117 Major 2) and
            # build_watchlist_expanded (commit 4678398) already closed. Falls
            # back to latest eval only for legacy NULL-FK rows or fresh installs.
            pipeline_eval_row = conn.execute(
                """SELECT evaluation_run_id FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            pipeline_eval_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            candidates: list[Candidate] = []
            if pipeline_eval_id is not None:
                candidates = fetch_candidates_for_run(conn, pipeline_eval_id)
            else:
                row = conn.execute(
                    "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
                ).fetchone()
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
            # Chart URL + criteria BOTH bind to the latest completed pipeline
            # run's own evaluation_run (adversarial-review Round 3 Major 1:
            # mixed as-of anchors produce contradictory UI when a standalone
            # `swing eval` ran after the pipeline). Eval-linkage uses the
            # same `data_asof_date + run_ts <= finished_ts` heuristic as
            # chart_scope, keeping both views internally consistent.
            pipe_row = conn.execute(
                """SELECT finished_ts, data_asof_date FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1""",
            ).fetchone()
            data_asof = pipe_row[1] if pipe_row else None
            eval_run_id: int | None = None
            if pipe_row is not None:
                finished_ts, pipeline_asof = pipe_row
                linked = conn.execute(
                    """SELECT id FROM evaluation_runs
                       WHERE data_asof_date = ? AND run_ts <= ?
                       ORDER BY run_ts DESC LIMIT 1""",
                    (pipeline_asof, finished_ts),
                ).fetchone()
                if linked is not None:
                    eval_run_id = linked[0]
                # If pipe_row IS set but linkage failed, deliberately leave
                # eval_run_id=None. Falling back to the latest-eval here
                # would re-introduce the mixed-anchor bug (Round 3 Major 1):
                # a post-pipeline standalone `swing eval` would silently
                # seed the criteria panel with an eval the pipeline did not
                # chart. The chart_scope resolver collapses this same case
                # to 'insufficient-data'; the criteria panel accepts the
                # symmetric cost and renders without criteria.
            else:
                # Fresh-install / no-pipeline-yet path — fall back to the
                # latest eval so the criteria panel can still render
                # something useful. No chart will render either way
                # (chart_reason will be no-run).
                fallback = conn.execute(
                    "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
                ).fetchone()
                if fallback is not None:
                    eval_run_id = fallback[0]
            candidate = None
            if eval_run_id is not None:
                for c in fetch_candidates_for_run(conn, eval_run_id):
                    if c.ticker == ticker:
                        candidate = c
                        break
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
