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
    chart = _make_chart(pipeline_run_id, ticker="XYZ", surface="hyprec_detail")
    with conn:
        chart_id = repo.insert_chart_render(conn, chart)
    row = conn.execute(
        "SELECT ticker, surface, pipeline_run_id, pattern_class, "
        "source_data_hash FROM chart_renders WHERE id = ?",
        (chart_id,),
    ).fetchone()
    assert row == ("XYZ", "hyprec_detail", pipeline_run_id, None, "deadbeef")


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
            "watchlist_row", "hyprec_detail", "watchlist_row",
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
