"""WatchlistVM + builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, WatchlistEntry
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.pattern_classifications import (
    list_classifications_for_run,
)
from swing.data.repos.watchlist import list_active_watchlist
from swing.evaluation.dates import action_session_for_run
from swing.web.chart_scope import (
    CHART_REASON_MESSAGES,
    latest_completed_pipeline_run,
    resolve_chart_scope,
)
from swing.web.price_cache import PriceCache, PriceSnapshot
from swing.web.view_models.dashboard import (
    _flag_tags,
    _pattern_tags,
    _sort_watchlist,
)


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
    # Spec §3.5 (Phase 4 Task 4.2): SIBLING to flag_tags. {ticker: 'flag (0.78)'}
    # for chart-scope tickers with detected flag patterns. Default empty dict so
    # VMs constructed without classifications (tests, fixtures, code paths
    # without a pipeline_run_id) render gracefully.
    pattern_tags: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WatchlistRowVM:
    """Compact-row context for the /watchlist/<ticker>/row collapse path.

    Mirrors the (w, price, tags) shape `partials/watchlist_row.html.j2`
    expects so the route handler can render that partial directly.

    Phase 4 Task 4.4: `pattern_tag` is a parallel field — independent of
    `tags` so the sort surface (which the row VM does not participate
    in) cannot drift. Default None matches the template's
    `{% if pattern_tag %}` guard.

    CC-pivot R1-Major-3 (hyp-recs trade-prep expansion plan, Task 1):
    `current_pivot` carries the candidates.pivot value for the row's
    ticker so the close-path render surfaces the same value the
    dashboard top-5 and standalone watchlist surface — without this
    field, expand-then-close would revert the Pivot column to
    entry_target.
    """
    w: WatchlistEntry
    price: PriceSnapshot | None
    tags: tuple[str, ...]
    pattern_tag: str | None = None
    current_pivot: float | None = None


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
            rows = list_active_watchlist(conn)
            # Sort moved BELOW the candidates load: `_sort_watchlist` needs
            # flag_tags (computed from candidates) for the primary key.
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
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            pipeline_run_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            pipeline_eval_id = (
                pipeline_eval_row[1] if pipeline_eval_row else None
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
            # Bug-7-family anchor discipline (Phase 4 Task 4.3):
            # classifications bind to pipeline_run_id. Reuse the SAME
            # most-recent COMPLETE pipeline_run id we already resolved
            # above; do NOT re-derive via a SELECT id FROM pipeline_runs
            # WHERE evaluation_run_id = ? lookup, because that
            # round-trip can race with concurrent pipeline_runs writes
            # and silently mis-anchor. The resolved id IS the parent of
            # `pipeline_eval_id` by construction. NO MAX(run_ts) fallback
            # for classifications — when no completed pipeline exists,
            # classifications stay empty (legacy NULL-FK eval rows have
            # no chart-pattern data anyway).
            if pipeline_run_id is not None:
                classifications = list_classifications_for_run(
                    conn, pipeline_run_id=pipeline_run_id,
                )
            else:
                classifications = {}
    finally:
        conn.close()
    by_ticker = {c.ticker: c for c in candidates}
    flag_tags = _flag_tags(by_ticker)
    pattern_tags = _pattern_tags(
        classifications,
        display_threshold=cfg.web.flag_pattern_display_threshold,
    )
    # Sort outside `with conn:` is safe — `_sort_watchlist` is pure (no DB).
    rows = _sort_watchlist(list(rows), flag_tags)
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
        flag_tags=flag_tags,
        candidates_by_ticker=by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
        pattern_tags=pattern_tags,
    )


def build_watchlist_row(
    *, cfg: Config, cache: PriceCache, ticker: str, executor,
) -> WatchlistRowVM | None:
    """Build the (w, price, tags) tuple for the compact-row collapse route.

    Returns None when `ticker` is not on the active watchlist — the route
    surfaces this as 404, mirroring `build_watchlist_expanded`'s contract.
    Tag computation reuses `_flag_tags` so the compact row's tag column
    matches what /watchlist renders for the same ticker.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            rows = list_active_watchlist(conn)
            row = next((r for r in rows if r.ticker == ticker), None)
            if row is None:
                return None
            # Bind candidates to the pipeline's own eval (same anchor logic
            # as build_watchlist) so flag tags don't drift from /watchlist.
            pipeline_eval_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            pipeline_run_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            pipeline_eval_id = (
                pipeline_eval_row[1] if pipeline_eval_row else None
            )
            candidates: list[Candidate] = []
            if pipeline_eval_id is not None:
                candidates = fetch_candidates_for_run(conn, pipeline_eval_id)
            else:
                fallback = conn.execute(
                    "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
                ).fetchone()
                if fallback is not None:
                    candidates = fetch_candidates_for_run(conn, fallback[0])
            # Phase 4 Task 4.4: classification lookup for the compact row,
            # bound to the same `pipeline_run_id` as build_watchlist.
            # Inside the same `with conn:` block (plan note: refactor scope
            # so the new query is inside the same transaction). We reuse
            # `_pattern_tags` rather than `get_classification` so the
            # threshold + format logic is identical to the full watchlist
            # path — single source of truth for the rendered string.
            row_classifications = {}
            if pipeline_run_id is not None:
                row_classifications = list_classifications_for_run(
                    conn, pipeline_run_id=pipeline_run_id,
                )
    finally:
        conn.close()
    by_ticker = {c.ticker: c for c in candidates}
    snaps = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = snaps.get(ticker)
    tags = _flag_tags(by_ticker).get(ticker, ())
    pattern_tag = _pattern_tags(
        row_classifications,
        display_threshold=cfg.web.flag_pattern_display_threshold,
    ).get(ticker)
    return WatchlistRowVM(
        w=row,
        price=snap,
        tags=tags,
        pattern_tag=pattern_tag,
        current_pivot=(by_ticker[ticker].pivot if ticker in by_ticker else None),
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
            # `swing eval` ran after the pipeline). The PipelineRunBinding
            # closes the intra-request race between the data_asof_date read
            # (used for chart URLs) and the chart_scope resolver's read of
            # pipeline_chart_targets — same binding instance used by both.
            binding = latest_completed_pipeline_run(conn)
            data_asof = binding.data_asof_date if binding else None
            eval_run_id: int | None = None
            if binding is not None:
                if binding.evaluation_run_id is not None:
                    # FK-backed path — bind candidates to the pipeline's own eval.
                    eval_run_id = binding.evaluation_run_id
                else:
                    # Legacy NULL-FK pipeline run — fall back to the heuristic
                    # eval-linkage lookup (same as the legacy resolver path).
                    # Eval-linkage uses the same
                    # `data_asof_date + run_ts <= finished_ts` heuristic as
                    # chart_scope, keeping both views internally consistent.
                    # If pipe_row IS set but linkage failed, deliberately
                    # leave eval_run_id=None. Falling back to the latest-eval
                    # here would re-introduce the mixed-anchor bug (Round 3
                    # Major 1): a post-pipeline standalone `swing eval` would
                    # silently seed the criteria panel with an eval the
                    # pipeline did not chart. The chart_scope resolver
                    # collapses this same case to 'insufficient-data'; the
                    # criteria panel accepts the symmetric cost and renders
                    # without criteria.
                    linked = conn.execute(
                        """SELECT id FROM evaluation_runs
                           WHERE data_asof_date = ? AND run_ts <= ?
                           ORDER BY run_ts DESC LIMIT 1""",
                        (binding.data_asof_date, binding.finished_ts),
                    ).fetchone()
                    if linked is not None:
                        eval_run_id = linked[0]
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
            if binding is None:
                chart_reason: str | None = "no-run"
                chart_reason_message: str | None = CHART_REASON_MESSAGES["no-run"]
            else:
                chart_reason, chart_reason_message = resolve_chart_scope(
                    conn, binding=binding, ticker=ticker,
                    charts_dir=cfg.paths.charts_dir,
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
