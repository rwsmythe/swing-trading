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


def test_schemas_for_flat_cup_htf_dbw_omit_extrapolated_stage_and_criteria_pass(
) -> None:
    """Codex R1 M#5 closure - spec sections 5.3 through 5.6 enumerate
    abbreviated structural evidence field lists that DO NOT include
    `stage` or `criteria_pass`. Section 5.2 (VCP) DOES include both
    explicitly. Schemas must mirror spec verbatim per class.
    """
    for cls in ("flat_base", "cup_with_handle", "high_tight_flag",
                "double_bottom_w"):
        schema = get_structural_evidence_schema(cls)
        assert "stage" not in schema["fields"], (
            f"{cls!r} schema must not extrapolate `stage` beyond spec "
            f"section {schema['spec_section']} (spec lists only the "
            "abbreviated structural fields)"
        )
        assert "criteria_pass" not in schema["fields"], (
            f"{cls!r} schema must not extrapolate `criteria_pass` "
            f"beyond spec section {schema['spec_section']}"
        )
    # VCP DOES include both per spec section 5.2 VCPEvidence dataclass.
    vcp_schema = get_structural_evidence_schema("vcp")
    assert "stage" in vcp_schema["fields"]
    assert "criteria_pass" in vcp_schema["fields"]


# ============================================================================
# T-A.1.8 Deficiency 3 — sub-window date fields per V1 class.
#
# Per closer brief T-1.8.4 + operator T-A.1.7 resume signal: each class's
# structural_evidence_schema MUST enumerate enough sub-window date fields
# for the pattern-labeler subagent to scope shape identification to the
# actual base/pole/cup/trough region within a possibly-larger fetched
# window. Pre-fix flat_base omitted base_start_date + base_end_date even
# though the lock string at rule_criteria[5]['lock'] references
# `(base_end - base_start).days`. Audit across all 5 classes:
#   - vcp:             base_start_date + base_end_date          ✓ (pre-fix)
#   - flat_base:       base_start_date + base_end_date          ✗ -> FIX
#   - cup_with_handle: cup_left_edge_date / cup_bottom_date /
#                      cup_right_edge_date / handle_start_date /
#                      handle_end_date                          ✓ (pre-fix)
#   - high_tight_flag: pole_start_date / pole_end_date /
#                      consolidation_start_date /
#                      consolidation_end_date                   ✓ (pre-fix;
#       operator's "flag_start_date / flag_end_date" terminology is a
#       misnomer — spec section 5.5 names the sub-window `consolidation_*`
#       NOT `flag_*` per criterion 3 + 4 lock strings; existing schema
#       satisfies the contract.)
#   - double_bottom_w: trough_1_date / center_peak_date /
#                      trough_2_date                            ✓ (pre-fix)
# ============================================================================


@pytest.mark.parametrize(
    "pattern_class,required_sub_window_fields",
    [
        ("vcp", {"base_start_date", "base_end_date"}),
        ("flat_base", {"base_start_date", "base_end_date"}),
        (
            "cup_with_handle",
            {
                "cup_left_edge_date", "cup_bottom_date",
                "cup_right_edge_date",
                "handle_start_date", "handle_end_date",
            },
        ),
        (
            "high_tight_flag",
            {
                "pole_start_date", "pole_end_date",
                "consolidation_start_date", "consolidation_end_date",
            },
        ),
        (
            "double_bottom_w",
            {"trough_1_date", "center_peak_date", "trough_2_date"},
        ),
    ],
)
def test_structural_evidence_schema_carries_sub_window_dates_per_class(
    pattern_class: str,
    required_sub_window_fields: set[str],
) -> None:
    """Per Deficiency 3: each V1 class's structural_evidence_schema MUST
    enumerate enough date-typed sub-window fields for the subagent to
    scope shape identification within a possibly-larger fetched window.

    The rule_criteria locks for these classes reference sub-window dates
    (e.g., flat_base criterion 6: `(base_end - base_start).days >= 35`);
    if the schema doesn't expose the date fields, the subagent has no
    structured slot to record them + must inline-compute the window
    boundaries from the bars list.
    """
    schema = get_structural_evidence_schema(pattern_class)
    actual_fields = set(schema["fields"].keys())
    missing = required_sub_window_fields - actual_fields
    assert not missing, (
        f"{pattern_class!r} structural_evidence_schema missing sub-window "
        f"date fields: {missing}. Spec section "
        f"{schema['spec_section']} criteria lock strings reference these "
        f"date boundaries; the subagent needs structured slots to record "
        f"them."
    )
    # Each sub-window field MUST be typed as a date string for downstream
    # rule-detector consumption (T2.SB3+/SB4) - guard against type drift
    # to float / int that would silently break sub-window math.
    for field in required_sub_window_fields:
        type_hint = schema["fields"][field]
        assert "date" in type_hint.lower() and "iso" in type_hint.lower(), (
            f"{pattern_class!r} field {field!r} type hint {type_hint!r} "
            f"missing 'date' + 'ISO' markers; expected "
            f"'date (ISO YYYY-MM-DD)' shape per VCP schema convention."
        )


def test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming(
) -> None:
    """Spec section 5.5 names the sub-window between pole + breakout as
    'consolidation' (criterion #3 + #4 lock strings + structural evidence
    enumeration). The operator's T-A.1.7 resume note referenced
    'flag_start_date / flag_end_date' which is a colloquial misnomer. This
    test pins the schema to the spec's authoritative naming + guards
    against a future contributor renaming consolidation_* to flag_* (which
    would silently break the lock-string-vs-schema field mapping).
    """
    schema = get_structural_evidence_schema("high_tight_flag")
    fields = schema["fields"]
    assert "consolidation_start_date" in fields
    assert "consolidation_end_date" in fields
    # Defense-in-depth: assert flag_start_date / flag_end_date are NOT in
    # the schema (so a rename would fail the test immediately).
    assert "flag_start_date" not in fields, (
        "HTF schema must use 'consolidation_*' naming per spec section 5.5; "
        "operator's 'flag_*' terminology is a misnomer."
    )
    assert "flag_end_date" not in fields


def test_get_rule_criteria_returns_deep_copy() -> None:
    """Codex R1 Minor #2 closure - module-level data must not be poisoned
    by caller mutation.
    """
    first = get_rule_criteria("vcp")
    first["criteria"][0]["lock"] = "MUTATED"
    second = get_rule_criteria("vcp")
    assert second["criteria"][0]["lock"] != "MUTATED", (
        "get_rule_criteria leaked module state to caller mutation"
    )


def test_get_structural_evidence_schema_returns_deep_copy() -> None:
    """Codex R1 Minor #2 closure - module-level data must not be poisoned
    by caller mutation.
    """
    first = get_structural_evidence_schema("vcp")
    first["fields"]["stage"] = "MUTATED"
    second = get_structural_evidence_schema("vcp")
    assert second["fields"]["stage"] != "MUTATED", (
        "get_structural_evidence_schema leaked module state to caller "
        "mutation"
    )


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
