from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.metrics.pattern_outcomes import _count_reached_1r_hit_stop
# Reuse the ladder test's seed helpers via a tiny local copy or import.
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def _exemplar(conn, ticker, pattern_class="vcp"):
    # NOT-NULL-no-default cols verified against live v24: timeframe,
    # structural_evidence_json, created_by are required (Expansion #4
    # SQL-skeleton-column-verify).
    conn.execute(
        "INSERT INTO pattern_exemplars (ticker, timeframe, start_date, "
        "end_date, proposed_pattern_class, label_source, final_decision, "
        "labeler_evidence_json, structural_evidence_json, created_by, "
        "created_at) "
        "VALUES (?, 'daily', '2026-05-01','2026-05-20', ?, 'claude_silver',"
        "'confirmed', '{}', '{}', 'synthetic_generator', "
        "'2026-05-20T00:00:00Z')",
        (ticker, pattern_class))


def test_denominator_excludes_watch_origin(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    _exemplar(conn, "AAA"); _exemplar(conn, "BBB")
    _cand(conn, 1, "AAA", "aplus"); _pe(conn, 1, "AAA")        # aplus-origin
    _cand(conn, 1, "BBB", "watch"); _pe(conn, 1, "BBB"); _pde(conn, 1, "BBB", "watch")
    conn.commit()
    denom, _r, _h = _count_reached_1r_hit_stop(conn, pattern_class="vcp")
    # Post-isolation: ONLY the aplus PE counts (denom == 1). Pre-isolation
    # (no filter) would count both (denom == 2). Discriminating axis: the
    # watch PE's presence in the denominator.
    assert denom == 1
