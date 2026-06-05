"""The PROVABLE-aplus ladder (plan section 4): all six branches.

Discriminating axis: each case asserts INCLUDE vs EXCLUDE for a pe row whose
ONLY difference is which ladder branch it lands in. A no-op predicate (TRUE for
all) would fail the EXCLUDE cases; a naive `OR c.id IS NULL` would fail the
deleted-candidate watch case (it would leak).
"""
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE


def _db(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    return conn


def _run(conn, run_id, *, eval_run_id, asof, session, finished_ts):
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES (?,?,?,?,1,1,0,0,0,0)",
        (eval_run_id, session + "T18:00:00", asof, session))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, lease_token, state, "
        "evaluation_run_id) VALUES (?,?,?,'manual',?,?,?,?,?)",
        (run_id, session + "T18:00:00", finished_ts, asof, session,
         f"tok{run_id}", "complete", eval_run_id))


def _cand(conn, eval_run_id, ticker, bucket):
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        "rs_return_12w_vs_spy, rs_method) VALUES (?,?,?,15.0,2.5,3,5.0,40.0,"
        "85,12.0,'universe')",
        (eval_run_id, ticker, bucket))


def _pe(conn, run_id, ticker, pattern_class="vcp", score=0.7):
    # pattern_evaluations NOT-NULL cols (migration 0020:230-251, VERIFIED at
    # writing-plans): pipeline_run_id, ticker, pattern_class (CHECK detector
    # classes), detector_version, geometric_score, geometric_score_json,
    # composite_score, structural_evidence_json, feature_distribution_log_json,
    # window_start_date, window_end_date, created_at. There is NO `surface`
    # column on this table (that is chart_renders).
    cur = conn.execute(
        "INSERT INTO pattern_evaluations (pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) VALUES (?,?,?, 'v1', 0.7, '{}', ?, '{}', '{}', "
        "'2026-05-01','2026-05-20','2026-05-20T18:00:00')",
        (run_id, ticker, pattern_class, score))
    return cur.lastrowid


def _pde(conn, run_id, ticker, bucket, pattern_class="vcp", detection_date=None):
    # detection_date defaults to the run's action_session_date so the durable
    # historical-gate boundary (MIN(detection_date) over watch PDEs) reflects the
    # run's session -- a watch PDE on a later widened run sets a later boundary.
    import json
    if detection_date is None:
        r = conn.execute(
            "SELECT action_session_date FROM pipeline_runs WHERE id = ?",
            (run_id,)).fetchone()
        detection_date = r[0] if r is not None else "2026-05-20"
    conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date, "
        "data_asof_date, pattern_class, structural_anchors_json, "
        "composite_score, detector_version, finviz_screen_state, source, "
        "per_pattern_metadata_json, pipeline_run_id, created_at) VALUES "
        "(?,?,?,?,'{}',0.7,'v1',?, 'pipeline','{}',?, '2026-05-20T00:00:00Z')",
        (ticker, detection_date, "2026-05-19", pattern_class,
         json.dumps({"bucket": bucket}), run_id))


def _included_ids(conn) -> set[int]:
    rows = conn.execute(
        f"SELECT pe.id FROM pattern_evaluations pe "
        f"WHERE {PROVABLE_APLUS_PE_PREDICATE}").fetchall()
    return {r[0] for r in rows}


def test_ladder_all_six_branches(tmp_path):
    conn = _db(tmp_path)
    # A widen has shipped: run 2 (a later session) emitted a watch PDE, so the
    # durable historical boundary is MIN(detection_date) over watch PDEs =
    # run 2's action_session_date (2026-06-03).
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")   # pre-widen run
    _run(conn, 2, eval_run_id=2, asof="2026-06-02", session="2026-06-03",
         finished_ts="2026-06-03T18:30:00")   # first widened run (has watch PDE)
    # Case A (step 1 INCLUDE): candidate present, bucket aplus.
    _cand(conn, 1, "AAA", "aplus"); a = _pe(conn, 1, "AAA")
    # Case B (step 1 path -> EXCLUDE): candidate present, bucket watch.
    _cand(conn, 2, "BBB", "watch"); b = _pe(conn, 2, "BBB"); _pde(conn, 2, "BBB", "watch")
    # Case C (step 2 INCLUDE): candidate GONE, PDE bucket aplus.
    _cand(conn, 2, "CCC", "aplus"); c = _pe(conn, 2, "CCC"); _pde(conn, 2, "CCC", "aplus")
    conn.execute("DELETE FROM candidates WHERE ticker='CCC'")
    # Case D (step 2 path -> EXCLUDE): candidate GONE, PDE bucket watch (the
    # Codex-R2 leak vector: must NOT leak).
    _cand(conn, 2, "DDD", "watch"); d = _pe(conn, 2, "DDD"); _pde(conn, 2, "DDD", "watch")
    conn.execute("DELETE FROM candidates WHERE ticker='DDD'")
    # Case E (step 3 INCLUDE): pre-widen historical PE, NO candidate, NO PDE,
    # run strictly before the boundary.
    e = _pe(conn, 1, "EEE")
    # Case F (step 4 EXCLUDE): post-widen PE on the widened run, NO candidate,
    # NO PDE (pathological), run NOT before the boundary.
    f = _pe(conn, 2, "FFF")
    conn.commit()
    got = _included_ids(conn)
    assert a in got   # step 1 aplus
    assert b not in got   # step 1 watch
    assert c in got   # step 2 aplus
    assert d not in got   # step 2 watch (no leak)
    assert e in got   # step 3 historical
    assert f not in got   # step 4 unprovable


