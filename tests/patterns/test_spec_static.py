"""Phase 13 T2.SB1 T-A.1.5b Defect 2 tests — verify static rule_criteria +
structural_evidence_schema dispatch contracts match spec section 5.2
through 5.6 verbatim per V1 pattern class.

Each pattern class has class-specific anchor fields/criteria that the
spec defines uniquely; the parametrized assertions exercise those anchors
so regression-on-spec-drift trips the right class.

ASCII-only verification at the end - the CLI payload emit path uses
`click.echo(json.dumps(...))` which flows through Windows cp1252 stdout
(CLAUDE.md gotcha); non-ASCII glyphs in any criteria text crash PowerShell.
"""
from __future__ import annotations

import json

import pytest

from swing.data.models import DETECTOR_PATTERN_CLASSES
from swing.patterns.spec_static import (
    get_rule_criteria,
    get_structural_evidence_schema,
)


def test_rule_criteria_unknown_pattern_class_raises() -> None:
    with pytest.raises(ValueError, match="pattern_class must be one of"):
        get_rule_criteria("bogus_class_not_in_v1_set")


def test_structural_evidence_schema_unknown_pattern_class_raises() -> None:
    with pytest.raises(ValueError, match="pattern_class must be one of"):
        get_structural_evidence_schema("bogus_class_not_in_v1_set")


def test_rule_criteria_covers_all_5_v1_classes_no_placeholders() -> None:
    """Spec section 5.2 through 5.6 cover 5 V1 pattern classes. EACH must
    have a non-placeholder rule_criteria entry. Guards against the
    placeholder shape that forced the T-A.1.7 paired-session abort.
    """
    assert set(DETECTOR_PATTERN_CLASSES) == {
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag",
        "double_bottom_w",
    }
    for cls in DETECTOR_PATTERN_CLASSES:
        rc = get_rule_criteria(cls)
        # Anti-placeholder guard: previous V1 emit had a `_note` field
        # saying "placeholder; populated by T2.SB3+". This MUST not appear
        # any longer.
        assert "placeholder" not in json.dumps(rc).lower(), (
            f"rule_criteria for {cls!r} still carries placeholder text"
        )
        assert "criteria" in rc, (
            f"rule_criteria for {cls!r} missing 'criteria' list"
        )
        assert len(rc["criteria"]) >= 2, (
            f"rule_criteria for {cls!r} has too few criteria; spec "
            f"defines 6-8 per class"
        )


@pytest.mark.parametrize(
    "pattern_class,expected_section,expected_criteria_count,"
    "anchor_criterion_names",
    [
        # VCP (spec section 5.2): 8 criteria per spec table.
        (
            "vcp", "section 5.2", 8,
            {
                "stage_2_uptrend", "prior_uptrend_leg",
                "contractions_monotonic", "contraction_depth_bounds",
                "volume_decline_through_contractions", "base_duration",
                "pivot_at_base_top", "breakout_volume_optional",
            },
        ),
        # Flat base (spec section 5.3): 7 criteria.
        (
            "flat_base", "section 5.3", 7,
            {
                "stage_2_uptrend", "prior_uptrend_leg", "bounded_range",
                "low_slope", "tight_atr", "base_duration",
                "pivot_at_range_top",
            },
        ),
        # Cup-with-handle (spec section 5.4): 8 criteria + rounded-vs-V test.
        (
            "cup_with_handle", "section 5.4", 8,
            {
                "stage_2_uptrend", "cup_left_to_bottom",
                "cup_right_edge_recovery", "cup_duration",
                "handle_shape", "handle_above_cup_midpoint",
                "pivot_at_cup_right_edge",
                "volume_dries_during_handle",
            },
        ),
        # High-tight flag (spec section 5.5): 6 criteria.
        (
            "high_tight_flag", "section 5.5", 6,
            {
                "stage_2_uptrend", "prior_advance_pole",
                "consolidation_pullback", "consolidation_width",
                "consolidation_volume_contracts",
                "pivot_at_consolidation_top",
            },
        ),
        # Double-bottom W (spec section 5.6): 8 criteria including
        # optional volume-rises + undercut bonus.
        (
            "double_bottom_w", "section 5.6", 8,
            {
                "stage_context", "trough_1_drawdown",
                "center_peak_retracement", "trough_2_alignment",
                "symmetric_durations", "pivot_at_center_peak",
                "trough_2_volume_rises", "trough_2_undercut_bonus",
            },
        ),
    ],
)
def test_rule_criteria_class_specific_shape(
    pattern_class: str,
    expected_section: str,
    expected_criteria_count: int,
    anchor_criterion_names: set[str],
) -> None:
    """Per-class criteria-set + spec-section match per spec sections 5.2
    through 5.6.
    """
    rc = get_rule_criteria(pattern_class)
    assert rc["pattern_class"] == pattern_class
    assert rc["spec_section"] == expected_section
    assert len(rc["criteria"]) == expected_criteria_count, (
        f"{pattern_class!r} criteria count mismatch: expected "
        f"{expected_criteria_count}, got {len(rc['criteria'])}"
    )
    actual_names = {c["name"] for c in rc["criteria"]}
    assert actual_names == anchor_criterion_names, (
        f"{pattern_class!r} criterion-name set drift: "
        f"missing={anchor_criterion_names - actual_names}, "
        f"extra={actual_names - anchor_criterion_names}"
    )
    # Each criterion must carry the four spec-table columns.
    for crit in rc["criteria"]:
        assert {"id", "name", "lock", "tolerance"}.issubset(crit.keys()), (
            f"{pattern_class!r} criterion {crit.get('name')!r} missing "
            "spec-table columns"
        )
    assert "composite_scoring_note" in rc


