from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
# The cohort lives in the private _build_outcome_distribution(conn, *,
# pattern_class, current_evaluation_id, composite_score, cohort_limit=20)
# (review_form.py:275-280). This test drives it directly to assert the
# filter-before-LIMIT property end-to-end.
from swing.web.view_models.patterns.review_form import _build_outcome_distribution  # noqa
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def test_cohort_filter_before_limit_drives_production(tmp_path):
    """Drives the PRODUCTION _build_outcome_distribution (NOT a re-implemented
    query -- Codex R1 MAJOR #2 closed the tautology). Seed 10 aplus PEs (lower
    pe.id) + 20 watch PEs (HIGHER pe.id) at the same composite score, cohort
    LIMIT=20. The returned row's `n` (= cohort size) discriminates all 3 states:
      - FIXED (filter-BEFORE-LIMIT): cohort = the 10 aplus  -> n == 10
      - CURRENT/unfiltered: cohort = top-20 by id = the 20 watch -> n == 20
      - BROKEN filter-AFTER-LIMIT: top-20 (20 watch) then aplus-filter = 0
        -> cohort_n == 0 (< 5 suppression path).
    Asserting n == 10 fails BOTH the current code AND the after-LIMIT bug."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    score = 0.70
    for i in range(10):   # 10 aplus, LOWER ids (inserted first)
        _cand(conn, 1, f"A{i}", "aplus"); _pe(conn, 1, f"A{i}", score=score)
    for i in range(20):   # 20 watch, HIGHER ids
        _cand(conn, 1, f"W{i}", "watch"); _pe(conn, 1, f"W{i}", score=score)
        _pde(conn, 1, f"W{i}", "watch")
    _cand(conn, 1, "CUR", "aplus"); cur = _pe(conn, 1, "CUR", score=score)
    conn.commit()
    (row,) = _build_outcome_distribution(
        conn, pattern_class="vcp", current_evaluation_id=cur,
        composite_score=score, cohort_limit=20)
    assert row.n == 10   # filter-before-LIMIT kept all 10 aplus, dropped watch
