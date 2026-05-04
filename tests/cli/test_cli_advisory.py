"""`swing trade advisory` CLI — SMA50 and previous-close flags (Phase 3d §3.6)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main


def test_trade_advisory_accepts_sma50_and_previous_close(tmp_path: Path):
    """The command accepts --sma50 and --previous-close and plumbs them
    into AdvisoryContext. Exit code 0; output references 50MA EXIT rule."""
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.db import connect
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.models import Trade

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    # Seed an open trade by direct repo call — avoids coupling this test
    # to the `swing trade entry` CLI (the real command name; the previous
    # plan draft used `trade enter` which does not exist).
    from swing.config import load as load_cfg
    loaded_cfg = load_cfg(cfg)
    conn = connect(loaded_cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10,
                initial_stop=170.0, current_stop=170.0,
                status="open", state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid = insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()

    # Run advisory with SMA50 + previous-close.
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "advisory",
        "--trade-id", str(tid),
        "--current-price", "200.0",
        "--sma10", "198.0",
        "--sma20", "196.0",
        "--sma50", "195.0",
        "--previous-close", "190.0",
        "--weather", "Bullish",
    ])
    assert r.exit_code == 0, r.output
    # The 50MA exit rule should fire (previous_close 190 < sma50 195).
    assert "50MA" in r.output
    assert "190.00" in r.output
