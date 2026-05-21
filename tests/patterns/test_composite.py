"""Phase 13 T2.SB5 T-A.5.3 - composite scoring tests.

Per spec section 5.8 (lines 708-724 BINDING):
    composite_score = 0.60 * geometric_score + 0.40 * template_match_score
    -> wrapped via min(1.0, ...) per section 5.8 line 712 + 718.

LOCKs honored:
- L1: spec section 5.8 BINDING text - coefficients (0.60 + 0.40),
  clamp (min(1.0, ...)), fallback (template_match_score=None ->
  composite = min(1.0, geometric_score)).
- L5: min(1.0, ...) wrap PRESERVED inside compute_composite_score on
  BOTH the template-bearing path AND the None-fallback path - DBW
  evidence may reach 1.10 per spec section 5.8 line 718 + section
  10.5 line 1325 undercut bonus.
- L11: composite_score is 0..1 evidence-strength, NOT probability.
"""
from __future__ import annotations

import pytest

from swing.patterns.composite import (
    COMPOSITE_GEOMETRIC_WEIGHT,
    COMPOSITE_TEMPLATE_MATCH_WEIGHT,
    compute_composite_score,
)


class TestCompositeFormula:
    """T-A.5.3: 4+ discriminating tests per spec section 5.8 LOCK."""

    def test_basic_arithmetic_60_40_weighting(self) -> None:
        """(a) compute_composite_score(0.8, 0.7) = min(1.0, 0.60*0.8 + 0.40*0.7).

        Pre-clamp result: 0.48 + 0.28 = 0.76 (within [0.0, 1.0];
        clamp passive).
        """
        s = compute_composite_score(geometric=0.8, template_match=0.7)
        # 0.60 * 0.8 + 0.40 * 0.7 = 0.48 + 0.28 = 0.76
        assert s == pytest.approx(0.76, abs=1e-12)

    def test_dbw_undercut_bonus_clamps_at_one(self) -> None:
        """(b) DBW geometric=1.10 + template=1.0 -> CLAMPED at 1.0.

        Pre-clamp result: 0.60 * 1.10 + 0.40 * 1.0 = 0.66 + 0.40 = 1.06.
        Post-clamp via min(1.0, ...): 1.0.

        This is the L5 LOCK + T2.SB4 R2 Critical #1 forward-binding
        discriminating test - without the clamp, drift_logging
        _composite_score_histogram (section 5.11 LOCK [0.0, 1.0]) would
        raise ValueError aborting the entire Pass-2 emit loop.
        """
        s = compute_composite_score(geometric=1.10, template_match=1.0)
        assert s == 1.0

    def test_template_match_none_fallback_preserves_clamp(self) -> None:
        """(c) template_match=None fallback ALSO applies min(1.0, ...) wrap.

        L5 LOCK + section 5.8 line 720 fallback semantics:
        - template_match=None for geometric=0.35 -> composite=0.35
        - template_match=None for geometric=1.10 (DBW pre-T2.SB5 path)
          -> composite=1.0 (clamped from raw 1.10; otherwise drift_logging
          histogram raises).
        """
        s_normal = compute_composite_score(geometric=0.35, template_match=None)
        assert s_normal == pytest.approx(0.35, abs=1e-12)
        s_dbw = compute_composite_score(geometric=1.10, template_match=None)
        assert s_dbw == 1.0
        s_zero = compute_composite_score(geometric=0.0, template_match=None)
        assert s_zero == 0.0

    def test_calibration_lock_doc_not_probability(self) -> None:
        """(d) Calibration LOCK: composite_score is 0..1 evidence-strength,
        NOT probability (per spec section 5.8 line 724).

        Documented in function docstring + dataclass docstring.
        """
        doc = (compute_composite_score.__doc__ or "").lower()
        assert "evidence-strength" in doc or "evidence strength" in doc
        assert "not a probability" in doc or "not probability" in doc

    def test_coefficient_constants_locked(self) -> None:
        """Coefficients 0.60 + 0.40 LOCKED per section 5.8 line 714."""
        assert COMPOSITE_GEOMETRIC_WEIGHT == 0.60
        assert COMPOSITE_TEMPLATE_MATCH_WEIGHT == 0.40
        # Weights sum to exactly 1.0 (sanity check on the locked values).
        assert (
            pytest.approx(1.0, abs=1e-12)
            == COMPOSITE_GEOMETRIC_WEIGHT + COMPOSITE_TEMPLATE_MATCH_WEIGHT
        )

    def test_composite_in_zero_to_one_for_all_template_paths(self) -> None:
        """Smoke: across the input grid, composite always in [0.0, 1.0]."""
        for geo in (0.0, 0.35, 0.4, 0.7, 1.0, 1.10):
            # None-fallback.
            s_none = compute_composite_score(geometric=geo, template_match=None)
            assert 0.0 <= s_none <= 1.0, f"geo={geo} -> {s_none}"
            # Template-bearing path.
            for tm in (0.0, 0.5, 1.0):
                s_tm = compute_composite_score(
                    geometric=geo, template_match=tm
                )
                assert 0.0 <= s_tm <= 1.0, (
                    f"geo={geo}, tm={tm} -> {s_tm}"
                )

    def test_rejects_non_finite_inputs(self) -> None:
        """L1 safety: NaN/inf inputs raise (defense-in-depth)."""
        with pytest.raises(ValueError):
            compute_composite_score(
                geometric=float("nan"), template_match=0.5
            )
        with pytest.raises(ValueError):
            compute_composite_score(
                geometric=0.5, template_match=float("inf")
            )

    def test_rejects_negative_geometric_score(self) -> None:
        """L1 safety: geometric_score must be >= 0 (caller bug, not input)."""
        with pytest.raises(ValueError):
            compute_composite_score(geometric=-0.1, template_match=0.5)
        # Negative template_match also invalid.
        with pytest.raises(ValueError):
            compute_composite_score(geometric=0.5, template_match=-0.1)

    def test_template_match_above_one_rejected(self) -> None:
        """template_match_score must be in [0.0, 1.0] per spec section 5.7
        line 692 - the only evidence-tier >1 source is geometric_score
        for DBW; template_match is normalized [0, 1] always.
        """
        with pytest.raises(ValueError):
            compute_composite_score(geometric=0.5, template_match=1.5)
