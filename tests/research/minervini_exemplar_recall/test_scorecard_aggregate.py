# tests/research/minervini_exemplar_recall/test_scorecard_aggregate.py
from __future__ import annotations

import pytest

from research.harness.minervini_exemplar_recall.scorecard import (
    ControlSummary,
    ExemplarSummary,
    build_scorecard,
)


_ALL_PASS = {"risk_feasibility": True, "trend_template": True, "vcp": True}


def _ex(eid, ticker, cls, outcome, gate=None, faith=None, iso=None, gate_passes="auto"):
    # Default: screenable outcomes get an all-pass gate_passes (so they don't trip the
    # build_scorecard missing-threading guard); attrition outcomes get None.
    if gate_passes == "auto":
        gate_passes = None if outcome in ("skip_insufficient_history", "no_data") else _ALL_PASS
    return ExemplarSummary(eid, ticker, cls, outcome, gate, faith, iso, gate_passes)


def test_build_scorecard_detector_recall_excludes_unmapped():
    exemplars = [
        _ex("a", "CRUS", "vcp", "surfaced_aplus", None, True, True),
        _ex("b", "ANSS", "vcp", "surfaced_watch", None, False, True),
        _ex("c", "GRA", "unmapped", "surfaced_aplus", None, None, None),
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    fired, denom = sc.detector_recall.per_class_faithful["vcp"]
    # 2 mapped vcp exemplars; 1 fired faithful. unmapped 'c' is NOT in the denom.
    # WRONG-PATH (counts unmapped): denom 3.  RIGHT-PATH: denom 2.
    assert (fired, denom) == (1, 2)
    # isolated: both vcp fired -> 2/2. delta = 2/2 - 1/2 = 0.5.
    assert sc.detector_recall.per_class_isolated["vcp"] == (2, 2)
    assert sc.detector_recall.stage2_delta["vcp"] == pytest.approx(0.5)


def test_build_scorecard_gate_histogram_over_skip_gate_rejection():
    exemplars = [
        _ex("a", "T1", "vcp", "skip_gate_rejection", "risk_feasibility"),
        _ex("b", "T2", "vcp", "skip_gate_rejection", "vcp"),
        _ex("c", "T3", "vcp", "skip_gate_rejection", "risk_feasibility"),
        _ex("d", "T4", "vcp", "skip_insufficient_history", None),  # excluded from histogram
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    assert sc.gate_attribution_hist == {"risk_feasibility": 2, "vcp": 1}


def test_build_scorecard_specificity_contrast_from_controls():
    exemplars = [_ex("a", "CRUS", "vcp", "surfaced_aplus", None, True, True)]
    controls = [
        ControlSummary("CRUS", "vcp", surfaced=False, fired_faithful=False, fired_isolated=True),
        ControlSummary("CRUS", "vcp", surfaced=True, fired_faithful=False, fired_isolated=False),
    ]
    sc = build_scorecard("window_sweep", exemplars, controls, bootstrap_b=50, base_seed=1)
    # control surfaced rate 1/2; isolated-fire rate 1/2 -> labeled temporal-specificity contrast.
    assert sc.specificity_contrast["control_surfaced_rate"] == pytest.approx(0.5)
    assert sc.specificity_contrast["control_fired_isolated_rate"] == pytest.approx(0.5)


def test_build_scorecard_per_gate_pass_rate_over_screenable():
    exemplars = [
        _ex("a", "T1", "vcp", "surfaced_aplus", gate_passes={"risk_feasibility": True, "trend_template": True, "vcp": True}),
        _ex("b", "T2", "vcp", "skip_gate_rejection", "vcp", gate_passes={"risk_feasibility": True, "trend_template": True, "vcp": False}),
        # insufficient-history exemplar -> EXCLUDED from the per-gate denominator (gate_passes None).
        _ex("c", "T3", "vcp", "skip_insufficient_history", None, gate_passes=None),
    ]
    sc = build_scorecard("window_sweep", exemplars, [], bootstrap_b=50, base_seed=1)
    # denom = 2 screenable; vcp gate passed 1/2; risk + tt passed 2/2.
    # WRONG-PATH (denom includes insufficient): /3.  RIGHT-PATH: /2.
    assert sc.per_gate_pass_rate_screenable["vcp"] == pytest.approx(0.5)
    assert sc.per_gate_pass_rate_screenable["risk_feasibility"] == pytest.approx(1.0)
    assert sc.per_gate_pass_rate_screenable["trend_template"] == pytest.approx(1.0)


def test_build_scorecard_raises_on_screenable_missing_gate_passes():
    # A screenable exemplar with gate_passes None is a threading bug -> raise loudly (not silently
    # shrink the denominator). WRONG-PATH (filter-and-continue): rates silently overstated.
    bad = [_ex("a", "T1", "vcp", "surfaced_aplus", None, True, True, gate_passes=None)]
    with pytest.raises(ValueError, match="threading bug"):
        build_scorecard("window_sweep", bad, [], bootstrap_b=10, base_seed=1)
