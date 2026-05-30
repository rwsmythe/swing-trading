"""``chart_renders`` repo — Phase 13 T2.SB1 task T-A.1.1b.

Minimum CRUD (insert / get_by_id / list) per plan §G.1 T-A.1.1b acceptance.
Caller-tx contract (NO ``conn.commit()`` in repo) + NO ``INSERT OR REPLACE``
per plan §A.15 LOCK (cache invalidation uses DELETE-then-INSERT atomic
refresh wrapped in caller's ``BEGIN IMMEDIATE`` per §C.2 / §A.15).

Cache uniqueness is enforced via 3 partial unique indexes per spec §3.2:
``idx_chart_renders_run_bound`` + ``idx_chart_renders_position_detail`` +
``idx_chart_renders_theme2_annotated`` (SQLite NULL-distinct defense per
Codex R1 M#3 + R2 M#5 closure).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import ChartRender

_CHART_COLUMNS: tuple[str, ...] = (
    "id",
    "ticker",
    "surface",
    "pipeline_run_id",
    "pattern_class",
    "chart_svg_bytes",
    "source_data_hash",
    "rendered_at",
    "data_asof_date",
)

_SELECT_COLUMNS_SQL: str = ", ".join(_CHART_COLUMNS)


def _row_to_chart_render(row: tuple) -> ChartRender:
    return ChartRender(
        id=row[0],
        ticker=row[1],
        surface=row[2],
        pipeline_run_id=row[3],
        pattern_class=row[4],
        chart_svg_bytes=row[5],
        source_data_hash=row[6],
        rendered_at=row[7],
        data_asof_date=row[8],
    )


def insert_chart_render(
    conn: sqlite3.Connection, chart_render: ChartRender,
) -> int:
    """Insert one ``chart_renders`` row; return new id.

    Caller-tx contract: NO ``conn.commit()``. Partial unique indexes
    enforce one cache row per surface-class cache key; caller decides
    DELETE-then-INSERT atomic refresh per §C.2 cache invalidation pattern.
    """
    cur = conn.execute(
        """
        INSERT INTO chart_renders
            (ticker, surface, pipeline_run_id, pattern_class,
             chart_svg_bytes, source_data_hash, rendered_at, data_asof_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chart_render.ticker,
            chart_render.surface,
            chart_render.pipeline_run_id,
            chart_render.pattern_class,
            chart_render.chart_svg_bytes,
            chart_render.source_data_hash,
            chart_render.rendered_at,
            chart_render.data_asof_date,
        ),
    )
    return int(cur.lastrowid)


def get_chart_render_by_id(
    conn: sqlite3.Connection, chart_render_id: int,
) -> ChartRender | None:
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS_SQL} FROM chart_renders WHERE id = ?",
        (chart_render_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_chart_render(row)


def list_chart_renders(
    conn: sqlite3.Connection,
    *,
    ticker: str | None = None,
    surface: str | None = None,
    pipeline_run_id: int | None = None,
    pattern_class: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ChartRender]:
    """List chart_renders filtered by optional ticker / surface /
    pipeline_run_id / pattern_class. Ordered by (id ASC) for deterministic
    pagination.
    """
    where_clauses: list[str] = []
    params: list[object] = []
    if ticker is not None:
        where_clauses.append("ticker = ?")
        params.append(ticker)
    if surface is not None:
        where_clauses.append("surface = ?")
        params.append(surface)
    if pipeline_run_id is not None:
        where_clauses.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
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
        f"SELECT {_SELECT_COLUMNS_SQL} FROM chart_renders"
        f"{where_sql} ORDER BY id ASC{limit_sql}",
        tuple(params),
    ).fetchall()
    return [_row_to_chart_render(r) for r in rows]


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6 T-A.6.2 — cache-consumer helpers (spec §C.2 LOCK).
# ---------------------------------------------------------------------------


