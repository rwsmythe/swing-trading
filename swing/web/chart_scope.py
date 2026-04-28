"""Chart-unavailable reason resolver — Tranche B-ops spec §4 (Bug 4).

Classifies why a chart is not available for a given watchlist ticker-session
pair, returning one of six states (five "unavailable" reasons + None for
available).

**FK-backed path (Tranche C T3, current).** When the latest completed
`pipeline_runs` row has a non-NULL `evaluation_run_id` (set by `_step_evaluate`
post-migration-0006), the resolver reads scope directly from
`pipeline_chart_targets` — the per-pipeline-run record of what was actually
charted. This eliminates the two drift modes documented in spec §4:

- **Drift mode A** (eval-linkage race against mid-pipeline standalone
  `swing eval`): the FK is the structural source of truth for which eval the
  pipeline used; no race window remains.
- **Drift mode B** (top-N near-by-proximity recomputed at render time): the
  resolver no longer recomputes proximity — it reads the persisted target
  set, so churn between T1 (pipeline) and T2 (render) cannot flip the
  in-/out-of-scope answer.

**Heuristic fallback (legacy path, retained).** When the latest completed
`pipeline_runs` row has `evaluation_run_id IS NULL` (rows from before
migration 0006), the resolver falls back to the original best-effort
heuristic:

- A+ set from persisted `candidates` rows linked via
  `data_asof_date + run_ts <= finished_ts ORDER BY run_ts DESC LIMIT 1`.
- Top-N near-by-proximity from the live `watchlist` sorted by
  `abs((last_close - entry_target) / entry_target)`, truncated to
  `chart_top_n_watch`.

The heuristic carries the spec §4 documented drift modes — accepted-with-
rationale for legacy rows because backfilling `evaluation_run_id` for
historical pipeline_runs is out of scope (spec §8 deferred).

**Session-gating semantics (adversarial-review Round 1 Major 2).** The resolver
binds to the most-recent completed `pipeline_runs` row by `finished_ts DESC`,
regardless of whether that run's `action_session_date` matches today. This
matches the project's broader "latest completed artifact" convention (see
`swing.data.repos.weather.get_latest`, which returns the latest weather run
regardless of asof date — CLAUDE.md explicitly warns against gating read-only
UIs on `action_session_date`). Consequence: on a pre-pipeline Monday morning
the operator may see Friday's chart without a `no-run` banner on this page.
Staleness for the dashboard-decisions view is handled separately by
`DashboardVM.stale_banner`; propagating that banner to the watchlist/expand
surface is flagged as a cross-UI follow-up, not scope for Tranche B-ops
session 2. The `no-run` state still fires correctly for fresh installs (no
completed runs at all) and the `data_asof_date` chart-URL binding is already
a strict improvement over the pre-change eval-sourced binding.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.watchlist import list_active_watchlist


@dataclass(frozen=True)
class PipelineRunBinding:
    """Pinned pipeline_run state for race-free chart-scope resolution.

    Computed once at request entry by `latest_completed_pipeline_run(conn)`
    and passed to `resolve_chart_scope` so all downstream reads bind to the
    SAME run, even if a new run completes mid-request. Closes the R2 Major
    drift race surfaced in chart-access UX dispatch (commit `f0d13e8`,
    2026-04-27).
    """
    run_id: int
    finished_ts: str
    data_asof_date: str
    charts_status: str | None
    evaluation_run_id: int | None


def latest_completed_pipeline_run(conn: sqlite3.Connection) -> PipelineRunBinding | None:
    """Single-read source of truth for 'which pipeline_run does this request bind to?'.

    Returns None when no completed runs exist. Caller MUST handle the None
    case before calling resolve_chart_scope.

    Codex R1 Minor 1: `id DESC` tiebreaker defends against second-precision
    finished_ts collisions on rapid runs.

    Codex R1 Minor 2: dataclass constructed via NAMED arguments — defensive
    against future SELECT column-order drift.
    """
    row = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status, evaluation_run_id
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC, id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    run_id, finished_ts, data_asof_date, charts_status, evaluation_run_id = row
    return PipelineRunBinding(
        run_id=run_id,
        finished_ts=finished_ts,
        data_asof_date=data_asof_date,
        charts_status=charts_status,
        evaluation_run_id=evaluation_run_id,
    )


CHART_REASON_MESSAGES: dict[str, str] = {
    "no-run": "Chart unavailable — no pipeline run yet for this session.",
    "engine-missing": (
        "Chart unavailable — charting engine (mplfinance) not installed on this host."
    ),
    "pipeline-failed": (
        "Chart unavailable — last pipeline run's chart step failed. Re-run when ready."
    ),
    "out-of-scope": (
        "Chart unavailable — this ticker isn't in today's charting scope "
        "(A+ candidates, open positions, and tag-aware watchlist top-10)."
    ),
    "insufficient-data": (
        "Chart unavailable — data too thin or fetch error for this ticker at "
        "last pipeline run."
    ),
    # Tranche C T5 (spec §8 deferred item, now closed): the FK-backed code
    # path can distinguish these two from each other and from the catch-all
    # 'insufficient-data' (which still fires on the heuristic legacy path
    # and on 'pending' chart_status).
    "fetcher_failed": (
        "Chart unavailable — yfinance fetch failed for this ticker at last "
        "pipeline run."
    ),
    "too_few_bars": (
        "Chart unavailable — insufficient historical bars for this ticker at "
        "last pipeline run."
    ),
}


def resolve_chart_scope(
    conn: sqlite3.Connection,
    *,
    binding: PipelineRunBinding,
    ticker: str,
    charts_dir: Path,
    chart_top_n_watch: int,
) -> tuple[str | None, str | None]:
    """Race-free chart-scope resolver.

    Caller MUST pin the binding at request handler entry via
    `latest_completed_pipeline_run(conn)`. Resolver does NOT re-read
    `pipeline_runs` internally. Returns `(reason, message)` — both None when
    chart is available; otherwise reason ∈ {no-run, engine-missing,
    pipeline-failed, out-of-scope, insufficient-data, fetcher_failed,
    too_few_bars} and message is the operator-facing copy.

    Binding contract (spec §C "Binding scope definition"):
    - One binding per HTTP request handler.
    - The binding closes the intra-request race between the caller's read
      of `pipeline_runs.data_asof_date` (used to construct chart URLs) and
      the resolver's read of `pipeline_chart_targets`.
    - Multiple `resolve_chart_scope` calls within the same request handler
      MUST share the same binding instance to honor the contract. Future
      surfaces composing multiple resolutions in one handler MUST pin the
      binding ONCE at the top and pass it through to all calls.
    - Inter-request races (different HTTP requests from the same dashboard)
      are NOT closed by this contract; cross-request session pinning is
      out-of-scope (spec §C "What the binding does NOT close").
    """
    if binding.charts_status == "skipped":
        return "engine-missing", CHART_REASON_MESSAGES["engine-missing"]
    if binding.charts_status == "failed":
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]
    if binding.charts_status != "ok":
        # None, or any unexpected sentinel — the chart step never signaled
        # success, so a PNG cannot be trusted. Prefer pipeline-failed so the
        # operator is told to re-run, not that this specific ticker was thin.
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]

    # charts_status == 'ok'.
    if binding.evaluation_run_id is not None:
        # FK-backed path (Tranche C T3): scope is the persisted chart_targets
        # row set; no recomputation, no eval-linkage heuristic.
        return _resolve_via_chart_targets(
            conn, ticker=ticker, pipeline_run_id=binding.run_id,
            data_asof_date=binding.data_asof_date, charts_dir=charts_dir,
        )

    # Legacy fallback (pre-migration-0006 rows): heuristic eval-linkage +
    # live-watchlist proximity. Spec §4 accepted-with-rationale drift.
    return _resolve_via_heuristic(
        conn, ticker=ticker, finished_ts=binding.finished_ts,
        data_asof_date=binding.data_asof_date, charts_dir=charts_dir,
        chart_top_n_watch=chart_top_n_watch,
    )


def _resolve_via_chart_targets(
    conn: sqlite3.Connection, *, ticker: str, pipeline_run_id: int,
    data_asof_date: str, charts_dir: Path,
) -> tuple[str | None, str | None]:
    """Tranche C T3: read scope directly from pipeline_chart_targets."""
    row = conn.execute(
        """SELECT chart_status FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND ticker = ?""",
        (pipeline_run_id, ticker),
    ).fetchone()
    if row is None:
        # Pipeline did not chart this ticker.
        return "out-of-scope", CHART_REASON_MESSAGES["out-of-scope"]
    chart_status = row[0]
    if chart_status == "ok":
        png_path = charts_dir / data_asof_date / f"{ticker}.png"
        if not png_path.exists():
            # Persisted status says ok but the PNG vanished from disk.
            # Surface as data-quality bucket rather than claim availability.
            return "insufficient-data", CHART_REASON_MESSAGES["insufficient-data"]
        return None, None
    # Tranche C T5: split fetcher_failed and too_few_bars into dedicated
    # states (closes spec §8 deferred item). 'pending' (the chart step never
    # finalized — usually a crash mid-step) collapses to the insufficient-
    # data catch-all because it does not describe a known cause.
    if chart_status in ("fetcher_failed", "too_few_bars"):
        return chart_status, CHART_REASON_MESSAGES[chart_status]
    return "insufficient-data", CHART_REASON_MESSAGES["insufficient-data"]


def _resolve_via_heuristic(
    conn: sqlite3.Connection, *, ticker: str, finished_ts: str,
    data_asof_date: str, charts_dir: Path, chart_top_n_watch: int,
) -> tuple[str | None, str | None]:
    """Pre-Tranche-C heuristic. Used for legacy pipeline_runs rows that
    pre-date migration 0006 (NULL evaluation_run_id). Carries the spec §4
    drift modes as documented; new pipeline runs use _resolve_via_chart_targets.
    """
    eval_row = conn.execute(
        """SELECT id FROM evaluation_runs
           WHERE data_asof_date = ? AND run_ts <= ?
           ORDER BY run_ts DESC LIMIT 1""",
        (data_asof_date, finished_ts),
    ).fetchone()
    if eval_row is None:
        # Heuristic missed; collapse to data-quality bucket.
        return "insufficient-data", CHART_REASON_MESSAGES["insufficient-data"]
    eval_run_id = eval_row[0]

    aplus_tickers = {
        c.ticker for c in fetch_candidates_for_run(conn, eval_run_id)
        if c.bucket == "aplus"
    }

    watchlist = list_active_watchlist(conn)
    near_by_proximity = sorted(
        [w for w in watchlist if w.entry_target and w.last_close],
        key=lambda w: abs((w.last_close - w.entry_target) / w.entry_target),
    )[:chart_top_n_watch]
    top_n_tickers = {w.ticker for w in near_by_proximity}

    if ticker not in aplus_tickers and ticker not in top_n_tickers:
        return "out-of-scope", CHART_REASON_MESSAGES["out-of-scope"]

    png_path = charts_dir / data_asof_date / f"{ticker}.png"
    if not png_path.exists():
        return "insufficient-data", CHART_REASON_MESSAGES["insufficient-data"]

    return None, None