def test_vcp_criteria_match_spec_section_5_2_anchors() -> None:
    """VCP spec section 5.2 anchor values: criterion #3 monotonic
    contraction lock + criterion #7 pivot near base top bound.
    """
    rc = get_rule_criteria("vcp")
    by_name = {c["name"]: c for c in rc["criteria"]}
    # Criterion #3: depth_pct monotonic decrease per spec.
    monotonic = by_name["contractions_monotonic"]
    assert "depth_pct" in monotonic["lock"]
    assert "len(contractions) >= 2" in monotonic["lock"]
    # Criterion #7: pivot within 1% of base top.
    pivot = by_name["pivot_at_base_top"]
    assert "pivot_price / base_top_price" in pivot["lock"]
    assert "[0.99, 1.01]" in pivot["lock"]


def test_flat_base_criteria_match_spec_section_5_3_anchors() -> None:
    rc = get_rule_criteria("flat_base")
    by_name = {c["name"]: c for c in rc["criteria"]}
    # Range width must be in [3%, 12%] per spec.
    rng = by_name["bounded_range"]
    assert "[0.03, 0.12]" in rng["lock"]
    # ATR <= 0.025 per spec.
    atr = by_name["tight_atr"]
    assert "mean_atr_pct <= 0.025" in atr["lock"]


def test_cup_with_handle_criteria_match_spec_section_5_4_anchors() -> None:
    rc = get_rule_criteria("cup_with_handle")
    by_name = {c["name"]: c for c in rc["criteria"]}
    # Cup duration 6-26 weeks = [42, 182] days.
    dur = by_name["cup_duration"]
    assert "[42, 182]" in dur["lock"]
    # Cup right edge >= 95% of left edge.
    recov = by_name["cup_right_edge_recovery"]
    assert "0.95" in recov["lock"]
    # Rounded-vs-V supplementary test included.
    assert "rounded_vs_v_test" in rc
    rvt = rc["rounded_vs_v_test"]
    assert "cup_bottom_price" in rvt["rounded_predicate"]


def test_high_tight_flag_criteria_match_spec_section_5_5_anchors() -> None:
    rc = get_rule_criteria("high_tight_flag")
    by_name = {c["name"]: c for c in rc["criteria"]}
    # Pole >= 90% gain over 28-56 days.
    pole = by_name["prior_advance_pole"]
    assert "pole_pct >= 0.90" in pole["lock"]
    assert "[28, 56]" in pole["lock"]
    # Consolidation width <= 15%.
    width = by_name["consolidation_width"]
    assert "consolidation_width_pct <= 0.15" in width["lock"]


