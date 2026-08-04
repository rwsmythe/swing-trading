"""D29 rider -- the PRESERVED ORIGINAL criterion as PROVENANCE DETAIL.

RD ruling 2026-08-04: "the amended text renders with its 0034 marker
(already shipped); the ORIGINAL becomes accessible as provenance detail --
a secondary render (detail row / title attribute / expandable), NOT inline
prose -- and it lands WITH the D29 four-site fix, which touches exactly
these surfaces."

So these tests pin BOTH halves:
  * the original IS reachable on each of the three criterion-rendering
    surfaces, and
  * it is NOT inline beside the live criterion -- it sits behind a
    collapsed ``<details>`` affordance, and a never-amended cohort renders
    NO such affordance at all (the migration-0034 NULL semantic:
    never-amended, not unknown).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.tier import (
    APLUS_COHORT,
    compute_deviation_outcome,
    compute_tier_comparison,
)
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from tests.data.test_migration_0034_h1_criteria_amendment import (
    PREREGISTERED_H1_DECISION_CRITERIA,
)

_PROVENANCE_CLASS = "preregistered-criterion"
_NEVER_AMENDED = "Sub-A+ VCP-not-formed"


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "d29_provenance.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


# ---------------------------------------------------------------------------
# The VMs carry it
# ---------------------------------------------------------------------------

def test_tier_comparison_carries_the_preserved_original(
    conn: sqlite3.Connection,
):
    result = compute_tier_comparison(conn)
    by_name = {c.cohort_name: c for c in result.cohorts}
    assert by_name[APLUS_COHORT].preregistered_decision_criteria == (
        PREREGISTERED_H1_DECISION_CRITERIA
    )
    # NULL on a never-amended row means NEVER AMENDED, not unknown.
    assert by_name[_NEVER_AMENDED].preregistered_decision_criteria is None


def test_deviation_outcome_carries_the_preserved_original(
    conn: sqlite3.Connection,
):
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    assert by_name[APLUS_COHORT].preregistered_decision_criteria == (
        PREREGISTERED_H1_DECISION_CRITERIA
    )
    assert by_name[_NEVER_AMENDED].preregistered_decision_criteria is None


def test_progress_card_vm_carries_the_preserved_original(conn, cfg):
    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    by_name = {c.cohort_name: c for c in vm.cohorts}
    assert by_name[APLUS_COHORT].preregistered_decision_criteria == (
        PREREGISTERED_H1_DECISION_CRITERIA
    )
    assert by_name[_NEVER_AMENDED].preregistered_decision_criteria is None
