"""Append-only repo for ``pattern_forward_observations`` (migration 0022).

APPEND-ONLY (spec section 2.3 + OQ-10 LOCK): NO ``update_*`` / ``delete_*``.
Caller-tx: NO ``conn.commit()``.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from swing.data.models import PatternForwardObservation
from swing.data.ohlcv_finiteness import is_finite_ohlc

_COLS = (
    "observation_id, detection_id, observation_date, ohlc_today_json, "
    "status, status_change_event, sessions_since_detection, created_at"
)

# The 4 OHLC keys the WRITE barrier gates (volume EXEMPT -- Arc-8: legit
# volume-less bars exist; finiteness is OHLC-only, matching is_finite_ohlc's
# "callers pass only the OHLC values they wish to gate").
_OHLC_KEYS = ("open", "high", "low", "close")


def _assert_finite_ohlc_for_write(ohlc_today_json: str, *, detection_id: int) -> None:
    """WRITE-BARRIER (18-B.1 / commissioning-brief section 6.6 FIX 2).

    Fail-loud finiteness guard on the ONLY INSERT path into the immutable,
    append-only ``pattern_forward_observations`` substrate: RAISE if any of the
    4 OHLC values is missing / None / non-numeric / non-finite (NaN / +/-inf),
    BEFORE the row is written, so non-finite OHLC never reaches durable storage
    via this path going forward. ``ohlc_today_json`` is plain ``TEXT NOT NULL``
    (migration 0022) -- there is NO schema CHECK enforcing finiteness, so this
    application-layer barrier is the structural prevention.

    Mirrors the ``build_ohlc_today_json`` construction-barrier (Arc-8 / 18-A) at
    this SECOND write path via the ONE shared predicate
    ``swing.data.ohlcv_finiteness.is_finite_ohlc`` (C1 -- no re-implementation of
    NaN/inf detection). The per-key None/missing/non-numeric guard runs BEFORE
    the predicate because ``is_finite_ohlc`` calls ``math.isfinite`` (raises
    ``TypeError`` on ``None``).

    WRITE-PATH ONLY (CHARC carve-out): this is deliberately NOT on
    ``PatternForwardObservation.__post_init__`` -- that fires on the READ mapper
    ``_row_to_observation`` and would regress reads of the accepted historical
    non-finite rows (the immutable 06-10 cohort). Volume is EXEMPT.
    """
    try:
        bar = json.loads(ohlc_today_json)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"ohlc_today_json is not valid JSON (detection_id={detection_id}): "
            f"{exc}"
        ) from exc
    if not isinstance(bar, dict):
        raise ValueError(
            f"ohlc_today_json must decode to an object, got {type(bar).__name__} "
            f"(detection_id={detection_id})"
        )
    values: list[float] = []
    for key in _OHLC_KEYS:
        val = bar.get(key)
        # bool is an int subclass but never a valid OHLC value -- reject it so a
        # JSON `true`/`false` cannot sneak past the numeric check.
        if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(
                f"ohlc_today_json OHLC field {key!r} is missing / None / "
                f"non-numeric (got {val!r}; detection_id={detection_id})"
            )
        values.append(float(val))
    if not is_finite_ohlc(*values):
        o, h, low_, c = values
        raise ValueError(
            f"ohlc_today_json refuses a non-finite OHLC bar "
            f"(open={o!r}, high={h!r}, low={low_!r}, close={c!r}; "
            f"detection_id={detection_id})"
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

    WRITE-BARRIER (18-B.1): raises ValueError on a non-finite / malformed OHLC
    ``ohlc_today_json`` BEFORE the INSERT, so non-finite OHLC never enters this
    immutable, append-only substrate via this (the SOLE) insert path.
    """
    _assert_finite_ohlc_for_write(
        observation.ohlc_today_json, detection_id=observation.detection_id
    )
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
