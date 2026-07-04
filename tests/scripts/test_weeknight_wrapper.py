"""19-C: scripts/run-weeknight-pipeline.ps1 -- the unit-testable slices.

The register/unregister scripts are witness-verified (a real scheduled fire),
NOT unit-mocked; only the wrapper's pure exit-code mapping, its pre-flight, its
one-line append, and its bounded-run outcome are exercised here (via a real
PowerShell child + a stub exe). Skips cleanly where powershell.exe is absent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WRAPPER = REPO_ROOT / "scripts" / "run-weeknight-pipeline.ps1"

_POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(
    _POWERSHELL is None, reason="powershell.exe not available"
)


def _ps_command(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, timeout=120,
    )


def _ps_file(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(WRAPPER), *args],
        capture_output=True, text=True, timeout=120,
    )


def _write_stub_exe(tmp_path: Path, exit_code: int) -> Path:
    stub = tmp_path / "stub.cmd"
    stub.write_text(f"@echo off\r\nexit /b {exit_code}\r\n", encoding="ascii")
    return stub


def test_outcome_mapping_all_rows():
    """The five contract rows: 0->OK/0, 75->SKIP/0, 1->FAIL/1, 78->ERROR/78,
    and any-other->ERROR/<code> (2 = wrapper/registration coding bug, surfaced)."""
    expected = {
        0: ("OK", 0),
        75: ("SKIP", 0),
        1: ("FAIL", 1),
        78: ("ERROR", 78),
        2: ("ERROR", 2),
        99: ("ERROR", 99),
    }
    codes = ",".join(str(c) for c in expected)
    cmd = (
        f". '{WRAPPER}' -NoRun; "
        f"foreach ($c in {codes}) {{ Get-WeeknightOutcome -Code $c | "
        f"ConvertTo-Json -Compress }}"
    )
    proc = _ps_command(cmd)
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(rows) == len(expected)
    by_input = dict(zip(expected.keys(), rows))
    for code, (tag, exit_code) in expected.items():
        row = by_input[code]
        assert row["Tag"] == tag, (code, row)
        assert row["ExitCode"] == exit_code, (code, row)


def test_preflight_missing_exe_writes_error_line(tmp_path: Path):
    """Task 4: a nonexistent -SwingExe -> ERROR line + non-zero exit WITHOUT
    attempting the run."""
    result_log = tmp_path / "logs" / "weeknight-task.log"
    proc = _ps_file(
        "-SwingExe", str(tmp_path / "nope.exe"),
        "-RepoRoot", str(tmp_path),
        "-ConfigPath", str(tmp_path / "cfg.toml"),
        "-ResultLog", str(result_log),
    )
    assert proc.returncode != 0
    assert result_log.exists()
    lines = [ln for ln in result_log.read_text(encoding="ascii").splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    assert "ERROR" in lines[0]
    assert "not found" in lines[0].lower()


def test_preflight_missing_repo_writes_error_line(tmp_path: Path):
    """Task 4: a nonexistent -RepoRoot -> ERROR line + non-zero exit."""
    result_log = tmp_path / "logs" / "weeknight-task.log"
    proc = _ps_file(
        "-SwingExe", str(_write_stub_exe(tmp_path, 0)),
        "-RepoRoot", str(tmp_path / "no-such-repo"),
        "-ConfigPath", str(tmp_path / "cfg.toml"),
        "-ResultLog", str(result_log),
    )
    assert proc.returncode != 0
    lines = [ln for ln in result_log.read_text(encoding="ascii").splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    assert "ERROR" in lines[0]
    assert "repo root not found" in lines[0].lower()


def test_write_result_line_appends_one_ascii_line(tmp_path: Path):
    """The append helper writes exactly one ASCII line per call + mkdir-Forces
    the parent."""
    result_log = tmp_path / "nested" / "wt.log"
    cmd = (
        f". '{WRAPPER}' -NoRun; "
        f"Write-WeeknightResultLine -ResultLog '{result_log}' -Tag 'OK' -ExitCode 0; "
        f"Write-WeeknightResultLine -ResultLog '{result_log}' -Tag 'SKIP' -ExitCode 0 "
        f"-Message 'another run in progress'"
    )
    proc = _ps_command(cmd)
    assert proc.returncode == 0, proc.stderr
    raw = result_log.read_bytes()
    assert all(b < 128 for b in raw), "result line must be ASCII"
    lines = [ln for ln in raw.decode("ascii").splitlines() if ln.strip()]
    assert len(lines) == 2, lines
    assert "OK exit=0" in lines[0]
    assert "SKIP exit=0 another run in progress" in lines[1]


def test_run_stub_skip_exits_zero(tmp_path: Path):
    """Task 5: a child exiting 75 -> one SKIP line + wrapper exit 0 (task green)."""
    result_log = tmp_path / "logs" / "weeknight-task.log"
    proc = _ps_file(
        "-SwingExe", str(_write_stub_exe(tmp_path, 75)),
        "-RepoRoot", str(tmp_path),
        "-ConfigPath", str(tmp_path / "cfg.toml"),
        "-ResultLog", str(result_log),
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in result_log.read_text(encoding="ascii").splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    assert "SKIP exit=75" in lines[0]


def test_run_stub_ok_exits_zero(tmp_path: Path):
    """Task 5: a child exiting 0 -> one OK line + wrapper exit 0."""
    result_log = tmp_path / "logs" / "weeknight-task.log"
    proc = _ps_file(
        "-SwingExe", str(_write_stub_exe(tmp_path, 0)),
        "-RepoRoot", str(tmp_path),
        "-ConfigPath", str(tmp_path / "cfg.toml"),
        "-ResultLog", str(result_log),
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in result_log.read_text(encoding="ascii").splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    assert "OK exit=0" in lines[0]
