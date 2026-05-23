"""Phase 13 T-T4.SB.3 (Item 5; OQ-5.1 R4 LOCK) — ``swing diagnose
prune-chart-cache`` CLI tests.

Per plan §B.3 Sub-task 3G: deletes chart_renders rows older than
--older-than days. Discriminating test plants OLD + NEW rows + verifies
only OLD deleted.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main as cli
from swing.data.db import ensure_schema


def _plant_chart_render(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    rendered_at: str,
    pipeline_run_id: int | None = None,
    surface: str = "hyprec_detail",
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO chart_renders "
            "(ticker, surface, pipeline_run_id, pattern_class, "
            "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
            "VALUES (?, ?, ?, NULL, ?, 'planted', ?, '2026-05-22')",
            (ticker, surface, pipeline_run_id, b"<svg/>", rendered_at),
        )


def _ensure_pipeline_run(conn: sqlite3.Connection) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T00:00:00.000', 'manual', '2026-05-22', "
            "'2026-05-22', 'complete', 'tok-prune')"
        )
        return int(cur.lastrowid)


def test_diagnose_prune_chart_cache_deletes_rows_older_than_days(tmp_path: Path):
    runner = CliRunner()
    db_path = tmp_path / "prune.db"
    conn = ensure_schema(db_path)
    try:
        run_id = _ensure_pipeline_run(conn)
        # OLD row (>365 days).
        old_ts = (
            datetime.now(UTC) - timedelta(days=500)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        _plant_chart_render(
            conn, ticker="OLD", rendered_at=old_ts,
            pipeline_run_id=run_id,
        )
        # NEW row (just now).
        new_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _plant_chart_render(
            conn, ticker="NEW", rendered_at=new_ts,
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()

    result = runner.invoke(
        cli,
        [
            "diagnose", "prune-chart-cache",
            "--db", str(db_path), "--older-than", "365",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Deleted 1 chart_renders rows" in result.output

    conn = sqlite3.connect(str(db_path))
    try:
        remaining = [row[0] for row in conn.execute(
            "SELECT ticker FROM chart_renders ORDER BY ticker"
        )]
    finally:
        conn.close()
    assert remaining == ["NEW"], remaining


def test_diagnose_prune_chart_cache_zero_days_deletes_all(tmp_path: Path):
    """--older-than 0 deletes EVERYTHING (cutoff = now; all rows < now)."""
    runner = CliRunner()
    db_path = tmp_path / "prune_zero.db"
    conn = ensure_schema(db_path)
    try:
        run_id = _ensure_pipeline_run(conn)
        old_ts = (
            datetime.now(UTC) - timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        _plant_chart_render(
            conn, ticker="A", rendered_at=old_ts, pipeline_run_id=run_id,
        )
        _plant_chart_render(
            conn, ticker="B", rendered_at=old_ts, pipeline_run_id=run_id,
        )
    finally:
        conn.close()

    result = runner.invoke(
        cli,
        ["diagnose", "prune-chart-cache",
         "--db", str(db_path), "--older-than", "0"],
    )
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(str(db_path))
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM chart_renders"
        ).fetchone()[0]
    finally:
        conn.close()
    assert cnt == 0


def test_diagnose_prune_chart_cache_does_not_delete_when_nothing_older(
    tmp_path: Path,
):
    """If all rows are NEW relative to threshold, zero deletions."""
    runner = CliRunner()
    db_path = tmp_path / "prune_none.db"
    conn = ensure_schema(db_path)
    try:
        run_id = _ensure_pipeline_run(conn)
        new_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _plant_chart_render(
            conn, ticker="FRESH", rendered_at=new_ts,
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()

    result = runner.invoke(
        cli,
        ["diagnose", "prune-chart-cache",
         "--db", str(db_path), "--older-than", "365"],
    )
    assert result.exit_code == 0, result.output
    assert "Deleted 0 chart_renders rows" in result.output
