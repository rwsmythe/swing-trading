"""pytest-xdist baseline assertions.

Post-phase10-infra-bundle T-3 (2026-05-13). Pins the xdist version floor
declared in pyproject.toml + verifies the test-suite addopts include
``-n auto`` so default invocations parallelize.

This test does NOT measure wall-clock; that is the operator-witnessed S1
gate's responsibility (3 serial + 3 parallel runs, median ratio per
dispatch brief §0.7). This test only verifies the configuration is in
place + the package is importable.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_pytest_xdist_is_installed_and_modern() -> None:
    """pytest-xdist must be importable AND >= 3.5.0 for xdist_group support."""
    xdist = pytest.importorskip("xdist", minversion="3.5.0")
    # Version string check (importorskip alone doesn't enforce min)
    version_tuple = tuple(int(x) for x in xdist.__version__.split(".")[:2])
    assert version_tuple >= (3, 5), (
        f"pytest-xdist version {xdist.__version__} too old; T-3 requires "
        f">=3.5.0 for xdist_group + worker-isolated tmp_path_factory semantics"
    )


def test_pyproject_addopts_enables_xdist_by_default() -> None:
    """pyproject.toml's pytest addopts must include ``-n auto`` so default
    invocations parallelize per T-3 design.

    Operator can override per-call with ``-n 0`` for debug workflows; that
    knob is documented in the inline comment above the addopts line.
    """
    source = PYPROJECT.read_text(encoding="utf-8")
    # Match the `addopts = "..."` line under `[tool.pytest.ini_options]`
    match = re.search(r'addopts\s*=\s*"([^"]+)"', source)
    assert match is not None, "pyproject.toml missing pytest addopts line"
    addopts = match.group(1)
    assert "-n auto" in addopts, (
        f"pyproject.toml pytest addopts does not enable xdist `-n auto`: "
        f"{addopts!r}; T-3 expects parallel-by-default."
    )


def test_pyproject_declares_xdist_in_dev_extras() -> None:
    """pytest-xdist must appear in [project.optional-dependencies].dev."""
    source = PYPROJECT.read_text(encoding="utf-8")
    assert "pytest-xdist" in source, (
        "pyproject.toml [project.optional-dependencies].dev does not declare "
        "pytest-xdist; T-3 expects the dependency in the dev extras."
    )