def get_cached_chart_svg(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    surface: str,
    pipeline_run_id: int | None = None,
    pattern_class: str | None = None,
    min_data_asof_date: str | None = None,
) -> bytes | None:
    """Return the cached SVG bytes for the canonical chart cache key, or None.

    Per spec §C.2 cache key shape LOCK:
      - Run-bound surfaces (``watchlist_row``, ``ticker_detail``,
        ``market_weather``): key on ``(ticker, surface, pipeline_run_id)``.
      - ``position_detail`` surface: key on ``(ticker, surface)`` with
        ``pipeline_run_id IS NULL``.
      - ``theme2_annotated`` surface: key on
        ``(ticker, surface, pipeline_run_id, pattern_class)``.

    Per spec §A.13 session-anchor read/write predicate alignment LOCK:
    ``min_data_asof_date`` is the staleness predicate; pass
    ``last_completed_session(now()).isoformat()`` (backward-looking; same
    function the writer uses) so the read returns rows whose
    ``data_asof_date >= min_data_asof_date``. If ``min_data_asof_date`` is
    None, no staleness filter applies (return the most-recent row
    regardless of asof). Discriminating round-trip test pattern lives at
    ``tests/data/test_chart_renders_repo.py`` (Phase 8 ``cfacbc5``
    precedent).
    """
    where_clauses = ["ticker = ?", "surface = ?"]
    params: list[object] = [ticker, surface]

    if pipeline_run_id is None:
        where_clauses.append("pipeline_run_id IS NULL")
    else:
        where_clauses.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)

    if pattern_class is None:
        where_clauses.append("pattern_class IS NULL")
    else:
        where_clauses.append("pattern_class = ?")
        params.append(pattern_class)

    if min_data_asof_date is not None:
        where_clauses.append("data_asof_date >= ?")
        params.append(min_data_asof_date)

    sql = (
        "SELECT chart_svg_bytes FROM chart_renders WHERE "
        + " AND ".join(where_clauses)
        + " ORDER BY id DESC LIMIT 1"
    )
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        return None
    return bytes(row[0]) if row[0] is not None else None


def refresh_chart_render(
    conn: sqlite3.Connection, chart_render: ChartRender,
) -> int:
    """DELETE-then-INSERT atomic refresh of one cache row.

    Per §A.15 LOCK (no ``INSERT OR REPLACE`` on audit-trail tables) +
    §C.2 cache invalidation pattern (atomic DELETE-then-INSERT wrapped in
    caller's ``BEGIN IMMEDIATE``).

    Caller-tx contract: the function does NOT call ``conn.commit()``; the
    caller is responsible for transaction discipline (typically
    ``BEGIN IMMEDIATE`` + ``COMMIT`` / ``ROLLBACK``).

    The DELETE key shape mirrors the partial unique indexes:
      - ``theme2_annotated``:
        ``(ticker, surface, pipeline_run_id, pattern_class)``.
      - run-bound non-theme2: ``(ticker, surface, pipeline_run_id)`` with
        ``pipeline_run_id IS NOT NULL`` predicate.
      - ``position_detail``: ``(ticker, surface)`` with
        ``pipeline_run_id IS NULL`` predicate.
    """
    if chart_render.surface == "theme2_annotated":
        conn.execute(
            "DELETE FROM chart_renders WHERE ticker = ? AND surface = ? "
            "AND pipeline_run_id = ? AND pattern_class = ?",
            (
                chart_render.ticker,
                chart_render.surface,
                chart_render.pipeline_run_id,
                chart_render.pattern_class,
            ),
        )
    elif chart_render.surface == "position_detail":
        conn.execute(
            "DELETE FROM chart_renders WHERE ticker = ? AND surface = ? "
            "AND pipeline_run_id IS NULL",
            (chart_render.ticker, chart_render.surface),
        )
    else:
        # Run-bound: watchlist_row / ticker_detail / market_weather.
        conn.execute(
            "DELETE FROM chart_renders WHERE ticker = ? AND surface = ? "
            "AND pipeline_run_id = ?",
            (
                chart_render.ticker,
                chart_render.surface,
                chart_render.pipeline_run_id,
            ),
        )
    return insert_chart_render(conn, chart_render)
