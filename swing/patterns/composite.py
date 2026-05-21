"""Phase 13 T2.SB5 T-A.5.3 - Composite scoring per spec section 5.8.

Pure function combining detector-rule geometric_score with the template-
match overlay into the V1 composite_score persisted on the
``pattern_evaluations.composite_score`` column.

Spec section 5.8 V1 formula LOCK (lines 712-720 BINDING):
    composite_score = 0.60 * geometric_score + 0.40 * template_match_score
    wrapped via min(1.0, ...) per line 712 + 718.

When ``template_match_score`` is unavailable (first run; exemplar corpus
empty for a class; candidate skipped per pruning #2 pre-gate), the
fallback is ``composite_score = geometric_score`` per line 720 LOCK -
BUT the min(1.0, ...) wrap STILL applies because DBW evidence may reach
1.10 per spec section 5.8 line 718 + section 10.5 line 1325 (undercut
bonus). Without the fallback-path clamp, drift_logging
``_composite_score_histogram`` (section 5.11 LOCK [0.0, 1.0]) raises
ValueError that aborts the entire Pass-2 emit loop (T2.SB4 R2 Critical
#1 forward-binding lesson).

LOCKs (per dispatch brief section 6):
- L1: spec section 5.8 BINDING text fidelity (coefficients + clamp).
- L2: ZERO DB writes (pure function).
- L5: min(1.0, ...) wrap PRESERVED on BOTH paths.
- L11: composite_score is 0..1 evidence-strength signal, NOT a
  probability. V2 calibration (Brier + isotonic) per plan V2-6.
"""
from __future__ import annotations

import math

# Spec section 5.8 line 714 V1 LOCK formula coefficients. Sum exactly to 1.0.
COMPOSITE_GEOMETRIC_WEIGHT: float = 0.60
COMPOSITE_TEMPLATE_MATCH_WEIGHT: float = 0.40

# Spec section 5.8 line 712 composite cap.
COMPOSITE_SCORE_MAX: float = 1.0


def compute_composite_score(
    *,
    geometric: float,
    template_match: float | None,
) -> float:
    """Compute the V1 composite_score per spec section 5.8 LOCK.

    Formula (BINDING):
        composite_score = min(
            1.0,
            0.60 * geometric_score + 0.40 * template_match_score
        )

    Fallback (BINDING, line 720): when ``template_match`` is None,
    composite = min(1.0, geometric_score). The clamp is preserved on
    the fallback path because DBW evidence may reach 1.10 (undercut
    bonus per spec section 5.8 line 718 + section 10.5 line 1325) +
    drift_logging._composite_score_histogram (spec section 5.11 LOCK)
    rejects non-[0, 1] values.

    Returns a float in [0.0, 1.0] (post-clamp). This is an
    evidence-strength signal for operator triage, NOT a probability
    (L11; V1 NOT calibrated per spec section 5.8 line 724 LOCK).

    Args:
        geometric: rule-tier geometric_score in [0.0, 1.10] (1.10 cap
          covers DBW undercut bonus; other detectors land in [0.0, 1.0]).
        template_match: top-K max similarity in [0.0, 1.0] from
          match_forward, OR None when template matching is unavailable
          (empty exemplar corpus; geometric < pre-gate; skipped per
          pruning).

    Raises:
        ValueError: on non-finite inputs (NaN/inf) or geometric < 0 or
          template_match outside [0.0, 1.0].
    """
    # L1 safety: defense-in-depth against NaN/inf + invalid range.
    if not math.isfinite(geometric):
        raise ValueError(
            f"geometric must be finite, got {geometric!r}"
        )
    if geometric < 0.0:
        raise ValueError(
            f"geometric must be >= 0.0, got {geometric!r}"
        )
    if template_match is not None:
        if not math.isfinite(template_match):
            raise ValueError(
                f"template_match must be finite, got {template_match!r}"
            )
        if not (0.0 <= template_match <= 1.0):
            raise ValueError(
                f"template_match must be in [0.0, 1.0], got {template_match!r}"
            )

    if template_match is None:
        # L5 + L1 line 720 fallback - still clamp because DBW evidence
        # may reach 1.10.
        return min(COMPOSITE_SCORE_MAX, geometric)

    pre_clamp = (
        COMPOSITE_GEOMETRIC_WEIGHT * geometric
        + COMPOSITE_TEMPLATE_MATCH_WEIGHT * template_match
    )
    # L5 + section 5.8 line 712 clamp. Lower bound is 0.0 by input
    # contract (geometric >= 0 + template_match in [0, 1]).
    return min(COMPOSITE_SCORE_MAX, pre_clamp)
