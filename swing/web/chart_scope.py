"""Chart-unavailable reason resolver — Tranche B-ops spec §4 (Bug 4).

Classifies why a chart is not available for a given watchlist ticker-session
pair, returning one of six states (five "unavailable" reasons + None for
available). Mirrors `swing.pipeline.runner._step_charts` scope logic:

- **A+ set**: from persisted `candidates` rows filtered by `bucket='aplus'`,
  linked to the *pipeline's own* evaluation run via a
  `data_asof_date + run_ts <= finished_ts` heuristic (best-effort —
  races against mid-pipeline standalone `swing eval` calls are documented in
  spec §4; §8 tracks the pipeline-linkage fix as deferred).
- **Top-N near-by-proximity set**: reconstructed from the *live*
  `watchlist` table sorted by `abs((last_close - entry_target) / entry_target)`
  and truncated to `chart_top_n_watch`. This is approximate — watchlist
  churn and price movement between pipeline-run time (T1) and render
  time (T2) can shift the top-N boundary; spec §4 "Drift acknowledgment"
  enumerates the bounded failure modes.

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
from pathlib import Path

from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.watchlist import list_active_watchlist

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
        "(A+ names + top near-trigger watchlist)."
    ),
    "insufficient-data": (
        "Chart unavailable — data too thin or fetch error for this ticker at "
        "last pipeline run."
    ),
}


def resolve_chart_scope(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    charts_dir: Path,
    chart_top_n_watch: int,
) -> tuple[str | None, str | None]:
    """Return (chart_reason, chart_reason_message).

    Both are None when the chart is available (PNG on disk + charts_status=ok
    + ticker in scope). Otherwise the reason is one of:
      no-run | engine-missing | pipeline-failed | out-of-scope | insufficient-data
    """
    latest = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC LIMIT 1""",
    ).fetchone()
    if latest is None:
        return "no-run", CHART_REASON_MESSAGES["no-run"]
    _run_id, finished_ts, data_asof_date, charts_status = latest

    if charts_status == "skipped":
        return "engine-missing", CHART_REASON_MESSAGES["engine-missing"]
    if charts_status == "failed":
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]
    if charts_status != "ok":
        # None, or any unexpected sentinel — the chart step never signaled
        # success, so a PNG cannot be trusted. Prefer pipeline-failed so the
        # operator is told to re-run, not that this specific ticker was thin.
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]

    # charts_status == 'ok'. Resolve scope: A+ ∪ top-N near-by-proximity.
    eval_row = conn.execute(
        """SELECT id FROM evaluation_runs
           WHERE data_asof_date = ? AND run_ts <= ?
           ORDER BY run_ts DESC LIMIT 1""",
        (data_asof_date, finished_ts),
    ).fetchone()
    if eval_row is None:
        # Pipeline-linkage heuristic missed — spec §4 "If the heuristic query
        # returns no row, resolver falls back to insufficient-data." Cannot
        # distinguish scope here, so fail safe toward data-quality bucket.
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
