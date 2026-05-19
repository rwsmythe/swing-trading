"""Phase 13 T2.SB1 task T-A.1.3 — dev-time labeling discriminating tests.

Per plan §G.1 T-A.1.3 Step 1: 4 discriminating tests covering
``fire_claude_silver_label`` + ``fire_codex_review_for_silver_row`` +
phased policy decision (T2.SB1 vs T2.SB3+) + Codex disagreement-chain
``parent_exemplar_id`` linkage.

Per Codex R4 M#1 closure: NO ``PHASE13_TEST_MOCK_SUBAGENT`` env-var
backdoor (production data-integrity footgun risk); mock injection via
in-process pytest ``monkeypatch`` ONLY.
"""
from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.patterns.labeling import (
    CODEX_RANDOM_SAMPLE_PROBABILITY,
    CodexReviewResponse,
    SilverLabelResponse,
    fire_claude_silver_label,
    fire_codex_review_for_silver_row,
    should_fire_codex,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb1_labeling.db"
    return ensure_schema(db_path)


# ============================================================================
# Test 1: fire_claude_silver_label dispatches subagent + persists silver row.
# ============================================================================


def test_fire_claude_silver_label_dispatches_and_persists_silver_row(
    conn: sqlite3.Connection,
) -> None:
    """``fire_claude_silver_label`` with injected dispatch_subagent persists
    one ``pattern_exemplars`` row with ``label_source='claude_silver'`` +
    parent_exemplar_id=NULL + codex_reviewed=0 + dispatch SHA in
    ``ai_labeler_version``.
    """
    captured_payload: dict = {}

    def fake_subagent(**kwargs: object) -> SilverLabelResponse:
        captured_payload.update(kwargs)
        return SilverLabelResponse(
            evaluation="confirmed",
            confidence="high",
            structural_evidence_json=json.dumps(
                {"contractions": [], "pivot_price": 25.0}
            ),
            geometric_evidence_narrative=(
                "Stage 2 uptrend confirmed; pivot at 25.00."
            ),
        )

    exemplar_id = fire_claude_silver_label(
        conn,
        ticker="ABC",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        pattern_class="vcp",
        window_payload={
            "ticker": "ABC",
            "timeframe": "daily",
            "bars": [],
        },
        rule_criteria={"min_contractions": 2},
        structural_evidence_schema={"contractions": "list"},
        ai_labeler_version="claude-sonnet-4-6-dispatch-abc123",
        dispatch_subagent=fake_subagent,
    )

    # Dispatch payload propagated correctly.
    assert captured_payload["pattern_class"] == "vcp"
    assert captured_payload["window_payload"]["ticker"] == "ABC"

    # Persisted row shape.
    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    assert persisted.label_source == "claude_silver"
    assert persisted.proposed_pattern_class == "vcp"
    assert persisted.final_decision == "confirmed"
    assert persisted.final_pattern_class is None
    assert persisted.codex_reviewed == 0
    assert persisted.codex_agreement is None
    assert persisted.parent_exemplar_id is None
    assert persisted.ai_labeler_version == "claude-sonnet-4-6-dispatch-abc123"
    assert persisted.created_by == "claude_dispatch"

    # geometric_score_json NULL pre-detector-backfill; labeler_evidence_json set.
    assert persisted.geometric_score_json is None
    assert persisted.labeler_evidence_json is not None
    parsed_ev = json.loads(persisted.labeler_evidence_json)
    assert parsed_ev["evaluation"] == "confirmed"
    assert parsed_ev["confidence"] == "high"


def test_fire_claude_silver_label_relabel_maps_to_relabeled_decision(
    conn: sqlite3.Connection,
) -> None:
    """``evaluation='relabel:<other_class>'`` maps to final_decision='relabeled'
    with final_pattern_class=<other_class> distinct from proposed.
    """
    def fake_subagent(**_kwargs: object) -> SilverLabelResponse:
        return SilverLabelResponse(
            evaluation="relabel:flat_base",
            confidence="medium",
            structural_evidence_json=json.dumps(
                {"reason": "VCP criteria failed; window is a flat base"}
            ),
            geometric_evidence_narrative=(
                "Window is a 6-week flat base not a VCP."
            ),
        )

    exemplar_id = fire_claude_silver_label(
        conn,
        ticker="XYZ",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-15",
        pattern_class="vcp",
        window_payload={"ticker": "XYZ", "bars": []},
        rule_criteria={},
        structural_evidence_schema={},
        ai_labeler_version="claude-sonnet-4-6",
        dispatch_subagent=fake_subagent,
    )
    persisted = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    assert persisted is not None
    assert persisted.final_decision == "relabeled"
    assert persisted.final_pattern_class == "flat_base"
    assert persisted.proposed_pattern_class == "vcp"


# ============================================================================
# Test 2: should_fire_codex phased policy (T2.SB1 vs T2.SB3+).
# ============================================================================


class _SeededRng(random.Random):
    """Random with explicit ``random()`` sequence for deterministic tests."""

    def __init__(self, values: list[float]) -> None:
        super().__init__()
        self._values = list(values)
        self._index = 0

    def random(self) -> float:  # type: ignore[override]
        value = self._values[self._index]
        self._index = (self._index + 1) % len(self._values)
        return value


def test_should_fire_codex_t2_sb1_phase_random_only() -> None:
    """T2.SB1 phase: random 15% sampling ONLY. NO high-stakes clauses."""
    # Below 15% threshold -> fires.
    fire = should_fire_codex(
        phase="t2_sb1",
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.001]),
    )
    assert fire is True

    # Above 15% threshold -> does NOT fire (no high-stakes fallback at SB1).
    no_fire = should_fire_codex(
        phase="t2_sb1",
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY + 0.001]),
    )
    assert no_fire is False

    # T2.SB1: NO matter the confidence + geometric score, only random matters.
    no_fire_high_stakes_ignored = should_fire_codex(
        phase="t2_sb1",
        silver_confidence="high",
        geometric_score=0.1,  # would be disagreement A at T2.SB3+
        rng=_SeededRng([0.99]),  # above 15% threshold
    )
    assert no_fire_high_stakes_ignored is False


