# tests/research/minervini_exemplar_recall/test_screen_eval.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.config import Config
from swing.data.models import CriterionResult

TT_NAMES = ["TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
            "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
            "TT7_within_52w_high_25pct", "TT8_rs_rank"]


def _tt(passes: dict[str, str]) -> list[CriterionResult]:
    # passes maps name -> result; default 'pass'.
    return [CriterionResult(n, "trend_template", passes.get(n, "pass")) for n in TT_NAMES]


def _vcp(n_fail: int) -> list[CriterionResult]:
    out = []
    for i in range(9):
        res = "fail" if i < n_fail else "pass"
        out.append(CriterionResult(f"VCP{i}", "vcp", res))
    return out


def _risk(result: str) -> list[CriterionResult]:
    return [CriterionResult("RISK_feasible", "risk", result)]


def test_classify_insufficient_history_below_floor():
    from research.harness.minervini_exemplar_recall.screen_eval import classify_h1_outcome

    # bucket would be 'skip' but n_sliced < 221 -> insufficient (NOT gate_rejection).
    # WRONG-PATH (bucket-first): skip_gate_rejection.  RIGHT-PATH (floor-first): skip_insufficient_history.
    assert classify_h1_outcome(has_bars=True, n_sliced=210, bucket="skip", floor=221) == "skip_insufficient_history"
    assert classify_h1_outcome(has_bars=False, n_sliced=0, bucket=None, floor=221) == "no_data"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="aplus", floor=221) == "surfaced_aplus"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="watch", floor=221) == "surfaced_watch"
    assert classify_h1_outcome(has_bars=True, n_sliced=250, bucket="skip", floor=221) == "skip_gate_rejection"


def test_attribute_risk_wins_even_when_tt_also_fails():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    criteria = _tt({"TT1_above_150_200": "fail", "TT2_150_above_200": "fail"}) + _vcp(0) + _risk("fail")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    # risk is the hard filter checked FIRST. WRONG-PATH (TT-first): trend_template.
    # RIGHT-PATH (risk-first): risk_feasibility.
    assert attrib.first_rejecting_gate == "risk_feasibility"


def test_attribute_unallowed_tt_miss_when_passes_met():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()  # min_passes=7, allowed={TT8_rs_rank}
    # 7 passes (TT2 is the single fail) -> min_passes met, but TT2 is NOT allowed -> trend_template.
    criteria = _tt({"TT2_150_above_200": "fail"}) + _vcp(0) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    # WRONG-PATH (min_passes-only check passes -> falls through to vcp): vcp.
    # RIGHT-PATH (unallowed-miss check): trend_template.
    assert attrib.first_rejecting_gate == "trend_template"
    assert "TT2_150_above_200" in attrib.failing_gates


def test_attribute_min_passes_shortfall():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    # 5 passes (3 fails) -> below min_passes 7.
    criteria = _tt({"TT1_above_150_200": "fail", "TT3_200_rising": "fail", "TT4_50_above_150_200": "fail"}) + _vcp(0) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    assert attrib.first_rejecting_gate == "trend_template_min_passes"


def test_attribute_vcp_when_tt_clean():
    from research.harness.minervini_exemplar_recall.screen_eval import attribute_first_rejecting_gate

    cfg = Config.from_defaults()
    # all TT pass, 3 vcp fails (>2) -> vcp.  (2 vcp fails would be 'watch', not a skip at all.)
    criteria = _tt({}) + _vcp(3) + _risk("pass")
    attrib = attribute_first_rejecting_gate(criteria, cfg)
    assert attrib.first_rejecting_gate == "vcp"


def test_tt_names_match_production():
    # _TT_NAMES (used to synthesize NA rows for tiny slices) must match the real CHECK_NAMES
    # or faithful-stage seeding drifts.
    from swing.evaluation.criteria.trend_template import CHECK_NAMES
    from research.harness.minervini_exemplar_recall.screen_eval import _TT_NAMES

    assert tuple(_TT_NAMES) == tuple(CHECK_NAMES)


def test_compute_gate_passes_distinguishes_each_layer():
    from research.harness.minervini_exemplar_recall.screen_eval import compute_gate_passes

    cfg = Config.from_defaults()
    # risk fail -> risk gate False; everything else passing.
    g = compute_gate_passes(_tt({}) + _vcp(0) + _risk("fail"), cfg)
    assert g == {"risk_feasibility": False, "trend_template": True, "vcp": True}
    # TT2 unallowed fail -> trend_template gate False (WRONG-PATH min_passes-only: True).
    g2 = compute_gate_passes(_tt({"TT2_150_above_200": "fail"}) + _vcp(0) + _risk("pass"), cfg)
    assert g2["trend_template"] is False and g2["risk_feasibility"] is True
    # 3 vcp fails -> vcp gate False; 2 would be True.
    assert compute_gate_passes(_tt({}) + _vcp(3) + _risk("pass"), cfg)["vcp"] is False
    assert compute_gate_passes(_tt({}) + _vcp(2) + _risk("pass"), cfg)["vcp"] is True


def _flat_bars(n: int, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    return pd.DataFrame(
        {"Open": [10.0] * n, "High": [10.0] * n, "Low": [10.0] * n,
         "Close": [10.0] * n, "Volume": [1_000] * n},
        index=idx,
    )


def test_below_floor_short_circuits_without_calling_evaluate_one(monkeypatch):
    # Codex executing-plans R1 major: below the screenable floor, evaluate_h1 must NOT call
    # evaluate_one (the old broad except would mask a genuine evaluator failure as attrition).
    from research.harness.minervini_exemplar_recall import screen_eval

    def _boom(ctx):
        raise RuntimeError("evaluate_one must NOT be called below the screenable floor")

    monkeypatch.setattr(screen_eval, "evaluate_one", _boom)
    cfg = Config.from_defaults()  # floor 221
    bars = _flat_bars(50)  # < 221 -> below floor
    res = screen_eval.evaluate_h1(
        ticker="AAA", exemplar_full=bars, spy_full=None, session=bars.index[-1].date(), config=cfg
    )
    # WRONG-PATH (old broad except swallows the boom): also skip_insufficient_history, masking the
    # bug. RIGHT-PATH: the short-circuit returns BEFORE evaluate_one, so _boom never fires.
    assert res.outcome == "skip_insufficient_history"
    assert len(res.tt_criteria) == 8
    assert all(c.result == "na" for c in res.tt_criteria)


def test_above_floor_evaluate_one_raise_propagates(monkeypatch):
    # At/above the floor a raise from evaluate_one is a genuine bug and MUST propagate (never
    # silently swallowed as attrition).
    from research.harness.minervini_exemplar_recall import screen_eval

    def _boom(ctx):
        raise RuntimeError("genuine evaluator bug above the floor")

    monkeypatch.setattr(screen_eval, "evaluate_one", _boom)
    cfg = Config.from_defaults()
    bars = _flat_bars(260)  # > 221 -> above floor
    with pytest.raises(RuntimeError, match="genuine evaluator bug"):
        screen_eval.evaluate_h1(
            ticker="AAA", exemplar_full=bars, spy_full=None,
            session=bars.index[-1].date(), config=cfg,
        )
