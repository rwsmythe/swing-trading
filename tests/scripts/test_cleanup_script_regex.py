r"""Validate the cleanup-locked-scratch-dirs.ps1 -DeregisterFirst regex widening.

Phase 12 Sub-bundle A T-A.4 (2026-05-15). Sub-bundle B/C/D Schwab-arc husks
were skipped during 2026-05-15 cleanup because the safety-filter regex only
matched `phase\d+-*` paths. Widened to also match `schwab[-{arc?}]-bundle-*`
naming convention while preserving backward compatibility for `phase\d+-*`.

This file complements ``test_cleanup_locked_scratch_dirs_safety_filter.py``
(Phase 10 infra-bundle T-2 precedent). Same extraction pattern: parse the
``$script:DeregisterPathPattern`` literal from the .ps1 source + compile
as a Python regex + assert match/no-match semantics on candidate paths.

The pattern is BINDING — it gates a destructive ``git worktree remove
--force`` invocation. Any future widening or tightening MUST land discriminating
tests here first.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "cleanup-locked-scratch-dirs.ps1"


def _read_safety_filter_pattern() -> re.Pattern[str]:
    """Extract the ``$script:DeregisterPathPattern`` regex from the .ps1 source.

    Mirrors the established extraction pattern in
    ``test_cleanup_locked_scratch_dirs_safety_filter.py``. PowerShell's
    ``-match`` is case-insensitive by default; ``re.IGNORECASE`` mirrors that.
    """
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"\$script:DeregisterPathPattern\s*=\s*'([^']+)'",
        source,
    )
    if match is None:
        raise AssertionError(
            "Could not locate $script:DeregisterPathPattern in "
            f"{SCRIPT_PATH}; T-A.4 regex extraction needs to be re-anchored."
        )
    return re.compile(match.group(1), flags=re.IGNORECASE)


@pytest.fixture(scope="module")
def safety_filter() -> re.Pattern[str]:
    return _read_safety_filter_pattern()


# --- Backward-compat: existing phase\d+-* admission ---


def test_pattern_matches_phase9_bundle_a_worktree(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 1: phase{NN}-bundle-* still admits (backward compat)."""
    path = "C:/Users/rwsmy/swing-trading/.worktrees/phase9-bundle-A-foo"
    assert safety_filter.search(path) is not None, (
        f"Backward-compat regression: phase9-bundle-* path not matched: {path}"
    )


def test_pattern_matches_phase10_bundle_e_historical_path(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 8: phase10-bundle-E full historical name admits (backward compat)."""
    path = (
        "C:/Users/rwsmy/swing-trading/.worktrees/"
        "phase10-bundle-E-process-grade-trend-and-polish"
    )
    assert safety_filter.search(path) is not None, (
        f"Backward-compat regression: phase10-bundle-E path not matched: {path}"
    )


# --- New: schwab-bundle-* admission ---


def test_pattern_matches_schwab_bundle_a_foundational(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 2: Sub-bundle A's actual name admits."""
    path = (
        "C:/Users/rwsmy/swing-trading/.worktrees/schwab-bundle-A-foundational"
    )
    assert safety_filter.search(path) is not None, (
        f"T-A.4 regression: schwab-bundle-A path not matched: {path}"
    )


def test_pattern_matches_schwab_bundle_b_trader_and_snapshot(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 3: Sub-bundle B's actual name admits."""
    path = (
        "C:/Users/rwsmy/swing-trading/.worktrees/"
        "schwab-bundle-B-trader-and-snapshot"
    )
    assert safety_filter.search(path) is not None, (
        f"T-A.4 regression: schwab-bundle-B path not matched: {path}"
    )


def test_pattern_matches_future_schwab_bundle_x(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 4: forward-compat for future Schwab-arc bundles."""
    path = "C:/Users/rwsmy/swing-trading/.worktrees/schwab-bundle-X-anything"
    assert safety_filter.search(path) is not None, (
        f"T-A.4 regression: schwab-bundle-X future name not matched: {path}"
    )


def test_pattern_matches_schwab_bundle_a_no_tail(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 7 (edge): schwab-bundle-A with no trailing descriptor admits.

    The `[-_]` separator after the alternation group only requires a hyphen
    or underscore — the rest of the bundle name (e.g., `-A`, `-foundational`)
    sits beyond the matched prefix.
    """
    path = "C:/Users/rwsmy/swing-trading/.worktrees/schwab-bundle-A"
    assert safety_filter.search(path) is not None, (
        f"T-A.4 regression: schwab-bundle-A (no tail) not matched: {path}"
    )


# --- Rejection (defense-in-depth) ---


def test_pattern_rejects_unrelated_branch_name(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 5: arbitrary branch names MUST be rejected."""
    path = "C:/Users/rwsmy/swing-trading/.worktrees/random-branch-name"
    assert safety_filter.search(path) is None, (
        f"T-A.4 regression: unrelated path admitted (should be rejected): {path}"
    )


def test_pattern_rejects_project_root_itself(
    safety_filter: re.Pattern[str],
) -> None:
    """T-A.4 Test 6: the project root itself MUST be rejected (own-worktree family)."""
    path = "C:/Users/rwsmy/swing-trading"
    assert safety_filter.search(path) is None, (
        f"T-A.4 regression: project root admitted (should be rejected): {path}"
    )
