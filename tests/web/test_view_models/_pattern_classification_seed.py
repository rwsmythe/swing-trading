"""Shared seed helper for Phase 4 pattern-classification VM tests.

Tasks 4.3, 4.4, 4.6 (compounding-confound), and 4.7 (route-level
rendering) all need to insert: an evaluation_runs row, a pipeline_runs
row with `state='complete'` linked via `evaluation_run_id`, an active
watchlist entry, and a `pipeline_pattern_classifications` row keyed on
the pipeline_run_id. Centralizing here avoids drift across the four
test files. Module is leading-underscored so pytest does not collect it
as a test module.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from swing.data.db import connect, ensure_schema
from swing.data.repos.pattern_classifications import insert_classification
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult


def seed_pipeline_with_classification(
    db_path: Path,
    *,
    ticker: str,
    pattern: str,
    confidence: float,
    components: dict | None = None,
) -> tuple[int, int]:
    """Seed a complete-pipeline + classification scaffold.

    Inserts: one evaluation_runs row, one pipeline_runs row with
    `state='complete'` and `evaluation_run_id` pointing at the eval, one
    active `watchlist` row for `ticker`, and one
    `pipeline_pattern_classifications` row keyed on `(pipeline_run_id,
    ticker)` with the given pattern + confidence.

    Returns `(pipeline_run_id, evaluation_run_id)`.

    The watchlist row is seeded with realistic numbers (entry_target=110,
    last_close=100) so build_watchlist's price-snapshot path doesn't
    short-circuit. Tests that need additional rows (e.g., Task 4.6's
    second ticker for sort-neutrality compounding-confound) insert them
    separately after this helper returns.
    """
    conn = ensure_schema(db_path)
    try:
        conn.execute(
            "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
            "action_session_date, finviz_csv_path, tickers_evaluated, "
            "aplus_count, watch_count, skip_count, excluded_count, "
            "error_count) VALUES ('2026-04-26T00:00:00','2026-04-25',"
            "'2026-04-26', NULL, 1,1,0,0,0,0)"
        )
        eval_id = int(conn.execute(
            "SELECT id FROM evaluation_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token, "
            "evaluation_run_id) VALUES ('2026-04-26T00:00:00', "
            "'2026-04-26T00:30:00','manual','2026-04-25','2026-04-26',"
            "'complete','t', ?)",
            (eval_id,),
        )
        run_id = int(conn.execute(
            "SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) "
            "VALUES (?, '2026-04-01','2026-04-26','watch',1,0,"
            "'2026-04-25',110.0,100.0)",
            (ticker,),
        )
        with conn:
            insert_classification(
                conn, pipeline_run_id=run_id, ticker=ticker,
                result=FlagClassificationResult(
                    detected=(pattern == "flag"),
                    confidence=confidence, pattern=pattern,
                    pole_start_date=date(2026, 4, 1),
                    pole_end_date=date(2026, 4, 10),
                    flag_start_date=date(2026, 4, 11),
                    flag_end_date=date(2026, 4, 18),
                    pole_high=120.0, flag_low=110.0, pivot=119.5,
                    components=components or {"pole_gain": 0.45},
                ),
                computed_at="2026-04-26T00:00:00",
            )
        conn.commit()
    finally:
        conn.close()
    return run_id, eval_id


def add_active_watchlist_row(
    db_path: Path,
    *,
    ticker: str,
    entry_target: float = 110.0,
    last_close: float = 100.0,
) -> None:
    """Add another active watchlist row WITHOUT a classification. Used by
    Task 4.6's compounding-confound test (two tickers, only one
    classified)."""
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, "
            "last_qualified_date, status, qualification_count, "
            "not_qualified_streak, last_data_asof_date, entry_target, "
            "last_close) VALUES (?, '2026-04-01','2026-04-26','watch',"
            "1,0,'2026-04-25',?,?)",
            (ticker, entry_target, last_close),
        )
        conn.commit()
    finally:
        conn.close()


def delete_all_classifications(db_path: Path) -> None:
    """Wipe pipeline_pattern_classifications. Used by compounding-confound
    tests to verify pattern_tags becomes empty without changing sort
    order."""
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM pipeline_pattern_classifications")
        conn.commit()
    finally:
        conn.close()
