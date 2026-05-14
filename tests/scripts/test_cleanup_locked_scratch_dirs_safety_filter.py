r"""Validate the cleanup-locked-scratch-dirs.ps1 -DeregisterFirst safety filter.

Post-phase10-infra-bundle T-2 (2026-05-13). PowerShell test infrastructure is
heavy and elevation-gated; instead we extract the safety-filter regex from
the script source and verify match/no-match semantics at the string level.

The pattern is BINDING per the dispatch brief §0.6: only paths matching
the in-script ``$script:DeregisterPathPattern`` (`.worktrees/phase\d+...` or
`.claude/worktrees/phase\d+...`) are admitted for deregister; any other
path (in-flight branches, polish
bundles, the post-phase10-infra-bundle worktree itself) is left alone.

This test reads the regex pattern directly from the .ps1 source so that any
future widening or tightening of the filter is reflected immediately and
caught by the assertions below (treating each as a regression boundary).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "cleanup-locked-scratch-dirs.ps1"


def _read_safety_filter_pattern() -> re.Pattern[str]:
    """Extract the ``$script:DeregisterPathPattern`` regex from the .ps1 source.

    The PowerShell pattern uses single quotes (no interpolation); we translate
    the embedded ``\\d`` and character-class syntax to a Python ``re`` pattern
    by treating the literal string as a Python regex. PowerShell's ``-match``
    is case-insensitive by default; ``re.IGNORECASE`` mirrors that.
    """
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"\$script:DeregisterPathPattern\s*=\s*'([^']+)'",
        source,
    )
    if match is None:
        raise AssertionError(
            "Could not locate $script:DeregisterPathPattern in "
            f"{SCRIPT_PATH}; T-2 regex extraction needs to be re-anchored."
        )
    return re.compile(match.group(1), flags=re.IGNORECASE)


@pytest.fixture(scope="module")
def safety_filter() -> re.Pattern[str]:
    return _read_safety_filter_pattern()


# --- ADMIT: phase\d+-* under .worktrees/ or .claude/worktrees/ ---

@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-B-reconciliation-depth",
        r"C:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-C-hypothesis-and-equity",
        r"C:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-D-capital-maturity-funnel",
        r"C:\Users\rwsmy\swing-trading\.claude\worktrees\phase8-v1-polish",
        # Forward-slash variant (git can emit either separator on Windows)
        "C:/Users/rwsmy/swing-trading/.worktrees/phase9-bundle-E-polish-and-phase10-handoff",
        # Underscore separator (defense-in-depth — not currently used, but
        # the pattern admits both `phase\d+-` and `phase\d+_` to mirror
        # how phase-named branches occasionally use either glyph)
        r"C:\repo\.worktrees\phase11_bundle_a_setup",
    ],
)
def test_safety_filter_admits_phase_worktrees(
    safety_filter: re.Pattern[str], path: str
) -> None:
    r"""Phase\d+-* worktrees under .worktrees/ OR .claude/worktrees/ admit."""
    assert safety_filter.search(path) is not None, (
        f"Safety filter rejected expected-admit path: {path}"
    )


# --- REJECT: anything else ---

@pytest.mark.parametrize(
    "path",
    [
        # This bundle's own worktree — MUST be rejected; we are running INSIDE it
        r"C:\Users\rwsmy\swing-trading\.worktrees\post-phase10-infra-bundle",
        # Polish bundles and other dated branches — not phase\d+-*
        r"C:\Users\rwsmy\swing-trading\.worktrees\polish-bundle-2026-05-09",
        r"C:\Users\rwsmy\swing-trading\.worktrees\polish-bundle-2026-05-10",
        r"C:\Users\rwsmy\swing-trading\.worktrees\3e8-bundle-1-advisory-parity",
        r"C:\Users\rwsmy\swing-trading\.worktrees\3e16-cadence-review-trade-summary",
        # Investigation / diagnostic branches
        r"C:\Users\rwsmy\swing-trading\.worktrees\tos-import-diagnostic",
        r"C:\Users\rwsmy\swing-trading\.worktrees\3e8-sell-side-advisories-investigation",
        # Top-level scratch dirs — the .worktrees/ prefix MUST be present
        r"C:\Users\rwsmy\swing-trading\.tmp-scratch",
        r"C:\Users\rwsmy\swing-trading\.pytest_tmp",
        # Main repo path (no .worktrees/ segment)
        r"C:\Users\rwsmy\swing-trading",
        # Phase\d+-* under arbitrary directory — must require .worktrees/ or .claude/worktrees/
        r"C:\Users\rwsmy\swing-trading\experiments\phase9-something",
        # Almost-phase: lowercase "phase" but no digits
        r"C:\repo\.worktrees\phase-bundle-test",
        # phase\d but no separator after
        r"C:\repo\.worktrees\phase10",
    ],
)
def test_safety_filter_rejects_non_phase_paths(
    safety_filter: re.Pattern[str], path: str
) -> None:
    r"""Non-phase\d+-* paths MUST be rejected (defense against accidental deregister)."""
    assert safety_filter.search(path) is None, (
        f"Safety filter ADMITTED unexpected path (regression in T-2 regex): {path}"
    )


def test_safety_filter_rejects_own_worktree_explicitly(
    safety_filter: re.Pattern[str],
) -> None:
    """BINDING per dispatch brief §0.6: this bundle's own worktree name
    (`post-phase10-infra-bundle`) does NOT start with `phase\\d+-` and MUST
    be rejected even when invoked from inside it via -DeregisterFirst.
    """
    own_worktree = (
        r"C:\Users\rwsmy\swing-trading\.worktrees\post-phase10-infra-bundle"
    )
    assert safety_filter.search(own_worktree) is None


def test_script_file_present_with_deregister_first_param() -> None:
    """Smoke test: the script file exists and declares the -DeregisterFirst switch."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "[switch]$DeregisterFirst" in source, (
        "cleanup-locked-scratch-dirs.ps1 missing -DeregisterFirst param declaration"
    )
    # The deregister loop must check the switch
    assert "if ($DeregisterFirst)" in source, (
        "cleanup-locked-scratch-dirs.ps1 missing -DeregisterFirst gate on pre-pass"
    )
    # DryRun + DeregisterFirst combination handled
    assert "[DRY-RUN] Would run: git -C" in source, (
        "cleanup-locked-scratch-dirs.ps1 missing -DryRun branch for deregister pre-pass"
    )
