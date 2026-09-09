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

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_SCRIPT = _SCRIPTS / "start_directors.ps1"

# The declared START configuration per role, as each bootstrap states it in its
# "LAUNCH CONFIGURATION" block (operator-ruled 2026-09-01, e0582397). The
# launcher's $RoleLaunch table MUST agree; from 2026-09-01 to 2026-09-06 it did
# not (opus/max, opus/xhigh) and every launcher-started role ran off-config.
_BOOTSTRAP_LAUNCH = {
    "charc": ("director_bootstrap_charc.md", "Fable 5.1", "high", "fable"),
    "rd": ("director_bootstrap_rd.md", "Fable 5.1", "high", "fable"),
    "orchestrator": ("orchestrator_bootstrap.md", "Opus 5", "high", "opus"),
}


def _script_text() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def _launch_config_block(bootstrap: str) -> str:
    text = (_SCRIPTS / bootstrap).read_text(encoding="utf-8")
    start = text.index("LAUNCH CONFIGURATION")
    return text[start:start + 700]


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
    # The orchestrator launches at its bootstrap-declared START config
    # (Opus 5 / high; the Opus-4.x-era xhigh default is retired there).
    assert "claude --model opus --effort high --permission-mode auto" in out
    assert "orchestrator_bootstrap.md" in out             # the bootstrap in the prompt
    assert "DRY RUN" in out                                # no window launched


# --- Task 4: role-aware launch effort + role-aware session name ------------

# Static-content distinguisher (always runs): the launcher's per-role
# $RoleLaunch table agrees with EACH role's bootstrap-declared START config.
# Pinned in BOTH directions (bootstrap text -> expected values, launcher table
# -> the same values) so a change to either surface without the other fails.

@pytest.mark.parametrize("role", sorted(_BOOTSTRAP_LAUNCH))
def test_rolelaunch_table_matches_bootstrap_declaration(role):
    bootstrap, model_name, effort, alias = _BOOTSTRAP_LAUNCH[role]
    block = _launch_config_block(bootstrap)
    # the bootstrap still declares what this test expects (guards the fixture)
    assert f"model  = {model_name}" in block, bootstrap
    assert f"effort = {effort}" in block, bootstrap
    # the launcher's table carries the matching alias + effort for the role
    text = _script_text()
    assert "$RoleLaunch" in text
    assert "$RoleEffort" not in text  # the retired opus/max table is gone
    assert f"'{role}'" in text
    line = next(ln for ln in text.splitlines()
                if ln.strip().startswith(f"'{role}'") and "Model" in ln)
    assert f"Model = '{alias}'" in line, line
    assert f"Effort = '{effort}'" in line, line


def test_rolelaunch_never_starts_at_escalation_effort():
    # xhigh / max are in-session escalations, never START settings (bootstraps).
    text = _script_text()
    table = text[text.index("$RoleLaunch = @{"):]
    table = table[:table.index("\n}")]
    assert "xhigh" not in table and "'max'" not in table, table


# Issue 2 static-content distinguisher (always runs): New-SessionName gives the
# orchestrator a non-'director-' display name; directors keep their scheme.

def test_orchestrator_session_name_not_director_prefixed():
    text = _script_text()
    assert 'return "orchestrator-$stamp"' in text       # orchestrator gets its own name
    assert 'return "director-$role-$stamp"' in text     # directors UNCHANGED


# Behavioral -DryRun (skip-guarded): directors launch fable/high + keep the
# 'director-<role>-<stamp>' name.

def test_dryrun_charc_launches_fable_high_and_director_name():
    if shutil.which("powershell") is None or shutil.which("claude") is None:
        pytest.skip("powershell + claude CLI required for the behavioral DryRun")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SCRIPT),
         "-Role", "charc", "-DryRun"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    out = r.stdout + r.stderr
    # bootstrap START config; director naming unchanged
    assert "claude --model fable --effort high --permission-mode auto" in out
    assert "session name 'director-charc-" in out


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


# --- -Model / -Effort per-launch overrides (skip-guarded DryRun) ------------

def _dryrun(*extra):
    if shutil.which("powershell") is None or shutil.which("claude") is None:
        pytest.skip("powershell + claude CLI required for the behavioral DryRun")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(_SCRIPT), *extra, "-DryRun"],
        capture_output=True, text=True, timeout=60)
    return r, r.stdout + r.stderr


def test_dryrun_model_and_effort_override_apply_to_both_directors():
    r, out = _dryrun("-Role", "both", "-Model", "sonnet", "-Effort", "xhigh")
    assert r.returncode == 0
    # both directors take the override; the role table is bypassed for both
    cmds = [ln for ln in out.splitlines() if "  cmd: " in ln]
    assert len(cmds) == 2 and all(
        "claude --model sonnet --effort xhigh --permission-mode auto" in ln for ln in cmds), out
    assert "--model fable" not in out


def test_dryrun_effort_only_override_keeps_role_model():
    # the two overrides are independent: -Effort alone keeps the role's model
    # (this discriminates against a case-insensitive $model/$Model shadowing
    # bug, which silently ignored the override on first implementation)
    r, out = _dryrun("-Role", "orchestrator", "-Effort", "max")
    assert r.returncode == 0
    assert "claude --model opus --effort max --permission-mode auto" in out


