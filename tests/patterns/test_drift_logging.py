"""Phase 13 T2.SB3 T-A.3.5 - discriminating tests for drift_logging.py.

Per plan section G.4 T-A.3.5 Step 1: 4 failing tests covering spec
section 5.11 + section D.7 + OQ-9 disposition:
(a) capture_feature_distribution(detector_class, evidence,
    universe_context) returns FeatureDistributionLog dataclass.
(b) FeatureDistributionLog is serializable to JSON.
(c) all 5 detectors emit consistent FeatureDistributionLog schema.
(d) composite_score histogram bin count matches section 5.11
    specification (10 bins of width 0.1 over [0.0, 1.0]).

LOCKs honored:
- L1: spec section 5.11 + D.7 + OQ-9 verbatim.
- L7: FeatureDistributionLog frozen dataclass + __post_init__
  runtime validation against explicit allowed-value frozensets
  (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date

import pytest

from swing.patterns.cup_with_handle import CupWithHandleEvidence
from swing.patterns.drift_logging import (
    _DETECTOR_CLASS_VALUES,
    FeatureDistributionLog,
    capture_feature_distribution,
)
from swing.patterns.flat_base import FlatBaseEvidence
from swing.patterns.vcp import Contraction, VCPEvidence

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_vcp_evidence() -> VCPEvidence:
    """Construct a synthetic VCPEvidence for drift-log capture tests.

    Field shape mirrors the spec section 5.2 ``VCPEvidence``; values are
    not load-bearing on detector semantics, only on the drift-log
    extraction path.
    """
    full_flags = {f"criterion_{i}": True for i in range(1, 9)}
    return VCPEvidence(
        stage="stage_2",
        prior_uptrend_pct=45.0,
        prior_uptrend_weeks=14,
        base_start_date=date(2026, 1, 5),
        base_end_date=date(2026, 3, 10),
        contractions=(
            Contraction(
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 20),
                peak_price=100.0,
                trough_price=78.0,
                depth_pct=22.0,
                duration_days=15,
                avg_volume=1_200_000.0,
            ),
            Contraction(
                start_date=date(2026, 1, 21),
                end_date=date(2026, 2, 10),
                peak_price=96.0,
                trough_price=82.0,
                depth_pct=14.6,
                duration_days=20,
                avg_volume=900_000.0,
            ),
            Contraction(
                start_date=date(2026, 2, 11),
                end_date=date(2026, 3, 5),
                peak_price=94.0,
                trough_price=87.0,
                depth_pct=7.5,
                duration_days=22,
                avg_volume=700_000.0,
            ),
        ),
        pivot_price=94.0,
        base_top_price=100.0,
        pivot_within_top_pct=94.0,
        volume_decline_passes=True,
        breakout_observed=False,
        breakout_volume_ratio=None,
        criteria_pass=full_flags,
        geometric_score=0.75,
    )


def _build_flat_base_evidence() -> FlatBaseEvidence:
    full_flags = {f"criterion_{i}": True for i in range(1, 8)}
    return FlatBaseEvidence(
        stage="stage_2",
        prior_uptrend_pct=30.0,
        prior_uptrend_weeks=10,
        base_start_date=date(2026, 2, 1),
        base_end_date=date(2026, 3, 20),
        range_top_price=50.0,
        range_bottom_price=46.0,
        range_width_pct=8.0,
        regression_slope_pct_per_week=0.2,
        mean_atr_pct=1.4,
        base_duration_days=35,
        pivot_price=50.0,
        pivot_within_top_pct=100.0,
        criteria_pass=full_flags,
        geometric_score=0.6,
    )


def _build_cup_with_handle_evidence() -> CupWithHandleEvidence:
    full_flags = {f"criterion_{i}": True for i in range(1, 9)}
    return CupWithHandleEvidence(
        stage="stage_2",
        cup_left_edge_price=100.0,
        cup_left_edge_date=date(2026, 1, 5),
        cup_right_edge_price=98.0,
        cup_right_edge_date=date(2026, 3, 10),
        cup_bottom_price=78.0,
        cup_bottom_date=date(2026, 2, 5),
        cup_depth_pct=22.0,
        cup_duration_days=64,
        cup_right_edge_pct_of_left_edge=98.0,
        handle_high_price=98.0,
        handle_low_price=92.0,
        handle_start_date=date(2026, 3, 11),
        handle_end_date=date(2026, 3, 25),
        handle_depth_pct=6.1,
        handle_duration_days=14,
        handle_low_vs_cup_midpoint_pct=3.0,
        handle_volume_vs_cup_volume_pct=70.0,
        pivot_price=98.0,
        pivot_within_cup_right_edge_pct=100.0,
        rounded_cup_passes=True,
        rounded_cup_penalty=0.0,
        rounded_cup_bars_in_marginal_zone=0,
        criteria_pass=full_flags,
        geometric_score=0.82,
    )


def _build_universe_context() -> dict:
    """Synthetic universe-context dict for capture_feature_distribution.

    Per spec section 5.11 + section D.7 LOCK: composer-side context
    captured at detector run time.
    """
    return {
        "universe_size": 142,
        "stage_2_pass_rate": 0.35,
        "rs_rank_distribution": {
            "mean": 78.2,
            "median": 82.0,
            "std": 11.5,
            "min": 70.0,
            "max": 99.0,
        },
        "verdict_counts_per_pattern_class": {
            "vcp": 12,
            "flat_base": 8,
            "cup_with_handle": 5,
            "high_tight_flag": 0,
            "double_bottom_w": 0,
        },
        "composite_scores": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
        "smoothing_params": {"window": 5.0, "polyorder": 2.0},
        "extrema_density_per_session": 0.18,
        "volume_aggregates": {"mean": 1_000_000.0, "std": 250_000.0},
    }


# ---------------------------------------------------------------------------
# Test (a): capture helper returns FeatureDistributionLog
# ---------------------------------------------------------------------------


def test_capture_feature_distribution_returns_feature_distribution_log() -> None:
    """capture_feature_distribution returns a FeatureDistributionLog instance.

    Per plan section G.4 T-A.3.5 Step 1 (a). Discriminates against any
    helper that returns a dict or other shape.
    """
    evidence = _build_vcp_evidence()
    universe_context = _build_universe_context()

    log = capture_feature_distribution(
        detector_class="vcp",
        evidence=evidence,
        universe_context=universe_context,
    )

    assert isinstance(log, FeatureDistributionLog), (
        f"capture_feature_distribution must return FeatureDistributionLog, "
        f"got {type(log).__name__}"
    )
    # VCP-specific: contraction_depths populated from evidence.contractions.
    assert log.contraction_depths is not None
    assert len(log.contraction_depths) == 3
    assert log.contraction_depths[0] == pytest.approx(22.0)
    assert log.contraction_depths[1] == pytest.approx(14.6)
    assert log.contraction_depths[2] == pytest.approx(7.5)
    # DBW-specific field is None for VCP.
    assert log.center_trough_retracement is None
    # Universe context plumbed through.
    assert log.universe_size == 142
    assert log.stage_2_pass_rate == pytest.approx(0.35)
    # Histogram has 10 bins per section 5.11 LOCK (test (d) below).
    assert len(log.composite_score_histogram_bins) == 10


# ---------------------------------------------------------------------------
# Test (b): JSON serializable
# ---------------------------------------------------------------------------


def test_feature_distribution_log_serializable_to_json() -> None:
    """FeatureDistributionLog round-trips through json.dumps / json.loads.

    Per plan section G.4 T-A.3.5 Step 1 (b) + the recon section 8
    encoding rule: ``dataclasses.asdict(...) -> json.dumps(..., default=str)``
    -> ``json.loads(...)``. Discriminates against any non-serializable
    field type (tuple, date, custom object).
    """
    log = capture_feature_distribution(
        detector_class="vcp",
        evidence=_build_vcp_evidence(),
        universe_context=_build_universe_context(),
    )

    payload = json.dumps(dataclasses.asdict(log), default=str)
    decoded = json.loads(payload)

    assert isinstance(decoded, dict)
    assert decoded["universe_size"] == 142
    assert decoded["contraction_depths"] == [
        pytest.approx(22.0),
        pytest.approx(14.6),
        pytest.approx(7.5),
    ]
    assert decoded["center_trough_retracement"] is None
    # 10-bin histogram per section 5.11 LOCK.
    assert len(decoded["composite_score_histogram_bins"]) == 10
    # All bin values are integers (count per bin).
    for n in decoded["composite_score_histogram_bins"]:
        assert isinstance(n, int)


# ---------------------------------------------------------------------------
# Test (c): all 5 detectors emit consistent schema
# ---------------------------------------------------------------------------


def test_all_5_detectors_emit_consistent_schema() -> None:
    """FeatureDistributionLog schema stable across 5 V1 detector classes.

    Per plan section G.4 T-A.3.5 Step 1 (c). T2.SB3 ships 3 of 5
    detectors (vcp + flat_base + cup_with_handle); T2.SB4 will add
    high_tight_flag + double_bottom_w. The dataclass SCHEMA must accept
    all 5 detector_class values + the emitted log shape must have the
    SAME set of fields regardless of detector_class.

    Discriminating fixture: build a FeatureDistributionLog directly per
    detector_class via the 5-value frozenset; assert dataclasses.fields
    return identical field names; assert the 5 detector_class strings
    all pass __post_init__ validation.
    """
    expected_detector_classes = frozenset(
        {"vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w"}
    )
    assert expected_detector_classes == _DETECTOR_CLASS_VALUES, (
        f"_DETECTOR_CLASS_VALUES must equal {sorted(expected_detector_classes)}, "
        f"got {sorted(_DETECTOR_CLASS_VALUES)}"
    )

    # Test (c.1): each detector_class string validates at __post_init__.
    for cls in sorted(expected_detector_classes):
        log = FeatureDistributionLog(
            detector_class=cls,
            smoothing_params={"window": 5.0, "polyorder": 2.0},
            extrema_density_per_session=0.1,
            contraction_depths=None,
            center_trough_retracement=None,
            volume_aggregates={"mean": 1_000_000.0},
            composite_score_histogram_bins=[0] * 10,
            universe_size=100,
            stage_2_pass_rate=0.3,
            rs_rank_distribution={"mean": 80.0},
            verdict_counts_per_pattern_class={
                "vcp": 0,
                "flat_base": 0,
                "cup_with_handle": 0,
                "high_tight_flag": 0,
                "double_bottom_w": 0,
            },
        )
        assert log.detector_class == cls

    # Test (c.2): invalid detector_class raises ValueError per L7.
    with pytest.raises(ValueError, match="detector_class"):
        FeatureDistributionLog(
            detector_class="not_a_real_detector",
            smoothing_params={},
            extrema_density_per_session=0.0,
            contraction_depths=None,
            center_trough_retracement=None,
            volume_aggregates={},
            composite_score_histogram_bins=[0] * 10,
            universe_size=0,
            stage_2_pass_rate=0.0,
            rs_rank_distribution={},
            verdict_counts_per_pattern_class={},
        )

    # Test (c.3): the 3 T2.SB3 detectors emit a log with identical field
    # names (i.e., schema is stable across detectors).
    log_vcp = capture_feature_distribution(
        detector_class="vcp",
        evidence=_build_vcp_evidence(),
        universe_context=_build_universe_context(),
    )
    log_flat_base = capture_feature_distribution(
        detector_class="flat_base",
        evidence=_build_flat_base_evidence(),
        universe_context=_build_universe_context(),
    )
    log_cup_with_handle = capture_feature_distribution(
        detector_class="cup_with_handle",
        evidence=_build_cup_with_handle_evidence(),
        universe_context=_build_universe_context(),
    )

    field_names_vcp = {f.name for f in dataclasses.fields(log_vcp)}
    field_names_flat = {f.name for f in dataclasses.fields(log_flat_base)}
    field_names_cup = {f.name for f in dataclasses.fields(log_cup_with_handle)}

    assert field_names_vcp == field_names_flat == field_names_cup, (
        "FeatureDistributionLog field names must be identical across all "
        "detector classes per OQ-9 LOCK (T2.SB4 future detectors plug in "
        "without breaking schema)"
    )

    # Non-VCP detectors should NOT populate contraction_depths.
    assert log_flat_base.contraction_depths is None
    assert log_cup_with_handle.contraction_depths is None
    # All 3 emit the same detector_class string they were called with.
    assert log_vcp.detector_class == "vcp"
    assert log_flat_base.detector_class == "flat_base"
    assert log_cup_with_handle.detector_class == "cup_with_handle"


# ---------------------------------------------------------------------------
# Test (d): histogram bin count matches section 5.11 spec
# ---------------------------------------------------------------------------


def test_composite_score_histogram_bin_count_matches_5_11_spec() -> None:
    """composite_score histogram = 10 bins of width 0.1 over [0.0, 1.0].

    Per plan section G.4 T-A.3.5 Step 1 (d) + spec section 5.11.
    composite_score is a clamped [0.0, 1.0] value; 10 equal-width bins
    is the canonical histogram representation. Bin i covers
    [i * 0.1, (i + 1) * 0.1) for i in 0..8; bin 9 covers [0.9, 1.0]
    (inclusive on the right edge so a perfect 1.0 score lands in bin 9
    rather than overflowing).

    Discriminating fixture: planted composite_scores at the bin
    boundaries; assert the resulting bin counts match the expected
    placement.
    """
    universe_context = _build_universe_context()
    # composite_scores = [0.05, 0.15, ..., 0.95] (one per bin midpoint).
    # Each bin should contain exactly 1 score.
    log = capture_feature_distribution(
        detector_class="vcp",
        evidence=_build_vcp_evidence(),
        universe_context=universe_context,
    )
    assert len(log.composite_score_histogram_bins) == 10
    assert log.composite_score_histogram_bins == [1] * 10

    # Test (d.2): 0.0 lands in bin 0, 1.0 lands in bin 9 (inclusive right
    # edge).
    universe_context2 = dict(universe_context)
    universe_context2["composite_scores"] = [0.0, 1.0]
    log2 = capture_feature_distribution(
        detector_class="vcp",
        evidence=_build_vcp_evidence(),
        universe_context=universe_context2,
    )
    expected = [0] * 10
    expected[0] = 1
    expected[9] = 1
    assert log2.composite_score_histogram_bins == expected

    # Test (d.3): out-of-range scores raise ValueError per L7 (composite
    # is clamped [0.0, 1.0] by upstream; capture helper rejects
    # malformed input rather than silently dropping).
    universe_context3 = dict(universe_context)
    universe_context3["composite_scores"] = [1.5]
    with pytest.raises(ValueError, match="composite_score"):
        capture_feature_distribution(
            detector_class="vcp",
            evidence=_build_vcp_evidence(),
            universe_context=universe_context3,
        )

    # Test (d.4): missing composite_scores key -> empty bin histogram
    # (all zeros), NOT a crash.
    universe_context4 = dict(universe_context)
    del universe_context4["composite_scores"]
    log4 = capture_feature_distribution(
        detector_class="vcp",
        evidence=_build_vcp_evidence(),
        universe_context=universe_context4,
    )
    assert log4.composite_score_histogram_bins == [0] * 10
