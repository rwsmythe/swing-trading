"""Spec §5 low-sample-size honesty policy — Wilson CI + bootstrap CI + suppression dispatcher.

Implements the §A.7 honesty utility interface (binding for Sub-bundles B-E).

Honesty classes (per spec §5.1-§5.4):
- A (rate): Wilson CI on k/n proportion; suppress below ``policy.low_sample_size_threshold_class_a_n``.
- B (mean): bootstrap CI on samples; suppress below ``policy.low_sample_size_threshold_class_b_n``.
- C (ratio): point estimate (no CI in V1); suppress below ``policy.low_sample_size_threshold_class_c_n``
  OR when win-loss diversity insufficient.
- D (trend): rolling-window line; spec-locked effective_n>=5 threshold for line drawability,
  ``policy.low_sample_size_threshold_class_d_n`` for window-fullness badge,
  ``policy.global_confidence_floor_n`` for confidence-floor warning.

All cross-class confidence-warning removal uses ``policy.global_confidence_floor_n``
(decoupling discipline per spec §5 R3 M2 + R4 M1).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from swing.data.models import RiskPolicy

# Spec-locked threshold: Class D rolling line is suppressed when effective_n
# in window is below 5. NOT operator-configurable in V1 — policy.class_d_n
# instead captures the rolling WINDOW SIZE (N, default 10).
CLASS_D_LINE_DRAW_FLOOR: int = 5

# Spec-locked z-value for two-sided 95% CI (alpha=0.05).
_Z_975: float = 1.959963984540054


def _suppression_placeholder(*, metric_name: str, n: int, n_required: int) -> str:
    """Spec §5.6 suppression text format: italic placeholder with current vs required n."""
    return f"[{metric_name}: n too low (current: {n}, need: ≥{n_required})]"


def _diversity_placeholder(*, metric_name: str) -> str:
    """Spec §5.3 ratio-metric diversity-failure placeholder."""
    return f"[{metric_name}: Insufficient outcome diversity]"


def _check_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (NaN/inf rejected); got {value!r}")


@dataclass(frozen=True)
class WilsonCI:
    point: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        _check_finite("point", self.point)
        _check_finite("lower", self.lower)
        _check_finite("upper", self.upper)
        if not (self.lower <= self.point <= self.upper):
            raise ValueError(
                "WilsonCI invariant violated: require lower <= point <= upper; got "
                f"lower={self.lower!r}, point={self.point!r}, upper={self.upper!r}"
            )


@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lower: float
    upper: float
    resample_count: int

    def __post_init__(self) -> None:
        _check_finite("point", self.point)
        _check_finite("lower", self.lower)
        _check_finite("upper", self.upper)
        if not (self.lower <= self.point <= self.upper):
            raise ValueError(
                "BootstrapCI invariant violated: require lower <= point <= upper; got "
                f"lower={self.lower!r}, point={self.point!r}, upper={self.upper!r}"
            )
        if self.resample_count < 1:
            raise ValueError(
                f"BootstrapCI resample_count must be >= 1; got {self.resample_count!r}"
            )


@dataclass(frozen=True)
class SuppressedMetric:
    metric_name: str
    n: int
    n_required: int
    placeholder_text: str  # spec §5.6 format

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ValueError(f"SuppressedMetric.n must be >= 0; got {self.n!r}")
        if self.n_required < 1:
            raise ValueError(
                f"SuppressedMetric.n_required must be >= 1; got {self.n_required!r}"
            )


@dataclass(frozen=True)
class HonestyBadges:
    confidence_floor_warning: bool   # spec §5 — visible when n < global_confidence_floor_n
    low_confidence_warning: bool     # spec §5 — visible when 3 <= n < 5


class HonestyClass(StrEnum):
    A = "rate"     # Wilson CI; spec §5.1
    B = "mean"     # bootstrap CI; spec §5.2
    C = "ratio"    # point estimate (no CI in V1); spec §5.3
    D = "trend"    # rolling-window line; spec §5.4


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------

def wilson_ci(*, k: int, n: int, alpha: float = 0.05) -> WilsonCI:
    """Wilson score interval (standard, no continuity correction).

    Pure-Python implementation per Wikipedia "Binomial proportion confidence
    interval — Wilson score interval" primary formula. Returns WilsonCI with
    ``point`` = k/n (the unbiased sample proportion) and ``lower``/``upper``
    bounded to [0, 1] (clamped to absorb floating-point overshoot at edge
    cases k=0 or k=n).

    Raises ValueError on n<0, k<0, or k>n.

    For k=0, n=0 returns WilsonCI(0.0, 0.0, 0.0) — callers should normally
    funnel n<class-threshold through ``suppress_for_n`` first.
    """
    if not isinstance(k, int) or not isinstance(n, int):
        raise TypeError("wilson_ci requires integer k and n")
    if n < 0:
        raise ValueError(f"wilson_ci n must be >= 0; got {n!r}")
    if k < 0:
        raise ValueError(f"wilson_ci k must be >= 0; got {k!r}")
    if k > n:
        raise ValueError(f"wilson_ci k must be <= n; got k={k!r}, n={n!r}")
    if not (0 < alpha < 1):
        raise ValueError(f"wilson_ci alpha must be in (0, 1); got {alpha!r}")

    if n == 0:
        return WilsonCI(point=0.0, lower=0.0, upper=0.0)

    # z for two-sided CI at given alpha (only alpha=0.05 needs ~1.96 for V1;
    # general implementation via rational approximation kept for future use).
    z = _z_for_alpha(alpha)
    p_hat = k / n
    z_sq = z * z
    denom = 1.0 + z_sq / n
    center = (p_hat + z_sq / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n + z_sq / (4.0 * n * n))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    # `point` is the sample proportion (k/n), not the Wilson center, so the
    # downstream renderer can surface the unbiased value alongside the
    # smoothed CI bounds. Re-clamp inside [lower, upper] to preserve the
    # WilsonCI invariant at p_hat extremes (k=0 → p_hat=0.0 but lower=0.0
    # after clamp, so invariant holds without further work).
    point = max(lower, min(upper, p_hat))
    return WilsonCI(point=point, lower=lower, upper=upper)


def _z_for_alpha(alpha: float) -> float:
    """Two-sided z critical value for given alpha.

    V1 implementation: hardcoded for alpha=0.05 (the only value Phase 10
    surfaces use). Defends against silent drift if a future caller passes a
    different alpha by raising explicitly.
    """
    if alpha == 0.05:
        return _Z_975
    raise NotImplementedError(
        f"wilson_ci/bootstrap_ci_mean V1 only supports alpha=0.05; got {alpha!r}"
    )


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

def bootstrap_ci_mean(
    *,
    samples: list[float],
    resample_count: int,
    alpha: float = 0.05,
    rng_seed: int | None = None,
) -> BootstrapCI:
    """Bootstrap percentile CI for the mean of ``samples``.

    Uses ``random.Random(rng_seed)`` for reproducibility in tests. Production
    callers pass ``rng_seed=None`` for non-deterministic behavior.

    Per spec §5.2: 1000 resamples default (passed via ``resample_count``,
    sourced from ``policy.bootstrap_resample_count``); percentile method;
    alpha=0.05.

    Raises ValueError on empty samples, non-finite samples, or
    resample_count<1.
    """
    if not samples:
        raise ValueError("bootstrap_ci_mean requires non-empty samples")
    if resample_count < 1:
        raise ValueError(
            f"bootstrap_ci_mean resample_count must be >= 1; got {resample_count!r}"
        )
    if not (0 < alpha < 1):
        raise ValueError(f"bootstrap_ci_mean alpha must be in (0, 1); got {alpha!r}")
    for i, x in enumerate(samples):
        _check_finite(f"samples[{i}]", float(x))
    _ = _z_for_alpha(alpha)  # validate alpha is supported.

    rng = random.Random(rng_seed)  # noqa: S311 (non-cryptographic by design)
    n = len(samples)
    point = sum(samples) / n
    resampled_means = [
        sum(rng.choice(samples) for _ in range(n)) / n for _ in range(resample_count)
    ]
    resampled_means.sort()
    lo_idx = int(math.floor((alpha / 2.0) * resample_count))
    hi_idx = int(math.ceil((1.0 - alpha / 2.0) * resample_count)) - 1
    lo_idx = max(0, min(resample_count - 1, lo_idx))
    hi_idx = max(0, min(resample_count - 1, hi_idx))
    lower = min(resampled_means[lo_idx], point)
    upper = max(resampled_means[hi_idx], point)
    return BootstrapCI(
        point=point,
        lower=lower,
        upper=upper,
        resample_count=resample_count,
    )


# ---------------------------------------------------------------------------
# Suppression dispatcher
# ---------------------------------------------------------------------------

def _class_threshold(*, klass: HonestyClass, policy: RiskPolicy) -> int:
    """Per-class suppression floor.

    Per spec §A.7 + plan §A.18: Class A/B/C floors are policy-configurable
    via ``policy.low_sample_size_threshold_class_X_n``. Class D's line-
    drawability floor is spec-locked at 5 (``CLASS_D_LINE_DRAW_FLOOR``);
    the policy field ``low_sample_size_threshold_class_d_n`` captures the
    rolling WINDOW SIZE (N), not the suppression floor.
    """
    if klass is HonestyClass.A:
        return int(policy.low_sample_size_threshold_class_a_n)
    if klass is HonestyClass.B:
        return int(policy.low_sample_size_threshold_class_b_n)
    if klass is HonestyClass.C:
        return int(policy.low_sample_size_threshold_class_c_n)
    if klass is HonestyClass.D:
        return CLASS_D_LINE_DRAW_FLOOR
    raise ValueError(f"unknown HonestyClass: {klass!r}")


def suppress_for_n(
    *,
    metric_name: str,
    n: int,
    klass: HonestyClass,
    policy: RiskPolicy,
) -> SuppressedMetric | None:
    """Return SuppressedMetric if ``n`` is below the class suppression floor,
    else None.

    Per spec §5 + plan §A.7 decoupling discipline: this is the SUPPRESSION
    dispatcher (renders the placeholder when n is too low to render the
    metric at all). The confidence-floor BADGE visibility (separate concept)
    is decided per-class by ``render_class_*`` using
    ``policy.global_confidence_floor_n``.
    """
    floor = _class_threshold(klass=klass, policy=policy)
    if n < floor:
        return SuppressedMetric(
            metric_name=metric_name,
            n=n,
            n_required=floor,
            placeholder_text=_suppression_placeholder(
                metric_name=metric_name, n=n, n_required=floor,
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Per-class render dispatchers
# ---------------------------------------------------------------------------

def _badges_for_n(*, n: int, policy: RiskPolicy) -> HonestyBadges:
    """Confidence-floor badge composition per spec §5 decoupling discipline.

    - ``low_confidence_warning`` = True when 3 <= n < 5 (point-with-warning band).
    - ``confidence_floor_warning`` = True when n < ``global_confidence_floor_n``
      (CI rendered but interval too wide to be a headline).
    """
    return HonestyBadges(
        confidence_floor_warning=n < int(policy.global_confidence_floor_n),
        low_confidence_warning=3 <= n < 5,
    )


def render_class_a(
    *,
    k: int,
    n: int,
    policy: RiskPolicy,
    metric_name: str,
) -> WilsonCI | SuppressedMetric:
    """Class A rate-metric rendering per spec §5.1.

    - n < class-A floor → SuppressedMetric.
    - n >= floor → WilsonCI (point + lower + upper). Badge composition is the
      caller's responsibility via ``_badges_for_n`` or its analogue —
      Class A's WilsonCI is value-carrying only; badges layered at the
      view-model level so the same WilsonCI can be rendered with or without
      warnings (per spec §5 R3 M2 decoupling).

    Codex R2 Minor #1 note: the signature is deliberately VALUE-ONLY; per-
    surface VMs compose ``HonestyBadges`` alongside via ``_badges_for_n``.
    """
    suppressed = suppress_for_n(
        metric_name=metric_name, n=n, klass=HonestyClass.A, policy=policy,
    )
    if suppressed is not None:
        return suppressed
    return wilson_ci(k=k, n=n)


def render_class_b(
    *,
    samples: list[float],
    policy: RiskPolicy,
    metric_name: str,
) -> BootstrapCI | SuppressedMetric:
    """Class B mean-metric rendering per spec §5.2.

    - len(samples) < class-B floor → SuppressedMetric.
    - else → BootstrapCI from ``bootstrap_ci_mean`` with R from
      ``policy.bootstrap_resample_count``.
    """
    n = len(samples)
    suppressed = suppress_for_n(
        metric_name=metric_name, n=n, klass=HonestyClass.B, policy=policy,
    )
    if suppressed is not None:
        return suppressed
    return bootstrap_ci_mean(
        samples=list(samples),
        resample_count=int(policy.bootstrap_resample_count),
    )


def render_class_c(
    *,
    value: float | None,
    n: int,
    n_wins: int,
    n_losses: int,
    policy: RiskPolicy,
    metric_name: str,
) -> tuple[float | None, HonestyBadges] | SuppressedMetric:
    """Class C ratio-metric rendering per spec §5.3.

    - n < class-C floor OR n_wins<1 OR n_losses<1 → SuppressedMetric
      (diversity placeholder when n meets the floor but diversity fails).
    - else → (value, HonestyBadges).

    ``value`` may be None when the metric is mathematically undefined even
    after diversity passes (very rare; caller's responsibility).
    """
    if n_wins < 0 or n_losses < 0:
        raise ValueError(
            f"render_class_c requires n_wins >= 0 and n_losses >= 0; got "
            f"n_wins={n_wins!r}, n_losses={n_losses!r}"
        )
    floor = _class_threshold(klass=HonestyClass.C, policy=policy)
    if n < floor:
        return SuppressedMetric(
            metric_name=metric_name,
            n=n,
            n_required=floor,
            placeholder_text=_suppression_placeholder(
                metric_name=metric_name, n=n, n_required=floor,
            ),
        )
    if n_wins < 1 or n_losses < 1:
        return SuppressedMetric(
            metric_name=metric_name,
            n=n,
            n_required=floor,
            placeholder_text=_diversity_placeholder(metric_name=metric_name),
        )
    if value is not None:
        _check_finite("value", float(value))
    return (value, _badges_for_n(n=n, policy=policy))


def render_class_d(
    *,
    samples_in_window: list[float],
    window_n: int,
    policy: RiskPolicy,
    metric_name: str,
    underlying_class: Literal["A", "B", "C", "point"],
    events_in_window: int | None = None,
    n_wins: int | None = None,
    n_losses: int | None = None,
) -> tuple[WilsonCI | BootstrapCI | float | None, HonestyBadges, str] | SuppressedMetric:
    """Class D trend-metric rendering per spec §5.4 + plan §A.21.

    Returns a 3-tuple decoupling cadence (rolling-line drawability) from
    confidence (CI on per-window value):

      (value, badges, drawability_text)

    where ``value`` shape depends on ``underlying_class``:
      - "A" → WilsonCI (rate metric in window; ``events_in_window`` is the
        generic k count, e.g., disqualifying_violation_rate_rolling_N).
      - "B" → BootstrapCI (mean metric in window, e.g.,
        process_grade_rolling_N).
      - "C" → float | None (ratio metric; suppress without diversity).
      - "point" → float | None (sum-only metric, e.g.,
        mistake_cost_R_rolling_N_total).

    ``drawability_text`` is one of:
      - "rolling line drawable" — line should be rendered.
      - "show points only" — line suppressed; per-trade markers only.

    Cadence vs confidence decoupling (spec §5.4):
      - effective_n < ``CLASS_D_LINE_DRAW_FLOOR`` (5) → SuppressedMetric for
        the per-window VALUE (line suppressed; per-trade markers always
        shown at the template layer).
      - effective_n >= 5 → value rendered + ``HonestyBadges``:
        - ``confidence_floor_warning`` True when effective_n <
          ``global_confidence_floor_n``;
        - ``low_confidence_warning`` True when 3 <= effective_n < 5
          (unreachable here since suppression hits at <5; left True-able
          per the badge contract for completeness).
    """
    if underlying_class not in {"A", "B", "C", "point"}:
        raise ValueError(
            f"render_class_d underlying_class must be one of "
            f"'A'|'B'|'C'|'point'; got {underlying_class!r}"
        )
    effective_n = len(samples_in_window)
    if effective_n < CLASS_D_LINE_DRAW_FLOOR:
        return SuppressedMetric(
            metric_name=metric_name,
            n=effective_n,
            n_required=CLASS_D_LINE_DRAW_FLOOR,
            placeholder_text=_suppression_placeholder(
                metric_name=metric_name,
                n=effective_n,
                n_required=CLASS_D_LINE_DRAW_FLOOR,
            ),
        )

    badges = _badges_for_n(n=effective_n, policy=policy)
    drawability_text = (
        "rolling line drawable" if effective_n >= window_n else "show points only"
    )

    value: WilsonCI | BootstrapCI | float | None
    if underlying_class == "A":
        if events_in_window is None:
            raise ValueError(
                "render_class_d underlying_class='A' requires events_in_window"
            )
        if events_in_window < 0 or events_in_window > effective_n:
            raise ValueError(
                f"render_class_d events_in_window must be in [0, effective_n]; "
                f"got {events_in_window!r} (effective_n={effective_n})"
            )
        value = wilson_ci(k=int(events_in_window), n=effective_n)
    elif underlying_class == "B":
        value = bootstrap_ci_mean(
            samples=list(samples_in_window),
            resample_count=int(policy.bootstrap_resample_count),
        )
    elif underlying_class == "C":
        if n_wins is None or n_losses is None:
            raise ValueError(
                "render_class_d underlying_class='C' requires n_wins + n_losses"
            )
        if n_wins < 0 or n_losses < 0:
            raise ValueError(
                f"render_class_d requires n_wins >= 0 and n_losses >= 0; got "
                f"n_wins={n_wins!r}, n_losses={n_losses!r}"
            )
        if n_wins < 1 or n_losses < 1:
            return SuppressedMetric(
                metric_name=metric_name,
                n=effective_n,
                n_required=CLASS_D_LINE_DRAW_FLOOR,
                placeholder_text=_diversity_placeholder(metric_name=metric_name),
            )
        # Caller computes the ratio (profit_factor / payoff_ratio) from
        # cohort-grain win/loss sums; helper hands back None as a sentinel +
        # passes through the diversity-passed badges so the caller layers
        # the final value at the VM level. Spec §5.3 V1: no CI for ratios.
        value = None
    else:  # "point"
        # Spec §A.21 + §J.1.1: V1 "point" branch covers
        # mistake_cost_R_rolling_N_total — a SUM over the window. Returns the
        # raw sum (NOT mean) so the §4.8 secondary-axis surface renders the
        # mistake-cost trajectory honestly. V2.1 §VII.F amendment candidate
        # may add a sum-class with bootstrap CI on the window sum.
        value = float(sum(samples_in_window))

    return (value, badges, drawability_text)
