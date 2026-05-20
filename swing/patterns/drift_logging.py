"""Phase 13 T2.SB3 T-A.3.5 - drift logging baseline substrate per OQ-9.

Per spec section 5.11 + section D.7 + OQ-9 disposition:
- V1 substrate is a JSON column ``pattern_evaluations.feature_distribution_log_json``
  per detector run.
- V2 dedicated table only if Phase 13.5 monitoring side demands.
- Schema captures input feature value distributions per detector + universe
  context + composite-score histogram.

LOCKs (per plan section G.4 T-A.3.5 LOCKs + dispatch brief section 4.3 watch
items):
- L1: spec section 5.11 + D.7 + OQ-9 verbatim.
- L7: ``FeatureDistributionLog`` is a frozen dataclass with
  ``__post_init__`` runtime validation against explicit allowed-value
  frozensets (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").

Cross-detector consistent schema: T2.SB3 ships 3 of 5 V1 detector classes
(vcp + flat_base + cup_with_handle); T2.SB4 will add high_tight_flag +
double_bottom_w. The dataclass schema is stable across all 5 classes so
T2.SB4 detectors plug in without breaking the JSON envelope.

Histogram bin count per spec section 5.11: 10 bins of width 0.1 over
[0.0, 1.0]. Bin i covers [i * 0.1, (i + 1) * 0.1) for i in 0..8; bin 9
covers [0.9, 1.0] inclusive on the right edge so a perfect 1.0 score
lands in bin 9 rather than overflowing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from swing.patterns.cup_with_handle import CupWithHandleEvidence
from swing.patterns.flat_base import FlatBaseEvidence
from swing.patterns.vcp import VCPEvidence

# ---------------------------------------------------------------------------
# Module-level constants (L7 + L1)
# ---------------------------------------------------------------------------


_DETECTOR_CLASS_VALUES: frozenset[str] = frozenset(
    {
        "vcp",
        "flat_base",
        "cup_with_handle",
        "high_tight_flag",
        "double_bottom_w",
    }
)
"""V1 detector classes per spec section 3.0 + section 5.2..5.6.

T2.SB3 emits the first 3; T2.SB4 will emit the remaining 2. The
frozenset is stable across the bundle so the JSON envelope on
``pattern_evaluations.feature_distribution_log_json`` is consistent
when T2.SB4 lands.
"""


_HISTOGRAM_BIN_COUNT: int = 10
"""Number of equal-width bins for the composite_score histogram.

