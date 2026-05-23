"""Phase 13 T-T4.SB.4 Sub-task 4A — SilverLabelResponse.rule_criteria field tests.

Per plan section B.4 Sub-task 4A.1-4A.5: discriminating tests for the
additive ``rule_criteria`` field + ``__post_init__`` validation.

Production fixtures (per the dataclass's contract) construct
``SilverLabelResponse`` via dispatch shape — ``structural_evidence_json``
accepts either dict or pre-serialized JSON string (T-A.1.5b Codex R1 M#4
coercion). These tests pre-serialize via ``json.dumps({...})`` for
fixture clarity.

Validation rules per L15 LOCK + CLAUDE.md gotcha "Literal[...] type hints
are NOT runtime-enforced":
  - ``rule_criteria`` defaults to None;
  - when provided, MUST be a list of dicts;
  - each element MUST carry non-empty ``name`` (str) +
    ``status`` in ``{"pass", "fail"}``;
  - optional ``evidence_value`` / ``threshold`` / ``tolerance`` keys are
    NOT type-validated (V1 deviation; banked in return report).
"""
from __future__ import annotations

import json

import pytest

from swing.patterns.labeling import SilverLabelResponse


def _base(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        evaluation="confirmed",
        confidence="high",
        structural_evidence_json=json.dumps({"x": 1}),
        geometric_evidence_narrative="A clean cup with a defined handle.",
    )
    base.update(overrides)
    return base


def test_silver_label_response_accepts_well_formed_rule_criteria() -> None:
    resp = SilverLabelResponse(**_base(rule_criteria=[
        {"name": "depth_pct_in_range", "status": "pass",
         "evidence_value": "22.5", "threshold": "15-35", "tolerance": None},
        {"name": "handle_duration_min", "status": "fail",
         "evidence_value": "3", "threshold": ">=5", "tolerance": None},
    ]))
    assert resp.rule_criteria is not None
    assert len(resp.rule_criteria) == 2
    assert resp.rule_criteria[0]["name"] == "depth_pct_in_range"
    assert resp.rule_criteria[1]["status"] == "fail"


def test_silver_label_response_defaults_rule_criteria_to_none() -> None:
    assert SilverLabelResponse(**_base()).rule_criteria is None


def test_silver_label_response_rejects_rule_criteria_missing_name() -> None:
    with pytest.raises(ValueError, match="name"):
        SilverLabelResponse(**_base(rule_criteria=[
            {"status": "pass", "evidence_value": "x",
             "threshold": "y", "tolerance": None},
        ]))


def test_silver_label_response_rejects_rule_criteria_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        SilverLabelResponse(**_base(rule_criteria=[
            {"name": "", "status": "pass"},
        ]))


def test_silver_label_response_rejects_rule_criteria_invalid_status() -> None:
    with pytest.raises(ValueError, match="status"):
        SilverLabelResponse(**_base(rule_criteria=[
            {"name": "x", "status": "maybe", "evidence_value": "x",
             "threshold": "y", "tolerance": None},
        ]))


def test_silver_label_response_rejects_rule_criteria_non_list() -> None:
    with pytest.raises(ValueError, match="rule_criteria"):
        SilverLabelResponse(**_base(rule_criteria={"not": "a list"}))


def test_silver_label_response_rejects_rule_criteria_element_non_dict() -> None:
    with pytest.raises(ValueError, match="dict"):
        SilverLabelResponse(**_base(rule_criteria=[
            "not_a_dict_at_all",
        ]))


def test_silver_label_response_accepts_empty_rule_criteria_list() -> None:
    """Empty list is a valid degenerate case (zero criteria evaluated) —
    not the same semantic as None (no payload). The VM parser handles
    both gracefully.
    """
    resp = SilverLabelResponse(**_base(rule_criteria=[]))
    assert resp.rule_criteria == []
