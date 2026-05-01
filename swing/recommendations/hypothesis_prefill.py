"""Public helper for resolving the active hypothesis recommendation label
for a given ticker — used by both the CLI (`swing trade entry` pre-fill)
and the web entry form (Phase 4.5 hypothesis-label web-form gap closure).

Frontend brief §0 + §4.3: the matcher's ``suggested_label_descriptive``
starts with the canonical hypothesis name (case-insensitive). Passing it
through unchanged preserves that prefix so future tripwire/progress
aggregation attributes the trade correctly. Determinism: the matcher +
prioritizer + per-ticker dedup are pure functions on (registry,
candidates, progress); re-running yields the same label — needed by the
brief §5 watch item on pre-fill stability.

Cross-surface consistency (adversarial review R1 Major 1 from the CLI's
original implementation): use the SAME evaluation_run id the dashboard
binds candidates to. If the operator sees a recommendation on the
dashboard for ticker X, the CLI/web-form for X must pre-fill the same
label.

Imports of ``swing.web.view_models.dashboard`` happen inside the function
body (not at module top) so this module stays import-cheap and avoids
any future circular-import risk if dashboard.py grows imports of its own.
"""
from __future__ import annotations

import sqlite3


def lookup_active_recommendation_label(
    conn: sqlite3.Connection, *, ticker: str, starting_equity: float,
) -> str | None:
    """Return the suggested hypothesis label for ``ticker`` from the latest
    completed pipeline run's active hypothesis match, or ``None`` if there
    is no run / no candidate / no match.
    """
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )
    from swing.web.view_models.dashboard import (
        build_recommendation_progress,
        latest_evaluation_run_id,
    )

    eval_id = latest_evaluation_run_id(conn)
    if eval_id is None:
        return None
    candidates = fetch_candidates_for_run(conn, eval_id)
    cand = next((c for c in candidates if c.ticker == ticker), None)
    if cand is None:
        return None

    registry = list_hypotheses(conn)
    matches = match_candidate_to_hypotheses(cand, registry=registry)
    if not matches:
        return None

    _, progress_summaries = build_recommendation_progress(
        conn, registry, starting_equity=starting_equity,
    )
    prioritized = prioritize_recommendations(
        matches, registry=registry, progress=progress_summaries,
    )
    if not prioritized:
        return None
    return prioritized[0].suggested_label_descriptive
