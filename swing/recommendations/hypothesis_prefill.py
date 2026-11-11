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
from dataclasses import dataclass

# Arc 22-B RULING R1-3-SURFACES item 2: the prefill DEGRADES on both
# consuming surfaces (CLI `swing trade entry`, the web entry-form GET) --
# a bookkeeping transient must never refuse a REAL TRADE (R1-1's
# asymmetry). The suggestion is skipped and the entry PROCEEDS; the
# operator sees this exact ASCII line (the CLI prints it; the web form
# renders it beside the field). Shared here so both surfaces render the
# identical ruled text.
PREFILL_UNAVAILABLE_TEXT = (
    "hypothesis suggestion unavailable: cohort read raced an intent write; "
    "pass --hypothesis or re-run"
)

# D102/D104 (sg-label arc, N = 5 RULED by CHARC and RD): how many of a
# ticker's newest candidates rows count as "recent" for a watch fire. ONE
# constant, read by the entry form's decision-night offer and by the
# watch-fire relabel's last-fire walk
# (`swing/trades/cohort_provenance_correction.py`), so the two paths cannot
# disagree about the window. The reason is RD's, not a measurement: a fill
# more than five of the ticker's rows after its fire is a resting order
# older than a week of briefings, and it stops counting as that fire.
WATCH_FIRE_WINDOW_ROWS = 5


@dataclass(frozen=True)
class DecisionNight:
    """One night the entry form offers as the trade's DECISION night (D102).

    ``label`` is the matcher's suggestion for that night's candidate row
    against the CURRENT registry (accepted limitation 1: a suggestion the
    operator confirms, never evidence), or ``None`` when nothing matched.
    """

    candidate_id: int
    evaluation_run_id: int
    action_session_date: str
    data_asof_date: str
    bucket: str
    label: str | None


def label_for_candidate(cand, *, registry, progress) -> str | None:
    """THE one ``include_baseline=True`` prefill call site (D102 T2.1).

    The governance tripwire
    (``tests/integration/test_include_baseline_inventory_guard.py``) pins
    the opt-in call sites by AST census, so the per-night lister and the
    latest-night lookup both reach THIS function instead of adding a site.

    ``progress`` is a zero-argument callable returning the progress
    summaries, called only when the matcher returned something -- so the
    expensive cohort read still runs only after a match, exactly as before
    the extraction, and a caller labelling several nights memoizes it.
    """
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )

    matches = match_candidate_to_hypotheses(cand, registry=registry, include_baseline=True)
    if not matches:
        return None
    prioritized = prioritize_recommendations(
        matches, registry=registry, progress=progress(),
    )
    if not prioritized:
        return None
    return prioritized[0].suggested_label_descriptive


def _progress_reader(conn, registry, *, starting_equity, budget_seconds):
    """A memoized zero-argument progress read for ``label_for_candidate``.
    ``CohortReadRacedError`` propagates from the first call, as before."""
    from swing.web.view_models.dashboard import build_recommendation_progress

    memo: list = []

    def read():
        if not memo:
            _, summaries = build_recommendation_progress(
                conn, registry, starting_equity=starting_equity,
                budget_seconds=budget_seconds,
            )
            memo.append(summaries)
        return memo[0]

    return read


def lookup_active_recommendation_label(
    conn: sqlite3.Connection, *, ticker: str, starting_equity: float,
    budget_seconds: float | None = None,
) -> str | None:
    """Return the suggested hypothesis label for ``ticker`` from the latest
    completed pipeline run's active hypothesis match, or ``None`` if there
    is no run / no candidate / no match.

    22-A2 Task 10: the prefill CONSUMES the cohort read (the prioritizer's
    N) and renders no count, so it renders nothing of it (RD G-T10-2);
    ``budget_seconds`` is threaded to that read (the web entry form passes
    ``WEB_REPLAY_BUDGET_SECONDS``, the CLI none -- CHARC G-T10-1 (2)).

    D102 T2.1: behaviour-identical; the match + prioritize step moved into
    ``label_for_candidate``.
    """
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.web.view_models.dashboard import latest_evaluation_run_id

    eval_id = latest_evaluation_run_id(conn)
    if eval_id is None:
        return None
    candidates = fetch_candidates_for_run(conn, eval_id)
    cand = next((c for c in candidates if c.ticker == ticker), None)
    if cand is None:
        return None

    registry = list_hypotheses(conn)
    return label_for_candidate(
        cand, registry=registry,
        progress=_progress_reader(
            conn, registry, starting_equity=starting_equity,
            budget_seconds=budget_seconds))


