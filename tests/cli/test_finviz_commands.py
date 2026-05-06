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
        # code-review I1 (2026-05-06): insert_call no longer commits internally.
        # Test fixture must commit explicitly so the CliRunner's fresh conn
        # (opened by `swing finviz status`) sees the seeded row.
        conn.commit()
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
    """Discriminating: missing token -> exit code != 0 + friendly error message
    AND audit row written (Codex R2 Major-1: cross-surface observability —
    missing-cred CLI failures must show up in `finviz_api_calls` just like
    pipeline-step failures do).

    USERPROFILE/HOME redirected to tmp_path so the operator's real
    user-config.toml (which DOES have a token) doesn't bleed through.
    """
    from swing.data.repos.finviz_api_calls import list_recent_calls

    runner, cfg_path, main = cli_runner_with_cfg
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code != 0
    assert "token" in res.output.lower() or "screen_query" in res.output.lower()

    # Codex R2 Major-1 discriminator: pre-fix the CLI raised before
    # `_perform_finviz_fetch_no_lease()`, so no audit row was inserted.
    # Post-fix the helper runs, writes status='error', and the CLI translates
    # the row to a friendly Click exception.
    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        rows = list_recent_calls(conn)
    finally:
        conn.close()
    assert len(rows) == 1, rows
    assert rows[0].status == "error"
    assert "token" in (rows[0].error_message or "").lower()


def test_swing_finviz_fetch_bare_question_mark_screen_query_friendly_error(
    cli_runner_with_cfg, tmp_path, monkeypatch,
) -> None:
    """Codex R2 Minor-1: a bare '?' (or '?'-only padding) in screen_query
    canonicalizes to empty after lstrip('?'); must be treated as missing.
    Pre-fix: `not screen_query` returned False so the URL was built as
    `?&auth=...` (degenerate). Post-fix: friendly error + audit row.
    """
    from swing.data.repos.finviz_api_calls import list_recent_calls

    runner, cfg_path, main = cli_runner_with_cfg
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir(exist_ok=True)
    (user_cfg_dir / "user-config.toml").write_text(
        '[integrations.finviz]\n'
        'token = "abc"\n'
        'screen_query = "?"\n'
    )
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    res = runner.invoke(main, ["--config", str(cfg_path), "finviz", "fetch"])
    assert res.exit_code != 0
    assert "screen_query" in res.output.lower()

    conn = sqlite3.connect(tmp_path / "swing.db")
    try:
        rows = list_recent_calls(conn)
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert "screen_query" in (rows[0].error_message or "").lower()


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