def test_double_bottom_w_criteria_match_spec_section_5_6_anchors() -> None:
    rc = get_rule_criteria("double_bottom_w")
    by_name = {c["name"]: c for c in rc["criteria"]}
    # Trough_1 drawdown >= 15%.
    t1 = by_name["trough_1_drawdown"]
    assert "trough_1_drawdown_pct >= 0.15" in t1["lock"]
    # Center peak >= 50% retracement.
    cp = by_name["center_peak_retracement"]
    assert "center_peak_retracement_pct >= 0.50" in cp["lock"]
    # Undercut bonus +0.10.
    undercut = by_name["trough_2_undercut_bonus"]
    assert "+= 0.10" in undercut["lock"]


@pytest.mark.parametrize(
    "pattern_class,expected_section,expected_dataclass_name,"
    "anchor_field_names",
    [
        (
            "vcp", "section 5.2", "VCPEvidence",
            {
                "stage", "contractions", "pivot_price", "base_top_price",
                "volume_decline_passes", "geometric_score",
            },
        ),
        (
            "flat_base", "section 5.3", "FlatBaseEvidence",
            {
                "range_top", "range_bottom",
                "regression_slope_pct_per_week", "mean_atr_pct",
                "pivot_price", "geometric_score",
            },
        ),
        (
            "cup_with_handle", "section 5.4", "CupWithHandleEvidence",
            {
                "cup_left_edge_price", "cup_bottom_price",
                "cup_right_edge_price", "handle_depth_pct", "is_rounded",
                "pivot_price", "geometric_score",
            },
        ),
        (
            "high_tight_flag", "section 5.5", "HighTightFlagEvidence",
            {
                "pole_pct", "pole_duration_days",
                "consolidation_pullback_pct", "consolidation_width_pct",
                "pivot_price", "geometric_score",
            },
        ),
        (
            "double_bottom_w", "section 5.6", "DoubleBottomWEvidence",
            {
                "trough_1_price", "center_peak_price", "trough_2_price",
                "undercut", "pivot_price", "geometric_score",
            },
        ),
    ],
)
def test_structural_evidence_schema_class_specific_shape(
    pattern_class: str,
    expected_section: str,
    expected_dataclass_name: str,
    anchor_field_names: set[str],
) -> None:
    """Per-class structural_evidence_schema dataclass shape per spec
    sections 5.2 through 5.6.
    """
    schema = get_structural_evidence_schema(pattern_class)
    assert schema["pattern_class"] == pattern_class
    assert schema["spec_section"] == expected_section
    assert schema["evidence_dataclass"] == expected_dataclass_name
    actual_fields = set(schema["fields"].keys())
    missing = anchor_field_names - actual_fields
    assert not missing, (
        f"{pattern_class!r} schema missing anchor fields: {missing}"
    )


def test_vcp_schema_has_contraction_nested_shape() -> None:
    """VCPEvidence nests Contraction dataclass per spec section 5.2."""
    schema = get_structural_evidence_schema("vcp")
    assert "nested_shapes" in schema
    contraction = schema["nested_shapes"]["Contraction"]
    expected = {
        "start_date", "end_date", "peak_price", "trough_price",
        "depth_pct", "duration_days", "avg_volume",
    }
    assert set(contraction.keys()) == expected


def test_all_spec_static_strings_are_ascii() -> None:
    """Per CLAUDE.md Windows cp1252 stdout gotcha: rule_criteria + schema
    flow through click.echo(json.dumps(...)) at the CLI payload-emit path
    (test_label_exemplars_output_is_ascii_only enforces this on the CLI
    surface; we double-tap here at the data source).
    """
    for cls in DETECTOR_PATTERN_CLASSES:
        rc_str = json.dumps(get_rule_criteria(cls))
        schema_str = json.dumps(get_structural_evidence_schema(cls))
        for source, payload in (("rule_criteria", rc_str),
                                ("schema", schema_str)):
            for char in payload:
                assert ord(char) < 128, (
                    f"non-ASCII char {char!r} (ord {ord(char)}) in "
                    f"{source} for {cls!r}"
                )
