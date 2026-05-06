"""swing finviz {fetch,status} CLI — Task 8."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.data.db import ensure_schema
from swing.data.models import FinvizApiCall
from swing.data.repos.finviz_api_calls import insert_call


@pytest.fixture
def cli_runner_with_cfg(tmp_path: Path):
    """Builds a tmp swing.config.toml + DB; returns (runner, cfg_path, main)."""
    from swing.cli import main
    runner = CliRunner()
    base_toml = Path("swing.config.toml").read_text()
    cfg_path = tmp_path / "swing.config.toml"
    # Use posix-style paths so the TOML parser doesn't interpret Windows
    # backslashes (e.g. "C:\Users\...") as invalid escape sequences.
    tmp_posix = tmp_path.as_posix()
    rewritten = base_toml.replace(
        'db_path = "swing-data/swing.db"',
        f'db_path = "{tmp_posix}/swing.db"',
    ).replace(
        'finviz_inbox_dir = "data/finviz-inbox"',
        f'finviz_inbox_dir = "{tmp_posix}/finviz-inbox"',
    )
    cfg_path.write_text(rewritten)
    (tmp_path / "finviz-inbox").mkdir()
    ensure_schema(tmp_path / "swing.db").close()
    return runner, cfg_path, main


def test_swing_finviz_status_lists_recent_calls(cli_runner_with_cfg, tmp_path) -> None:
    runner, cfg_path, main = cli_runner_with_cfg
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        insert_call(conn, FinvizApiCall(
            call_id=None, ts="2026-05-05T12:00:00", screen_query="v=152",
            status="ok", row_count=42, response_time_ms=180,
            rate_limit_remaining=99,
            signature_hash="abc123def456" + "0" * 52, error_message=None,
        ))
    finally:
        conn.close()
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "status"])
    assert res.exit_code == 0, res.output
    assert "ok" in res.output
    assert "42" in res.output
    assert "abc123de" in res.output  # truncated 8 chars of signature


def test_swing_finviz_status_empty_state(cli_runner_with_cfg) -> None:
    runner, cfg_path, main = cli_runner_with_cfg
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "status"])
    assert res.exit_code == 0, res.output
    assert "no" in res.output.lower()  # "no calls recorded" or similar


def test_swing_finviz_fetch_token_missing_friendly_error(
    cli_runner_with_cfg, tmp_path, monkeypatch,
) -> None:
    """Discriminating: missing token -> exit code != 0 + friendly error message.

    USERPROFILE/HOME redirected to tmp_path so the operator's real
    user-config.toml (which DOES have a token) doesn't bleed through.
    """
    runner, cfg_path, main = cli_runner_with_cfg
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code != 0
    assert "token" in res.output.lower() or "screen_query" in res.output.lower()


def test_swing_finviz_fetch_friendly_error_when_pipeline_running(
    cli_runner_with_cfg, tmp_path, monkeypatch,
) -> None:
    """Codex R2 Major-3 + R3 Minor-1 fix: CLI translates FinvizPipelineActiveError
    to a friendly user-facing error.
    """
    runner, cfg_path, main = cli_runner_with_cfg
    # User-config with valid token + screen_query so the early token-missing
    # check passes and the helper's pipeline-running guard fires.
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir(exist_ok=True)
    (user_cfg_dir / "user-config.toml").write_text(
        '[integrations.finviz]\n'
        'token = "test-sentinel-token"\n'
        'screen_query = "v=152&f=test"\n'
    )
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, trigger, data_asof_date, action_session_date,"
            "  state, lease_token, lease_heartbeat_ts"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2026-05-05T12:00:00", "manual",
             "2026-05-04", "2026-05-05",
             "running", "tok-test", "2026-05-05T12:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code != 0
    assert "pipeline run is currently in flight" in res.output


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_swing_finviz_fetch_happy_path_emits_csv_and_persists_row(
    cli_runner_with_cfg, tmp_path, monkeypatch,
) -> None:
    """USERPROFILE/swing-data/user-config.toml is the canonical user-config path.

    Codex R1 Major-3 fix: write to tmp_path/swing-data/user-config.toml +
    set USERPROFILE to tmp_path so resolution lands on the file we wrote.
    """
    runner, cfg_path, main = cli_runner_with_cfg
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir(exist_ok=True)
    (user_cfg_dir / "user-config.toml").write_text(
        '[integrations.finviz]\n'
        'token = "test-sentinel-token"\n'
        'screen_query = "v=152&f=cap_largeover"\n'
    )
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code == 0, res.output
    csvs = list((tmp_path / "finviz-inbox").glob("finviz*.csv"))
    assert len(csvs) == 1
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        rows = conn.execute(
            "SELECT status, row_count, signature_hash FROM finviz_api_calls"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "ok"
    assert rows[0][1] > 0
    assert rows[0][2] is not None
