"""``pattern_evaluations`` repo — Phase 13 T2.SB1 task T-A.1.1b.

Minimum CRUD (insert / get_by_id / list) per plan §G.1 T-A.1.1b acceptance.
Caller-tx contract (NO ``conn.commit()`` in repo) + NO ``INSERT OR REPLACE``
per plan §A.15 LOCK.

One-verdict-per-(pipeline_run_id, ticker, pattern_class) uniqueness is
enforced at the SQL layer via ``idx_pattern_evaluations_run_ticker_class``
UNIQUE index. SELECT-then-UPDATE-or-INSERT upsert semantics deferred to
T2.SB3 + T2.SB4 detector-driven sub-bundles (per Codex R1 M#1 closure +
spec §3.3 + plan §A.15 LOCK).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import PatternEvaluation

_EVALUATION_COLUMNS: tuple[str, ...] = (
    "id",
    "pipeline_run_id",
    "ticker",
    "pattern_class",
    "detector_version",
    "geometric_score",
    "geometric_score_json",
    "composite_score",
    "structural_evidence_json",
    "feature_distribution_log_json",
    "window_start_date",
    "window_end_date",
    "created_at",
    "template_match_score",
    "template_match_nearest_exemplar_ids_json",
)

_SELECT_COLUMNS_SQL: str = ", ".join(_EVALUATION_COLUMNS)


def _row_to_evaluation(row: tuple) -> PatternEvaluation:
    return PatternEvaluation(
        id=row[0],
        pipeline_run_id=row[1],
        ticker=row[2],
        pattern_class=row[3],
        detector_version=row[4],
        geometric_score=row[5],
        geometric_score_json=row[6],
        composite_score=row[7],
        structural_evidence_json=row[8],
        feature_distribution_log_json=row[9],
        window_start_date=row[10],
        window_end_date=row[11],
        created_at=row[12],
        template_match_score=row[13],
        template_match_nearest_exemplar_ids_json=row[14],
    )


def insert_evaluation(
    conn: sqlite3.Connection, evaluation: PatternEvaluation,
) -> int:
    """Insert one ``pattern_evaluations`` row; return new id.

    Caller-tx contract: NO ``conn.commit()``. The unique index on
    (pipeline_run_id, ticker, pattern_class) will raise ``sqlite3.IntegrityError``
    on duplicate per-run-per-ticker-per-class insert; caller decides UPSERT
    semantics (SELECT-then-UPDATE-or-INSERT) per detector dispatch.
    """
    cur = conn.execute(
        """
        INSERT INTO pattern_evaluations
            (pipeline_run_id, ticker, pattern_class, detector_version,
             geometric_score, geometric_score_json, composite_score,
             structural_evidence_json, feature_distribution_log_json,
             window_start_date, window_end_date, created_at,
             template_match_score, template_match_nearest_exemplar_ids_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evaluation.pipeline_run_id,
            evaluation.ticker,
            evaluation.pattern_class,
            evaluation.detector_version,
            evaluation.geometric_score,
            evaluation.geometric_score_json,
            evaluation.composite_score,
            evaluation.structural_evidence_json,
            evaluation.feature_distribution_log_json,
            evaluation.window_start_date,
            evaluation.window_end_date,
            evaluation.created_at,
            evaluation.template_match_score,
            evaluation.template_match_nearest_exemplar_ids_json,
        ),
    )
    return int(cur.lastrowid)


def get_evaluation_by_id(
    conn: sqlite3.Connection, evaluation_id: int,
) -> PatternEvaluation | None:
    """Return the evaluation with matching id, or None."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS_SQL} FROM pattern_evaluations WHERE id = ?",
        (evaluation_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_evaluation(row)


def list_evaluations(
    conn: sqlite3.Connection,
    *,
    pipeline_run_id: int | None = None,
    ticker: str | None = None,
    pattern_class: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[PatternEvaluation]:
    """List evaluations filtered by optional pipeline_run_id / ticker /
    pattern_class. Ordered by (id ASC) for deterministic pagination.
    """
    where_clauses: list[str] = []
    params: list[object] = []
    if pipeline_run_id is not None:
        where_clauses.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
    if ticker is not None:
        where_clauses.append("ticker = ?")
        params.append(ticker)
    if pattern_class is not None:
        where_clauses.append("pattern_class = ?")
        params.append(pattern_class)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS_SQL} FROM pattern_evaluations"
        f"{where_sql} ORDER BY id ASC{limit_sql}",
        tuple(params),
    ).fetchall()
    return [_row_to_evaluation(r) for r in rows]
