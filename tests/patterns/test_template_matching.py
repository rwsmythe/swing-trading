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

from swing.data.models import PatternExemplar
from swing.patterns.template_matching import (
    EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT,
    EXEMPLAR_CORPUS_SUBSAMPLE_THRESHOLD,
    GEOMETRIC_SCORE_PREGATE_THRESHOLD,
    MAX_WINDOWS_PER_TICKER,
    SAKOE_CHIBA_WINDOW_RATIO,
    TemplateMatchExemplar,
    TemplateMatchHit,
    _dtw_distance,
    _min_max_normalize,
    _similarity_from_distance,
    cap_candidates_per_ticker,
    match_forward,
    match_reverse,
    subsample_exemplar_corpus,
)

# ============================================================================
# Helpers shared across T-A.5.1 + T-A.5.2 tests
# ============================================================================


def _make_exemplar(
    *,
    exemplar_id: int,
    pattern_class: str,
    ticker: str = "AAA",
    quality_grade: int | None = 3,
    start_date: str = "2024-01-01",
    end_date: str = "2024-02-01",
) -> PatternExemplar:
    """Build a PatternExemplar carrying minimal valid fields for tests."""
    return PatternExemplar(
        id=exemplar_id,
        ticker=ticker,
        timeframe="daily",
        start_date=start_date,
        end_date=end_date,
        proposed_pattern_class=pattern_class,
        final_decision="confirmed",
        label_source="curated_gold",
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00",
        created_by="operator",
        quality_grade=quality_grade,
        gold_validated_at="2024-02-02T00:00:00",
        geometric_score_json="{}",
        labeler_evidence_json="{}",
    )


