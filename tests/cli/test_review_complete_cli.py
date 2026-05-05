"""CLI tests for `swing review complete --review-id <id> --primary-lesson "..."`.

Phase 7 Sub-B B.6 fixture migration: legacy ``Exit(...)``+``insert_exit_with_event``
seeding rewritten to ``Fill(action='exit')``+``insert_fill_with_event``. The
``Exit`` dataclass is a stub post Sub-A T3 and raises on construction.

Module unskipped at end of B.9 (Codex R1 Major 3 / R2 Minor 1 docstring fix).
B.9's journal-layer rewrite migrated ``swing.journal.stats`` +
``swing.trades.review`` helpers to the fills surface, restoring the
``complete_review_atomic`` aggregate path that this module exercises.
"""
import pytest
from pathlib import Path
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config

# pytestmark unskipped during Codex R1 verification (B.9 journal rewrites landed)


@pytest.fixture
def populated_db_with_pending_daily(tmp_path: Path) -> Path:
    """DB with a closed trade in the daily period + a pre-created review_log row.

    Returns the db_path (Path). Uses _minimal_config to seed the DB properly.
    """
    from swing.data.db import ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.review_log import insert_pre_create
    from swing.data.repos.trades import insert_trade_with_event

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)

    # Run db-migrate so the schema is initialized
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])

    import tomllib
    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])

    conn = ensure_schema(db_path)
    try:
        with conn:
            # Closed trade whose exit_date falls in the daily period.
            # Phase 7 Sub-B B.6: seed via insert_trade_with_event + entry/exit
            # fills, then UPDATE state directly to 'closed' (fixture brevity).
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="VIR", entry_date="2026-04-29",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                    trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-29T09:30:00",
                ),
                event_ts="2026-04-29T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=trade_id,
                    fill_datetime="2026-04-29T09:30:00",
                    action="entry", quantity=10.0, price=10.0,
                ),
                event_ts="2026-04-29T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=trade_id,
                    fill_datetime="2026-04-30T09:30:00",
                    action="exit", quantity=10.0, price=12.0,
                    reason="manual",
                ),
                event_ts="2026-04-30T09:30:00",
            )
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (trade_id,),
            )
            # Pre-created review_log row for that daily period:
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
    finally:
        conn.close()
    return cfg_path, db_path


def test_review_complete_freezes_aggregates(populated_db_with_pending_daily, tmp_path):
    """Atomic completion: closed trades in the period are computed
    and frozen on the row.
    """
    cfg_path, db_path = populated_db_with_pending_daily
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(cfg_path),
        "review", "complete",
        "--review-id", "1",
        "--duration-minutes", "12",
        "--primary-lesson", "Inaugural review.",
        "--next-period-focus", "Same setup.",
    ])
    assert result.exit_code == 0, result.output

    # Verify freeze: re-read the row, assert completed_date + aggregates
    # populated; n_trades_reviewed > 0.
    from swing.data.db import connect
    conn = connect(db_path)
    row = conn.execute(
        """SELECT completed_date, primary_lesson, n_trades_reviewed,
                  net_R_effective, profit_factor
           FROM review_log WHERE review_id = 1"""
    ).fetchone()
    conn.close()
    assert row[0] is not None  # completed_date set
    assert "Inaugural" in row[1]
    assert row[2] >= 1


def test_review_complete_list_mode_shows_pending(populated_db_with_pending_daily, tmp_path):
    cfg_path, db_path = populated_db_with_pending_daily
    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(cfg_path),
        "review", "complete", "--list",
    ])
    assert result.exit_code == 0
    assert "daily" in result.output.lower()
