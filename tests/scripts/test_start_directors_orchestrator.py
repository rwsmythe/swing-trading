"""Tests for the orchestrator role in scripts/start_directors.ps1 (G6 Arc B).

Task 1a is a deterministic, always-runs static-content distinguisher (no
PowerShell / claude CLI needed). Task 1b is a supplementary behavioral -DryRun
test, skip-guarded on the operator's box where powershell + claude both resolve
(exactly where the merged-head no-false-green re-run executes).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "start_directors.ps1"


def _script_text() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


# --- Task 1a: static-content distinguisher (always runs) -------------------

def test_validateset_includes_orchestrator():
    text = _script_text()
    # the ValidateSet line that gates the -Role parameter must accept orchestrator
    for line in text.splitlines():
        if "[ValidateSet(" in line:
            assert "'orchestrator'" in line, (
                "the -Role [ValidateSet] must include 'orchestrator'")
            break
    else:
        raise AssertionError("no [ValidateSet(...)] line found in the launcher")


def test_bootstrapfiles_maps_orchestrator():
    text = _script_text()
    # $BootstrapFiles must carry an 'orchestrator' -> orchestrator_bootstrap.md entry
    assert "$BootstrapFiles" in text
    assert "'orchestrator'" in text
    assert "orchestrator_bootstrap.md" in text


def test_roletitles_maps_orchestrator():
    text = _script_text()
    # $RoleTitles must carry an 'orchestrator' -> 'ORCHESTRATOR' title (ASCII tab title)
    assert "$RoleTitles" in text
    assert "'ORCHESTRATOR'" in text


# --- Task 1b: behavioral -DryRun (skip-guarded) ----------------------------

def test_dryrun_orchestrator_sets_role_and_prints_command():
    if shutil.which("powershell") is None or shutil.which("claude") is None:
        pytest.skip("powershell + claude CLI required for the behavioral DryRun")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SCRIPT),
         "-Role", "orchestrator", "-DryRun"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert "$env:SWING_ROLE='orchestrator'" in out        # role set inside the shell
    assert "claude --model opus --effort max --permission-mode auto" in out
    assert "orchestrator_bootstrap.md" in out             # the bootstrap in the prompt
    assert "DRY RUN" in out                                # no window launched
