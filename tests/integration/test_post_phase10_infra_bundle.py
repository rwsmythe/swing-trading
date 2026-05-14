"""Integration smoke for post-phase10-infra-bundle T-6.

Pins the combined acceptance contract of T-2 (cleanup-script
-DeregisterFirst) + T-3 (pytest-xdist baseline) at a single
integration-test boundary. Neither task ships production code, so the
smoke tests assert configuration + script-source invariants rather than
runtime behavior.

Operator-witnessed gate S2 (elevated PowerShell) exercises the
cleanup-script extension end-to-end against the 7 worktree husks; this
test file is the regression boundary that catches accidental rollback
of either task's configuration / source-string contracts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cleanup_script_carries_deregister_first_pre_pass_after_t2() -> None:
    """T-2 contract: the script source must declare -DeregisterFirst + the
    pre-pass loop must exist + the dry-run branch + the safety filter."""
    source = (REPO_ROOT / "cleanup-locked-scratch-dirs.ps1").read_text(encoding="utf-8")
    assert "[switch]$DeregisterFirst" in source
    assert "$script:DeregisterPathPattern" in source
    assert "if ($DeregisterFirst)" in source
    assert "git -C $ProjectRoot worktree remove --force" in source
    assert "[DRY-RUN] Would run: git -C" in source
    # The pre-pass must run BEFORE the orphan-discovery (so deregister-induced
    # orphans land in the candidates set)
    pre_pass_idx = source.index("if ($DeregisterFirst)")
    orphan_idx = source.index("Discovery: orphaned worktree subdirs")
    assert pre_pass_idx < orphan_idx, (
        "T-2 ordering invariant: the -DeregisterFirst pre-pass MUST run "
        "BEFORE the orphan-discovery pass so deregister-induced orphans "
        "are picked up in the same script invocation."
    )


def test_pyproject_carries_xdist_baseline_after_t3() -> None:
    """T-3 contract: pyproject declares xdist dev dep + addopts include -n auto."""
    source = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pytest-xdist>=3.5.0" in source
    addopts_match = re.search(r'addopts\s*=\s*"([^"]+)"', source)
    assert addopts_match is not None
    assert "-n auto" in addopts_match.group(1)


def test_pytest_xdist_importable_with_version_floor() -> None:
    """T-3 runtime contract: pytest-xdist must be importable + >= 3.5.0."""
    xdist = pytest.importorskip("xdist", minversion="3.5.0")
    version_tuple = tuple(int(x) for x in xdist.__version__.split(".")[:2])
    assert version_tuple >= (3, 5)
