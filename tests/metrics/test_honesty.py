"""Phase 10 Sub-bundle A T-A.1 — honesty utility tests.

Tests Wilson CI, bootstrap CI, suppression dispatcher, and per-class render
helpers per plan §A.7 + §D Task A.1 acceptance criteria + dispatch brief
§3.2 Codex pre-emption (Wilson edge cases at k=0 or k=n).

Plan reference value note: plan §D Task A.1 acceptance gives k=2,n=4 →
[0.094, 0.901]. Standard Wilson score interval (no continuity correction,
the Wikipedia primary form) yields [0.150, 0.850] for k=2,n=4. Plan's value
appears to be Wilson-with-continuity-correction (~[0.092, 0.908]) rounded
inconsistently. Standard Wilson matches plan's other two reference values
(k=0,n=20 → [0.000, 0.161]; k=20,n=20 → [0.839, 1.000]) exactly. This
implementation uses standard Wilson — see honesty.py for rationale —
tests assert standard Wilson reference values. Return report §5 notes the
plan-text deviation; binding §A.7 interface unchanged.
"""
from __future__ import annotations

import math

import pytest

from swing.metrics.honesty import (
    CLASS_D_LINE_DRAW_FLOOR,
    BootstrapCI,
    HonestyBadges,
    HonestyClass,
    SuppressedMetric,
    WilsonCI,
    bootstrap_ci_mean,
    render_class_a,
    render_class_b,
    render_class_c,
    render_class_d,
    suppress_for_n,
    wilson_ci,
)


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------

def test_wilson_ci_known_values_k0_n20():
    """k=0, n=20 → standard Wilson [0.000, 0.161] (plan reference)."""
    ci = wilson_ci(k=0, n=20)
    assert math.isclose(ci.lower, 0.0, abs_tol=1e-3)
    assert math.isclose(ci.upper, 0.161, abs_tol=1e-3)
    assert math.isclose(ci.point, 0.0, abs_tol=1e-3)


def test_wilson_ci_known_values_k20_n20():
    """k=20, n=20 → standard Wilson [0.839, 1.000] (plan reference)."""
    ci = wilson_ci(k=20, n=20)
    assert math.isclose(ci.lower, 0.839, abs_tol=1e-3)
    assert math.isclose(ci.upper, 1.0, abs_tol=1e-3)
    assert math.isclose(ci.point, 1.0, abs_tol=1e-3)


def test_wilson_ci_known_values_k2_n4_standard():
    """k=2, n=4 → standard Wilson [0.150, 0.850] (NOT plan's [0.094, 0.901]
    which is Wilson-with-continuity-correction; standard Wilson is used per
    Wikipedia primary form)."""
    ci = wilson_ci(k=2, n=4)
    assert math.isclose(ci.lower, 0.150, abs_tol=1e-3)
    assert math.isclose(ci.upper, 0.850, abs_tol=1e-3)
    assert math.isclose(ci.point, 0.5, abs_tol=1e-3)


def test_wilson_ci_symmetric_under_k_swap():
    """Symmetry: WilsonCI(k=K, n=N) bounds reflect WilsonCI(k=N-K, n=N)."""
    lo = wilson_ci(k=3, n=10)
    hi = wilson_ci(k=7, n=10)
    assert math.isclose(lo.lower, 1.0 - hi.upper, abs_tol=1e-9)
    assert math.isclose(lo.upper, 1.0 - hi.lower, abs_tol=1e-9)


def test_wilson_ci_n_zero_returns_zero_triple():
    """Edge case: n=0 returns WilsonCI(0,0,0) (callers should suppress first)."""
    ci = wilson_ci(k=0, n=0)
    assert ci == WilsonCI(point=0.0, lower=0.0, upper=0.0)


def test_wilson_ci_rejects_negative_n():
    with pytest.raises(ValueError, match="n must be >= 0"):
        wilson_ci(k=0, n=-1)


def test_wilson_ci_rejects_negative_k():
    with pytest.raises(ValueError, match="k must be >= 0"):
        wilson_ci(k=-1, n=10)


