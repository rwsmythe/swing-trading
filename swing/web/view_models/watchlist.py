"""WatchlistVM + builder."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

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
    latest_evaluation_run_id,
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
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None
    # Spec §3.5 (Phase 4 Task 4.2): SIBLING to flag_tags. {ticker: 'flag (0.78)'}
    # for chart-scope tickers with detected flag patterns. Default empty dict so
    # VMs constructed without classifications (tests, fixtures, code paths
    # without a pipeline_run_id) render gracefully.
    pattern_tags: Mapping[str, str] = field(default_factory=dict)
    # Phase 13 T2.SB6b T-A.6.6 — per-ticker thumbnail SVG bytes from the
    # chart_renders cache (surface='watchlist_row') for the standalone
    # /watchlist page. Default empty dict so VMs constructed outside the
    # builder render gracefully. Keyed by ticker.
    watchlist_chart_svg_bytes: Mapping[str, bytes] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "WatchlistVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "WatchlistVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


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
    # Phase 13 T-T4.SB.3 (Item 5): inline SVG bytes from chart_renders cache
    # (surface='hyprec_detail' — shared with the hyp-recs route per spec §B.5
    # cache-key reuse + renderer-kwargs uniformity LOCK). None when no cache
    # row exists; populated by the route via the JIT helper at request time.
    # Template uses if-else cascade so non-None SVG suppresses the PNG +
    # chart-unavailable banner cascade.
    watchlist_expanded_chart_svg_bytes: bytes | None = None
    # Phase 13 T4.SB Codex R1 Major #1 — pinned pipeline_run_id that the VM
    # bound to. Threaded into the route's JIT chart lookup so chart URL +
    # candidate criteria + chart-scope reason + JIT bytes ALL bind to the
    # SAME pipeline_run (Option A one-anchor LOCK; §1.5.3). None when no
    # completed pipeline_run exists at request time.
    pipeline_run_id: int | None = None


def build_watchlist(*, cfg: Config, cache: PriceCache, executor) -> WatchlistVM:
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
    )

    now = datetime.now()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            rows = list_active_watchlist(conn)
            # Sort moved BELOW the candidates load: `_sort_watchlist` needs
            # flag_tags (computed from candidates) for the primary key.
            # Phase 4 (Task 3): dual-contract migration. Classifications
            # bind via `latest_completed_pipeline_run` (pipeline-bound, no
            # fallback) — no chart-pattern data exists on non-pipeline
            # evals. Candidates bind via `latest_evaluation_run_id`
            # (with-fallback to standalone eval) so flag-tag rendering
            # survives Sunday-evening / fresh-install / NULL-FK states.
            # Both helpers consume the same `conn`, preserving the
            # single-transaction read semantics the inline queries had.
            binding = latest_completed_pipeline_run(conn)
            pipeline_run_id = binding.run_id if binding else None
            candidates_eval_id = latest_evaluation_run_id(conn)
            candidates: list[Candidate] = []
            if candidates_eval_id is not None:
                candidates = fetch_candidates_for_run(conn, candidates_eval_id)
            # Bug-7-family anchor discipline preserved: classifications
            # bind ONLY to a completed-pipeline `pipeline_run_id`. NO
            # MAX(run_ts) fallback for classifications — when no
            # completed pipeline exists, classifications stay empty
            # (legacy NULL-FK eval rows have no chart-pattern data
            # anyway).
            if pipeline_run_id is not None:
                classifications = list_classifications_for_run(
                    conn, pipeline_run_id=pipeline_run_id,
                )
            else:
                classifications = {}
            unresolved = count_unresolved_material(conn)
            recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
            # Phase 13 T2.SB6b T-A.6.6 — pull cached watchlist row chart
            # bytes from the chart_renders cache (T2.SB6a substrate
            # verbatim). Empty dict when no pipeline run / no cache rows.
            watchlist_chart_svg_bytes: dict[str, bytes] = {}
            if pipeline_run_id is not None:
                from swing.data.repos.chart_renders import (
                    get_cached_chart_svg,
                )
                for r in rows:
                    svg = get_cached_chart_svg(
                        conn, ticker=r.ticker,
                        surface="watchlist_row",
                        pipeline_run_id=pipeline_run_id,
                    )
                    if svg is not None:
                        watchlist_chart_svg_bytes[r.ticker] = svg
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
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        watchlist_chart_svg_bytes=watchlist_chart_svg_bytes,
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
            # Phase 4 (Task 3): dual-contract migration mirrors
            # build_watchlist. Classifications bind via
            # `latest_completed_pipeline_run` (pipeline-bound, no
            # fallback). Candidates bind via `latest_evaluation_run_id`
            # (with-fallback) so the compact-row flag tag matches what
            # /watchlist renders for the same ticker.
            binding = latest_completed_pipeline_run(conn)
            pipeline_run_id = binding.run_id if binding else None
            candidates_eval_id = latest_evaluation_run_id(conn)
            candidates: list[Candidate] = []
            if candidates_eval_id is not None:
                candidates = fetch_candidates_for_run(conn, candidates_eval_id)
            # Classification lookup bound to the pipeline run (no
            # fallback). Reuse `_pattern_tags` so threshold + format
            # logic stays identical to the full watchlist path.
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
        # Codex R1 Major #1: pin the binding's run_id so the route's
        # JIT helper threads the SAME anchor used for chart URL +
        # candidate criteria + chart-scope reason.
        pipeline_run_id=(binding.run_id if binding is not None else None),
    )
