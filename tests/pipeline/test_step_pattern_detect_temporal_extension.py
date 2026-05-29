"""Phase 14 Sub-bundle 2 T-2.4 -- detect-step temporal-log extension tests.

Imports the shared fixtures + helpers from conftest_temporal (plan section L.4).
The detection-event INSERT shape matches the production emitter exactly
(anti-drift): the seed helpers use the REAL candidate/eval-run repos and the
step is driven through the production _step_pattern_detect.
"""
from __future__ import annotations
import json
from unittest.mock import patch
import pytest
from swing.data.repos.pattern_detection_events import list_detection_events

# Reuse the proven harness from the shared temporal conftest module.
from tests.pipeline.conftest_temporal import (  # noqa: F401  (tmp_db_v22 fixture)
    tmp_db_v22,
    _build_bars, _seed_aplus_candidate_and_run, _seed_run_with_zero_aplus,
    _drive_detect, _StubOhlcvCache,
)


def test_detection_event_appended_with_metadata(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(
        tmp_db_v22, ticker="AAA", sector="Tech", industry="Software",
        adr_pct=3.2, rs_rank=42)
    run_warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), run_warnings)
    dets = list_detection_events(conn, ticker="AAA")
    assert len(dets) >= 1
    md = json.loads(dets[0].per_pattern_metadata_json)
    assert md["sector"] == "Tech" and md["industry"] == "Software"
    assert md["adr_pct"] == pytest.approx(3.2)
    assert md["rs_rank"] == 42
    assert "atr_pct" in md and "ret_90d" in md and "prox_52w_high_pct" in md
    assert md["market_cap"] is None  # OQ-16 LOCK
    assert dets[0].source == "pipeline"
    assert dets[0].data_asof_date is not None  # populated
    # structural_anchors_json carries window + evidence (incl. pivot_price).
    anchors = json.loads(dets[0].structural_anchors_json)
    assert "window" in anchors and "evidence" in anchors


def test_chart_render_id_populated_on_success(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is not None
    row = conn.execute("SELECT surface, pattern_class FROM chart_renders "
                       "WHERE id = ?", (det.chart_render_id,)).fetchone()
    assert row[0] == "theme2_annotated" and row[1] == det.pattern_class


def test_chart_render_failure_leaves_null_and_warns(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    run_warnings: list[dict] = []
    with patch("swing.pipeline.runner.render_and_capture_detection_chart",
               return_value=None):
        _drive_detect(conn, cfg, lease, eval_run_id,
                      _StubOhlcvCache({"AAA": _build_bars()}), run_warnings)
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is None
    assert any(w.get("reason") == "chart render failed" for w in run_warnings)


def test_idempotent_rerun_skips_recompute_frozen_facts(tmp_db_v22):
    # Codex chain #2 Major #5 (+ R2 Minor #1 scope fix): a re-run with DIFFERENT
    # bars must NOT duplicate AND must NOT recompute/replace the FROZEN detection
    # facts. The frozen-fact tuple is structural_anchors_json + composite_score
    # + per_pattern_metadata_json + detector_version + data_asof_date.
    # chart_render_id is a NULLABLE AUDIT LINKAGE (not a frozen fact) --
    # asserted SEPARATELY as "the same-run skip did not refresh the linkage".
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    first = list_detection_events(conn, ticker="AAA")
    frozen_before = [(d.structural_anchors_json, d.composite_score,
                      d.per_pattern_metadata_json, d.detector_version,
                      d.data_asof_date) for d in first]
    linkage_before = [d.chart_render_id for d in first]
    drifted = _build_bars().copy()
    drifted[["Open", "High", "Low", "Close"]] *= 1.5
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": drifted}), [])
    second = list_detection_events(conn, ticker="AAA")
    assert len(second) == len(first)  # no duplicate (SELECT-then-skip)
    frozen_after = [(d.structural_anchors_json, d.composite_score,
                     d.per_pattern_metadata_json, d.detector_version,
                     d.data_asof_date) for d in second]
    assert frozen_after == frozen_before          # FROZEN FACTS unchanged
    # The skip also left the audit linkage untouched in the SAME run.
    assert [d.chart_render_id for d in second] == linkage_before


def test_pattern_evaluations_still_written_l7(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    n_eval = conn.execute("SELECT COUNT(*) FROM pattern_evaluations").fetchone()[0]
    assert n_eval >= 1  # the existing write is UNCHANGED (L7)


def test_empty_aplus_pool_warns_and_writes_nothing(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_run_with_zero_aplus(tmp_db_v22)
    run_warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, _StubOhlcvCache({}), run_warnings)
    assert conn.execute("SELECT COUNT(*) FROM pattern_detection_events").fetchone()[0] == 0
    entry = next(w for w in run_warnings if w["step"] == "pattern_detect")
    assert entry["actual_aplus_pool"] == 0
    assert entry["reason"] == "zero aplus candidates"