def test_wilson_ci_rejects_k_gt_n():
    with pytest.raises(ValueError, match="k must be <= n"):
        wilson_ci(k=11, n=10)


def test_wilson_ci_rejects_unsupported_alpha():
    with pytest.raises(NotImplementedError, match="only supports alpha=0.05"):
        wilson_ci(k=1, n=10, alpha=0.10)


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

def test_bootstrap_ci_deterministic_with_seed():
    """Same seed + same samples + same resample_count → identical bounds."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci1 = bootstrap_ci_mean(samples=samples, resample_count=500, rng_seed=42)
    ci2 = bootstrap_ci_mean(samples=samples, resample_count=500, rng_seed=42)
    assert ci1 == ci2


def test_bootstrap_ci_different_seeds_diverge():
    """Different seeds (very likely) yield different CIs at a sample size
    where percentile indices land in different regions of the resample
    distribution."""
    samples = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]  # heavy-tailed, more variance
    ci1 = bootstrap_ci_mean(samples=samples, resample_count=100, rng_seed=1)
    ci2 = bootstrap_ci_mean(samples=samples, resample_count=100, rng_seed=2)
    # Either lower or upper should differ; if both equal, the seed
    # truly produced an identical run (~probability 0 at R=100 with these
    # samples).
    assert (ci1.lower, ci1.upper) != (ci2.lower, ci2.upper)


def test_bootstrap_ci_resample_count_carried_in_result():
    """`resample_count` field on BootstrapCI matches the input."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci = bootstrap_ci_mean(samples=samples, resample_count=500, rng_seed=42)
    assert ci.resample_count == 500


