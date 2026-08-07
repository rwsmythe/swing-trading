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


# ===========================================================================
# Item 3b Task 2 -- the A+ STRUCTURAL gate, single-sourced.
#
# T2.1 is committed BEFORE the refactor and must stay green through it. Its
# expected values are LITERALS, so the oracle is independent of the
# implementation: a test that called the pre-refactor function as its own
# oracle would be comparing `bucket_for` with itself and could never fail.
# ===========================================================================

# (tt_pass_count, tt_fail_names, vcp_fail_count, risk_pass) -> bucket
_BUCKET_CHARACTERIZATION = [
    # risk is a HARD pre-filter and returns before the structure is looked at,
    # which is the whole reason `risk_feasibility` must be excluded from the
    # structural gate (L4).
    (8, (), 0, False, "skip"),
    (7, ("TT8_rs_rank",), 0, False, "skip"),
    # below min_passes (7 of 8)
    (6, ("TT7_within_52w_high_25pct", "TT8_rs_rank"), 0, True, "skip"),
    # at min_passes, but the failing TT is NOT an allowed miss
    (7, ("TT3_200_rising",), 0, True, "skip"),
    # the allowed miss, then the vcp band
    (7, ("TT8_rs_rank",), 0, True, "aplus"),
    (8, (), 0, True, "aplus"),
    (8, (), 1, True, "watch"),
    (8, (), 2, True, "watch"),
    (8, (), 3, True, "skip"),
]


def _tt_results(pass_count: int, fail_names: tuple[str, ...]):
    """8 TT rows: `pass_count` passes plus the named fails."""
    names = [
        "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
        "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
        "TT7_within_52w_high_25pct", "TT8_rs_rank",
    ]
    passing = [n for n in names if n not in fail_names][:pass_count]
    return (
        [_make("trend_template", "pass", n) for n in passing]
        + [_make("trend_template", "fail", n) for n in fail_names]
    )


def _vcp_results(fail_count: int):
    names = [
        "adr", "ma_short_rising", "ma_stack_10_20_50", "orderliness",
        "prior_trend", "proximity_20ma", "pullback", "tightness",
        "vcp_volume_contraction",
    ]
    return (
        [_make("vcp", "fail", n) for n in names[:fail_count]]
        + [_make("vcp", "pass", n) for n in names[fail_count:]]
    )


def test_bucket_for_characterization_table(sample_config):
    """T2.1 -- NOT DROPPABLE (L3). The behaviour-preservation oracle for the
    Task-2 refactor, written as literals so it cannot degenerate into
    comparing the function with itself."""
    for tt_pass, tt_fails, vcp_fails, risk_pass, expected in (
            _BUCKET_CHARACTERIZATION):
        tt = _tt_results(tt_pass, tt_fails)
        vcp = _vcp_results(vcp_fails)
        risk = [_make("risk", "pass" if risk_pass else "fail",
                      "risk_feasibility")]
        assert bucket_for(tt, vcp, risk, sample_config) == expected, (
            f"tt_pass={tt_pass} fails={tt_fails} vcp_fails={vcp_fails} "
            f"risk_pass={risk_pass}")
