"""D104 test 1u -- the review form's outcome cohort under a kind-2 correction.

PREMISE CORRECTION (recorded in the arc ledger, cell 4). The plan's section
0.3 says `_build_outcome_distribution` attributes a trade to the DECISION
night's PE row "for both a T2-named night and a kind-2 correction". Read at
the code: the cohort is filtered by `PROVABLE_APLUS_PE_PREDICATE`
(`review_form.py`, the aplus-isolation arc), and a kind-2 correction moves a
WATCH anchor to a WATCH fire -- so on the live shape neither SG PE row is in
the cohort before or after the correction, and the reading is UNCHANGED.

So the test is two halves:
  (i)  LIVE SHAPE: SG's PE rows on runs 207 and 208 with watch candidates
       (and watch detection events) -- the hit-stop share is identical before
       and after ``correct_watch_fire_label``; nothing shifts.
  (ii) MECHANISM CONTROL (a synthetic state, named as such): only run 207's
       SG PE row is made provably aplus by an aplus detection event. Before
       the correction the trade's candidate is 15980 (run 208), whose row is
       NOT in the cohort, so no hit-stop counts; after, it is 15901 (run 207)
       and the hit-stop counts on 207's row. That proves the join FOLLOWS
       ``trades.candidate_id`` -- so (i)'s "unchanged" is the aplus-only
       predicate's doing, not a dead join.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.cohort_provenance_correction import correct_watch_fire_label
from swing.web.view_models.patterns.review_form import (
    _build_outcome_distribution,
)
from tests.trades._cohort_provenance_fixtures import (
    SG_FIRE_CANDIDATE_ID,
    SG_TRADE_ID,
    build_sg_case,
)

SCORE = 0.70
PADDING = ("PADA", "PADB", "PADC", "PADD", "PADE")


def _pe(conn, run_id: int, ticker: str) -> int:
    cur = conn.execute(
        "INSERT INTO pattern_evaluations (pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) VALUES (?, ?, 'vcp', 'v1', 0.7, '{}', ?, '{}', '{}', "
        "'2026-10-01', '2026-11-04', '2026-11-04T18:00:00')",
        (run_id, ticker, SCORE))
    return int(cur.lastrowid)


def _pde(conn, run_id: int, ticker: str, bucket: str, session: str) -> None:
    conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date, "
        "data_asof_date, pattern_class, structural_anchors_json, "
        "composite_score, detector_version, finviz_screen_state, source, "
        "per_pattern_metadata_json, pipeline_run_id, created_at) VALUES "
        "(?, ?, ?, 'vcp', '{}', 0.7, 'v1', ?, 'pipeline', '{}', ?, "
        "'2026-11-04T00:00:00Z')",
        (ticker, session, session, json.dumps({"bucket": bucket}), run_id))


def _world(tmp_path: Path, name: str, *, aplus_pde_on_207: bool) -> tuple:
    root = tmp_path / name
    root.mkdir()
    conn = ensure_schema(root / "swing.db", backup_dir=root / "bak")
    build_sg_case(conn)
    # Padding: five provably-aplus PE rows of other tickers on run 207, so
    # the cohort clears the n >= 5 suppression floor.
    for ticker in PADDING:
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close,"
            " adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
            "rs_return_12w_vs_spy, rs_method) VALUES (193, ?, 'aplus', 15.0, "
            "2.5, 3, 5.0, 40.0, 85, 12.0, 'universe')", (ticker,))
        _pe(conn, 207, ticker)
    _pe(conn, 207, "SG")
    _pe(conn, 208, "SG")
    # The live shape: SG's detections are WATCH-origin.
    _pde(conn, 207, "SG", "aplus" if aplus_pde_on_207 else "watch",
         "2026-11-05")
    _pde(conn, 208, "SG", "watch", "2026-11-06")
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        "rs_return_12w_vs_spy, rs_method) VALUES (193, 'CUR', 'aplus', 15.0, "
        "2.5, 3, 5.0, 40.0, 85, 12.0, 'universe')")
    current = _pe(conn, 207, "CUR")
    # Trade 29 closed at negative R (the fixture's outcome; not live).
    conn.execute(
        "UPDATE trades SET state = 'closed', realized_R_if_plan_followed = "
        "-1.0 WHERE id = ?", (SG_TRADE_ID,))
    conn.commit()
    return conn, current


def _hit_stop_pct(conn, current: int):
    (row,) = _build_outcome_distribution(
        conn, pattern_class="vcp", current_evaluation_id=current,
        composite_score=SCORE)
    return row.n, row.hit_stop_pct


def _correct(conn) -> None:
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason="D104 test 1u")


def test_1u_live_shape_a_kind2_correction_does_not_move_the_cohort(
        tmp_path) -> None:
    conn, current = _world(tmp_path, "live", aplus_pde_on_207=False)
    before = _hit_stop_pct(conn, current)
    _correct(conn)
    after = _hit_stop_pct(conn, current)
    assert before == after == (5, 0.0)
    conn.close()


def test_1u_control_the_join_follows_the_moved_candidate(tmp_path) -> None:
    conn, current = _world(tmp_path, "control", aplus_pde_on_207=True)
    n_before, before = _hit_stop_pct(conn, current)
    assert (n_before, before) == (6, 0.0)
    _correct(conn)
    n_after, after = _hit_stop_pct(conn, current)
    assert n_after == 6
    assert after == pytest.approx(100.0 / 6)
    conn.close()