def test_bootstrap_ci_point_is_sample_mean():
    """point field equals the sample mean exactly."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci = bootstrap_ci_mean(samples=samples, resample_count=200, rng_seed=7)
    assert math.isclose(ci.point, 3.0, abs_tol=1e-9)


def test_bootstrap_ci_rejects_empty_samples():
    with pytest.raises(ValueError, match="non-empty"):
        bootstrap_ci_mean(samples=[], resample_count=100)


def test_bootstrap_ci_rejects_invalid_resample_count():
    with pytest.raises(ValueError, match="resample_count must be >= 1"):
        bootstrap_ci_mean(samples=[1.0], resample_count=0)


def test_bootstrap_ci_rejects_nan_sample():
    with pytest.raises(ValueError, match="must be finite"):
        bootstrap_ci_mean(samples=[1.0, float("nan")], resample_count=100, rng_seed=1)


def test_bootstrap_ci_rejects_inf_sample():
    with pytest.raises(ValueError, match="must be finite"):
        bootstrap_ci_mean(samples=[1.0, float("inf")], resample_count=100, rng_seed=1)


# ---------------------------------------------------------------------------
# suppress_for_n
# ---------------------------------------------------------------------------

def test_suppress_for_n_class_a_below_3_returns_suppressed(spec_default_policy):
    """Class A floor=3 (spec §5.1); n=2 → SuppressedMetric."""
    result = suppress_for_n(
        metric_name="win_rate", n=2,
        klass=HonestyClass.A, policy=spec_default_policy,
    )
    assert isinstance(result, SuppressedMetric)
    assert result.metric_name == "win_rate"
    assert result.n == 2
    assert result.n_required == 3
    assert "n too low" in result.placeholder_text
    assert "current: 2" in result.placeholder_text
    assert "need: ≥3" in result.placeholder_text


def test_suppress_for_n_class_a_at_floor_returns_none(spec_default_policy):
    """Class A floor=3; n=3 → None (renders normally)."""
    result = suppress_for_n(
        metric_name="win_rate", n=3,
        klass=HonestyClass.A, policy=spec_default_policy,
    )
    assert result is None


def test_suppress_for_n_class_c_diversity_floor(spec_default_policy):
    """Class C floor=5; n=4 → SuppressedMetric (diversity check happens in render_class_c)."""
    result = suppress_for_n(
        metric_name="profit_factor", n=4,
        klass=HonestyClass.C, policy=spec_default_policy,
    )
    assert isinstance(result, SuppressedMetric)
    assert result.n_required == 5


def test_suppress_for_n_class_d_uses_spec_lock_5(spec_default_policy):
    """Class D suppression floor is spec-locked at 5; policy.class_d_n (=10
    rolling window size) is NOT the suppression threshold."""
    result = suppress_for_n(
        metric_name="process_grade_rolling_N", n=4,
        klass=HonestyClass.D, policy=spec_default_policy,
    )
    assert isinstance(result, SuppressedMetric)
    assert result.n_required == 5  # CLASS_D_LINE_DRAW_FLOOR, NOT 10
    assert CLASS_D_LINE_DRAW_FLOOR == 5

    not_suppressed = suppress_for_n(
        metric_name="process_grade_rolling_N", n=5,
        klass=HonestyClass.D, policy=spec_default_policy,
    )
    assert not_suppressed is None


# ---------------------------------------------------------------------------
# render_class_a
# ---------------------------------------------------------------------------

def test_render_class_a_n_2_suppressed(spec_default_policy):
    result = render_class_a(
        k=1, n=2, policy=spec_default_policy, metric_name="win_rate",
    )
    assert isinstance(result, SuppressedMetric)


def test_render_class_a_n_5_returns_wilson_ci(spec_default_policy):
    """n=5 is above floor; returns WilsonCI value."""
    result = render_class_a(
        k=3, n=5, policy=spec_default_policy, metric_name="win_rate",
    )
    assert isinstance(result, WilsonCI)
    assert math.isclose(result.point, 0.6, abs_tol=1e-3)


def test_render_class_a_n_20_returns_wilson_ci(spec_default_policy):
    result = render_class_a(
        k=10, n=20, policy=spec_default_policy, metric_name="win_rate",
    )
    assert isinstance(result, WilsonCI)


# ---------------------------------------------------------------------------
# render_class_b
# ---------------------------------------------------------------------------

def test_render_class_b_n_below_3_suppressed(spec_default_policy):
    result = render_class_b(
        samples=[1.0, 2.0],
        policy=spec_default_policy,
        metric_name="expectancy_R",
    )
    assert isinstance(result, SuppressedMetric)
    assert result.n_required == 3


def test_render_class_b_returns_bootstrap_ci_above_floor(spec_default_policy):
    result = render_class_b(
        samples=[1.0, 2.0, 3.0, 4.0, 5.0],
        policy=spec_default_policy,
        metric_name="expectancy_R",
    )
    assert isinstance(result, BootstrapCI)
    assert result.resample_count == spec_default_policy.bootstrap_resample_count


def test_render_class_b_resample_count_from_policy(policy_factory):
    """Plan §D acceptance: resample_count comes from policy."""
    policy = policy_factory(bootstrap_resample_count=500)
    result = render_class_b(
        samples=[1.0, 2.0, 3.0],
        policy=policy,
        metric_name="expectancy_R",
    )
    assert isinstance(result, BootstrapCI)
    assert result.resample_count == 500


# ---------------------------------------------------------------------------
# render_class_c
# ---------------------------------------------------------------------------

def test_render_class_c_below_floor_suppressed(spec_default_policy):
    """n=4 < class-C floor=5 → SuppressedMetric (suppression placeholder)."""
    result = render_class_c(
        value=1.5, n=4, n_wins=2, n_losses=2,
        policy=spec_default_policy, metric_name="profit_factor",
    )
    assert isinstance(result, SuppressedMetric)
    assert "n too low" in result.placeholder_text


def test_render_class_c_no_wins_returns_diversity_suppressed(spec_default_policy):
    """n>=floor but n_wins=0 → SuppressedMetric (diversity placeholder)."""
    result = render_class_c(
        value=None, n=10, n_wins=0, n_losses=10,
        policy=spec_default_policy, metric_name="profit_factor",
    )
    assert isinstance(result, SuppressedMetric)
    assert "Insufficient outcome diversity" in result.placeholder_text


def test_render_class_c_no_losses_returns_diversity_suppressed(spec_default_policy):
    """Same as no_wins but for n_losses=0."""
    result = render_class_c(
        value=None, n=10, n_wins=10, n_losses=0,
        policy=spec_default_policy, metric_name="profit_factor",
    )
    assert isinstance(result, SuppressedMetric)
    assert "Insufficient outcome diversity" in result.placeholder_text


def test_render_class_c_value_and_badges_when_diversity_passes(spec_default_policy):
    """n>=floor + n_wins>=1 + n_losses>=1 → (value, HonestyBadges)."""
    result = render_class_c(
        value=2.5, n=10, n_wins=6, n_losses=4,
        policy=spec_default_policy, metric_name="profit_factor",
    )
    assert isinstance(result, tuple)
    value, badges = result
    assert value == 2.5
    assert isinstance(badges, HonestyBadges)
    # n=10 < global_confidence_floor_n=20 → warning visible.
    assert badges.confidence_floor_warning is True
    # n=10 not in [3, 5) → low_confidence not visible.
    assert badges.low_confidence_warning is False


def test_render_class_c_value_above_global_floor_drops_warning(spec_default_policy):
    """n=20 >= global_confidence_floor_n → no confidence_floor_warning."""
    result = render_class_c(
        value=2.5, n=20, n_wins=12, n_losses=8,
        policy=spec_default_policy, metric_name="profit_factor",
    )
    assert isinstance(result, tuple)
    _, badges = result
    assert badges.confidence_floor_warning is False


def test_render_class_c_rejects_negative_n_wins(spec_default_policy):
    with pytest.raises(ValueError, match="n_wins >= 0"):
        render_class_c(
            value=1.0, n=10, n_wins=-1, n_losses=5,
            policy=spec_default_policy, metric_name="profit_factor",
        )


# ---------------------------------------------------------------------------
# render_class_d
# ---------------------------------------------------------------------------

def test_render_class_d_effective_n_below_5_suppressed(spec_default_policy):
    """effective_n=4 < spec-locked 5 → SuppressedMetric."""
    result = render_class_d(
        samples_in_window=[1.0, 2.0, 3.0, 4.0],
        window_n=10,
        policy=spec_default_policy,
        metric_name="process_grade_rolling_N",
        underlying_class="B",
    )
    assert isinstance(result, SuppressedMetric)
    assert result.n_required == 5


def test_render_class_d_underlying_b_at_5_line_drawable_partial_window(
    spec_default_policy,
):
    """effective_n=5 + window_n=10 → drawability 'rolling line drawable'
    + window_not_full_warning=True (spec §5.4 second band: 5<=eff<N).

    Codex R1 Major #1 regression: prior implementation suppressed
    drawability_text to 'show points only' in this band, contradicting
    the spec's "Render rolling line + window-narrowing badge" requirement.
    Discriminating test pins the spec-correct behavior.
    """
    samples = [0.5, 0.6, 0.7, 0.8, 0.9]
    result = render_class_d(
        samples_in_window=samples,
        window_n=10,
        policy=spec_default_policy,
        metric_name="process_grade_rolling_N",
        underlying_class="B",
    )
    assert isinstance(result, tuple)
    value, badges, drawability = result
    assert isinstance(value, BootstrapCI)
    assert drawability == "rolling line drawable"
    assert badges.window_not_full_warning is True  # 5 < N=10
    assert badges.confidence_floor_warning is True  # 5 < 20


def test_render_class_d_underlying_b_at_window_full_drawable(spec_default_policy):
    """effective_n=window_n=10 → drawability 'rolling line drawable',
    window_not_full_warning=False, confidence_floor_warning=True (10<20)."""
    samples = [0.5] * 10
    result = render_class_d(
        samples_in_window=samples,
        window_n=10,
        policy=spec_default_policy,
        metric_name="process_grade_rolling_N",
        underlying_class="B",
    )
    assert isinstance(result, tuple)
    _, badges, drawability = result
    assert drawability == "rolling line drawable"
    assert badges.window_not_full_warning is False
    assert badges.confidence_floor_warning is True  # 10 < 20


def test_render_class_d_underlying_b_above_global_floor_drops_warning(spec_default_policy):
    """effective_n=20 → both window_not_full_warning AND
    confidence_floor_warning dropped (spec §5.4 fourth band)."""
    samples = [0.5] * 20
    result = render_class_d(
        samples_in_window=samples,
        window_n=10,
        policy=spec_default_policy,
        metric_name="process_grade_rolling_N",
        underlying_class="B",
    )
    assert isinstance(result, tuple)
    _, badges, _ = result
    assert badges.confidence_floor_warning is False
    assert badges.window_not_full_warning is False


def test_render_class_d_point_branch_rejects_nan_sample(spec_default_policy):
    """Codex R1 Minor #2: 'point' branch validates samples for NaN/inf.

    Prior version would silently sum NaN into the rendered value; fix
    surfaces ValueError before the sum.
    """
    samples = [0.1, float("nan"), 0.3, 0.4, 0.5]
    with pytest.raises(ValueError, match="must be finite"):
        render_class_d(
            samples_in_window=samples,
            window_n=10,
            policy=spec_default_policy,
            metric_name="mistake_cost_R_rolling_N_total",
            underlying_class="point",
        )


def test_render_class_d_rejects_invalid_window_n(spec_default_policy):
    """Codex R2 Minor #2: window_n <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="window_n must be > 0"):
        render_class_d(
            samples_in_window=[1.0] * 5,
            window_n=0,
            policy=spec_default_policy,
            metric_name="bogus",
            underlying_class="B",
        )


