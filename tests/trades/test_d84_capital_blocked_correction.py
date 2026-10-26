"""D84 R-T4.6 (RD B2, `20261026T084545Z`) -- the H4 mislabel REMEDY is reachable.

Plan section 0.3 names the Demand-C correction surface as the remedy for an H4
mislabel. That remedy is reachable from the D84 boundary only because the
citation seam reads the BUCKET alone: `cohort_provenance_correction.py`
admits an `aplus` cited candidate and re-derives `APLUS_TRADE_ORIGIN` from the
bucket, so a risk-flagged A+ candidate becomes citable. Nothing asserted that
reachability; this test does. It is a TEST edit inside the S1 envelope: no code
changes at the seam.

Shape: `tests/trades/test_cohort_provenance_write.py::
test_apply_writes_the_three_keys_and_one_audit_row`, on the KOD roster (the
18-criterion roster all `pass` except `risk_feasibility` = `fail`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.funnel import APLUS_TRADE_ORIGIN
from swing.trades.cohort_provenance_correction import correct_cohort_provenance
from tests.trades._cohort_provenance_fixtures import build_cadl_case

KOD_H4_LABEL = (
    "Capital-blocked: smaller-position test (aplus); failed: risk_feasibility")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def test_a_risk_flagged_aplus_citation_is_ADMITTED_with_the_H4_label(conn) -> None:
    """R-T4.6. The correction is ADMITTED, the derived label is exactly the H4
    label, and the written origin is `APLUS_TRADE_ORIGIN`. Before D84 the
    matcher labelled this candidate H1 (`A+ baseline (aplus); failed:
    risk_feasibility`), because H1 was `bucket == "aplus"` alone."""
    ids = build_cadl_case(conn, bucket="aplus",
                          non_pass={"risk_feasibility": "fail"})
    if conn.in_transaction:
        conn.commit()
    result = correct_cohort_provenance(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason="the framework's own contemporaneous record",
    )
    assert result.already_applied is False
    assert conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin FROM trades "
        "WHERE id = ?", (ids["trade_id"],)).fetchone() == (
        KOD_H4_LABEL, ids["candidate_id"], APLUS_TRADE_ORIGIN)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1
