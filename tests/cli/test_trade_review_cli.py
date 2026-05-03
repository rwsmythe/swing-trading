"""Click integration tests for swing trade review."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import ensure_schema
from swing.data.models import Exit, Trade
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    """Create a minimal config + migrated DB. Returns (runner, cfg_path, db_path)."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    return runner, cfg, db_path


def _seed_closed_trade(db_path: Path) -> int:
    """Seed a closed VIR trade with one exit. Returns the trade_id."""
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None,
                    ticker="VIR",
                    entry_date="2026-04-20",
                    entry_price=10.0,
                    initial_shares=10,
                    initial_stop=9.0,
                    current_stop=9.0,
                    status="open",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-20T09:30:00",
            )
            insert_exit_with_event(
                conn,
                Exit(
                    id=None,
                    trade_id=trade_id,
                    exit_date="2026-04-25",
                    exit_price=11.5,
                    shares=10,
                    reason="manual",
                    realized_pnl=15.0,
                    r_multiple=1.5,
                    notes=None,
                ),
                event_ts="2026-04-25T09:30:00",
            )
    finally:
        conn.close()
    return trade_id


def test_review_persists_all_ten_fields(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "CHASED",
        "--mistake-tags", "FOMO",
        "--entry-grade", "C",
        "--management-grade", "B",
        "--exit-grade", "B",
        "--realized-r-if-plan-followed", "2.0",
        "--mistake-cost-confidence", "medium",
        "--lesson-learned", "Wait for the breakout, not the build-up.",
    ])
    assert result.exit_code == 0, result.output

    # Verify persistence via direct SQL
    from swing.data.db import connect
    conn = connect(db_path)
    row = conn.execute(
        "SELECT reviewed_at, mistake_tags, entry_grade, process_grade, "
        "realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned "
        "FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    conn.close()

    assert row[0] is not None  # reviewed_at populated
    tags = json.loads(row[1])
    assert tags == ["CHASED", "FOMO"]  # canonicalized + sorted
    assert row[2] == "C"
    # process grade: entry=C(2), management=B(3), exit=B(3), disqualifying=False
    # weighted = 0.40*2 + 0.35*3 + 0.25*3 = 0.80 + 1.05 + 0.75 = 2.60 → C bucket [2.00, 2.75)
    assert row[3] == "C"
    assert row[4] == 2.0
    assert row[5] == "medium"
    assert "breakout" in row[6]


def test_review_list_flag_shows_pending_trades(tmp_path: Path) -> None:
    """R1 Major 2: brief §3.1 contract is `swing trade review --list`.

    Single command with `--list` flag, NOT a separate `review-list` subcommand.
    """
    runner, cfg, db_path = _setup(tmp_path)
    _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review", "--list",
    ])
    assert result.exit_code == 0, result.output
    assert "VIR" in result.output


def test_review_without_trade_id_or_list_flag_errors(tmp_path: Path) -> None:
    """Missing `--trade-id` AND missing `--list` flag → UsageError."""
    runner, cfg, db_path = _setup(tmp_path)

    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "review",
    ])
    assert result.exit_code != 0
    assert "trade-id" in result.output.lower() or "list" in result.output.lower()


def test_review_unknown_mistake_tag_rejected(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "NOT_REAL",
        "--entry-grade", "A",
        "--management-grade", "A",
        "--exit-grade", "A",
        "--lesson-learned", "n/a",
    ])
    assert result.exit_code != 0
    assert "unknown mistake tag" in result.output.lower()
