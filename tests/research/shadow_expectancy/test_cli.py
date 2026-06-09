from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def test_command_is_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--help"])
    assert result.exit_code == 0
    assert "--db" in result.output
    assert "--source" in result.output


def test_missing_db_is_friendly_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--db",
                                  str(tmp_path / "nope.db"), "--output-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Traceback" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe absent")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Build a minimal real DB via the harness testkit, then run through the OS encoder.
    # make_db runs migration 0008 which seeds the active hypothesis registry.
    from tests.research.shadow_expectancy.testkit import make_db
    make_db(tmp_path)
    out = tmp_path / "out"
    cmd = (
        f"{sys.executable} -m research.harness.shadow_expectancy.run "
        f"--db {tmp_path / 't.db'} --output-dir {out}"
    )
    proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True,
                          cwd=str(Path(__file__).resolve().parents[3]))
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
