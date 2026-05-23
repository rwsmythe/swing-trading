"""Phase 13 T-T4.SB.4 Sub-task 4D — VM parser <-> template integration tests.

Per plan section B.4 Sub-task 4D + Codex R3 M#2 LOCK + Architecture-
location audit Expansion #10(b) triangulation:

Item 2's "rendering gap" was at EMIT/PERSIST (envelope persistence), NOT
at the template OR VM parser — Sub-tasks 4A + 4B closed the EMIT side; the
template at swing/web/templates/patterns/exemplars.html.j2 + the parser at
swing/web/view_models/patterns/exemplars.py:_parse_criterion_rows
already do the right thing.

These tests confirm the FULL data flow (envelope -> repo -> VM -> render)
post-Sub-tasks 4A + 4B + verify back-compat for legacy exemplars that
predate the rule_criteria contract.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.patterns.labeling import (
    SilverLabelResponse,
    fire_claude_silver_label,
)
from swing.web.view_models.patterns.exemplars import (
    _parse_criterion_rows,
    _parse_narrative_text,
    build_patterns_exemplars_vm,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase13_t4sb4_vm.db")


def _plant_silver_via_fire(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    response: SilverLabelResponse,
) -> int:
    def fake_subagent(**_kwargs: object) -> SilverLabelResponse:
        return response

    return fire_claude_silver_label(
        conn,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        pattern_class="vcp",
        window_payload={"ticker": ticker, "timeframe": "daily", "bars": []},
        rule_criteria={"min_contractions": 2},
        structural_evidence_schema={"contractions": "list"},
        ai_labeler_version="claude-sonnet-4-6-dispatch-t4sb4-vm",
        dispatch_subagent=fake_subagent,
    )


def _plant_legacy_exemplar(
    conn: sqlite3.Connection, *, ticker: str, envelope: dict[str, object],
) -> int:
    """Pre-T4.SB.4 envelope shape (no rule_criteria; no narrative alias —
    only the legacy ``geometric_evidence_narrative`` key). Used to verify
    back-compat: legacy rows render gracefully (placeholder).
    """
    exemplar = PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2023-01-01",
        end_date="2023-02-01",
        proposed_pattern_class="vcp",
        final_decision="confirmed",
        label_source="claude_silver",
        structural_evidence_json="{}",
        created_at="2023-02-02T00:00:00",
        created_by="claude_dispatch",
        final_pattern_class=None,
        ai_labeler_version="legacy",
        gold_validated_at=None,
        codex_reviewed=0,
        codex_agreement=None,
        geometric_score_json=None,
        labeler_evidence_json=json.dumps(envelope, sort_keys=True),
        quality_grade=None,
        notes=None,
        parent_exemplar_id=None,
    )
    with conn:
        return exemplars_repo.insert_exemplar(conn, exemplar)


# ---------------------------------------------------------------------------
# Fresh-silver path (post-Sub-tasks 4A + 4B): VM parser lights up.
# ---------------------------------------------------------------------------


def test_exemplars_vm_renders_rule_criteria_for_fresh_silver_with_payload(
    conn: sqlite3.Connection,
) -> None:
    """Sub-tasks 4A + 4B EMIT side closed -> the VM's per-exemplar render
    surfaces criterion_rows + narrative_text from the envelope written
    by fire_claude_silver_label."""
    response = SilverLabelResponse(
        evaluation="confirmed",
        confidence="high",
        structural_evidence_json=json.dumps({"contractions": [22, 14, 8]}),
        geometric_evidence_narrative=(
            "Three contractions tightening from 22pct to 8pct."
        ),
        rule_criteria=[
            {"name": "cup_depth_pct", "status": "pass",
             "evidence_value": "22.0", "threshold": "15-35",
             "tolerance": None},
            {"name": "handle_dur_min", "status": "fail",
             "evidence_value": "3", "threshold": ">=5",
             "tolerance": None},
        ],
    )
    exemplar_id = _plant_silver_via_fire(
        conn, ticker="AAA", response=response,
    )

    vm = build_patterns_exemplars_vm(conn, session_date="2024-02-02")
    render = vm.exemplar_renders[exemplar_id]
    assert len(render.criterion_rows) == 2
    assert render.criterion_rows[0].name == "cup_depth_pct"
    assert render.criterion_rows[0].status == "pass"
    assert render.criterion_rows[1].name == "handle_dur_min"
    assert render.criterion_rows[1].status == "fail"
    # Narrative alias surfaced from the new envelope key.
    assert render.narrative_text == (
        "Three contractions tightening from 22pct to 8pct."
    )


def test_exemplars_vm_renders_narrative_alias_when_rule_criteria_absent(
    conn: sqlite3.Connection,
) -> None:
    """Fresh silver row with no rule_criteria payload -> narrative_text
    STILL lights up (envelope alias key is always populated per Sub-task
    4B), and criterion_rows is empty tuple (graceful placeholder)."""
    response = SilverLabelResponse(
        evaluation="watch",
        confidence="medium",
        structural_evidence_json=json.dumps({"reason": "pre-breakout"}),
        geometric_evidence_narrative=(
            "Setup forming but volume not yet confirmed."
        ),
    )
    exemplar_id = _plant_silver_via_fire(
        conn, ticker="BBB", response=response,
    )

    vm = build_patterns_exemplars_vm(conn, session_date="2024-02-02")
    render = vm.exemplar_renders[exemplar_id]
    assert render.criterion_rows == ()
    assert render.narrative_text == (
        "Setup forming but volume not yet confirmed."
    )


# ---------------------------------------------------------------------------
# Legacy back-compat (existing T2.SB1 corpus): graceful placeholder.
# ---------------------------------------------------------------------------


def test_legacy_exemplar_without_rule_criteria_or_alias_renders_placeholder(
    conn: sqlite3.Connection,
) -> None:
    """Back-compat regression anchor: a legacy exemplar (pre-T4.SB.4,
    only the legacy ``geometric_evidence_narrative`` key, NO
    ``narrative`` alias, NO ``rule_criteria``) renders with empty
    criterion_rows + None narrative_text -> the template surfaces the
    'no rule_criteria' + 'no narrative' placeholders (verified at
    swing/web/templates/patterns/exemplars.html.j2:75 + :84)."""
    exemplar_id = _plant_legacy_exemplar(
        conn, ticker="OLD",
        envelope={
            "evaluation": "confirmed",
            "confidence": "high",
            "geometric_evidence_narrative": (
                "Legacy narrative on key only; no alias."
            ),
        },
    )

    vm = build_patterns_exemplars_vm(conn, session_date="2024-02-02")
    render = vm.exemplar_renders[exemplar_id]
    # No rule_criteria persisted -> empty rows.
    assert render.criterion_rows == ()
    # Legacy envelope does NOT have the ``narrative`` alias key the parser
    # reads -> placeholder. (Sub-task 4B's alias only applies to FRESH
    # silver labels; legacy rows are not re-written.)
    assert render.narrative_text is None


def test_parser_handles_envelope_with_only_narrative_alias() -> None:
    """Unit-level coverage: VM parser reads the ``narrative`` alias
    independently from rule_criteria presence (Codex R3 M#2 LOCK)."""
    envelope = json.dumps({
        "narrative": "An alias-only narrative.",
    })
    assert _parse_narrative_text(envelope) == "An alias-only narrative."
    assert _parse_criterion_rows(envelope) == ()


def test_parser_skips_invalid_rule_criteria_elements_gracefully() -> None:
    """Defensive parsing: rule_criteria elements with bad status / missing
    name are silently skipped (per
    swing/web/view_models/patterns/exemplars.py:_parse_criterion_rows
    L122-167 contract)."""
    envelope = json.dumps({
        "rule_criteria": [
            {"name": "good", "status": "pass"},
            {"status": "pass"},  # missing name -> skip
            {"name": "bad", "status": "maybe"},  # bad status -> skip
            {"name": "also_good", "status": "fail"},
        ],
        "narrative": "Two of four parsed.",
    })
    rows = _parse_criterion_rows(envelope)
    assert len(rows) == 2
    assert rows[0].name == "good"
    assert rows[1].name == "also_good"