def test_should_fire_codex_t2_sb3_or_later_high_stakes_clauses() -> None:
    """T2.SB3+/SB4 phase: random 15% PLUS high-stakes clauses.

    Disagreement A: silver_confidence='high' AND geometric_score < 0.5.
    Disagreement B: silver_confidence='low'  AND geometric_score >= 0.8.
    """
    # Below 15% random -> fires (random branch).
    assert should_fire_codex(
        phase="t2_sb3_or_later",
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.01]),
    ) is True

    # Above 15% random + high silver_confidence + low geometric_score
    # (disagreement A) -> FIRES.
    assert should_fire_codex(
        phase="t2_sb3_or_later",
        silver_confidence="high",
        geometric_score=0.3,
        rng=_SeededRng([0.99]),
    ) is True

    # Above 15% random + low silver_confidence + high geometric_score
    # (disagreement B inverse) -> FIRES.
    assert should_fire_codex(
        phase="t2_sb3_or_later",
        silver_confidence="low",
        geometric_score=0.9,
        rng=_SeededRng([0.99]),
    ) is True

    # Above 15% random + medium silver_confidence -> does NOT fire (neither
    # disagreement clause applies).
    assert should_fire_codex(
        phase="t2_sb3_or_later",
        silver_confidence="medium",
        geometric_score=0.5,
        rng=_SeededRng([0.99]),
    ) is False

    # Above 15% random + high silver_confidence + high geometric_score
    # (NO disagreement) -> does NOT fire.
    assert should_fire_codex(
        phase="t2_sb3_or_later",
        silver_confidence="high",
        geometric_score=0.85,
        rng=_SeededRng([0.99]),
    ) is False


# ============================================================================
# Test 3: Codex disagreement-chain parent_exemplar_id linkage.
# ============================================================================