def test_ladder_no_widen_yet_includes_historical(tmp_path):
    # Boundary NULL (no watch PDE anywhere) => historical neither-cand-nor-PDE
    # row INCLUDED.
    conn = _db(tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    e = _pe(conn, 1, "EEE")  # no candidate, no PDE, no watch run exists
    conn.commit()
    assert e in _included_ids(conn)


def test_ladder_first_widened_run_finished_ts_null_excludes_unprovable(tmp_path):
    # Codex R1 MAJOR #1 regression: the first widened run's finished_ts is still
    # NULL (run crashed / in progress) but it HAS a watch PDE. An unprovable
    # same-run PE (no candidate, no PDE) must be EXCLUDED. The durable boundary
    # (action_session_date < MIN(detection_date)) does NOT use finished_ts at
    # all, so a NULL finished_ts is irrelevant; the same-session PE is excluded
    # because its action_session_date == the boundary (not strictly before).
    conn = _db(tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")          # pre-widen, finished
    # run 2 = first widened run, finished_ts NULL:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES "
        "(2,'2026-06-03T18:00:00','2026-06-02','2026-06-03',1,0,1,0,0,0)")
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, lease_token, state, "
        "evaluation_run_id) VALUES "
        "(2,'2026-06-03T18:00:00',NULL,'manual','2026-06-02','2026-06-03',"
        "'tok2','running',2)")
    e = _pe(conn, 1, "EEE")           # pre-widen historical -> INCLUDE
    _pe(conn, 2, "GGG"); _pde(conn, 2, "GGG", "watch")  # widened run has a watch PDE
    f = _pe(conn, 2, "FFF")           # unprovable same-run PE -> EXCLUDE
    conn.commit()
    got = _included_ids(conn)
    assert e in got
    assert f not in got


def test_ladder_survives_run_pruning_null_pde_run_id(tmp_path):
    # Codex R3 MAJOR regression: PDE.pipeline_run_id is ON DELETE SET NULL, so
    # pruning the FIRST widened run NULLs its surviving watch PDE's run id. The
    # DURABLE detection_date boundary must NOT move -> a pre-widen historical
    # row stays INCLUDED and a post-widen gap-run unprovable watch row stays
    # EXCLUDED even after the null-out.
    conn = _db(tmp_path)
    _run(conn, 3, eval_run_id=3, asof="2026-05-18", session="2026-05-19",
         finished_ts="2026-05-19T18:30:00")   # pre-widen
    _run(conn, 5, eval_run_id=5, asof="2026-06-02", session="2026-06-03",
         finished_ts="2026-06-03T18:30:00")   # first widened
    _run(conn, 6, eval_run_id=6, asof="2026-06-03", session="2026-06-04",
         finished_ts="2026-06-04T18:30:00")   # widened gap run
    _pde(conn, 5, "WW1", "watch")             # detection_date = 2026-06-03
    hist = _pe(conn, 3, "HIS")                # pre-widen historical -> INCLUDE
    leak = _pe(conn, 6, "LEK")                # post-widen unprovable watch -> EXCLUDE
    # Simulate run 5 pruning: NULL its surviving watch PDE's pipeline_run_id.
    conn.execute(
        "UPDATE pattern_detection_events SET pipeline_run_id = NULL "
        "WHERE ticker = 'WW1'")
    conn.commit()
    got = _included_ids(conn)
    assert hist in got      # boundary (detection_date 2026-06-03) is durable
    assert leak not in got  # gap-run unprovable watch NOT leaked
