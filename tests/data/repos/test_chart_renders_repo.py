"""Phase 13 T2.SB1 T-A.1.1b — chart_renders repo CRUD discriminating tests.

Per plan §G.1 T-A.1.1b Step 1: 3 discriminating tests covering
(a) insert_row roundtrips through SQL; (b) get_by_id returns inserted row;
(c) list_* paginates correctly. Caller-tx contract verified.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ChartRender
from swing.data.repos import chart_renders as repo


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb1_repo_charts.db"
    return ensure_schema(db_path)


@pytest.fixture
def pipeline_run_id(conn: sqlite3.Connection) -> int:
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2024-02-02T00:00:00.000', 'manual', '2024-02-01', "
            "'2024-02-02', 'complete', 'tok')"
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _make_chart(pipeline_run_id: int | None, **overrides: object) -> ChartRender:
    base = {
        "id": None,
        "ticker": "ABC",
        "surface": "watchlist_row",
        "chart_svg_bytes": b"<svg/>",
        "source_data_hash": "deadbeef",
        "rendered_at": "2024-02-02T00:00:00.000",
        "data_asof_date": "2024-02-01",
        "pipeline_run_id": pipeline_run_id,
        "pattern_class": None,
    }
    base.update(overrides)
    return ChartRender(**base)


def test_insert_chart_render_roundtrips_through_sql(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """insert_chart_render persists; SELECT post-INSERT returns matching values."""
    chart = _make_chart(pipeline_run_id, ticker="XYZ", surface="ticker_detail")
    with conn:
        chart_id = repo.insert_chart_render(conn, chart)
    row = conn.execute(
        "SELECT ticker, surface, pipeline_run_id, pattern_class, "
        "source_data_hash FROM chart_renders WHERE id = ?",
        (chart_id,),
    ).fetchone()
    assert row == ("XYZ", "ticker_detail", pipeline_run_id, None, "deadbeef")


def test_get_chart_render_by_id_returns_inserted_row(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """get_chart_render_by_id reconstructs the dataclass; None on missing.

    Also covers theme2_annotated surface (requires both pattern_class +
    pipeline_run_id non-NULL per spec §3.2 cross-column CHECK).
    """
    chart = _make_chart(
        pipeline_run_id,
        ticker="MMM",
        surface="theme2_annotated",
        pattern_class="vcp",
    )
    with conn:
        chart_id = repo.insert_chart_render(conn, chart)

    fetched = repo.get_chart_render_by_id(conn, chart_id)
    assert fetched is not None
    assert fetched.ticker == "MMM"
    assert fetched.surface == "theme2_annotated"
    assert fetched.pattern_class == "vcp"
    assert fetched.pipeline_run_id == pipeline_run_id
    assert fetched.chart_svg_bytes == b"<svg/>"

    assert repo.get_chart_render_by_id(conn, 999_999) is None


def test_list_chart_renders_paginates_correctly(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """list_chart_renders + filters + pagination work."""
    with conn:
        for i, sfc in enumerate([
            "watchlist_row", "ticker_detail", "watchlist_row",
            "market_weather", "watchlist_row",
        ]):
            chart = _make_chart(
                pipeline_run_id, ticker=f"T{i}", surface=sfc,
            )
            repo.insert_chart_render(conn, chart)

    all_rows = repo.list_chart_renders(conn)
    assert len(all_rows) == 5

    watchlist_rows = repo.list_chart_renders(conn, surface="watchlist_row")
    assert len(watchlist_rows) == 3

    run_rows = repo.list_chart_renders(conn, pipeline_run_id=pipeline_run_id)
    assert len(run_rows) == 5

    first_two = repo.list_chart_renders(conn, limit=2, offset=0)
    assert len(first_two) == 2
    next_two = repo.list_chart_renders(conn, limit=2, offset=2)
    assert next_two[0].id > first_two[1].id


def test_repo_does_not_commit_within_function(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Caller-tx contract: rollback undoes insert."""
    chart = _make_chart(pipeline_run_id, ticker="ROLLED_BACK")
    conn.execute("BEGIN")
    repo.insert_chart_render(conn, chart)
    conn.rollback()
    assert repo.list_chart_renders(conn, ticker="ROLLED_BACK") == []


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6 T-A.6.2 — cache-consumer helper tests (spec §C.2 + §A.13).
# ---------------------------------------------------------------------------


