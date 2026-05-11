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
                state="entered", watchlist_entry_target=None,
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


def test_trade_advisory_cli_suppresses_trim_into_strength_after_prior_fill(
    tmp_path: Path,
):
    """Codex R1 Major #1 — CLI must load fills + populate has_been_trimmed.

    Discriminating pair: same trade at +2R (above trim_first_r_trigger).
    Without prior non-entry fill → trim_into_strength fires.
    With a prior trim fill (action='trim') → trim_into_strength suppressed.
    """
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.db import connect
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    from swing.config import load as load_cfg
    loaded_cfg = load_cfg(cfg)
    conn = connect(loaded_cfg.paths.db_path)
    try:
        with conn:
            trade_a = Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10,
                initial_stop=170.0, current_stop=170.0,
                state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid_a = insert_trade_with_event(
                conn, trade_a, event_ts="2026-04-15T09:30:00",
            )
            trade_b = Trade(
                id=None, ticker="MSFT", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10,
                initial_stop=170.0, current_stop=170.0,
                state="partial_exited", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid_b = insert_trade_with_event(
                conn, trade_b, event_ts="2026-04-15T09:30:00",
            )
            # Trade B has a prior trim fill.
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=tid_b,
                    fill_datetime="2026-04-16T10:00:00",
                    action="trim", quantity=5.0, price=190.0,
                    reason=None, rule_based=None, fees=None,
                    manual_entry_confidence=None,
                    reconciliation_status="unreconciled",
                    tos_match_id=None,
                ),
                event_ts="2026-04-16T10:00:00",
            )
    finally:
        conn.close()

    def _invoke(trade_id: int):
        return runner.invoke(main, [
            "--config", str(cfg), "trade", "advisory",
            "--trade-id", str(trade_id),
            "--current-price", "200.0",  # +2R
            "--weather", "Bullish",
        ])

    r_a = _invoke(tid_a)
    assert r_a.exit_code == 0, r_a.output
    assert "trim_into_strength" in r_a.output, (
        f"No prior trim → trim_into_strength must fire; got: {r_a.output!r}"
    )

    r_b = _invoke(tid_b)
    assert r_b.exit_code == 0, r_b.output
    assert "trim_into_strength" not in r_b.output, (
        f"Prior trim fill → trim_into_strength must suppress; got: {r_b.output!r}"
    )


def test_trade_advisory_cli_accepts_adr_pct_for_parabolic_trim(tmp_path: Path):
    """Codex R1 Minor #2 — CLI accepts --adr-pct so the §4.D parabolic_trim
    rule can fire from the CLI surface."""
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    from swing.config import load as load_cfg
    loaded_cfg = load_cfg(cfg)
    conn = connect(loaded_cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10,
                initial_stop=170.0, current_stop=170.0,
                state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid = insert_trade_with_event(
                conn, trade, event_ts="2026-04-15T09:30:00",
            )
    finally:
        conn.close()

    # sma50=200, adr_pct=5, current_price=270 → extension = 35% = 7× ADR
    # → parabolic_trim fires.
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "advisory",
        "--trade-id", str(tid),
        "--current-price", "270.0",
        "--sma50", "200.0",
        "--adr-pct", "5.0",
        "--weather", "Bullish",
    ])
    assert r.exit_code == 0, r.output
    assert "parabolic_trim" in r.output, (
        f"Expected parabolic_trim to fire via CLI; got: {r.output!r}"
    )