def test_codex_disagreement_inserts_codex_silver_row_with_parent_linkage(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §5.9 step 4 + Codex R4 M#3 + R5 M#2: Codex disagreement
    INSERTs a SECOND row with ``label_source='codex_silver'`` +
    ``parent_exemplar_id`` pointing to the parent.
    """
    # Plant a claude_silver parent row first.
    def initial_subagent(**_kwargs: object) -> SilverLabelResponse:
        return SilverLabelResponse(
            evaluation="confirmed",
            confidence="high",
            structural_evidence_json=json.dumps({"placeholder": True}),
            geometric_evidence_narrative="Confirmed VCP per criteria.",
        )

    parent_id = fire_claude_silver_label(
        conn,
        ticker="ABC",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        pattern_class="vcp",
        window_payload={"ticker": "ABC", "bars": []},
        rule_criteria={},
        structural_evidence_schema={},
        ai_labeler_version="claude-sonnet-4-6",
        dispatch_subagent=initial_subagent,
    )

    # Codex dispatch returns DISAGREEMENT.
    def codex_dispatch_disagree(**_kwargs: object) -> CodexReviewResponse:
        return CodexReviewResponse(
            agreed=False,
            alternative_evaluation="rejected",
            alternative_confidence="high",
            alternative_structural_evidence_json=json.dumps(
                {"reason": "VCP criteria 5 failed: pivot not above prior high"}
            ),
        )

    # Force random fire via deterministic Rng (below 15% threshold).
    codex_id = fire_codex_review_for_silver_row(
        conn,
        exemplar_id=parent_id,
        phase="t2_sb1",
        ai_labeler_version="gpt-5-codex-dispatch",
        codex_dispatch=codex_dispatch_disagree,
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.001]),
    )
    assert codex_id is not None
    assert codex_id != parent_id

    # Parent row: codex_reviewed=1 + codex_agreement=0.
    parent_after = exemplars_repo.get_exemplar_by_id(conn, parent_id)
    assert parent_after is not None
    assert parent_after.codex_reviewed == 1
    assert parent_after.codex_agreement == 0
    assert parent_after.label_source == "claude_silver"
    assert parent_after.parent_exemplar_id is None

    # Codex disagreement row: label_source='codex_silver' + parent linkage.
    codex_row = exemplars_repo.get_exemplar_by_id(conn, codex_id)
    assert codex_row is not None
    assert codex_row.label_source == "codex_silver"
    assert codex_row.parent_exemplar_id == parent_id
    assert codex_row.proposed_pattern_class == "vcp"
    assert codex_row.final_decision == "rejected"
    assert codex_row.created_by == "codex_dispatch"


def test_codex_agreement_updates_parent_in_place_no_new_row(
    conn: sqlite3.Connection,
) -> None:
    """Codex AGREEMENT flips parent's flags WITHOUT inserting a second row."""
    def initial_subagent(**_kwargs: object) -> SilverLabelResponse:
        return SilverLabelResponse(
            evaluation="watch",
            confidence="medium",
            structural_evidence_json=json.dumps({"k": "v"}),
            geometric_evidence_narrative="Watching pre-pivot.",
        )

    parent_id = fire_claude_silver_label(
        conn,
        ticker="MMM",
        timeframe="weekly",
        start_date="2024-01-01",
        end_date="2024-03-01",
        pattern_class="flat_base",
        window_payload={"ticker": "MMM", "bars": []},
        rule_criteria={},
        structural_evidence_schema={},
        ai_labeler_version="claude-sonnet-4-6",
        dispatch_subagent=initial_subagent,
    )

    pre_count = len(exemplars_repo.list_exemplars(conn))

    def codex_dispatch_agree(**_kwargs: object) -> CodexReviewResponse:
        return CodexReviewResponse(agreed=True)

    result = fire_codex_review_for_silver_row(
        conn,
        exemplar_id=parent_id,
        phase="t2_sb1",
        ai_labeler_version="gpt-5-codex-dispatch",
        codex_dispatch=codex_dispatch_agree,
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.001]),
    )
    assert result is None  # No new row inserted.

    post_count = len(exemplars_repo.list_exemplars(conn))
    assert post_count == pre_count  # No row added.

    parent = exemplars_repo.get_exemplar_by_id(conn, parent_id)
    assert parent is not None
    assert parent.codex_reviewed == 1
    assert parent.codex_agreement == 1


def test_codex_skipped_when_random_above_threshold_returns_none(
    conn: sqlite3.Connection,
) -> None:
    """When phased policy decides NOT to fire, function returns None +
    NO codex_dispatch invocation.
    """
    def initial_subagent(**_kwargs: object) -> SilverLabelResponse:
        return SilverLabelResponse(
            evaluation="confirmed",
            confidence="high",
            structural_evidence_json="{}",
            geometric_evidence_narrative="Confirmed.",
        )

    parent_id = fire_claude_silver_label(
        conn,
        ticker="ABC",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        pattern_class="cup_with_handle",
        window_payload={"ticker": "ABC", "bars": []},
        rule_criteria={},
        structural_evidence_schema={},
        ai_labeler_version="claude-sonnet-4-6",
        dispatch_subagent=initial_subagent,
    )

    dispatch_calls: list = []

    def codex_dispatch_should_not_fire(**kwargs: object) -> CodexReviewResponse:
        dispatch_calls.append(kwargs)
        return CodexReviewResponse(agreed=True)

    result = fire_codex_review_for_silver_row(
        conn,
        exemplar_id=parent_id,
        phase="t2_sb1",
        ai_labeler_version="gpt-5-codex-dispatch",
        codex_dispatch=codex_dispatch_should_not_fire,
        rng=_SeededRng([0.99]),  # above 15% threshold
    )
    assert result is None
    assert dispatch_calls == []

    # Parent UNCHANGED.
    parent = exemplars_repo.get_exemplar_by_id(conn, parent_id)
    assert parent is not None
    assert parent.codex_reviewed == 0
    assert parent.codex_agreement is None
