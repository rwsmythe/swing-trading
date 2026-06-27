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


# --- G6 B.1 Task 4: role-neutral resume prompt -----------------------------

def test_resume_prompt_is_role_neutral():
    text = _script_text()
    line = next((ln for ln in text.splitlines() if "$ResumePrompt" in ln), None)
    assert line is not None, "no $ResumePrompt line found in the launcher"
    # both director-framed terms gone (FULL role-neutrality, not just clause 1)
    assert "director" not in line
    assert "charter" not in line
    # the role-neutral replacement is present
    assert "Resuming your session" in line
    assert "section-of-record" in line
    # the self-drain command is preserved (with the {0} role substitution)
    assert "read --role {0} --all" in line


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
    # Task 4 / Issue 1: the orchestrator launches at xhigh, NOT max (directors
    # stay max). This assertion CODIFIED the bug before Task 4 -- it asserted max.
    assert "claude --model opus --effort xhigh --permission-mode auto" in out
    assert "orchestrator_bootstrap.md" in out             # the bootstrap in the prompt
    assert "DRY RUN" in out                                # no window launched


# --- Task 4: role-aware launch effort + role-aware session name ------------

# Issue 1 static-content distinguisher (always runs): the launcher wires the
# per-role effort map -- orchestrator xhigh, directors max.

def test_roleeffort_map_is_role_aware():
    text = _script_text()
    assert "$RoleEffort" in text
    assert "'orchestrator' = 'xhigh'" in text
    assert "'charc' = 'max'" in text
    assert "'rd' = 'max'" in text


# Issue 2 static-content distinguisher (always runs): New-SessionName gives the
# orchestrator a non-'director-' display name; directors keep their scheme.

def test_orchestrator_session_name_not_director_prefixed():
    text = _script_text()
    assert 'return "orchestrator-$stamp"' in text       # orchestrator gets its own name
    assert 'return "director-$role-$stamp"' in text     # directors UNCHANGED


# Issue 1 behavioral -DryRun (skip-guarded): directors stay max + keep the
# 'director-<role>-<stamp>' name.

def test_dryrun_charc_keeps_max_effort_and_director_name():
    if shutil.which("powershell") is None or shutil.which("claude") is None:
        pytest.skip("powershell + claude CLI required for the behavioral DryRun")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SCRIPT),
         "-Role", "charc", "-DryRun"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert "claude --model opus --effort max --permission-mode auto" in out  # directors stay max
    assert "session name 'director-charc-" in out                            # director naming unchanged


# Issue 2 behavioral -DryRun (skip-guarded): the orchestrator's session name is
# 'orchestrator-<stamp>', NOT 'director-orchestrator-<stamp>'.

def test_dryrun_orchestrator_session_name_not_director_prefixed():
    if shutil.which("powershell") is None or shutil.which("claude") is None:
        pytest.skip("powershell + claude CLI required for the behavioral DryRun")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SCRIPT),
         "-Role", "orchestrator", "-DryRun"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert "session name 'orchestrator-" in out          # non-director display name
    assert "director-orchestrator-" not in out           # the 'director-' wart is gone
