"""Append-only repo for ``pattern_forward_observations`` (migration 0022).

APPEND-ONLY (spec section 2.3 + OQ-10 LOCK): NO ``update_*`` / ``delete_*``.
Caller-tx: NO ``conn.commit()``.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from swing.data.models import PatternForwardObservation

_COLS = (
    "observation_id, detection_id, observation_date, ohlc_today_json, "
    "status, status_change_event, sessions_since_detection, created_at"
)


def _row_to_observation(row: tuple) -> PatternForwardObservation:
    return PatternForwardObservation(
        observation_id=row[0],
        detection_id=row[1],
        observation_date=row[2],
        ohlc_today_json=row[3],
        status=row[4],
        status_change_event=row[5],
        sessions_since_detection=row[6],
        created_at=row[7],
    )


def insert_observation(conn: sqlite3.Connection, observation: PatternForwardObservation) -> int:
    """INSERT one row; return observation_id. Caller-tx (NO commit).
    UNIQUE(detection_id, observation_date) raises sqlite3.IntegrityError on
    duplicate-same-day; the observe step pre-checks for idempotency.
    """
    cur = conn.execute(
        """
        INSERT INTO pattern_forward_observations
            (detection_id, observation_date, ohlc_today_json, status,
             status_change_event, sessions_since_detection, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation.detection_id, observation.observation_date,
            observation.ohlc_today_json, observation.status,
            observation.status_change_event,
            observation.sessions_since_detection, observation.created_at,
        ),
    )
    return int(cur.lastrowid)


def get_observations_for_detection(
    conn: sqlite3.Connection, detection_id: int,
) -> list[PatternForwardObservation]:
    """The full chain, ORDER BY observation_date ASC."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM pattern_forward_observations "
        "WHERE detection_id = ? ORDER BY observation_date ASC, observation_id ASC",
        (detection_id,),
    )
    return [_row_to_observation(r) for r in rows]


def get_latest_observation_for_detection(
    conn: sqlite3.Connection, detection_id: int,
) -> PatternForwardObservation | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM pattern_forward_observations "
        "WHERE detection_id = ? "
        "ORDER BY observation_date DESC, observation_id DESC LIMIT 1",
        (detection_id,),
    ).fetchone()
    return _row_to_observation(row) if row is not None else None


def get_latest_observations_for_detections(
    conn: sqlite3.Connection, detection_ids: Sequence[int],
) -> dict[int, PatternForwardObservation]:
    """Batch latest-status read. Empty input short-circuits to {} BEFORE SQL
    (avoids invalid ``IN ()``). Dynamic '?' expansion for the IN clause
    (sqlite3 cannot bind a list to a single :name placeholder).
    """
    ids = list(detection_ids)
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    sql = f"""
        WITH ranked AS (
            SELECT {_COLS},
                   ROW_NUMBER() OVER (
                       PARTITION BY detection_id
                       ORDER BY observation_date DESC, observation_id DESC
                   ) AS rn
            FROM pattern_forward_observations
            WHERE detection_id IN ({placeholders})
        )
        SELECT {_COLS} FROM ranked WHERE rn = 1
    """
    out: dict[int, PatternForwardObservation] = {}
    for row in conn.execute(sql, ids):
        obs = _row_to_observation(row)
        out[obs.detection_id] = obs
    return out
