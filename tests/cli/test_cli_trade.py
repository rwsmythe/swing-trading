"""CLI: swing trade entry / exit / list / stop-adjust / advisory."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_trade_entry_then_list(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "VCP",
    ])
    assert result.exit_code == 0, result.output
    assert "trade id" in result.output.lower() or "entered" in result.output.lower()

    result2 = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result2.exit_code == 0
    assert "AAPL" in result2.output


def test_trade_list_shows_remaining_shares_after_partial_exit(tmp_path: Path):
    """Regression: `trade list` displayed `initial_shares` instead of
    remaining shares after partial exits. The web dashboard correctly
    computed remaining; the CLI did not. Both surfaces must agree."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "VIR", "--entry-date", "2026-04-20",
        "--entry-price", "10.76", "--shares", "2",
        "--initial-stop", "8.26", "--rationale", "near-pivot",
    ])
    runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-20",
        "--exit-price", "11.50", "--shares", "1",
        "--reason", "partial", "--rationale", "take half",
    ])
    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result.exit_code == 0, result.output
    # Output row should show 1 share remaining (2 initial - 1 exited),
    # not 2. Column is space-padded; grep for the VIR row and assert the
    # shares column.
    vir_lines = [ln for ln in result.output.splitlines() if "VIR" in ln]
    assert len(vir_lines) == 1, f"expected 1 VIR row, got {vir_lines}"
    row = vir_lines[0]
    # The shares column is the token immediately before "open".
    parts = row.split()
    sh_idx = parts.index("open") - 1
    assert parts[sh_idx] == "1", (
        f"trade list showed {parts[sh_idx]} shares after partial exit; "
        f"expected 1. full row: {row!r}"
    )


def test_trade_exit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target", "--rationale", "hit",
    ])
    assert result.exit_code == 0, result.output
    assert "R" in result.output


def test_trade_stop_adjust_blocked_when_lowering(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "165.0", "--rationale", "loosen",
    ])
    assert result.exit_code != 0
    assert "regression" in result.output.lower() or "force" in result.output.lower()


def test_trade_stop_adjust_persists_notes(tmp_path: Path):
    """Bug 3b: `swing trade stop-adjust --notes ...` writes notes to
    trade_events.notes (distinct from rationale)."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "175.0",
        "--rationale", "trail-10MA",
        "--notes", "low-volume up-day",
    ])
    assert result.exit_code == 0, result.output

    # Verify persisted notes via the repo, mirroring the service-level test
    # pattern (matches how other CLI tests read-back results).
    from swing.config import load as load_cfg
    from swing.data.db import connect
    from swing.data.repos.trades import list_events_for_trade
    conn = connect(load_cfg(cfg).paths.db_path)
    try:
        adj = next(
            e for e in list_events_for_trade(conn, 1) if e.event_type == "stop_adjust"
        )
    finally:
        conn.close()
    assert adj.rationale == "trail-10MA"
    assert adj.notes == "low-volume up-day"