def test_badges_for_n_is_public(spec_default_policy):
    """Codex R1 Minor #1: shared badge helper is public so view-model
    layers don't import a private helper or duplicate badge rules."""
    from swing.metrics.honesty import badges_for_n

    badges = badges_for_n(n=10, policy=spec_default_policy)
    assert badges.confidence_floor_warning is True   # 10 < 20
    assert badges.low_confidence_warning is False    # 10 not in [3, 5)
    assert badges.window_not_full_warning is False   # default for non-D classes


def test_render_class_d_underlying_a_returns_wilson_ci(spec_default_policy):
    """underlying_class='A' + events_in_window → WilsonCI in value slot."""
    result = render_class_d(
        samples_in_window=[1.0, 0.0, 1.0, 0.0, 1.0],
        window_n=10,
        policy=spec_default_policy,
        metric_name="disqualifying_violation_rate_rolling_N",
        underlying_class="A",
        events_in_window=3,
    )
    assert isinstance(result, tuple)
    value, _, _ = result
    assert isinstance(value, WilsonCI)
    assert math.isclose(value.point, 0.6, abs_tol=1e-3)


def test_render_class_d_underlying_a_requires_events_in_window(spec_default_policy):
    with pytest.raises(ValueError, match="requires events_in_window"):
        render_class_d(
            samples_in_window=[1.0, 0.0, 1.0, 0.0, 1.0],
            window_n=10,
            policy=spec_default_policy,
            metric_name="disqualifying_violation_rate_rolling_N",
            underlying_class="A",
            events_in_window=None,
        )


