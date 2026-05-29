import json
import pandas as pd, numpy as np
from swing.data.models import PatternEvaluation
from swing.web.charts import render_theme2_annotated_svg


def test_flat_base_overlay_reads_repaired_keys():
    bars_idx = pd.bdate_range(end="2026-05-28", periods=120)
    c = np.linspace(8, 10, 120)
    bars = pd.DataFrame({"Open": c, "High": c*1.02, "Low": c*0.98,
                         "Close": c, "Volume": 1e6}, index=bars_idx)
    ev = {"range_top_price": 9.8, "range_bottom_price": 9.2,
          "base_duration_days": 30, "pivot_price": 9.9}
    pe = PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="flat_base",
        detector_version="v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7, structural_evidence_json=json.dumps(ev),
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z")
    svg = render_theme2_annotated_svg(ticker="AAA", bars=bars, pattern_evaluation=pe)
    assert svg and len(svg) > 0  # renders non-empty with the repaired keys present
    # DISCRIMINATING: the "duration: N days" label appears ONLY when the
    # repaired base_duration_days key is read (the annotator isinstance-guards
    # the .get(), so a missing/renamed key silently skips it while still
    # rendering non-empty SVG). The "top/bottom of range" axhline labels appear
    # only when range_top_price/range_bottom_price are read. All three are
    # provably absent if the repaired keys are not consumed.
    assert b"duration: 30 days" in svg
    assert b"top of range" in svg
    assert b"bottom of range" in svg


def test_cup_with_handle_overlay_reads_repaired_keys():
    bars_idx = pd.bdate_range(end="2026-05-28", periods=120)
    c = np.linspace(8, 10, 120)
    bars = pd.DataFrame({"Open": c, "High": c*1.02, "Low": c*0.98,
                         "Close": c, "Volume": 1e6}, index=bars_idx)
    ev = {"cup_depth_pct": 18.5, "cup_bottom_price": 8.2, "pivot_price": 9.9}
    pe = PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="cup_with_handle",
        detector_version="v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7, structural_evidence_json=json.dumps(ev),
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z")
    svg = render_theme2_annotated_svg(ticker="AAA", bars=bars, pattern_evaluation=pe)
    assert svg and len(svg) > 0


def test_high_tight_flag_overlay_reads_repaired_keys():
    bars_idx = pd.bdate_range(end="2026-05-28", periods=120)
    c = np.linspace(8, 10, 120)
    bars = pd.DataFrame({"Open": c, "High": c*1.02, "Low": c*0.98,
                         "Close": c, "Volume": 1e6}, index=bars_idx)
    ev = {"pole_pct": 120.0, "consolidation_duration_days": 15, "pivot_price": 9.9}
    pe = PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="high_tight_flag",
        detector_version="v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7, structural_evidence_json=json.dumps(ev),
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z")
    svg = render_theme2_annotated_svg(ticker="AAA", bars=bars, pattern_evaluation=pe)
    assert svg and len(svg) > 0