# The buckets that carry a pipeline origin (`origin.derive_trade_origin`:
# aplus -> pipeline_aplus, watch -> one of the two watch origins). Any other
# bucket of the latest night is `manual_off_pipeline`, which has no night.
_OFFERED_BUCKETS = frozenset({"aplus", "watch"})


def list_decision_nights(
    conn: sqlite3.Connection, *, ticker: str, starting_equity: float,
    budget_seconds: float | None = None, n: int | None = None,
) -> list[DecisionNight]:
    """The nights the entry form offers for ``ticker`` (D102 T2.1).

    THE WINDOW is the ticker's ``n`` (default ``WATCH_FIRE_WINDOW_ROWS``)
    newest candidates rows in evaluation runs owned by a COMPLETE
    ``pipeline_runs`` row, newest first by the last-word key
    ``(action_session_date, run_ts, candidate_id)`` -- the N the
    watch-fire relabel's walk reads -- THEN restricted to the bucket of the
    ticker's row in the LATEST complete run (F6 = A). That run is read
    through the SAME function ``derive_trade_origin`` reads
    (``origin._latest_complete_evaluation_run_id``), so the origin the entry
    is recorded with, the offered nights' bucket and their labels agree by
    construction. A watch fire followed by an aplus night is an A+ entry
    (RD), so an aplus latest night offers only aplus nights.

    ``[]`` -- the form then behaves exactly as before -- when the latest
    complete run holds no row for the ticker or its bucket is outside
    ``{aplus, watch}`` (the origin is then ``manual_off_pipeline``).

    Registry and progress are read ONCE (memoized). ``CohortReadRacedError``
    from the progress read propagates exactly as it does from the
    latest-night lookup; the caller degrades (GET) or refuses (POST).

    A row whose stored session or run stamp does not parse is LEFT OUT of
    the offer rather than ranked lexically: this is a suggestion list, and
    the POST re-derives the offer through this same function, so a row the
    GET could not rank can never be persisted either.
    """
    from datetime import date, datetime

    from swing.data.repos.candidates import fetch_candidate_by_id
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.trades.origin import _latest_complete_evaluation_run_id

    window = WATCH_FIRE_WINDOW_ROWS if n is None else int(n)
    latest = _latest_complete_evaluation_run_id(conn)
    if latest is None:
        return []
    origin_row = conn.execute(
        "SELECT bucket FROM candidates WHERE evaluation_run_id = ? "
        "AND ticker = ?", (latest, ticker)).fetchone()
    if origin_row is None or origin_row[0] not in _OFFERED_BUCKETS:
        return []
    origin_bucket = str(origin_row[0])

    rows = conn.execute(
        "SELECT c.id, c.evaluation_run_id, c.bucket, er.action_session_date,"
        " er.data_asof_date, er.run_ts FROM candidates c "
        "JOIN evaluation_runs er ON er.id = c.evaluation_run_id "
        "WHERE c.ticker = ? AND EXISTS (SELECT 1 FROM pipeline_runs pr "
        "WHERE pr.evaluation_run_id = c.evaluation_run_id "
        "AND pr.state = 'complete')", (ticker,)).fetchall()
    ranked = []
    for cid, run_id, bucket, session, asof, run_ts in rows:
        try:
            key = (date.fromisoformat(str(session)),
                   datetime.fromisoformat(str(run_ts)), int(cid))
        except (TypeError, ValueError):
            continue
        ranked.append((key, int(cid), int(run_id), str(bucket),
                       str(session), str(asof)))
    ranked.sort(key=lambda r: r[0], reverse=True)
    offered = [r for r in ranked[:window] if r[3] == origin_bucket]
    if not offered:
        return []

    registry = list_hypotheses(conn)
    progress = _progress_reader(
        conn, registry, starting_equity=starting_equity,
        budget_seconds=budget_seconds)
    nights: list[DecisionNight] = []
    for _key, cid, run_id, bucket, session, asof in offered:
        cited = fetch_candidate_by_id(conn, cid)
        label = (None if cited is None else label_for_candidate(
            cited.candidate, registry=registry, progress=progress))
        nights.append(DecisionNight(
            candidate_id=cid, evaluation_run_id=run_id,
            action_session_date=session, data_asof_date=asof,
            bucket=bucket, label=label))
    return nights