def test_chart_renders_run_bound_cache_one_row_per_ticker_surface_run(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Run-bound surfaces (watchlist_row / ticker_detail / market_weather)
    key on (ticker, surface, pipeline_run_id) per spec §C.2.

    ``refresh_chart_render`` is the canonical DELETE-then-INSERT path;
    calling it twice with the same key must produce ONE row (the second
    writes over the first).
    """
    first = _make_chart(
        pipeline_run_id, ticker="ABC", surface="watchlist_row",
        chart_svg_bytes=b"<svg id=v1/>",
    )
    second = _make_chart(
        pipeline_run_id, ticker="ABC", surface="watchlist_row",
        chart_svg_bytes=b"<svg id=v2/>",
    )
    with conn:
        repo.refresh_chart_render(conn, first)
        repo.refresh_chart_render(conn, second)
    rows = repo.list_chart_renders(
        conn, ticker="ABC", surface="watchlist_row",
        pipeline_run_id=pipeline_run_id,
    )
    assert len(rows) == 1
    assert rows[0].chart_svg_bytes == b"<svg id=v2/>"


def test_chart_renders_position_detail_cache_no_pipeline_run_id_unique_per_ticker(
    conn: sqlite3.Connection,
) -> None:
    """position_detail keys on (ticker, surface) with pipeline_run_id IS NULL
    per spec §C.2. ``refresh_chart_render`` with the same ticker overwrites
    the prior row.
    """
    first = _make_chart(
        None, ticker="POS", surface="position_detail",
        chart_svg_bytes=b"<svg id=p1/>",
    )
    second = _make_chart(
        None, ticker="POS", surface="position_detail",
        chart_svg_bytes=b"<svg id=p2/>",
    )
    with conn:
        repo.refresh_chart_render(conn, first)
        repo.refresh_chart_render(conn, second)
    rows = repo.list_chart_renders(
        conn, ticker="POS", surface="position_detail",
    )
    assert len(rows) == 1
    assert rows[0].chart_svg_bytes == b"<svg id=p2/>"
    assert rows[0].pipeline_run_id is None


def test_chart_renders_theme2_annotated_cache_unique_per_ticker_surface_run_pattern_class(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """theme2_annotated keys on (ticker, surface, pipeline_run_id,
    pattern_class) per spec §C.2. Different pattern_class values for the
    same (ticker, surface, run) coexist.
    """
    vcp = _make_chart(
        pipeline_run_id, ticker="ABC", surface="theme2_annotated",
        pattern_class="vcp", chart_svg_bytes=b"<svg vcp/>",
    )
    flat = _make_chart(
        pipeline_run_id, ticker="ABC", surface="theme2_annotated",
        pattern_class="flat_base", chart_svg_bytes=b"<svg flat/>",
    )
    with conn:
        repo.refresh_chart_render(conn, vcp)
        repo.refresh_chart_render(conn, flat)
    rows = repo.list_chart_renders(
        conn, ticker="ABC", surface="theme2_annotated",
    )
    assert len(rows) == 2
    pattern_classes = {r.pattern_class for r in rows}
    assert pattern_classes == {"vcp", "flat_base"}


def test_chart_renders_session_anchor_read_write_alignment_no_false_miss(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Session-anchor read/write predicate alignment per spec §A.13 LOCK +
    Phase 8 ``cfacbc5`` round-trip precedent: writer stamps
    ``data_asof_date = last_completed_session(now())``; reader staleness
    predicate uses the SAME function. The discriminating round-trip:
    write at a known anchor; immediately read via the predicate; assert
    HIT (no false-MISS due to read/write anchor mismatch).
    """
    chart = _make_chart(
        pipeline_run_id, ticker="SESS", surface="ticker_detail",
        data_asof_date="2024-02-01",  # writer-stamped
    )
    with conn:
        repo.refresh_chart_render(conn, chart)

    # Reader uses the SAME anchor value the writer stamped.
    out = repo.get_cached_chart_svg(
        conn, ticker="SESS", surface="ticker_detail",
        pipeline_run_id=pipeline_run_id,
        min_data_asof_date="2024-02-01",
    )
    assert out == b"<svg/>"

    # Negative: a STRICTLY-LATER predicate (writer stamped 2024-02-01;
    # reader demands >= 2024-02-02) must return None (stale).
    stale = repo.get_cached_chart_svg(
        conn, ticker="SESS", surface="ticker_detail",
        pipeline_run_id=pipeline_run_id,
        min_data_asof_date="2024-02-02",
    )
    assert stale is None


def test_chart_renders_cache_invalidation_atomic_delete_then_insert(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Cache invalidation pattern per §A.15 + §C.2: DELETE-then-INSERT
    atomic refresh wrapped in caller's BEGIN IMMEDIATE. Distinguishes
    ``refresh_chart_render`` from ``INSERT OR REPLACE``.

    The second refresh must allocate a NEW PK (DELETE drops the old row;
    INSERT issues a new auto-increment id), not reuse the old PK as
    INSERT OR REPLACE would.
    """
    first = _make_chart(
        pipeline_run_id, ticker="ATM", surface="watchlist_row",
        chart_svg_bytes=b"<svg first/>",
    )
    with conn:
        first_id = repo.refresh_chart_render(conn, first)

    second = _make_chart(
        pipeline_run_id, ticker="ATM", surface="watchlist_row",
        chart_svg_bytes=b"<svg second/>",
    )
    with conn:
        second_id = repo.refresh_chart_render(conn, second)

    assert second_id != first_id
    rows = repo.list_chart_renders(
        conn, ticker="ATM", surface="watchlist_row",
    )
    assert len(rows) == 1
    assert rows[0].id == second_id
    assert rows[0].chart_svg_bytes == b"<svg second/>"


def test_get_cached_chart_svg_returns_none_on_miss(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Cache-miss path: no row for the key → None (NOT an exception)."""
    out = repo.get_cached_chart_svg(
        conn, ticker="MISS", surface="ticker_detail",
        pipeline_run_id=pipeline_run_id,
    )
    assert out is None


def test_refresh_chart_render_caller_tx_rollback_undoes_both_delete_and_insert(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Caller-tx contract over the atomic refresh pair: rollback after
    ``refresh_chart_render`` undoes both the DELETE and the INSERT.
    """
    pre = _make_chart(
        pipeline_run_id, ticker="ROLL", surface="watchlist_row",
        chart_svg_bytes=b"<svg pre/>",
    )
    with conn:
        repo.insert_chart_render(conn, pre)

    replacement = _make_chart(
        pipeline_run_id, ticker="ROLL", surface="watchlist_row",
        chart_svg_bytes=b"<svg post/>",
    )
    conn.execute("BEGIN")
    repo.refresh_chart_render(conn, replacement)
    conn.rollback()

    rows = repo.list_chart_renders(conn, ticker="ROLL")
    assert len(rows) == 1
    assert rows[0].chart_svg_bytes == b"<svg pre/>"


# ---------------------------------------------------------------------------
# Codex Round 1 fix-bundle 1: ChartRender.__post_init__ validator regression
# tests (CRITICAL #1 cache key shape + MAJOR #2 non-empty chart_svg_bytes).
# ---------------------------------------------------------------------------


def test_chart_render_rejects_run_bound_surface_with_null_pipeline_run_id() -> None:
    """Per plan §C.2: run-bound surfaces (watchlist_row, ticker_detail,
    market_weather) require non-NULL ``pipeline_run_id``. The pre-fix
    substrate accepted NULL silently; rows would be invisible to the
    canonical cache reader. Closes Codex R1 CRITICAL #1.
    """
    from swing.data.models import ChartRender

    for surface in ("watchlist_row", "ticker_detail", "market_weather"):
        with pytest.raises(ValueError, match="pipeline_run_id"):
            ChartRender(
                id=None, ticker="ABC", surface=surface,
                chart_svg_bytes=b"<svg/>",
                source_data_hash="x", rendered_at="2024-01-01T00:00:00",
                data_asof_date="2024-01-01", pipeline_run_id=None,
                pattern_class=None,
            )


def test_chart_render_rejects_position_detail_surface_with_non_null_pipeline_run_id() -> None:
    """Per plan §C.2: position_detail keys on ``(ticker, surface)`` with
    ``pipeline_run_id IS NULL``; a non-NULL run id breaks the cache key
    contract. Closes Codex R1 CRITICAL #1 (second branch).
    """
    from swing.data.models import ChartRender

    with pytest.raises(ValueError, match="pipeline_run_id"):
        ChartRender(
            id=None, ticker="ABC", surface="position_detail",
            chart_svg_bytes=b"<svg/>",
            source_data_hash="x", rendered_at="2024-01-01T00:00:00",
            data_asof_date="2024-01-01", pipeline_run_id=42,
            pattern_class=None,
        )


def test_chart_render_rejects_empty_chart_svg_bytes() -> None:
    """Per CLAUDE.md F6 lesson (external-API empty-result must be transient
    when write-through-caching): an empty SVG must NOT replace existing
    cache content. Closes Codex R1 MAJOR #2 at the construction barrier so
    ``refresh_chart_render`` cannot DELETE the existing row before the
    empty-bytes guard fires.
    """
    from swing.data.models import ChartRender

    with pytest.raises(ValueError, match="chart_svg_bytes"):
        ChartRender(
            id=None, ticker="ABC", surface="watchlist_row",
            chart_svg_bytes=b"",
            source_data_hash="x", rendered_at="2024-01-01T00:00:00",
            data_asof_date="2024-01-01", pipeline_run_id=1,
            pattern_class=None,
        )


def test_refresh_chart_render_empty_svg_does_not_blank_existing_cache(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """End-to-end F6 defense: a transient empty-bytes refresh attempt is
    rejected at ``ChartRender`` construction time, so the existing cache
    row is preserved. Distinguishes pre-fix (DELETE fires; cache blanks)
    from post-fix (construction raises; cache preserved).
    """
    from swing.data.models import ChartRender

    good = _make_chart(
        pipeline_run_id, ticker="GOOD", surface="watchlist_row",
        chart_svg_bytes=b"<svg good/>",
    )
    with conn:
        repo.insert_chart_render(conn, good)

    with pytest.raises(ValueError, match="chart_svg_bytes"):
        ChartRender(
            id=None, ticker="GOOD", surface="watchlist_row",
            chart_svg_bytes=b"",
            source_data_hash="x", rendered_at="2024-01-02T00:00:00",
            data_asof_date="2024-01-02", pipeline_run_id=pipeline_run_id,
            pattern_class=None,
        )

    # Existing row preserved verbatim — DELETE did not fire.
    rows = repo.list_chart_renders(conn, ticker="GOOD")
    assert len(rows) == 1
    assert rows[0].chart_svg_bytes == b"<svg good/>"
