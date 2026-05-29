"""Append-only repo for ``pattern_detection_events`` (migration 0022).

APPEND-ONLY (spec section 2.3 + OQ-10 LOCK): this module defines NO
``update_*`` / ``delete_*`` functions. Caller-tx contract: NO ``conn.commit()``.
Mirrors ``swing/data/repos/pattern_evaluations.py`` (the append-only +
caller-tx exemplar).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import PatternDetectionEvent

_COLS = (
    "detection_id, ticker, detection_date, data_asof_date, pattern_class, "
    "structural_anchors_json, composite_score, detector_version, "
    "finviz_screen_state, source, per_pattern_metadata_json, "
    "pipeline_run_id, chart_render_id, created_at"
)


def _row_to_detection_event(row: tuple) -> PatternDetectionEvent:
    return PatternDetectionEvent(
        detection_id=row[0],
        ticker=row[1],
        detection_date=row[2],
        data_asof_date=row[3],
        pattern_class=row[4],
        structural_anchors_json=row[5],
        composite_score=row[6],
        detector_version=row[7],
        finviz_screen_state=row[8],
        source=row[9],
        per_pattern_metadata_json=row[10],
        pipeline_run_id=row[11],
        chart_render_id=row[12],
        created_at=row[13],
    )


def insert_detection_event(conn: sqlite3.Connection, event: PatternDetectionEvent) -> int:
    """INSERT one row; return detection_id. Caller-tx (NO commit).

    UNIQUE(source, ticker, detection_date, pattern_class) raises
    sqlite3.IntegrityError on duplicate; the caller (detect step) does
    SELECT-then-skip idempotency (mirrors the existing _step_pattern_detect
    existing-key pattern).
    """
    cur = conn.execute(
        """
        INSERT INTO pattern_detection_events
            (ticker, detection_date, data_asof_date, pattern_class,
             structural_anchors_json, composite_score, detector_version,
             finviz_screen_state, source, per_pattern_metadata_json,
             pipeline_run_id, chart_render_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.ticker, event.detection_date, event.data_asof_date,
            event.pattern_class, event.structural_anchors_json,
            event.composite_score, event.detector_version,
            event.finviz_screen_state, event.source,
            event.per_pattern_metadata_json, event.pipeline_run_id,
            event.chart_render_id, event.created_at,
        ),
    )
    return int(cur.lastrowid)


def get_detection_event_by_id(
    conn: sqlite3.Connection, detection_id: int,
) -> PatternDetectionEvent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM pattern_detection_events WHERE detection_id = ?",
        (detection_id,),
    ).fetchone()
    return _row_to_detection_event(row) if row is not None else None


def list_detection_events(
    conn: sqlite3.Connection, *, ticker: str | None = None,
    pattern_class: str | None = None, source: str | None = None,
    pipeline_run_id: int | None = None, limit: int | None = None,
    offset: int = 0,
) -> list[PatternDetectionEvent]:
    clauses, params = [], []
    if ticker is not None:
        clauses.append("ticker = ?")
        params.append(ticker)
    if pattern_class is not None:
        clauses.append("pattern_class = ?")
        params.append(pattern_class)
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if pipeline_run_id is not None:
        clauses.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT {_COLS} FROM pattern_detection_events{where} "
        "ORDER BY detection_date DESC, detection_id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    return [_row_to_detection_event(r) for r in conn.execute(sql, params)]


_OPEN_STATUSES = ("pending", "triggered_open")


def list_observable_detections(
    conn: sqlite3.Connection, *, source: str = "pipeline",
    observation_date: str,
) -> list[PatternDetectionEvent]:
    """Detections OBSERVABLE for ``observation_date``:

      - detection.data_asof_date < observation_date  (STRICT on the data
        cutoff; the forward-walk starts the first COMPLETED session AFTER the
        detector's DATA CUTOFF -- includes the first tradable session, excludes
        same-run detections whose cutoff == observation_date), AND
      - the MOST-RECENT forward observation AS OF ``observation_date`` has a
        status in the OPEN set ('pending','triggered_open') OR there is NO
        observation yet.

    Window function (ROW_NUMBER() OVER PARTITION BY detection_id ORDER BY
    observation_date DESC) finds the latest status per detection. The ``latest``
    CTE is date-bounded (``observation_date <= ?``) so a FUTURE observation
    (from a replay/backfill/rerun) never drives the latest-status decision --
    latest-status is determined AS OF ``observation_date`` (date-anchored
    forward-walk model).
    """
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    sql = f"""
        WITH latest AS (
            SELECT detection_id, status,
                   ROW_NUMBER() OVER (
                       PARTITION BY detection_id
                       ORDER BY observation_date DESC, observation_id DESC
                   ) AS rn
            FROM pattern_forward_observations
            WHERE observation_date <= ?
        )
        SELECT {", ".join("d." + c for c in _COLS.split(", "))}
        FROM pattern_detection_events d
        LEFT JOIN latest l
            ON l.detection_id = d.detection_id AND l.rn = 1
        WHERE d.source = ?
          AND d.data_asof_date < ?
          AND (l.status IS NULL OR l.status IN ({placeholders}))
        ORDER BY d.detection_id
    """
    params = [observation_date, source, observation_date, *_OPEN_STATUSES]
    return [_row_to_detection_event(r) for r in conn.execute(sql, params)]