def test_dryrun_rejects_model_outside_validateset():
    r, out = _dryrun("-Role", "charc", "-Model", "turbo")
    assert r.returncode != 0
    assert "ValidateSet" in out and "turbo" in out
    assert "cmd:" not in out  # nothing computed, nothing launched


# --- the spawned shell scrubs the PARENT session's markers (2026-09-07) -----
# A successor launched from INSIDE a Claude session inherits the parent's
# environment; a child claude that sees these starts with transcript saving
# OFF and the parent's messaging identity (the RD self-launch finding).

_SESSION_MARKERS = (
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CLAUDE_PID",
    "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH",
    "CLAUDE_EFFORT",
)


def test_launcher_declares_every_session_marker():
    text = _script_text()
    block = text[text.index("$SessionMarkers = @("):]
    block = block[:block.index(")")]
    for name in _SESSION_MARKERS:
        assert f"'{name}'" in block, name
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in block   # global flag, kept


def test_dryrun_launch_line_scrubs_markers_before_claude():
    r, out = _dryrun("-Role", "charc")
    assert r.returncode == 0
    launch = next(ln for ln in out.splitlines() if "  launch: " in ln)
    claude_at = launch.index("; claude ")
    for name in _SESSION_MARKERS:
        stanza = f"Remove-Item Env:{name} -ErrorAction SilentlyContinue"
        assert stanza in launch, name
        assert launch.index(stanza) < claude_at, f"{name} scrubbed AFTER claude"
    # the role assignment still follows the scrub and precedes claude
    assert launch.index("$env:SWING_ROLE='charc'") < claude_at


# --- CLI auto-update under a live run (coa-chess finding, 2026-09-09) ------
#
# The claude CLI self-updates on ANY invocation from a shell without
# DISABLE_AUTOUPDATER=1. On the shared box it did so twice in eight hours
# (2026-09-08T20:41Z, 2026-09-09T04:41Z; the .old copies beside claude.exe are
# the evidence) under a live coa-chess run, and one game spanned a bump
# mid-game. Two sites in this launcher can move the binary: the SPAWNED role
# shell (every claude invocation it ever makes) and the launcher's OWN
# preflight (`claude --version` / `--help` -- a probe that can mutate its
# subject is not a probe). Both are pinned; a process inherits its parent's
# environment block, not the registry, so the operator's user-level setx does
# not cover a launcher started from an older shell.

_AUTOUPDATE_OFF = "$env:DISABLE_AUTOUPDATER = '1'"


def test_launcher_disables_autoupdate_before_its_own_preflight_probe():
    text = _script_text()
    assert _AUTOUPDATE_OFF in text
    # anchor on the INVOCATION, not the token: prose mentions of the probe
    # sit above the assignment and would false-fail a bare text search
    probe = "(claude --version | Out-String)"
    assert probe in text
    assert text.index(_AUTOUPDATE_OFF) < text.index(probe), (
        "the launcher probes the CLI before it disables the auto-updater")


def test_dryrun_launch_line_disables_autoupdate_after_scrub_before_claude():
    r, out = _dryrun("-Role", "charc")
    assert r.returncode == 0
    launch = next(ln for ln in out.splitlines() if "  launch: " in ln)
    stanza = "$env:DISABLE_AUTOUPDATER='1'"
    assert stanza in launch
    at = launch.index(stanza)
    last_scrub = max(
        launch.index(f"Remove-Item Env:{name} -ErrorAction SilentlyContinue")
        for name in _SESSION_MARKERS)
    assert last_scrub < at, "auto-update disabled BEFORE the marker scrub"
    assert at < launch.index("$env:SWING_ROLE='charc'")
    assert at < launch.index("; claude ")


# --- Named window: one project = one window = three role tabs -------------
#
# Operator-ruled 2026-09-08 after two self-launched rollovers landed the
# successor in the wrong window. '-w 0' resolves to the CALLER's window (or
# the most recently used one), so a rolling-over session placed its successor
# wherever IT happened to sit, and a mis-placed generation propagated. A NAMED
# window ('-w swing') is deterministic from any caller and is created if
# absent. Static pin (always runs) + a DryRun pin on the printed window line.

def test_launcher_opens_tabs_in_the_named_window_never_window_zero():
    text = _script_text()
    assert "'-w', '0'" not in text                       # the wrong-window form is gone
    assert "'-w', $Window, 'new-tab'" in text             # the named form is what launches
    assert "[string]$Window = 'swing'" in text            # one window per project, by default


def test_dryrun_prints_the_named_window_and_honours_override():
    r, out = _dryrun("-Role", "orchestrator")
    assert r.returncode == 0
    assert "window: wt -w swing new-tab --title ORCHESTRATOR" in out
    r, out = _dryrun("-Role", "rd", "-Window", "probe-win")
    assert r.returncode == 0
    assert "window: wt -w probe-win new-tab --title RD" in out