def test_render_class_d_underlying_point_returns_window_sum(spec_default_policy):
    """underlying_class='point' returns SUM over the window (spec §A.21
    `mistake_cost_R_rolling_N_total` semantics)."""
    samples = [0.1, -0.2, 0.3, -0.4, 0.5]  # sum = 0.3
    result = render_class_d(
        samples_in_window=samples,
        window_n=10,
        policy=spec_default_policy,
        metric_name="mistake_cost_R_rolling_N_total",
        underlying_class="point",
    )
    assert isinstance(result, tuple)
    value, _, _ = result
    assert math.isclose(value, 0.3, abs_tol=1e-9)


def test_render_class_d_underlying_c_diversity_failure(spec_default_policy):
    """underlying_class='C' + n_wins=0 → SuppressedMetric (diversity)."""
    result = render_class_d(
        samples_in_window=[1.0, 2.0, 3.0, 4.0, 5.0],
        window_n=10,
        policy=spec_default_policy,
        metric_name="payoff_ratio_rolling_N",
        underlying_class="C",
        n_wins=0,
        n_losses=5,
    )
    assert isinstance(result, SuppressedMetric)
    assert "Insufficient outcome diversity" in result.placeholder_text


def test_render_class_d_underlying_c_value_is_none_passthrough(spec_default_policy):
    """underlying_class='C' + diversity passes → value=None (caller computes ratio)."""
    result = render_class_d(
        samples_in_window=[1.0, 2.0, 3.0, 4.0, 5.0],
        window_n=10,
        policy=spec_default_policy,
        metric_name="payoff_ratio_rolling_N",
        underlying_class="C",
        n_wins=3,
        n_losses=2,
    )
    assert isinstance(result, tuple)
    value, _, _ = result
    assert value is None


