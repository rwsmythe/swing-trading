"""19-B Task 1 -- the single comms-root seam + the autouse suite-isolation guard.

The seam ``research_health._effective_comms_root`` is the ONE resolver every push
path consults (Codex R2 CRITICAL), so the autouse ``_guard_research_health_comms``
fixture (tests/conftest.py) can redirect ANY real-repo-comms resolution to tmp --
covering the default ``comms_root=None`` path AND an explicit
``comms_root=<repo>/comms``. These tests PROVE the guard closes both.
"""
from __future__ import annotations

from pathlib import Path

import swing.monitoring.research_health as rh
from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    push_research_health_red_to_rd,
)

_REPO_COMMS = (Path(rh.__file__).resolve().parents[2] / "comms").resolve()


def _red_status():
    return ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="red",
        summary="1 non-finite", detail="ZZZ@2026-06-20")])


def test_effective_comms_root_guarded_redirects_real_repo_comms(tmp_path):
    # Under the autouse fixture: BOTH the default (None -> repo comms) AND an
    # explicit repo-comms path resolve OUTSIDE the real repo comms tree; a tmp
    # path passes through unchanged. Pre-fix (no seam-guard) both return the real
    # repo comms -> would fail the "not under repo comms" assertion.
    for arg in (None, _REPO_COMMS):
        resolved = Path(rh._effective_comms_root(arg)).resolve()
        assert resolved != _REPO_COMMS
        assert _REPO_COMMS not in resolved.parents
    passthrough = tmp_path / "my_comms"
    assert Path(rh._effective_comms_root(passthrough)).resolve() == passthrough.resolve()


def test_push_with_explicit_real_comms_lands_in_tmp(tmp_path):
    # The exact bypass Codex R2 CRITICAL raised: a test that explicitly passes the
    # REAL repo comms as comms_root must still NOT write there -- the seam guard
    # redirects to tmp. Assert NOTHING landed under the real repo comms.
    before = (
        {p for p in _REPO_COMMS.rglob("*") if p.is_file()}
        if _REPO_COMMS.exists() else set()
    )
    push_research_health_red_to_rd(
        _red_status(), run_id=1, prior_overall="green", comms_root=_REPO_COMMS)
    after = (
        {p for p in _REPO_COMMS.rglob("*") if p.is_file()}
        if _REPO_COMMS.exists() else set()
    )
    assert after == before  # no real-repo-comms mutation
