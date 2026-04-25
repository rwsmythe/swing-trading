"""Aggregator tests on synthetic Candidate fixtures.

Boundary conditions of the near-A+ classification (the analytically-
sensitive primitive locked at D1) are the focus. Production-gated
blocker correctness is delegated to the canonical implementation in
``recompute_binding_prod_gated`` and tested at the wrapper level.
"""
from __future__ import annotations

from collections import Counter

from research.finviz_pool_analysis.aggregator import (
    NearAplusSample,
    aggregate_runs,
    classify_near_aplus,
    production_gated_blocker,
)
from research.finviz_pool_analysis.doctrine import (
    DEFENSIBLE_MISS_SET,
    DOCTRINE_INCOMPATIBLE_SET,
)
from swing.data.models import Candidate, CriterionResult


_TT_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)
_VCP_NAMES = (
    "prior_trend",
    "ma_stack_10_20_50",
    "ma_short_rising",
    "proximity_20ma",
    "adr",
    "pullback",
    "tightness",
    "vcp_volume_contraction",
    "orderliness",
)
_RISK_NAMES = ("risk_feasibility",)


def _layer_for(name: str) -> str:
    if name in _TT_NAMES:
        return "trend_template"
    if name in _VCP_NAMES:
        return "vcp"
    if name in _RISK_NAMES:
        return "risk"
    raise AssertionError(f"unknown criterion name {name!r}")


def _crits(overrides: dict[str, str] | None = None) -> tuple[CriterionResult, ...]:
    """Build a full criteria tuple defaulting to all-pass with optional
    per-name overrides."""
    overrides = overrides or {}
    results = []
    for name in _TT_NAMES + _VCP_NAMES + _RISK_NAMES:
        result = overrides.get(name, "pass")
        results.append(
            CriterionResult(
                criterion_name=name, layer=_layer_for(name), result=result
            )
        )
    return tuple(results)


def _candidate(
    *,
    ticker: str,
    bucket: str,
    overrides: dict[str, str] | None = None,
) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket=bucket,
        close=100.0,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=_crits(overrides),
    )


# -------------------- doctrine constants --------------------


def test_defensible_set_membership_locked_at_d1():
    """Defensible set membership is FROZEN at D1; this test pins it."""
    assert DEFENSIBLE_MISS_SET == frozenset(
        {"TT8_rs_rank", "risk_feasibility", "proximity_20ma"}
    )


def test_defensible_and_incompatible_sets_are_disjoint():
    assert DEFENSIBLE_MISS_SET.isdisjoint(DOCTRINE_INCOMPATIBLE_SET)


# -------------------- production_gated_blocker wrapper --------------------


def test_blocker_aplus_when_all_pass():
    cand = _candidate(ticker="X", bucket="aplus")
    assert production_gated_blocker(cand) == "<aplus>"


def test_blocker_risk_first_even_when_tt_also_fails():
    cand = _candidate(
        ticker="X",
        bucket="skip",
        overrides={"TT1_above_150_200": "fail", "risk_feasibility": "fail"},
    )
    # Production gating: risk hard-filter checked FIRST.
    assert production_gated_blocker(cand) == "risk_feasibility"


def test_blocker_tt8_alone_does_not_block_aplus():
    cand = _candidate(ticker="X", bucket="aplus", overrides={"TT8_rs_rank": "fail"})
    assert production_gated_blocker(cand) == "<aplus>"


# -------------------- classify_near_aplus boundary cases --------------------


def test_classify_not_watch_for_aplus_bucket():
    cand = _candidate(ticker="X", bucket="aplus")
    assert classify_near_aplus(cand) == "not_watch"


def test_classify_not_watch_for_skip_bucket():
    cand = _candidate(
        ticker="X", bucket="skip", overrides={"TT1_above_150_200": "fail"}
    )
    assert classify_near_aplus(cand) == "not_watch"


def test_classify_defensible_only_proximity_20ma_fails():
    """Watch ticker whose only fail is proximity_20ma → defensible."""
    cand = _candidate(
        ticker="X", bucket="watch", overrides={"proximity_20ma": "fail"}
    )
    assert classify_near_aplus(cand) == "defensible"


def test_classify_defensible_proximity_plus_tt8_both_in_set():
    cand = _candidate(
        ticker="X",
        bucket="watch",
        overrides={"proximity_20ma": "fail", "TT8_rs_rank": "fail"},
    )
    assert classify_near_aplus(cand) == "defensible"


def test_classify_incompatible_when_adr_fails():
    """Boundary case: failing TT8 + adr — adr is doctrine-incompatible."""
    cand = _candidate(
        ticker="X",
        bucket="watch",
        overrides={"TT8_rs_rank": "fail", "adr": "fail"},
    )
    assert classify_near_aplus(cand) == "incompatible"


def test_classify_incompatible_when_only_doctrine_incompatible_criterion_fails():
    cand = _candidate(
        ticker="X",
        bucket="watch",
        overrides={"prior_trend": "fail"},
    )
    assert classify_near_aplus(cand) == "incompatible"


def test_classify_treats_na_as_non_pass():
    """`na` is a non-pass result; an `na` outside the defensible set must
    classify as incompatible (not silently skipped)."""
    cand = _candidate(
        ticker="X", bucket="watch", overrides={"vcp_volume_contraction": "na"}
    )
    assert classify_near_aplus(cand) == "incompatible"


# -------------------- aggregate_runs end-to-end on synthetic data --------------------