Per spec section 5.11 LOCK: composite_score is clamped to [0.0, 1.0]
upstream; 10 equal-width bins of width 0.1 is the canonical histogram
representation. The right edge (1.0) is inclusive on bin 9 so a
perfect score lands in bin 9 rather than overflowing.
"""


# ---------------------------------------------------------------------------
# Dataclass (L7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureDistributionLog:
    """JSON-encoded substrate for ``pattern_evaluations.feature_distribution_log_json``.

    Per spec section D.7 LOCK shape:

    - ``detector_class`` Literal validated at __post_init__ time against
      ``_DETECTOR_CLASS_VALUES`` (the 5-value frozenset).
    - ``smoothing_params`` captures the smoothing window + polyorder
      that fed the detector's foundation primitives (T2.SB2).
    - ``extrema_density_per_session`` captures the swing-extrema density
      from the candidate window (T2.SB2 ``generate_candidate_windows``).
    - ``contraction_depths`` VCP-specific (None for other detectors).
    - ``center_trough_retracement`` DBW-specific (None for other
      detectors; T2.SB4 deliverable).
    - ``volume_aggregates`` captures volume-decline / handle-vs-cup
      ratios per detector.
    - ``composite_score_histogram_bins`` 10-bin histogram per
      ``_HISTOGRAM_BIN_COUNT`` LOCK.
    - ``universe_size`` / ``stage_2_pass_rate`` / ``rs_rank_distribution``
      captures composer-side run-time universe context.
    - ``verdict_counts_per_pattern_class`` captures per-detector verdict
      counts across the run.

    LOCK L7: ``detector_class`` validated against
    ``_DETECTOR_CLASS_VALUES``; runtime check (not just type hint) per
    CLAUDE.md gotcha "Literal[...] type hints are NOT runtime-enforced".
    """

    detector_class: Literal[
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w"
    ]
    smoothing_params: dict[str, float]
    extrema_density_per_session: float
    contraction_depths: list[float] | None
    center_trough_retracement: float | None
    volume_aggregates: dict[str, float]
    composite_score_histogram_bins: list[int]
    universe_size: int
    stage_2_pass_rate: float
    rs_rank_distribution: dict[str, float]
    verdict_counts_per_pattern_class: dict[str, int]

    def __post_init__(self) -> None:
        if self.detector_class not in _DETECTOR_CLASS_VALUES:
            raise ValueError(
                f"FeatureDistributionLog.detector_class must be one of "
                f"{sorted(_DETECTOR_CLASS_VALUES)}, got "
                f"{self.detector_class!r}"
            )
        if self.universe_size < 0:
            raise ValueError(
                f"FeatureDistributionLog.universe_size must be >= 0, "
                f"got {self.universe_size}"
            )
        if not (0.0 <= self.stage_2_pass_rate <= 1.0):
            raise ValueError(
                f"FeatureDistributionLog.stage_2_pass_rate must be in "
                f"[0.0, 1.0], got {self.stage_2_pass_rate}"
            )
        if len(self.composite_score_histogram_bins) != _HISTOGRAM_BIN_COUNT:
            raise ValueError(
                f"FeatureDistributionLog.composite_score_histogram_bins "
                f"must have exactly {_HISTOGRAM_BIN_COUNT} bins, got "
                f"{len(self.composite_score_histogram_bins)}"
            )
        for n in self.composite_score_histogram_bins:
            if not isinstance(n, int):
                raise ValueError(
                    f"FeatureDistributionLog.composite_score_histogram_bins "
                    f"values must be int counts, got {type(n).__name__}"
                )
            if n < 0:
                raise ValueError(
                    f"FeatureDistributionLog.composite_score_histogram_bins "
                    f"counts must be >= 0, got {n}"
                )


# ---------------------------------------------------------------------------
# Helper: composite_score histogram bucketing
# ---------------------------------------------------------------------------


def _composite_score_histogram(scores: list[float]) -> list[int]:
    """Bucket composite scores into 10 bins of width 0.1 over [0.0, 1.0].

    Bin i covers [i * 0.1, (i + 1) * 0.1) for i in 0..8; bin 9 covers
    [0.9, 1.0] inclusive on the right edge per spec section 5.11 LOCK.

    Raises ValueError on any score outside [0.0, 1.0] (composite_score
    is clamped upstream; out-of-range here indicates a contract
    violation, not silent data).
    """
    bins = [0] * _HISTOGRAM_BIN_COUNT
    for score in scores:
        if not isinstance(score, (int, float)) or math.isnan(float(score)):
            raise ValueError(
                f"composite_score values must be finite numbers in "
                f"[0.0, 1.0], got {score!r}"
            )
        s = float(score)
        if not (0.0 <= s <= 1.0):
            raise ValueError(
                f"composite_score must be in [0.0, 1.0], got {s}"
            )
        if s == 1.0:
            idx = _HISTOGRAM_BIN_COUNT - 1
        else:
            idx = int(s * _HISTOGRAM_BIN_COUNT)
            # Defensive clamp (handles floating-point edge cases at the
            # boundary just below 1.0).
            if idx >= _HISTOGRAM_BIN_COUNT:
                idx = _HISTOGRAM_BIN_COUNT - 1
        bins[idx] += 1
    return bins


# ---------------------------------------------------------------------------
# Helper: per-detector feature extraction
# ---------------------------------------------------------------------------


def _extract_contraction_depths(evidence: Any) -> list[float] | None:
    """VCP-specific: return contraction depths in percent units.

    Returns None for non-VCP detectors so the FeatureDistributionLog
    field is consistently shaped (Optional[list[float]]).
    """
    if isinstance(evidence, VCPEvidence):
        return [float(c.depth_pct) for c in evidence.contractions]
    return None


def _extract_volume_aggregates(evidence: Any) -> dict[str, float]:
    """Per-detector volume aggregate summary.

    - VCP: ``volume_decline_passes`` -> 1.0/0.0 + breakout_volume_ratio
      (NaN-safe -> 0.0).
    - FlatBase: mean_atr_pct (proxy for volume-aware tightness; flat-base
      has no dedicated volume column).
    - CupWithHandle: handle_volume_vs_cup_volume_pct.

    Returns an empty dict for unknown detector evidence shapes (T2.SB4
    will extend this when HTF + DBW evidence dataclasses land).
    """
    if isinstance(evidence, VCPEvidence):
        return {
            "volume_decline_passes": (
                1.0 if evidence.volume_decline_passes else 0.0
            ),
            "breakout_volume_ratio": float(
                evidence.breakout_volume_ratio or 0.0
            ),
        }
    if isinstance(evidence, FlatBaseEvidence):
        return {
            "mean_atr_pct": float(evidence.mean_atr_pct),
        }
    if isinstance(evidence, CupWithHandleEvidence):
        return {
            "handle_volume_vs_cup_volume_pct": float(
                evidence.handle_volume_vs_cup_volume_pct
            ),
        }
    return {}


# ---------------------------------------------------------------------------
# Public helper: capture_feature_distribution
# ---------------------------------------------------------------------------


def capture_feature_distribution(
    detector_class: str,
    evidence: VCPEvidence | FlatBaseEvidence | CupWithHandleEvidence,
    universe_context: dict[str, Any],
) -> FeatureDistributionLog:
    """Capture a per-detector-run FeatureDistributionLog.

    Args:
        detector_class: one of the 5 V1 detector class strings
            (validated against ``_DETECTOR_CLASS_VALUES`` via the
            dataclass __post_init__).
        evidence: the per-detector evidence dataclass emitted by the
            detector (VCPEvidence / FlatBaseEvidence /
            CupWithHandleEvidence in T2.SB3; HTF + DBW evidence will
            land at T2.SB4).
        universe_context: composer-side context captured at detector
            run time. Expected keys (per spec section 5.11 + section
            D.7):

            - ``universe_size`` (int; default 0)
            - ``stage_2_pass_rate`` (float in [0.0, 1.0]; default 0.0)
            - ``rs_rank_distribution`` (dict[str, float]; default {})
            - ``verdict_counts_per_pattern_class`` (dict[str, int];
              default {})
            - ``smoothing_params`` (dict[str, float]; default {})
            - ``extrema_density_per_session`` (float; default 0.0)
            - ``composite_scores`` (list[float] in [0.0, 1.0]; default
              []; bucketed into 10-bin histogram)
            - ``volume_aggregates`` (dict[str, float]; optional
              override; if absent, derived from evidence)

    Returns:
        FeatureDistributionLog frozen dataclass ready for
        ``json.dumps(dataclasses.asdict(log), default=str)`` -> persist
        to ``pattern_evaluations.feature_distribution_log_json``.

    Raises:
        ValueError: if ``detector_class`` is not in the 5-value
            frozenset, or if any composite_score is outside [0.0, 1.0],
            or if other dataclass __post_init__ invariants fail.
    """
    composite_scores = universe_context.get("composite_scores", [])
    histogram = _composite_score_histogram(list(composite_scores))

    # Per-detector feature extraction (VCP-specific contraction_depths;
    # DBW-specific center_trough_retracement is None until T2.SB4).
    contraction_depths = _extract_contraction_depths(evidence)
    center_trough_retracement = None  # T2.SB4 will populate for DBW.

    # Volume aggregates: prefer universe_context override; else derive
    # from evidence shape.
    volume_aggregates = universe_context.get("volume_aggregates")
    if volume_aggregates is None:
        volume_aggregates = _extract_volume_aggregates(evidence)

    return FeatureDistributionLog(
        detector_class=detector_class,  # type: ignore[arg-type]
        smoothing_params=dict(universe_context.get("smoothing_params", {})),
        extrema_density_per_session=float(
            universe_context.get("extrema_density_per_session", 0.0)
        ),
        contraction_depths=contraction_depths,
        center_trough_retracement=center_trough_retracement,
        volume_aggregates=dict(volume_aggregates),
        composite_score_histogram_bins=histogram,
        universe_size=int(universe_context.get("universe_size", 0)),
        stage_2_pass_rate=float(
            universe_context.get("stage_2_pass_rate", 0.0)
        ),
        rs_rank_distribution=dict(
            universe_context.get("rs_rank_distribution", {})
        ),
        verdict_counts_per_pattern_class=dict(
            universe_context.get("verdict_counts_per_pattern_class", {})
        ),
    )


__all__ = [
    "FeatureDistributionLog",
    "capture_feature_distribution",
]
