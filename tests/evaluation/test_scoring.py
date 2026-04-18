"""Tests for scoring (bucket logic)."""
from __future__ import annotations

from swing.evaluation.criteria._base import Result
from swing.evaluation.scoring import bucket_for


def _make(layer: str, result: str, name: str = "x") -> Result:
    return Result(name=name, layer=layer, result=result, value="", rule="")


def test_aplus_when_tt_7plus_and_vcp_all_pass(sample_config):
    # Only the criterion name in allowed_miss_names (TT8_rs_rank) may fail.
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(7)] + [
        _make("trend_template", "fail", "TT8_rs_rank")
    ]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "aplus"


def test_skip_when_failing_tt_is_not_allowed_miss(sample_config):
    # 7/8 pass but the fail is TT3 (not in allowed_miss_names) → must skip
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(7)] + [
        _make("trend_template", "fail", "TT3_200_rising")
    ]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"


def test_watch_when_vcp_has_1_or_2_fails(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(8)] + [
        _make("vcp", "fail", "v8"), _make("vcp", "fail", "v9")
    ]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "watch"


def test_skip_when_tt_below_min(sample_config):
    tt = [_make("trend_template", "fail", f"TT{i}") for i in range(5)] + [
        _make("trend_template", "pass", f"TT{i}") for i in range(5, 8)
    ]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"


def test_skip_when_vcp_3plus_fails(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "fail", f"v{i}") for i in range(3)] + [
        _make("vcp", "pass", f"v{i}") for i in range(3, 10)
    ]
    risk = [_make("risk", "pass", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"


def test_risk_fail_forces_skip(sample_config):
    tt = [_make("trend_template", "pass", f"TT{i}") for i in range(8)]
    vcp = [_make("vcp", "pass", f"v{i}") for i in range(10)]
    risk = [_make("risk", "fail", "risk")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"
