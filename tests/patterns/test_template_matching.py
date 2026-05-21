"""Phase 13 T2.SB5 - template matching unit tests.

T-A.5.1 lands DTW core + Sakoe-Chiba band tests + similarity mapping +
min-max normalization + TemplateMatchHit validation. T-A.5.2 extends the
file with retrieval + pruning tests.

LOCKs honored:
- L1: spec section 5.7 BINDING text - Sakoe-Chiba band ratio 0.1,
  min-max normalization, 4-item pruning constants.
- L7: TemplateMatchHit frozen dataclass __post_init__ validation.
- L9: Sakoe-Chiba band ratio locked at 0.1.
- L10: min-max normalization (z-score is V2).
"""
from __future__ import annotations

import numpy as np
import pytest

from swing.patterns.template_matching import (
    SAKOE_CHIBA_WINDOW_RATIO,
    TemplateMatchExemplar,
    TemplateMatchHit,
    _dtw_distance,
    _min_max_normalize,
    _similarity_from_distance,
)

# ============================================================================
# T-A.5.1 - DTW core + Sakoe-Chiba band
# ============================================================================


class TestDTWCore:
    """T-A.5.1: 6+ discriminating tests for _dtw_distance + helpers."""

    def test_dtw_identical_series_distance_zero(self) -> None:
        """(a) DTW(identical, identical) = 0.0 (spec section 5.7 BINDING)."""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=float)
        b = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=float)
        d = _dtw_distance(a, b)
        assert d == 0.0

    def test_dtw_known_similar_matches_fixture(self) -> None:
        """(b) DTW between known-similar series matches hand-computed fixture.

        For a=[1,2,3] and b=[1,2,3,4], unconstrained DTW with L1 distance
        has known result = |3-4| = 1.0 (path (0,0)->(1,1)->(2,2)->(2,3);
        cell costs 0+0+0+1 = 1).
        """
        a = np.array([1.0, 2.0, 3.0], dtype=float)
        b = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
        d = _dtw_distance(a, b, sakoe_chiba_window_ratio=1.0)
        assert d == pytest.approx(1.0, abs=1e-9)

    def test_dtw_sakoe_chiba_band_prevents_over_warping(self) -> None:
        """(c) Sakoe-Chiba band reduces over-warping vs unconstrained DTW.

        For a series where the best warp path crosses many cells far from
        the diagonal, the constrained band yields a HIGHER distance than
        unconstrained DTW.
        """
        rng = np.random.default_rng(42)
        n = 50
        a = np.cumsum(rng.standard_normal(n))
        # Construct b with a half-overlap shift: unconstrained DTW can
        # nearly perfectly warp to align the overlap; the 0.1 band cannot.
        b = np.concatenate([np.zeros(n // 2), a[: n // 2]])
        d_unconstrained = _dtw_distance(a, b, sakoe_chiba_window_ratio=1.0)
        d_constrained = _dtw_distance(a, b, sakoe_chiba_window_ratio=0.1)
        assert d_constrained >= d_unconstrained
        assert d_constrained > d_unconstrained + 1.0

    def test_similarity_score_zero_distance_is_one(self) -> None:
        """(d) similarity_score normalization 0..1 (1=identical)."""
        s = _similarity_from_distance(0.0, max_distance=10.0)
        assert s == 1.0

    def test_similarity_score_max_distance_is_zero(self) -> None:
        """(d-bis) similarity_score saturates at 0 for distance >= max."""
        s = _similarity_from_distance(10.0, max_distance=10.0)
        assert s == 0.0
        s2 = _similarity_from_distance(50.0, max_distance=10.0)
        assert s2 == 0.0

    def test_min_max_normalization_applied_per_v2_brief_section_7(self) -> None:
        """(f) Min-max normalization applied per v2 brief section 7 LOCK.

        Normalized series spans [0.0, 1.0]; constant series degrade
        gracefully (returned as zeros to avoid divide-by-zero).
        """
        a = np.array([10.0, 20.0, 30.0, 40.0, 50.0], dtype=float)
        norm = _min_max_normalize(a)
        assert norm[0] == pytest.approx(0.0, abs=1e-12)
        assert norm[-1] == pytest.approx(1.0, abs=1e-12)
        assert np.all(norm >= 0.0) and np.all(norm <= 1.0)
        const = np.array([5.0, 5.0, 5.0], dtype=float)
        norm_const = _min_max_normalize(const)
        assert np.all(norm_const == 0.0)

    def test_dtw_invariant_under_uniform_scaling_via_min_max_normalize(self) -> None:
        """Two series identical up to a uniform scale match after min-max norm."""
        a = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
        b = a * 100.0
        d = _dtw_distance(_min_max_normalize(a), _min_max_normalize(b))
        assert d == pytest.approx(0.0, abs=1e-9)

    def test_sakoe_chiba_band_ratio_lock_constant(self) -> None:
        """Sakoe-Chiba ratio LOCKED at 0.1 (L9; spec section 5.7 line 672+674)."""
        assert SAKOE_CHIBA_WINDOW_RATIO == 0.1

    def test_template_match_hit_post_init_validates_similarity_range(self) -> None:
        """L7: TemplateMatchHit __post_init__ Literal/range validation.

        similarity_score MUST be in [0.0, 1.0]; out-of-range raises.
        """
        hit = TemplateMatchHit(exemplar_id=1, distance=0.5, similarity_score=0.8)
        assert hit.exemplar_id == 1
        with pytest.raises(ValueError):
            TemplateMatchHit(exemplar_id=1, distance=0.5, similarity_score=1.5)
        with pytest.raises(ValueError):
            TemplateMatchHit(exemplar_id=1, distance=0.5, similarity_score=-0.1)
        with pytest.raises(ValueError):
            TemplateMatchHit(exemplar_id=1, distance=-0.1, similarity_score=0.5)
        with pytest.raises(ValueError):
            TemplateMatchHit(
                exemplar_id=1, distance=float("nan"), similarity_score=0.5
            )

    def test_template_match_hit_rejects_bool_exemplar_id(self) -> None:
        """L7: int Type-check rejects bool (bool is subclass of int)."""
        with pytest.raises(TypeError):
            TemplateMatchHit(
                exemplar_id=True,  # type: ignore[arg-type]
                distance=0.0,
                similarity_score=1.0,
            )

    def test_template_match_exemplar_rejects_non_ndarray(self) -> None:
        """TemplateMatchExemplar __post_init__ guards close_prices type."""
        # Minimal PatternExemplar import - use a lazy import to keep
        # test imports tight.
        from swing.data.models import PatternExemplar

        exemplar = PatternExemplar(
            id=1,
            ticker="AAA",
            timeframe="daily",
            start_date="2024-01-01",
            end_date="2024-02-01",
            proposed_pattern_class="vcp",
            final_decision="confirmed",
            label_source="curated_gold",
            structural_evidence_json="{}",
            created_at="2024-02-02T00:00:00",
            created_by="operator",
            gold_validated_at="2024-02-02T00:00:00",
            geometric_score_json="{}",
            labeler_evidence_json="{}",
        )
        # Non-ndarray rejected.
        with pytest.raises(TypeError):
            TemplateMatchExemplar(
                exemplar=exemplar,
                close_prices=[1.0, 2.0, 3.0],  # type: ignore[arg-type]
            )
        # 2-D rejected.
        with pytest.raises(ValueError):
            TemplateMatchExemplar(
                exemplar=exemplar,
                close_prices=np.array([[1.0, 2.0], [3.0, 4.0]]),
            )
