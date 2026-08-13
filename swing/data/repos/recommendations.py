"""Daily recommendations repo. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import DailyRecommendation


def upsert_recommendation(conn: sqlite3.Connection, r: DailyRecommendation) -> int:
    """Idempotent - re-running pipeline for same session updates in place via UNIQUE constraint."""
    cur = conn.execute(
        """
        INSERT INTO daily_recommendations
            (evaluation_run_id, data_asof_date, action_session_date, ticker,
             recommendation, action_text, entry_target, stop_target, shares,
             risk_dollars, risk_pct, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(action_session_date, ticker, recommendation) DO UPDATE SET
            evaluation_run_id = excluded.evaluation_run_id,
            data_asof_date = excluded.data_asof_date,
            action_text = excluded.action_text,
            entry_target = excluded.entry_target,
            stop_target = excluded.stop_target,
            shares = excluded.shares,
            risk_dollars = excluded.risk_dollars,
            risk_pct = excluded.risk_pct,
            rationale = excluded.rationale
        """,
        (r.evaluation_run_id, r.data_asof_date, r.action_session_date, r.ticker,
         r.recommendation, r.action_text, r.entry_target, r.stop_target, r.shares,
         r.risk_dollars, r.risk_pct, r.rationale),
    )
    return int(cur.lastrowid)


def list_for_session(
    conn: sqlite3.Connection, action_session_date: str,
    *, evaluation_run_id: int | None = None,
) -> list[DailyRecommendation]:
    """Recommendations for the session.

    When `evaluation_run_id` is provided, the result is additionally scoped
    to that eval — the dashboard passes `pipeline_runs.evaluation_run_id`
    here so today_decisions binds to the same eval the chart-scope resolver
    uses (Tranche C T4, fixes Bug 7's mixed-anchor inconsistency between
    today_decisions and chart-scope's A+ set). When the FK is None (legacy
    pipeline_runs row pre-migration-0006), callers omit this argument and
    fall back to the pre-T4 date-only behavior.
    """
    if evaluation_run_id is not None:
        rows = conn.execute(
            """
            SELECT id, evaluation_run_id, data_asof_date, action_session_date,
                   ticker, recommendation, action_text, entry_target,
                   stop_target, shares, risk_dollars, risk_pct, rationale
            FROM daily_recommendations
            WHERE action_session_date = ? AND evaluation_run_id = ?
            ORDER BY recommendation, ticker
            """,
            (action_session_date, evaluation_run_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, evaluation_run_id, data_asof_date, action_session_date,
                   ticker, recommendation, action_text, entry_target,
                   stop_target, shares, risk_dollars, risk_pct, rationale
            FROM daily_recommendations WHERE action_session_date = ?
            ORDER BY recommendation, ticker
            """,
            (action_session_date,),
        ).fetchall()
    return [_row(r) for r in rows]


def _row(r: tuple) -> DailyRecommendation:
    return DailyRecommendation(
        id=r[0], evaluation_run_id=r[1], data_asof_date=r[2],
        action_session_date=r[3], ticker=r[4], recommendation=r[5],
        action_text=r[6], entry_target=r[7], stop_target=r[8], shares=r[9],
        risk_dollars=r[10], risk_pct=r[11], rationale=r[12],
    )


# ---------------------------------------------------------------------------
# Demand C readers. Every one loads BY ID or by an EQUALITY on ids -- never a
# predicate, ordering or LIMIT over one of this table's unconstrained TEXT
# timestamp columns, because a lexical SQL comparison excludes a malformed row
# before any validator can see it.
# ---------------------------------------------------------------------------

REQUIRED_RECOMMENDATION_KIND: str = "today_decision"


def get_daily_recommendation_by_id(
    conn: sqlite3.Connection, recommendation_id: int,
) -> DailyRecommendation | None:
    """One row by primary key, or None."""
    row = conn.execute(
        """
        SELECT id, evaluation_run_id, data_asof_date, action_session_date,
               ticker, recommendation, action_text, entry_target,
               stop_target, shares, risk_dollars, risk_pct, rationale
        FROM daily_recommendations WHERE id = ?
        """,
        (recommendation_id,),
    ).fetchone()
    return _row(row) if row else None


def list_today_decisions_for_run_ticker(
    conn: sqlite3.Connection, *, evaluation_run_id: int, ticker: str,
) -> list[DailyRecommendation]:
    """ALL same-run same-ticker ``today_decision`` rows -- never ``fetchone``.

    The unique index is ``ux_daily_recs_action_session_date_ticker_rec`` on
    ``(action_session_date, ticker, recommendation)``, NOT on
    ``(evaluation_run_id, ticker, recommendation)``, and
    ``upsert_recommendation``'s ``DO UPDATE SET`` REWRITES
    ``evaluation_run_id`` in place on conflict. So two rows with different
    action sessions can legitimately carry the same run id, and a
    ``fetchone()`` would let SQLite's row order pick the citation. The caller
    counts and REFUSES on zero or two-or-more.
    """
    rows = conn.execute(
        """
        SELECT id, evaluation_run_id, data_asof_date, action_session_date,
               ticker, recommendation, action_text, entry_target,
               stop_target, shares, risk_dollars, risk_pct, rationale
        FROM daily_recommendations
        WHERE evaluation_run_id = ? AND ticker = ? AND recommendation = ?
        ORDER BY id ASC
        """,
        (evaluation_run_id, ticker, REQUIRED_RECOMMENDATION_KIND),
    ).fetchall()
    return [_row(r) for r in rows]


def snapshot_recommendation_row(
    conn: sqlite3.Connection, recommendation_id: int,
) -> dict[str, object] | None:
    """The WHOLE row as a dict, column set DERIVED from ``PRAGMA table_info``.

    NEVER hand-listed. The cited row is MUTABLE IN PLACE -- every column in
    ``upsert_recommendation``'s ``DO UPDATE SET`` clause can move underneath
    the citation, including ``evaluation_run_id`` -- so the freeze has to be
    total. A hand-list is a manifest that rots on the next ``ALTER TABLE``,
    and the first draft of this snapshot silently omitted ``action_text``,
    ``risk_dollars`` and ``risk_pct`` while calling itself "the full row".
    Same reasoning as ``_assert_real_column_name``'s PRAGMA derivation.
    """
    columns = [
        r[1] for r in conn.execute(
            "PRAGMA table_info(daily_recommendations)").fetchall()
    ]
    row = conn.execute(
        f"SELECT {', '.join(columns)} FROM daily_recommendations WHERE id = ?",
        (recommendation_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(columns, row, strict=True))