def _bundle(
    *,
    exemplar_id: int,
    pattern_class: str,
    close_prices: np.ndarray,
    ticker: str = "AAA",
    quality_grade: int | None = 3,
) -> TemplateMatchExemplar:
    return TemplateMatchExemplar(
        exemplar=_make_exemplar(
            exemplar_id=exemplar_id,
            pattern_class=pattern_class,
            ticker=ticker,
            quality_grade=quality_grade,
        ),
        close_prices=close_prices,
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
        exemplar = _make_exemplar(exemplar_id=1, pattern_class="vcp")
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


# ============================================================================
# T-A.5.2 - match_forward + match_reverse retrieval + pruning LOCK
# ============================================================================


class TestMatchForward:
    """T-A.5.2: 6+ discriminating tests for retrieval + pruning."""

    def test_match_forward_returns_top_k_ordered_by_similarity(self) -> None:
        """(a) match_forward returns top_k hits ordered by similarity desc."""
        candidate = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
        ex_identical = _bundle(
            exemplar_id=1,
            pattern_class="vcp",
            close_prices=np.array([1.0, 2.0, 3.0, 2.0, 1.0]),
        )
        ex_shifted = _bundle(
            exemplar_id=2,
            pattern_class="vcp",
            close_prices=np.array([1.1, 2.1, 3.1, 2.1, 1.1]),
        )
        ex_different = _bundle(
            exemplar_id=3,
            pattern_class="vcp",
            close_prices=np.array([5.0, 1.0, 5.0, 1.0, 5.0]),
        )
        hits = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[ex_different, ex_shifted, ex_identical],
            top_k=3,
        )
        assert len(hits) == 3
        assert hits[0].similarity_score >= hits[1].similarity_score
        assert hits[1].similarity_score >= hits[2].similarity_score
        # Identical exemplar should rank first.
        assert hits[0].exemplar_id == 1

    def test_match_forward_per_pattern_class_filtering_pruning_1(self) -> None:
        """(b) Per-pattern filtering: VCP candidate vs only VCP exemplars."""
        candidate = np.array([1.0, 2.0, 3.0], dtype=float)
        ex_vcp = _bundle(
            exemplar_id=10,
            pattern_class="vcp",
            close_prices=np.array([1.0, 2.0, 3.0]),
        )
        ex_flat = _bundle(
            exemplar_id=20,
            pattern_class="flat_base",
            close_prices=np.array([1.0, 2.0, 3.0]),
        )
        ex_cwh = _bundle(
            exemplar_id=30,
            pattern_class="cup_with_handle",
            close_prices=np.array([1.0, 2.0, 3.0]),
        )
        hits = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[ex_vcp, ex_flat, ex_cwh],
            top_k=3,
        )
        assert {h.exemplar_id for h in hits} == {10}

    def test_match_forward_geometric_score_pregate_below_threshold_returns_empty(
        self,
    ) -> None:
        """(c) Geometric-score pre-gate: candidate < 0.4 -> empty hits."""
        candidate = np.array([1.0, 2.0, 3.0], dtype=float)
        ex_vcp = _bundle(
            exemplar_id=1,
            pattern_class="vcp",
            close_prices=np.array([1.0, 2.0, 3.0]),
        )
        hits = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[ex_vcp],
            top_k=3,
            geometric_score=0.35,
        )
        assert hits == []
        # At or above pre-gate -> DTW fires.
        hits_pass = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[ex_vcp],
            top_k=3,
            geometric_score=0.40,
        )
        assert len(hits_pass) == 1
        assert GEOMETRIC_SCORE_PREGATE_THRESHOLD == 0.4

    def test_match_forward_empty_exemplar_corpus_returns_empty_list(self) -> None:
        """(e) Edge case: empty exemplar corpus returns empty list."""
        candidate_close = np.array([1.0, 2.0, 3.0], dtype=float)
        hits = match_forward(
            candidate_close_prices=candidate_close,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[],
            top_k=3,
        )
        assert hits == []

    def test_cap_candidates_per_ticker_pruning_3(self) -> None:
        """(d) Max-windows-per-ticker = 3 per spec section 5.7 pruning #3."""
        from datetime import date
        assert MAX_WINDOWS_PER_TICKER == 3
        candidates: list[tuple[str, date]] = [
            ("AAA", date(2024, 1, 1)),
            ("AAA", date(2024, 2, 1)),
            ("AAA", date(2024, 3, 1)),
            ("AAA", date(2024, 4, 1)),  # 4th: must be dropped
            ("BBB", date(2024, 1, 1)),
            ("BBB", date(2024, 2, 1)),
        ]
        capped = cap_candidates_per_ticker(
            candidates,
            key=lambda c: c[0],
            max_per_ticker=MAX_WINDOWS_PER_TICKER,
        )
        aaa_count = sum(1 for c in capped if c[0] == "AAA")
        bbb_count = sum(1 for c in capped if c[0] == "BBB")
        assert aaa_count == MAX_WINDOWS_PER_TICKER == 3
        assert bbb_count == 2
        # Order preserved (top-3 AAA + all BBB).
        assert capped[0] == ("AAA", date(2024, 1, 1))
        assert capped[2] == ("AAA", date(2024, 3, 1))

    def test_subsample_exemplar_corpus_pruning_4(self) -> None:
        """(e) Exemplar corpus subsampling at 100+ rows (top-50 by quality)."""
        assert EXEMPLAR_CORPUS_SUBSAMPLE_THRESHOLD == 100
        assert EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT == 50
        # Below threshold: returned as-is.
        small_corpus = [
            _make_exemplar(
                exemplar_id=i, pattern_class="vcp", quality_grade=1 + (i % 5)
            )
            for i in range(50)
        ]
        out_small = subsample_exemplar_corpus(small_corpus)
        assert len(out_small) == 50
        # At threshold (== 100): returned as-is (only strict > triggers subsample).
        boundary_corpus = [
            _make_exemplar(
                exemplar_id=i, pattern_class="vcp", quality_grade=1 + (i % 5)
            )
            for i in range(100)
        ]
        out_boundary = subsample_exemplar_corpus(boundary_corpus)
        assert len(out_boundary) == 100
        # Above threshold: capped at 50 highest quality_grade.
        big_corpus = [
            _make_exemplar(
                exemplar_id=i, pattern_class="vcp", quality_grade=(i % 5) + 1
            )
            for i in range(120)
        ]
        out_big = subsample_exemplar_corpus(big_corpus)
        assert len(out_big) == EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT == 50
        kept_grades = sorted({e.quality_grade for e in out_big}, reverse=True)
        assert kept_grades[0] == 5  # top tier represented
        # NULL quality_grade falls last (deterministic).
        big_with_nulls = list(big_corpus) + [
            _make_exemplar(
                exemplar_id=200 + i, pattern_class="vcp", quality_grade=None
            )
            for i in range(20)
        ]
        out_with_nulls = subsample_exemplar_corpus(big_with_nulls)
        assert len(out_with_nulls) == EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT
        assert all(e.quality_grade is not None for e in out_with_nulls)

    def test_match_reverse_returns_top_k_candidates_for_exemplar(self) -> None:
        """(f) match_reverse: given exemplar, return top_k candidate hits."""
        from dataclasses import dataclass

        exemplar_close = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)

        @dataclass(frozen=True)
        class _Candidate:
            candidate_id: int
            pattern_class: str
            ticker: str
            close_prices: np.ndarray

        c_identical = _Candidate(
            candidate_id=11,
            pattern_class="vcp",
            ticker="AAA",
            close_prices=np.array([1.0, 2.0, 3.0, 2.0, 1.0]),
        )
        c_shifted = _Candidate(
            candidate_id=12,
            pattern_class="vcp",
            ticker="BBB",
            close_prices=np.array([1.1, 2.1, 3.1, 2.1, 1.1]),
        )
        c_off_class = _Candidate(
            candidate_id=13,
            pattern_class="flat_base",
            ticker="CCC",
            close_prices=np.array([1.0, 2.0, 3.0, 2.0, 1.0]),
        )
        hits = match_reverse(
            exemplar_close_prices=exemplar_close,
            exemplar_pattern_class="vcp",
            candidate_corpus=[c_off_class, c_shifted, c_identical],
            top_k=10,
        )
        ids = [h.exemplar_id for h in hits]
        # Off-class candidate filtered out.
        assert 13 not in ids
        # Identical candidate ranks first.
        assert ids[0] == 11

    def test_match_forward_subsampling_kicks_in_above_100_rows(self) -> None:
        """Integration test: match_forward respects subsampling pruning #4.

        Plant 105 same-class exemplars; only 50 highest quality_grade
        survive into the DTW comparison set; match_forward returns at
        most top_k=3 hits drawn from that subsampled set.
        """
        rng = np.random.default_rng(7)
        candidate = np.cumsum(rng.standard_normal(20))
        exemplars = []
        for i in range(105):
            qg = (i % 5) + 1  # 1..5
            series = candidate + rng.standard_normal(20) * 0.1
            exemplars.append(
                _bundle(
                    exemplar_id=i + 1,
                    pattern_class="vcp",
                    close_prices=series.astype(float),
                    quality_grade=qg,
                )
            )
        hits = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=exemplars,
            top_k=3,
        )
        # Returned at most top_k.
        assert len(hits) <= 3
        # The subsampling kept top-50 quality_grade exemplars only.
        # Build the set of ids that COULD have been in the subsampled
        # cohort: the top 50 by quality_grade DESC then id ASC.
        from swing.patterns.template_matching import (
            subsample_exemplar_corpus as _subsample,
        )
        survivors = {
            e.id for e in _subsample([b.exemplar for b in exemplars])
        }
        assert all(h.exemplar_id in survivors for h in hits)

    def test_match_forward_isolates_bad_exemplar_from_cohort(self) -> None:
        """Codex R1 Minor #1: one NaN exemplar must NOT suppress all hits.

        Discriminating per `feedback_regression_test_arithmetic`:
        - Pre-fix: ``_min_max_normalize`` raises on the NaN-bearing
          exemplar; the exception propagates out of ``match_forward``;
          the pipeline caller's broad try/except buries the failure +
          stamps ``template_match_score=None`` for the row even though
          valid same-class exemplars exist in the cohort.
        - Post-fix: per-exemplar try/except catches the ValueError from
          ``_min_max_normalize``; the bad exemplar is skipped + the
          remaining valid exemplars contribute hits to the cohort.
        """
        candidate = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=float)
        # Bad exemplar: NaN in close_prices (slips past
        # ``TemplateMatchExemplar.__post_init__`` which only checks
        # type + ndim, NOT finiteness).
        bad_bundle = _bundle(
            exemplar_id=1,
            pattern_class="vcp",
            close_prices=np.array([1.0, np.nan, 3.0, 4.0, 5.0]),
        )
        good_bundle = _bundle(
            exemplar_id=2,
            pattern_class="vcp",
            close_prices=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
        )
        hits = match_forward(
            candidate_close_prices=candidate,
            candidate_pattern_class="vcp",
            candidate_ticker="AAA",
            exemplar_corpus=[bad_bundle, good_bundle],
            top_k=3,
        )
        # The good exemplar is the only survivor; bad exemplar skipped.
        assert len(hits) == 1
        assert hits[0].exemplar_id == 2
        assert hits[0].similarity_score == pytest.approx(1.0, abs=1e-9)

    def test_dtw_pure_python_no_scipy_dependency(self) -> None:
        """The template_matching module MUST NOT import scipy.

        L1 LOCK: pure-Python DTW per plan section G.7 T-A.5.1 step 2.
        Greps the source for ``import scipy`` / ``from scipy`` patterns.
        """
        import ast
        import importlib

        mod = importlib.import_module("swing.patterns.template_matching")
        with open(mod.__file__, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scipy"), (
                        f"scipy import found at top level: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("scipy"), (
                    f"scipy from-import found: {node.module}"
                )
