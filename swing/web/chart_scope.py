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

    Both are None when the chart is available. Otherwise the reason is one of:
      no-run | engine-missing | pipeline-failed | out-of-scope | insufficient-data
    """
    latest = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status,
                  evaluation_run_id
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC LIMIT 1""",
    ).fetchone()
    if latest is None:
        return "no-run", CHART_REASON_MESSAGES["no-run"]
    run_id, finished_ts, data_asof_date, charts_status, evaluation_run_id = latest

    if charts_status == "skipped":
        return "engine-missing", CHART_REASON_MESSAGES["engine-missing"]
    if charts_status == "failed":
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]
    if charts_status != "ok":
        # None, or any unexpected sentinel — the chart step never signaled
        # success, so a PNG cannot be trusted. Prefer pipeline-failed so the
        # operator is told to re-run, not that this specific ticker was thin.
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]

    # charts_status == 'ok'.
    if evaluation_run_id is not None:
        # FK-backed path (Tranche C T3): scope is the persisted chart_targets
        # row set; no recomputation, no eval-linkage heuristic.
        return _resolve_via_chart_targets(
            conn, ticker=ticker, pipeline_run_id=run_id,
            data_asof_date=data_asof_date, charts_dir=charts_dir,
        )

    # Legacy fallback (pre-migration-0006 rows): heuristic eval-linkage +
    # live-watchlist proximity. Spec §4 accepted-with-rationale drift.
    return _resolve_via_heuristic(
        conn, ticker=ticker, finished_ts=finished_ts,
        data_asof_date=data_asof_date, charts_dir=charts_dir,
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
    # 'pending', 'fetcher_failed', 'too_few_bars' — pre-T5 collapse all of
    # these to 'insufficient-data'. T5 splits fetcher_failed and too_few_bars
    # into dedicated states; this branch is the spec §8 starting point.
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
