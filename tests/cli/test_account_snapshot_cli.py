"""Phase 9 Sub-bundle C T-C.2 — `swing account snapshot` CLI tests.

Per plan §F T-C.2 + spec §4.4 V1 cadence.

Coverage:
  - Happy path: `--equity 1300` records a row at today's last completed
    session date.
  - `--date YYYY-MM-DD` override.
  - Back-recorded advisory printed for >7-day-past dates.
  - Re-record UPSERT on same (snapshot_date, source=manual): PK preserved.
  - Invalid equity rejected with ClickException (matches dataclass validator).

Monkeypatches USERPROFILE + HOME per CLAUDE.md gotcha to avoid pollution of
the operator's real `~/swing-data/user-config.toml`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def runner_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    # Bring DB to schema v17.
    r = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg_path, db_path


def test_snapshot_happy_path_records_row(runner_env):
    runner, cfg_path, db_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--notes", "operator gate S3",
    ])
    assert r.exit_code == 0, r.output
    assert "snapshot #" in r.output
    assert "$1300.00" in r.output
    assert "source=manual" in r.output

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT equity_dollars, source, notes FROM account_equity_snapshots"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0] == (1300.0, "manual", "operator gate S3")


def test_snapshot_with_date_override(runner_env):
    runner, cfg_path, db_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1400",
        "--date", "2026-04-01",
        "--notes", "back-record test",
    ])
    assert r.exit_code == 0, r.output

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT snapshot_date, equity_dollars FROM account_equity_snapshots"
    ).fetchone()
    conn.close()
    assert row == ("2026-04-01", 1400.0)


def test_snapshot_back_recorded_advisory_for_far_past_date(runner_env):
    """Per spec §3.5 GAP-FLAGGED policy + plan §F T-C.2 acceptance #6."""
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1400",
        "--date", "2026-01-01",
    ])
    assert r.exit_code == 0, r.output
    assert "back-recorded" in r.output


def test_snapshot_no_back_recorded_advisory_for_today(runner_env):
    """Within-threshold dates do not print the advisory."""
    from datetime import date as _date

    runner, cfg_path, _ = runner_env
    today = _date.today().isoformat()
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--date", today,
    ])
    assert r.exit_code == 0, r.output
    assert "back-recorded" not in r.output


def test_snapshot_rerecord_same_date_upserts_in_place(runner_env):
    """Re-record same (snapshot_date, source=manual) preserves PK."""
    runner, cfg_path, db_path = runner_env
    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--date", "2026-05-12",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1400",
        "--date", "2026-05-12",
    ])
    assert r2.exit_code == 0, r2.output

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT snapshot_id, equity_dollars FROM account_equity_snapshots"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, "second invocation should UPDATE not INSERT"
    assert rows[0][1] == 1400.0


def test_snapshot_rejects_zero_equity(runner_env):
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "0",
    ])
    assert r.exit_code != 0
    assert "equity_dollars" in r.output


def test_snapshot_rejects_negative_equity(runner_env):
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "-1",
    ])
    assert r.exit_code != 0
    assert "equity_dollars" in r.output


def test_snapshot_rejects_malformed_date(runner_env):
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--date", "May 12 2026",
    ])
    assert r.exit_code != 0
