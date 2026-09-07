"""22-A4 Task 1b -- (m8c) CLI half: DELIVERY through the UNCHANGED caller.

The half that makes this CHARC's condition rather than a type change. The CLI's
tier-2 surface maps a service `ValueError` to `click.UsageError`, which click
renders as EXIT CODE 2 with the message on stderr and no traceback
(`swing/cli.py`, the `except ValueError as e: raise click.UsageError(str(e))`
clause in `discrepancy_resolve_ambiguity_cmd`).

**Pre-fix:** the refusal is `sqlite3.IntegrityError` from
`trg_trades_attempt_id_immutable` -- a type the command's catch-ladder does not
name, so it escapes as an UNCAUGHT TRACEBACK (exit 1). The same is true of an
`ImmutableJournalFieldError` deriving from a bare `Exception`, which is the
shape this row exists to forbid.

The assertions are the EXACT exit code, not merely "not success": a weak
delivery row would pass on any non-zero result and would certify nothing about
legibility.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config

MINTED_TOKEN = "11111111-2222-4333-8444-555555555555"
OTHER_TOKEN = "99999999-8888-4777-8666-555555555555"


@pytest.fixture
def cli_workspace(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _seed(db_path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    try:
        trade_id = int(conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, attempt_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
             "manual_off_pipeline", "2026-04-27T16:00:00", MINTED_TOKEN),
        ).lastrowid)
        run_id = int(conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES (?,?,?)",
            ("schwab_api", "2026-09-07T12:00:00", "running"),
        ).lastrowid)
        disc_id = int(conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, trade_id, fill_id, ticker, field_name, "
            "expected_value_json, actual_value_json, material_to_review, "
            "resolution, ambiguity_kind, resolution_reason, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "stop_mismatch", trade_id, None, "CVGI", "current_stop",
             '{"current_stop": 4.0}', '{"current_stop": 4.5}', 1,
             "pending_ambiguity_resolution", "unsupported",
             "classifier did not recognize the shape", "2026-09-07T12:00:00"),
        ).lastrowid)
        conn.commit()
        return trade_id, disc_id
    finally:
        conn.close()


def test_m8c_cli_refusal_is_exit_2_with_no_traceback(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    trade_id, disc_id = _seed(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(disc_id),
        "--choice", "operator_truth",
        "--custom-value", '{"attempt_id": "' + OTHER_TOKEN + '"}',
        "--reason", "broker says the attempt token was different",
    ])

    assert r.exit_code == 2, (r.exit_code, r.output)
    # click.UsageError exits via SystemExit; an uncaught service exception
    # (today's sqlite3.IntegrityError, or a bare-Exception refusal) would leave
    # the original exception here and print a traceback.
    assert r.exception is None or isinstance(r.exception, SystemExit), r.exception
    assert "Traceback" not in r.output, r.output
    assert "trades.attempt_id" in r.output
    assert "WRITE-ONCE" in r.output

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()[0] == MINTED_TOKEN
        assert conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections",
        ).fetchone()[0] == 0
    finally:
        conn.close()