def test_render_class_d_rejects_invalid_underlying_class(spec_default_policy):
    with pytest.raises(ValueError, match="underlying_class must be one of"):
        render_class_d(
            samples_in_window=[1.0] * 5,
            window_n=10,
            policy=spec_default_policy,
            metric_name="bogus",
            underlying_class="X",  # type: ignore[arg-type]
        )


def test_render_class_d_underlying_a_rejects_events_outside_range(spec_default_policy):
    """events_in_window > effective_n → ValueError."""
    with pytest.raises(ValueError, match="events_in_window must be in"):
        render_class_d(
            samples_in_window=[1.0] * 5,
            window_n=10,
            policy=spec_default_policy,
            metric_name="rate_rolling_N",
            underlying_class="A",
            events_in_window=6,
        )


# ---------------------------------------------------------------------------
# Dataclass __post_init__ validators
# ---------------------------------------------------------------------------

def test_wilson_ci_post_init_rejects_nan():
    with pytest.raises(ValueError, match="must be finite"):
        WilsonCI(point=float("nan"), lower=0.0, upper=1.0)


def test_wilson_ci_post_init_rejects_inf():
    with pytest.raises(ValueError, match="must be finite"):
        WilsonCI(point=0.5, lower=float("-inf"), upper=1.0)


def test_wilson_ci_post_init_rejects_lower_above_point():
    with pytest.raises(ValueError, match="invariant violated"):
        WilsonCI(point=0.5, lower=0.6, upper=1.0)


def test_wilson_ci_post_init_rejects_point_above_upper():
    with pytest.raises(ValueError, match="invariant violated"):
        WilsonCI(point=0.9, lower=0.0, upper=0.5)


def test_bootstrap_ci_post_init_rejects_invalid_resample_count():
    with pytest.raises(ValueError, match="resample_count must be >= 1"):
        BootstrapCI(point=1.0, lower=0.5, upper=1.5, resample_count=0)


def test_bootstrap_ci_post_init_rejects_nan():
    with pytest.raises(ValueError, match="must be finite"):
        BootstrapCI(point=float("nan"), lower=0.0, upper=1.0, resample_count=100)


def test_bootstrap_ci_post_init_rejects_invariant_violation():
    with pytest.raises(ValueError, match="invariant violated"):
        BootstrapCI(point=0.5, lower=0.6, upper=1.0, resample_count=100)


def test_suppressed_metric_post_init_rejects_negative_n():
    with pytest.raises(ValueError, match="n must be >= 0"):
        SuppressedMetric(
            metric_name="x", n=-1, n_required=3, placeholder_text="...",
        )


def test_suppressed_metric_post_init_rejects_zero_n_required():
    with pytest.raises(ValueError, match="n_required must be >= 1"):
        SuppressedMetric(
            metric_name="x", n=0, n_required=0, placeholder_text="...",
        )


# ---------------------------------------------------------------------------
# Honesty class enum sanity
# ---------------------------------------------------------------------------

def test_honesty_class_values():
    """Spec §5.1-§5.4 class assignments."""
    assert HonestyClass.A.value == "rate"
    assert HonestyClass.B.value == "mean"
    assert HonestyClass.C.value == "ratio"
    assert HonestyClass.D.value == "trend"
