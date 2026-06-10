from __future__ import annotations

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

import swing.cli as cli
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    from swing.data.db import ensure_schema
    cfg = load(cfg_path)
    cfg.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def test_cleanup_compresses_dated_with_yes(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    dated = cfg.paths.logs_dir / "web.log.2026-05-06"
    dated.write_bytes(b"old log line\n" * 1000)
    (cfg.paths.logs_dir / "web.log").write_bytes(b"active\n")  # must NOT be touched
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code == 0, res.output
    assert not dated.exists()
    archive = cfg.paths.logs_dir / "web.log.2026-05-06.gz"
    assert archive.exists()
    assert gzip.decompress(archive.read_bytes()) == b"old log line\n" * 1000
    assert (cfg.paths.logs_dir / "web.log").read_bytes() == b"active\n"  # untouched


def test_cleanup_refuses_when_pipeline_running(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x")
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "('2026-06-09T00:00:00','manual','2026-06-08','2026-06-09','running','t')"
        )
    conn.close()
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code != 0
    assert "pipeline" in res.output.lower()


def test_cleanup_fail_closed_on_db_unavailable(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    cfg.paths.db_path.unlink()  # remove the DB -> query must fail-closed (refuse)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x")
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    # ensure_schema would recreate on connect; the impl opens read-only without
    # creating and pre-checks existence, so an absent DB refuses (fail-closed).
    assert res.exit_code != 0


def test_include_current_requires_web_stopped(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    res = CliRunner().invoke(
        cli.main,
        ["--config", str(cfg_path), "logs", "cleanup", "--yes", "--include-current"],
    )
    assert res.exit_code != 0
    assert "web-stopped" in res.output.lower() or "web server" in res.output.lower()


def test_include_current_compresses_oversized_current(tmp_path):
    # Proves the click wiring actually calls select_oversized_current_logs (not just
    # the dated-default scope). Oversized current web.log (> the 10 MB default
    # threshold) + the full app-stopped scope -> archived.
    cfg, cfg_path = _setup(tmp_path)
    payload = b"y" * (11 * 1024 * 1024)   # exceed the 10 MB oversize threshold
    (cfg.paths.logs_dir / "web.log").write_bytes(payload)
    res = CliRunner().invoke(
        cli.main,
        ["--config", str(cfg_path), "logs", "cleanup",
         "--yes", "--include-current", "--web-stopped"],
    )
    assert res.exit_code == 0, res.output
    assert not (cfg.paths.logs_dir / "web.log").exists()
    archive = cfg.paths.logs_dir / "web.log.gz"
    assert archive.exists()
    assert gzip.decompress(archive.read_bytes()) == payload


def test_cleanup_idempotent_no_candidates(tmp_path):
    cfg, cfg_path = _setup(tmp_path)
    res = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "logs", "cleanup", "--yes"]
    )
    assert res.exit_code == 0
    assert "no legacy" in res.output.lower()


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="cp1252 stdout footgun is Windows/PowerShell-specific",
)
def test_cleanup_stdout_is_ascii_through_powershell(tmp_path):
    # cp1252 footgun: the command's stdout must be ASCII so PowerShell's default
    # cp1252 encoder never raises UnicodeEncodeError in production.
    cfg, cfg_path = _setup(tmp_path)
    (cfg.paths.logs_dir / "web.log.2026-05-06").write_bytes(b"x" * 100)
    completed = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f'& "{sys.executable}" -m swing.cli --config "{cfg_path}" logs cleanup --yes',
        ],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    completed.stdout.encode("ascii")  # raises if any non-ASCII glyph slipped in
