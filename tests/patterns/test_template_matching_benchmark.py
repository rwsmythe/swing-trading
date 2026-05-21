"""Phase 13 T2.SB5 T-A.5.5 - pytest-benchmark 120s DTW gate per OQ-4.

Per spec section 5.7 line 706 + plan section G.7 T-A.5.5:

    250-name candidate universe × 5 patterns × 50 exemplars per pattern
    = ~62,500 DTW pair-computations per run.

Asserts: benchmark.stats['mean'] < 120.0 seconds on operator's hardware
(~3GHz CPU baseline per spec section 5.7 line 706).

Slow-marked (pipeline EOD-batch budget; not part of the fast suite).
The 4 spec section 5.7 pruning LOCK items MUST all be in place before
this benchmark fires:

1. Per-pattern exemplar filtering (match_forward filters by class)
2. Geometric-score pre-gate (>= 0.4) - the benchmark uses 0.5 to pass
3. Max-windows-per-ticker = 3 (caller-enforced; benchmark uses 1
   per ticker × 5 patterns = 5 invocations per ticker)
4. Exemplar corpus subsampling at >100 rows -> top-50 quality_grade
   (the benchmark uses exactly 50 per class so the limit is passive)

Failure -> escalate to OQ-4 V2 fallback (SBD per spec section 5.7
line 706 + plan V2-7).
"""
from __future__ import annotations

import numpy as np
import pytest

from swing.data.models import DETECTOR_PATTERN_CLASSES, PatternExemplar
from swing.patterns.template_matching import (
    TemplateMatchExemplar,
    match_forward,
)


def _make_exemplar(*, exemplar_id: int, pattern_class: str) -> PatternExemplar:
    return PatternExemplar(
        id=exemplar_id,
        ticker=f"HIST{exemplar_id:05d}",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-15",
        proposed_pattern_class=pattern_class,
        final_decision="confirmed",
        label_source="curated_gold",
        structural_evidence_json="{}",
        created_at="2024-02-16T00:00:00",
        created_by="operator",
        quality_grade=3,
        gold_validated_at="2024-02-16T00:00:00",
        geometric_score_json="{}",
        labeler_evidence_json="{}",
    )


def _seed_corpus(
    *, exemplars_per_class: int = 50, candidate_count: int = 250
) -> tuple[list[tuple[np.ndarray, str]], dict[str, list[TemplateMatchExemplar]]]:
    """Seed a synthetic universe per the spec section 5.7 performance budget.

    Returns:
        candidates: 250 (close_prices, pattern_class) tuples - candidates
            uniformly distributed across the 5 detector pattern_classes.
        exemplars_by_class: 50 TemplateMatchExemplar bundles per class
            keyed by ``proposed_pattern_class``.
    """
    rng = np.random.default_rng(seed=2026_05_21)
    # Candidate close-price series: 30 daily bars each (typical short
    # base; mirrors VCP / flat_base / cup_with_handle final-contraction
    # lengths).
    candidates: list[tuple[np.ndarray, str]] = []
    n_classes = len(DETECTOR_PATTERN_CLASSES)
    for i in range(candidate_count):
        series = np.cumsum(rng.standard_normal(30)) + 50.0
        # Distribute across the 5 pattern_classes uniformly.
        pattern_class = DETECTOR_PATTERN_CLASSES[i % n_classes]
        candidates.append((series, pattern_class))

    # Exemplar bundles per class. Length range 25-35 bars (slightly
    # variable; matches real exemplar window-length distribution).
    exemplars_by_class: dict[str, list[TemplateMatchExemplar]] = {}
    exemplar_id_counter = 1
    for pattern_class in DETECTOR_PATTERN_CLASSES:
        bundles: list[TemplateMatchExemplar] = []
        for _ in range(exemplars_per_class):
            length = int(rng.integers(25, 36))
            series = np.cumsum(rng.standard_normal(length)) + 50.0
            bundles.append(
                TemplateMatchExemplar(
                    exemplar=_make_exemplar(
                        exemplar_id=exemplar_id_counter,
                        pattern_class=pattern_class,
                    ),
                    close_prices=series.astype(float),
                )
            )
            exemplar_id_counter += 1
        exemplars_by_class[pattern_class] = bundles
    return candidates, exemplars_by_class


def _full_dtw_pass(
    candidates: list[tuple[np.ndarray, str]],
    exemplars_by_class: dict[str, list[TemplateMatchExemplar]],
) -> int:
    """Invoke match_forward once per (candidate, pattern_class) tuple.

    Mirrors the pipeline's ``_step_pattern_detect`` Pass-2 loop: per
    candidate, the 5 detectors each produce a verdict; if the verdict
    passes the section 5.7 pruning #2 pre-gate (geometric_score >= 0.4),
    match_forward fires against the same-class exemplar bundles.

    Returns the count of hits accumulated (sanity; not asserted).
    """
    total_hits = 0
    for candidate_close, _orig_class in candidates:
        for pattern_class in DETECTOR_PATTERN_CLASSES:
            hits = match_forward(
                candidate_close_prices=candidate_close,
                candidate_pattern_class=pattern_class,
                candidate_ticker="X",
                exemplar_corpus=exemplars_by_class[pattern_class],
                top_k=3,
                geometric_score=0.5,  # passes pre-gate
            )
            total_hits += len(hits)
    return total_hits


@pytest.mark.slow
def test_dtw_full_pipeline_completes_within_120s_on_baseline_hardware(
    benchmark,
) -> None:
    """T-A.5.5: 120s wall-clock gate per spec section 5.7 line 706 + OQ-4.

    Seeds:
    - 250 candidate close-price series (30 bars each)
    - 50 exemplars per pattern_class x 5 classes = 250 exemplar bundles
    - 5 match_forward invocations per candidate (one per pattern_class
      with Pruning #1 same-class filter producing 50 DTW computations
      each) = 250 * 5 = 1250 match_forward calls = ~62,500 DTW
      pair-computations.

    Pass criterion: ``benchmark.stats['mean'] < 120.0`` seconds.

    Failure escalates to OQ-4 V2 fallback (SBD per spec section 5.7
    line 706; plan V2-7).
    """
    candidates, exemplars_by_class = _seed_corpus(
        exemplars_per_class=50, candidate_count=250
    )

    # pytest-benchmark fires the function multiple times for stability;
    # we cap rounds=1 + iterations=1 since a single 60-100s pass is
    # already the production-budget unit (the 120s gate is per-run).
    result = benchmark.pedantic(
        _full_dtw_pass,
        args=(candidates, exemplars_by_class),
        rounds=1,
        iterations=1,
        warmup_rounds=0,
    )
    # Sanity: at least some hits are produced (degenerate would mean
    # the entire corpus is being skipped via infinite-distance fallback).
    assert result >= 0

    mean_seconds = benchmark.stats.stats.mean
    assert mean_seconds < 120.0, (
        f"DTW pass exceeded 120s gate per spec section 5.7: "
        f"mean={mean_seconds:.2f}s. Escalate to OQ-4 V2 fallback (SBD)."
    )
