"""Phase 13 T2.SB5 - Template matching (DTW + Sakoe-Chiba band).

Pure-functions module per spec section 5.7 + plan section G.7. T-A.5.1
lands the DTW core + Sakoe-Chiba band helper + min-max normalization +
similarity score mapping + frozen dataclasses (TemplateMatchHit +
TemplateMatchExemplar). T-A.5.2 extends with retrieval functions.

NO database I/O; NO scipy dependency. NumPy-vectorized inner loop on the
DTW cost matrix; pure-Python control flow.

LOCKs (per dispatch brief section 6):
- L1: spec section 5.7 BINDING text - Sakoe-Chiba band ratio 0.1 + min-max
  normalization + 4-item pruning constants.
- L2: ZERO DB writes (pure functions).
- L7: TemplateMatchHit frozen dataclass with __post_init__ Literal/range
  validation per CLAUDE.md "Literal[...] not runtime-enforced" gotcha.
- L9: Sakoe-Chiba band ratio LOCKED at 0.1 (do NOT widen without operator
  escalation).
- L10: Min-max normalization on candidate + exemplar windows (z-score
  is V2 per plan V2-5).
- L11: similarity_score is 0..1 evidence-strength, NOT probability.

Forward-binding (T2.SB4 inheritance):
- Evidence-tier vs composite-tier cap distinction (this module produces
  similarity_score in [0.0, 1.0]; downstream composite scoring may
  exceed 1.0 on evidence-tier and is clamped at composite-tier per
  spec section 5.8).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import numpy as np

from swing.data.models import DETECTOR_PATTERN_CLASSES, PatternExemplar

# ============================================================================
# Section 5.7 LOCK constants (BINDING text; do NOT paraphrase per L1)
# ============================================================================

# Sakoe-Chiba band ratio per spec section 5.7 lines 672 + 674: "window = 0.1
# x series length". V1 LOCK; V2 territory if widened (per L9).
SAKOE_CHIBA_WINDOW_RATIO: float = 0.1

# Pruning LOCK #2 (spec section 5.7 line 702): DTW only fires for
# geometric_score >= 0.4 (rule-tier minimum signal); below-threshold
# candidates skip the DTW pass entirely. Constant introduced here at
# T-A.5.1 + consumed in T-A.5.2 match_forward.
GEOMETRIC_SCORE_PREGATE_THRESHOLD: float = 0.4

# Pruning LOCK #3 (spec section 5.7 line 703): at most 3 candidate
# windows per ticker per pattern per pipeline run.
MAX_WINDOWS_PER_TICKER: int = 3

# Pruning LOCK #4 (spec section 5.7 line 704): when pattern_exemplars for
# a given pattern_class > 100 rows, subsample top-50 by quality_grade.
EXEMPLAR_CORPUS_SUBSAMPLE_THRESHOLD: int = 100
EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT: int = 50


# ============================================================================
# Frozen dataclasses
# ============================================================================


@dataclass(frozen=True)
class TemplateMatchHit:
    """One hit from match_forward/match_reverse retrieval.

    Per spec section 5.7 lines 689-693. ``exemplar_id`` is the integer
    primary key of the matched row (PatternExemplar.id for forward;
    candidate_id surrogate for reverse). ``distance`` is the raw DTW
    distance (lower = closer). ``similarity_score`` is the normalized
    [0.0, 1.0] inverse (1.0 = identical, 0.0 = saturated max distance).

    L7 LOCK: __post_init__ validates range + finiteness per CLAUDE.md
    "Literal[...] not runtime-enforced" gotcha (T-A.1.5b R3 M#1 family).
    """
    exemplar_id: int
    distance: float
    similarity_score: float

    def __post_init__(self) -> None:
        if not isinstance(self.exemplar_id, int) or isinstance(
            self.exemplar_id, bool
        ):
            raise TypeError(
                f"exemplar_id must be int, got {type(self.exemplar_id).__name__}"
            )
        if not math.isfinite(self.distance):
            raise ValueError(
                f"distance must be finite, got {self.distance!r}"
            )
        if not math.isfinite(self.similarity_score):
            raise ValueError(
                f"similarity_score must be finite, got {self.similarity_score!r}"
            )
        if self.distance < 0.0:
            raise ValueError(
                f"distance must be >= 0, got {self.distance!r}"
            )
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError(
                "similarity_score must be in [0.0, 1.0], "
                f"got {self.similarity_score!r}"
            )


@dataclass(frozen=True)
class TemplateMatchExemplar:
    """Bundle of a PatternExemplar row + its OHLCV close-price series.

    The pipeline layer pre-fetches close-price arrays for each exemplar
    in scope (via OhlcvCache / ohlcv_archive) and constructs this bundle
    before invoking ``match_forward`` (T-A.5.2). Keeps ``match_forward``
    itself pure (no DB I/O) per L2.
    """
    exemplar: PatternExemplar
    close_prices: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.close_prices, np.ndarray):
            raise TypeError(
                "close_prices must be np.ndarray, "
                f"got {type(self.close_prices).__name__}"
            )
        if self.close_prices.ndim != 1:
            raise ValueError(
                f"close_prices must be 1-D, got shape {self.close_prices.shape}"
            )


# ============================================================================
# DTW core
# ============================================================================


def _min_max_normalize(series: np.ndarray) -> np.ndarray:
    """Min-max scale a 1-D series into [0.0, 1.0].

    Per spec section 5.7 line 695 + v2 brief section 7 LOCK (L10). Constant
    series degrade to all-zeros (no divide-by-zero); the absence of
    variation makes any further DTW-on-normalized-series degenerate
    anyway.
    """
    arr = np.asarray(series, dtype=float)
    if arr.ndim != 1:
        raise ValueError(
            f"_min_max_normalize: series must be 1-D, got shape {arr.shape}"
        )
    if arr.size == 0:
        return arr.copy()
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            "_min_max_normalize: series contains non-finite values; caller "
            "must clean before invoking"
        )
    mn = float(arr.min())
    mx = float(arr.max())
    rng = mx - mn
    if rng <= 0.0:
        return np.zeros_like(arr)
    return (arr - mn) / rng


def _dtw_distance(
    a: np.ndarray,
    b: np.ndarray,
    *,
    sakoe_chiba_window_ratio: float = SAKOE_CHIBA_WINDOW_RATIO,
) -> float:
    """Dynamic Time Warping distance with Sakoe-Chiba band.

    Pure-Python DTW per plan section G.7 T-A.5.1 step 2 (NO scipy).
    NumPy-vectorized cost-row computation; Python row+cell loop for
    the DP recurrence (each cell depends on D[i-1, j], D[i, j-1],
    D[i-1, j-1] which is not safely vectorizable in pure NumPy).

    Distance metric: absolute difference (L1; chosen for numerical
    stability + interpretability over squared L2).

    Sakoe-Chiba band: cells (i, j) with abs(i - j) > window are forbidden
    (cost = +inf). ``window = ceil(sakoe_chiba_window_ratio * max(N, M))``;
    when ratio >= 1.0 the band collapses to unconstrained DTW.

    Per spec section 5.7 lines 671-674; L9 LOCK at 0.1.
    """
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    if a_arr.ndim != 1 or b_arr.ndim != 1:
        raise ValueError(
            "_dtw_distance: both series must be 1-D, got "
            f"{a_arr.shape} + {b_arr.shape}"
        )
    n = a_arr.size
    m = b_arr.size
    if n == 0 or m == 0:
        return float("inf")
    window = max(1, int(math.ceil(sakoe_chiba_window_ratio * max(n, m))))
    inf_cost = float("inf")
    dp = np.full((n + 1, m + 1), inf_cost, dtype=float)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        j_lo = max(1, i - window)
        j_hi = min(m, i + window)
        if j_hi < j_lo:
            continue
        a_i = a_arr[i - 1]
        b_slice = b_arr[j_lo - 1 : j_hi]
        cost_row = np.abs(b_slice - a_i)
        for k, j in enumerate(range(j_lo, j_hi + 1)):
            prev = min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
            dp[i, j] = cost_row[k] + prev
    return float(dp[n, m])


def _similarity_from_distance(distance: float, *, max_distance: float) -> float:
    """Map DTW distance to a similarity score in [0.0, 1.0].

    1.0 = identical (distance == 0); 0.0 = saturated (distance >= max_distance).
    Linear inverse: ``s = max(0, 1 - distance / max_distance)``.

    L11 LOCK: this is an evidence-strength signal, NOT a probability.
    Calibration (Brier + isotonic regression) is V2 per plan V2-6.
    """
    if max_distance <= 0.0:
        return 1.0 if distance == 0.0 else 0.0
    if not math.isfinite(distance):
        return 0.0
    s = 1.0 - (distance / max_distance)
    if s < 0.0:
        return 0.0
    if s > 1.0:
        return 1.0
    return s


# ============================================================================
# Pruning helpers (LOCK #3 + #4) - T-A.5.2
# ============================================================================


T = TypeVar("T")


def cap_candidates_per_ticker(
    candidates: Iterable[T],
    *,
    key: Callable[[T], str],
    max_per_ticker: int = MAX_WINDOWS_PER_TICKER,
) -> list[T]:
    """Cap candidate windows at ``max_per_ticker`` per ticker.

    Per spec section 5.7 pruning #3 (L8 LOCK; default 3). Caller is
    responsible for pre-sorting by anchor strength (zigzag-pivot down-swing
    magnitude or equivalent). This helper preserves caller order and
    drops surplus per-ticker tail entries.

    The cap is scoped per (ticker, pattern_class) at the caller's
    iteration boundary; this helper takes a single ticker-extracting
    key function and caps globally - call once per pattern_class.
    """
    if max_per_ticker < 1:
        raise ValueError(
            f"max_per_ticker must be >= 1, got {max_per_ticker}"
        )
    counts: dict[str, int] = {}
    out: list[T] = []
    for c in candidates:
        ticker = key(c)
        n = counts.get(ticker, 0)
        if n >= max_per_ticker:
            continue
        out.append(c)
        counts[ticker] = n + 1
    return out


def subsample_exemplar_corpus(
    corpus: Sequence[PatternExemplar],
    *,
    threshold: int = EXEMPLAR_CORPUS_SUBSAMPLE_THRESHOLD,
    limit: int = EXEMPLAR_CORPUS_SUBSAMPLE_LIMIT,
) -> list[PatternExemplar]:
    """Subsample exemplar corpus to ``limit`` highest quality_grade.

    Per spec section 5.7 pruning #4. STRICT > threshold triggers (count
    == threshold returns as-is). Ranking: quality_grade DESC, then
    exemplar.id ASC (deterministic; NULL quality_grade ranks last).

    The pipeline layer applies this PER pattern_class (caller pre-filters
    the corpus by pattern_class). This helper is class-agnostic.
    """
    if len(corpus) <= threshold:
        return list(corpus)

    def _sort_key(e: PatternExemplar) -> tuple[int, float, int]:
        # First key: NULL flag (0 for valued, 1 for NULL) - NULL sorts last.
        null_flag = 0 if e.quality_grade is not None else 1
        # Second key: -quality_grade (DESC).
        qg = -float(e.quality_grade) if e.quality_grade is not None else 0.0
        # Third key: id ASC (deterministic tie-break; treat None id as a
        # large sentinel so ID-less synthetic exemplars sort last).
        eid = int(e.id) if e.id is not None else 2**31
        return (null_flag, qg, eid)

    ranked = sorted(corpus, key=_sort_key)
    return ranked[:limit]


# ============================================================================
# Retrieval (T-A.5.2)
# ============================================================================


def match_forward(
    *,
    candidate_close_prices: np.ndarray,
    candidate_pattern_class: str,
    candidate_ticker: str,
    exemplar_corpus: Sequence[TemplateMatchExemplar],
    top_k: int = 3,
    geometric_score: float | None = None,
) -> list[TemplateMatchHit]:
    """Forward retrieval: candidate -> top-K most-similar historical bases.

    Per spec section 5.7 (V1 LOCK; 4-item pruning):
    - #1 per-pattern filtering (candidate_pattern_class vs
      exemplar.proposed_pattern_class)
    - #2 geometric_score pre-gate (skip when < 0.4)
    - #3 max-windows-per-ticker (caller's responsibility; not enforced here)
    - #4 exemplar corpus subsampling (>100 rows -> top-50 by quality_grade)

    Returns ``top_k`` hits ordered by similarity_score DESC. Empty list
    when corpus empty OR pre-gate fails OR no exemplars match the
    candidate's pattern_class.

    The function is PURE: no DB I/O, no logging side-effects. Caller
    pre-fetches close-price arrays for each exemplar.
    """
    # Pruning #2: geometric_score pre-gate.
    if (
        geometric_score is not None
        and geometric_score < GEOMETRIC_SCORE_PREGATE_THRESHOLD
    ):
        return []
    if candidate_pattern_class not in DETECTOR_PATTERN_CLASSES:
        raise ValueError(
            f"candidate_pattern_class must be one of {DETECTOR_PATTERN_CLASSES}, "
            f"got {candidate_pattern_class!r}"
        )
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")
    if not exemplar_corpus:
        return []

    # Pruning #1: same pattern_class only. Exemplars compare against the
    # candidate's pattern_class via PatternExemplar.proposed_pattern_class
    # (the rule-tier label of the historical base).
    filtered_exemplars: list[PatternExemplar] = [
        bundle.exemplar
        for bundle in exemplar_corpus
        if bundle.exemplar.proposed_pattern_class == candidate_pattern_class
    ]
    if not filtered_exemplars:
        return []

    # Pruning #4: subsample if corpus exceeds threshold.
    subsampled_rows = subsample_exemplar_corpus(filtered_exemplars)
    rows_by_id: dict[int, PatternExemplar] = {
        int(e.id): e for e in subsampled_rows if e.id is not None
    }
    bundles_by_id: dict[int, TemplateMatchExemplar] = {}
    for bundle in exemplar_corpus:
        eid = bundle.exemplar.id
        if eid is None:
            continue
        if int(eid) in rows_by_id:
            bundles_by_id[int(eid)] = bundle

    if not bundles_by_id:
        return []

    # Normalize candidate ONCE.
    candidate_norm = _min_max_normalize(candidate_close_prices)
    if candidate_norm.size == 0:
        return []

    hits: list[TemplateMatchHit] = []
    for eid, bundle in bundles_by_id.items():
        ex_norm = _min_max_normalize(bundle.close_prices)
        if ex_norm.size == 0:
            continue
        d = _dtw_distance(
            candidate_norm,
            ex_norm,
            sakoe_chiba_window_ratio=SAKOE_CHIBA_WINDOW_RATIO,
        )
        # Skip exemplars where the Sakoe-Chiba band makes the path
        # infeasible (e.g., grossly asymmetric series lengths: a 2-bar
        # candidate cannot align to a 50-bar exemplar within a 10%
        # band). The semantic is "no match found"; surface as a
        # skipped exemplar rather than poisoning the hit list with
        # a non-finite distance.
        if not math.isfinite(d):
            continue
        # Max distance heuristic: on min-max normalized series, the
        # maximum possible per-cell cost is 1.0 (max abs difference);
        # the maximum path length is N + M (boundary path). Use the
        # path-length bound as the similarity normalizer so identical
        # series saturate similarity=1.
        max_dist = float(candidate_norm.size + ex_norm.size)
        s = _similarity_from_distance(d, max_distance=max_dist)
        hit = TemplateMatchHit(
            exemplar_id=int(eid), distance=float(d), similarity_score=float(s)
        )
        hits.append(hit)

    # Sort by similarity_score DESC, then exemplar_id ASC (deterministic
    # tie-break).
    hits.sort(key=lambda h: (-h.similarity_score, h.exemplar_id))
    return hits[:top_k]


def match_reverse(
    *,
    exemplar_close_prices: np.ndarray,
    exemplar_pattern_class: str,
    candidate_corpus: Sequence[Any],
    top_k: int = 10,
) -> list[TemplateMatchHit]:
    """Reverse retrieval: exemplar -> top-K candidates matching its shape.

    Per spec section 5.7 retrieval mode 2 ("Show me candidates that
    look like this confirmed historical base").

    Candidate-corpus shape: each element must expose ``candidate_id: int``,
    ``pattern_class: str``, and ``close_prices: np.ndarray``. The
    function filters by ``exemplar_pattern_class`` (only candidates of
    the same class) + computes DTW distance per surviving candidate.

    Per spec section 5.7 line 695 + L10: min-max normalization applied
    to both exemplar + each candidate window.
    """
    if exemplar_pattern_class not in DETECTOR_PATTERN_CLASSES:
        raise ValueError(
            f"exemplar_pattern_class must be one of {DETECTOR_PATTERN_CLASSES}, "
            f"got {exemplar_pattern_class!r}"
        )
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")
    if not candidate_corpus:
        return []
    exemplar_norm = _min_max_normalize(exemplar_close_prices)
    if exemplar_norm.size == 0:
        return []
    hits: list[TemplateMatchHit] = []
    for cand in candidate_corpus:
        c_class = getattr(cand, "pattern_class", None)
        if c_class != exemplar_pattern_class:
            continue
        cid = getattr(cand, "candidate_id", None)
        cclose = getattr(cand, "close_prices", None)
        if cid is None or cclose is None:
            continue
        c_norm = _min_max_normalize(np.asarray(cclose, dtype=float))
        if c_norm.size == 0:
            continue
        d = _dtw_distance(
            exemplar_norm,
            c_norm,
            sakoe_chiba_window_ratio=SAKOE_CHIBA_WINDOW_RATIO,
        )
        # Skip infeasible-band cases (asymmetric lengths beyond the
        # Sakoe-Chiba band's reach) - surface as "no match" rather
        # than a non-finite TemplateMatchHit.
        if not math.isfinite(d):
            continue
        max_dist = float(exemplar_norm.size + c_norm.size)
        s = _similarity_from_distance(d, max_distance=max_dist)
        hits.append(
            TemplateMatchHit(
                exemplar_id=int(cid),
                distance=float(d),
                similarity_score=float(s),
            )
        )
    hits.sort(key=lambda h: (-h.similarity_score, h.exemplar_id))
    return hits[:top_k]
