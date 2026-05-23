"""Phase 13 T-T4.SB.4 Sub-task 4B — envelope persistence tests.

Per plan section B.4 Sub-task 4B.1-4B.5 + Codex R3 M#2 LOCK:

  - ``labeler_evidence_json`` envelope MUST persist:
      * ``narrative`` alias key (ALWAYS populated, even when
        rule_criteria is absent — pre-empts the VM parser's
        ``_parse_narrative_text`` reader that keys on ``narrative``).
      * ``geometric_evidence_narrative`` PRESERVED VERBATIM (back-compat
        regression anchor: existing T2.SB1 corpus carries this key).
      * ``rule_criteria`` (ONLY when SilverLabelResponse.rule_criteria is
        non-None; OMITTED when None per audit envelope empty-state
        uniformity gotcha — see CLAUDE.md).

Tests exercise the envelope via the production write path
``fire_claude_silver_label`` (the plan template referenced a
``_persist_silver_label`` helper that does not exist; the envelope
assembly lives inline at ``fire_claude_silver_label`` — adapter pattern
to existing test fixtures per ``tests/patterns/test_labeling.py``).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.patterns.labeling import (
    SilverLabelResponse,
    fire_claude_silver_label,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t4sb4_envelope.db"
    return ensure_schema(db_path)


def _run_fire(
    conn: sqlite3.Connection, *, response: SilverLabelResponse, ticker: str,
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
        ai_labeler_version="claude-sonnet-4-6-dispatch-t4sb4",
        dispatch_subagent=fake_subagent,
    )


def test_envelope_persists_rule_criteria_and_narrative_alias(
    conn: sqlite3.Connection,
) -> None:
    """Codex R3 M#2 LOCK: envelope carries BOTH narrative alias AND
    rule_criteria when rule_criteria provided."""
    response = SilverLabelResponse(
        evaluation="confirmed",
        confidence="high",
        structural_evidence_json=json.dumps({"base": "data"}),
        geometric_evidence_narrative="A textbook cup with handle on AAA.",
        rule_criteria=[
            {"name": "cup_depth_pct", "status": "pass",
             "evidence_value": "22.0", "threshold": "15-35",
             "tolerance": None},
        ],
    )
    exemplar_id = _run_fire(conn, response=response, ticker="AAA")

    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    envelope = json.loads(persisted.labeler_evidence_json or "{}")

    # Both narrative keys per Codex R3 M#2 LOCK.
    assert envelope["narrative"] == "A textbook cup with handle on AAA."
    assert envelope["geometric_evidence_narrative"] == (
        "A textbook cup with handle on AAA."
    )
    # rule_criteria propagates verbatim.
    assert envelope["rule_criteria"][0]["name"] == "cup_depth_pct"
    assert envelope["rule_criteria"][0]["status"] == "pass"


def test_envelope_omits_rule_criteria_when_none_but_keeps_narrative_alias(
    conn: sqlite3.Connection,
) -> None:
    """Audit envelope empty-state uniformity gotcha (CLAUDE.md):
    when rule_criteria is None, the key MUST be ABSENT (not
    serialized as ``null``) — but the narrative alias is ALWAYS
    populated."""
    response = SilverLabelResponse(
        evaluation="confirmed",
        confidence="high",
        structural_evidence_json=json.dumps({"x": 1}),
        geometric_evidence_narrative="Narrative.",
    )
    exemplar_id = _run_fire(conn, response=response, ticker="BBB")

    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    envelope = json.loads(persisted.labeler_evidence_json or "{}")

    assert "rule_criteria" not in envelope
    # Narrative alias STILL populated even with no rule_criteria.
    assert envelope["narrative"] == "Narrative."
    assert envelope["geometric_evidence_narrative"] == "Narrative."


def test_envelope_back_compat_anchor_geometric_evidence_narrative_preserved(
    conn: sqlite3.Connection,
) -> None:
    """Back-compat regression anchor: the legacy
    ``geometric_evidence_narrative`` envelope key MUST persist VERBATIM
    so existing T2.SB1 corpus readers (e.g.,
    swing/patterns/labeling.py:_extract_corpus_row_fields) keep working.
    """
    response = SilverLabelResponse(
        evaluation="watch",
        confidence="medium",
        structural_evidence_json=json.dumps({"reason": "pre-breakout"}),
        geometric_evidence_narrative=(
            "Stage 2 setup; awaiting volume confirmation at pivot."
        ),
    )
    exemplar_id = _run_fire(conn, response=response, ticker="CCC")

    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    envelope = json.loads(persisted.labeler_evidence_json or "{}")
    # The legacy reader key MUST survive byte-identically.
    assert envelope["geometric_evidence_narrative"] == (
        "Stage 2 setup; awaiting volume confirmation at pivot."
    )


def test_envelope_persists_empty_rule_criteria_list_when_provided(
    conn: sqlite3.Connection,
) -> None:
    """When the subagent emits an empty list (degenerate: zero criteria
    evaluated), the envelope MUST persist the empty list — not omit it
    (omission is reserved for None; empty list is a meaningful state)."""
    response = SilverLabelResponse(
        evaluation="rejected",
        confidence="low",
        structural_evidence_json=json.dumps({"reason": "no criteria fit"}),
        geometric_evidence_narrative="Window does not match the proposed class.",
        rule_criteria=[],
    )
    exemplar_id = _run_fire(conn, response=response, ticker="DDD")

    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    envelope = json.loads(persisted.labeler_evidence_json or "{}")
    assert envelope["rule_criteria"] == []
    assert envelope["narrative"] == (
        "Window does not match the proposed class."
    )