def test_aggregate_buckets_blockers_and_near_aplus_one_run():
    runs = [
        (
            42,
            "2026-04-21",
            [
                _candidate(ticker="A", bucket="aplus"),
                _candidate(
                    ticker="B",
                    bucket="watch",
                    overrides={"proximity_20ma": "fail"},
                ),
                _candidate(
                    ticker="C",
                    bucket="watch",
                    overrides={"adr": "fail", "tightness": "fail"},
                ),
                _candidate(
                    ticker="D",
                    bucket="skip",
                    overrides={"TT1_above_150_200": "fail"},
                ),
                _candidate(
                    ticker="E",
                    bucket="skip",
                    overrides={"risk_feasibility": "fail"},
                ),
            ],
        )
    ]
    result = aggregate_runs(runs)

    assert result.bucket_counts == Counter({"aplus": 1, "watch": 2, "skip": 2})
    assert result.total_evaluations == 5
    assert result.aplus_count == 1
    assert result.watch_count == 2
    assert result.watch_aplus_ratio == 2 / 1

    # Production-gated blocker counts: one <aplus>, one TT1, one risk_feasibility,
    # plus the watch-bucket VCP blockers.
    assert result.blocker_counts["<aplus>"] == 1
    assert result.blocker_counts["risk_feasibility"] == 1
    assert result.blocker_counts["TT1_above_150_200"] == 1
    # Watch-bucket VCP fails are still blockers under production gating
    # (1-2 VCP fails → watch, but the production-gated re-aggregation
    # surfaces the FIRST VCP-layer non-pass criterion).
    assert "proximity_20ma" in result.blocker_counts
    assert "adr" in result.blocker_counts

    # Near-A+ classification.
    assert result.near_aplus_defensible_count == 1
    assert result.near_aplus_incompatible_count == 1
    assert {s.ticker for s in result.defensible_sample} == {"B"}
    assert {s.ticker for s in result.incompatible_sample} == {"C"}
    # Failed-criteria list is on the incompatible row.
    inc = next(s for s in result.incompatible_sample if s.ticker == "C")
    assert set(inc.failed_criteria) == {"adr", "tightness"}


def test_aggregate_per_run_ratio_undefined_on_zero_aplus():
    runs = [
        (
            1,
            "2026-04-20",
            [
                _candidate(ticker="A", bucket="watch", overrides={"proximity_20ma": "fail"}),
            ],
        ),
        (
            2,
            "2026-04-21",
            [
                _candidate(ticker="B", bucket="aplus"),
                _candidate(ticker="C", bucket="watch", overrides={"proximity_20ma": "fail"}),
            ],
        ),
    ]
    result = aggregate_runs(runs)
    assert result.per_run_watch_aplus_ratio[1] is None  # zero A+ run
    assert result.per_run_watch_aplus_ratio[2] == 1.0


def test_aggregate_sample_ordering_action_session_desc_then_ticker_asc():
    runs = [
        (
            1,
            "2026-04-20",
            [
                _candidate(ticker="ZZZ", bucket="watch", overrides={"proximity_20ma": "fail"}),
            ],
        ),
        (
            2,
            "2026-04-22",
            [
                _candidate(ticker="AAA", bucket="watch", overrides={"proximity_20ma": "fail"}),
                _candidate(ticker="BBB", bucket="watch", overrides={"proximity_20ma": "fail"}),
            ],
        ),
    ]
    result = aggregate_runs(runs)
    # action_session_date DESC ⇒ run 2 first; within run 2 ticker ASC ⇒ AAA, BBB.
    assert [s.ticker for s in result.defensible_sample] == ["AAA", "BBB", "ZZZ"]


def test_aggregate_consistency_warning_on_aplus_bucket_with_blocker():
    """If a candidate has bucket='aplus' but the production-gated
    re-aggregation finds a blocker, surface a warning — do not crash."""
    runs = [
        (
            1,
            "2026-04-20",
            [
                _candidate(
                    ticker="X",
                    bucket="aplus",
                    overrides={"TT1_above_150_200": "fail"},  # production-gated says skip
                ),
            ],
        )
    ]
    result = aggregate_runs(runs)
    assert any("re-aggregation drift" in w for w in result.consistency_warnings)


def _empty_criteria_candidate(*, ticker: str, bucket: str) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket=bucket,
        close=None,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="unavailable",
        pattern_tag=None,
        notes=None,
        criteria=(),
    )


def test_aggregate_error_bucket_uses_error_sentinel():
    err_cand = _empty_criteria_candidate(ticker="X", bucket="error")
    runs = [(1, "2026-04-20", [err_cand])]
    result = aggregate_runs(runs)
    assert result.bucket_counts["error"] == 1
    assert result.blocker_counts["<error>"] == 1
    # Sum of blocker counts equals total evaluations (denominator integrity).
    assert sum(result.blocker_counts.values()) == result.total_evaluations


def test_aggregate_excluded_bucket_uses_excluded_sentinel_not_error():
    """Excluded rows must not be conflated with error rows — they are
    intentional exclusions, not operational failures. The blocker column
    distinguishes the two."""
    exc_cand = _empty_criteria_candidate(ticker="Y", bucket="excluded")
    err_cand = _empty_criteria_candidate(ticker="Z", bucket="error")
    runs = [(1, "2026-04-20", [exc_cand, err_cand])]
    result = aggregate_runs(runs)
    assert result.bucket_counts["excluded"] == 1
    assert result.bucket_counts["error"] == 1
    assert result.blocker_counts["<excluded>"] == 1
    assert result.blocker_counts["<error>"] == 1
    # Sum of blocker counts equals total evaluations (denominator integrity).
    assert sum(result.blocker_counts.values()) == result.total_evaluations
