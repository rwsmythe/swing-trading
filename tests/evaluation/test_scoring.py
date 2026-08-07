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


def test_the_structural_gate_EXCLUDES_risk_feasibility(sample_config):
    """T2.2 -- L4's guard, and the test that fails if any implementation reads
    `candidates.bucket` instead of recomputing the gate.

    A perfect structure whose ONLY failure is `risk_feasibility` buckets `skip`
    -- the risk pre-filter returns before the TT/vcp tests are even run -- while
    the STRUCTURAL gate passes. `risk_feasibility` is a fact about the
    operator's capital, so letting it into the gate would let his own account
    size withdraw his mandate. That is RD's exclusion and this is its guard.
    """
    from swing.evaluation.scoring import (
        structural_gate_passes,
        structural_inputs_from_results,
    )

    tt = _tt_results(8, ())
    vcp = _vcp_results(0)
    risk = [_make("risk", "fail", "risk_feasibility")]
    assert bucket_for(tt, vcp, risk, sample_config) == "skip"
    assert structural_gate_passes(
        structural_inputs_from_results(tt, vcp), sample_config) is True


def test_a_trend_template_na_is_a_NON_PASS_not_a_neutral(sample_config):
    """T2.6(b) -- the half an earlier draft claimed was covered while asserting
    only the vcp case.

    Discriminator: an adapter that counts only `result == "fail"` into
    `tt_failed_names` treats `na` as neutral, leaves `tt_pass_count` at 7 (>=
    min_passes) with no disallowed fail, and falsely PASSES the gate. Here TT3
    -- OUTSIDE `allowed_miss_names` -- is `na`, so the gate must FAIL.
    """
    from swing.evaluation.scoring import (
        structural_gate_passes,
        structural_inputs_from_results,
    )

    tt = [_make("trend_template", "pass", n) for n in (
        "TT1_above_150_200", "TT2_150_above_200", "TT4_50_above_150_200",
        "TT5_above_50", "TT6_above_52w_low_30pct",
        "TT7_within_52w_high_25pct", "TT8_rs_rank")]
    tt.append(_make("trend_template", "na", "TT3_200_rising"))
    inputs = structural_inputs_from_results(tt, _vcp_results(0))
    assert inputs.tt_pass_count == 7
    assert "TT3_200_rising" in inputs.tt_failed_names
    assert structural_gate_passes(inputs, sample_config) is False


def test_a_vcp_na_counts_as_a_vcp_FAILURE(sample_config):
    """T2.6(a). `bucket_for` has always counted `na` as a vcp fail
    ("insufficient data is a fail"); the reduction must not quietly relax it."""
    from swing.evaluation.scoring import structural_inputs_from_results

    vcp = _vcp_results(0)[:-1] + [_make("vcp", "na", "vcp_volume_contraction")]
    assert structural_inputs_from_results(_tt_results(8, ()), vcp
                                          ).vcp_fail_count == 1


def test_the_expected_criterion_rosters_match_the_real_evaluator(sample_config):
    """T2.7 -- THE ROSTER DRIFT-PIN, and what makes a hand-written roster safe.

    The rosters cannot be derived at runtime (the criterion modules expose no
    static name list; `evaluate` is a runtime call over a constructed context),
    so they are written out and pinned against the REAL emitter. A criterion
    added, renamed or removed changes what the structural gate MEANS -- and the
    latch reader's roster check would then start declaring every candidate
    UNVERIFIABLE, or worse, pass a partial set. This test fails first instead.
    """
    import pandas as pd

    from swing.evaluation.context import (
        BatchContext,
        CandidateContext,
        MarketContext,
    )
    from swing.evaluation.evaluator import evaluate_one
    from swing.evaluation.scoring import (
        EXPECTED_TT_CRITERIA,
        EXPECTED_VCP_CRITERIA,
    )

    n = 320
    idx = pd.bdate_range("2025-01-01", periods=n)
    close = pd.Series([10.0 + i * 0.05 for i in range(n)], index=idx)
    ohlcv = pd.DataFrame({
        "Open": close, "High": close * 1.01, "Low": close * 0.99,
        "Close": close, "Volume": [1_000_000] * n,
    }, index=idx)
    ctx = CandidateContext(
        ticker="ROSTER", ohlcv=ohlcv, config=sample_config,
        batch=BatchContext(
            returns_12w_by_ticker={"ROSTER": 0.40}, universe_tickers=("ROSTER",),
            universe_version="t", universe_hash="t", spy_return_12w=0.10),
        market=MarketContext(), current_equity=7500.0)
    # THE REAL PRODUCTION ASSEMBLY, not the individual criterion modules: the
    # vcp layer is built from NINE separate modules inside `evaluate_one`, so
    # calling one of them would pin a fragment of the roster and miss the
    # assembly -- which is where a criterion is actually added or dropped.
    criteria = evaluate_one(ctx).criteria
    tt_names = {c.criterion_name for c in criteria if c.layer == "trend_template"}
    vcp_names = {c.criterion_name for c in criteria if c.layer == "vcp"}
    risk_names = {c.criterion_name for c in criteria if c.layer == "risk"}
    assert tt_names == EXPECTED_TT_CRITERIA
    assert vcp_names == EXPECTED_VCP_CRITERIA
    # The risk layer is named here only to prove it is a SEPARATE layer the
    # gate never reads (L4) -- and that it has not quietly merged into `vcp`.
    assert risk_names == {"risk_feasibility"}
    assert not (EXPECTED_TT_CRITERIA & EXPECTED_VCP_CRITERIA)
