"""Phase 13 T2.SB1 T-A.1.8 - cassette-mode E2E for the Codex 2nd-reviewer.

Per closer brief T-1.8.2 acceptance criteria:
  - 1 slow E2E test marked ``@pytest.mark.slow`` (per CLAUDE.md convention).
  - Cassette content sanitized + sentinel-leak audit passes (committed
    cassette content is asserted free of openai-api-key shape, Bearer-
    token shape, 32+ hex-char token runs, and chatcmpl-* completion ids).
  - Disagreement-chain ``parent_exemplar_id`` linkage end-to-end verified
    via the full silver -> 15% sample -> disagreement -> codex_silver row
    insertion path.
  - SNAP-reproducibility-variance discriminating test passes (operator's
    T-A.1.7 observation that the same window dispatched twice yielded
    opposite labels — banked as forward-binding lesson #7).

V1 LIMITATION (per scripts/record_codex_mcp_pattern_review_cassettes.py):
the copowers Codex MCP server is a Claude Code HARNESS tool which is NOT
Python-HTTP-callable from inside pytest. V1 cassettes are therefore
SYNTHETIC playback fixtures rather than real VCR-recorded HTTP traffic.
V2 hardening per plan section H.4 + post-Phase-12 forward-binding lesson
#3: when the MCP server's HTTP transport is reachable from a pytest
harness, these cassettes will be re-recorded as real HTTP traffic with
the ``codex_mcp_vcr_config()`` filter chain applied at record-time.

Per CLAUDE.md gotcha "Synthetic-fixture-vs-production-emitter shape
drift": the cassette payload shape mirrors the production
``CodexReviewResponse`` dataclass contract EXACTLY (agreed +
alternative_evaluation + alternative_confidence +
alternative_structural_evidence_json + alternative_labeler_evidence_json).
Per T-A.1.5b R1 M#4 forward-binding lesson #4: the test exercises the
``__post_init__`` dict-or-string coercion path at dataclass construction.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest
import yaml

from swing.data.db import ensure_schema
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.patterns.labeling import (
    CODEX_RANDOM_SAMPLE_PROBABILITY,
    CodexReviewResponse,
    SilverLabelResponse,
    fire_claude_silver_label,
    fire_codex_review_for_silver_row,
)

_CASSETTE_DIR = (
    Path(__file__).resolve().parent
    / "cassettes"
    / "codex_mcp_pattern_review"
)

# Sentinel patterns the sentinel-leak audit script scans for; the test
# enforces the SAME contract against the committed YAML cassette files so
# any future contributor recording / hand-editing a cassette can't slip
# secrets past the audit step.
_SENTINEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-api-key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("authorization-header", re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}")),
    ("hex-token-shape", re.compile(r"\b[a-fA-F0-9]{32,}\b")),
    ("chatcmpl-id", re.compile(r"\bchatcmpl-[A-Za-z0-9]{10,}\b")),
)


class _SeededRng:
    """Deterministic RNG that replays a fixed sequence of float values."""

    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._index = 0

    def random(self) -> float:
        value = self._values[self._index]
        self._index = (self._index + 1) % len(self._values)
        return value


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "t-a-1-8-codex-e2e.db")


def _load_cassette(name: str) -> dict:
    """Load + parse a YAML cassette by basename (without .yaml)."""
    path = _CASSETTE_DIR / f"{name}.yaml"
    assert path.exists(), f"cassette missing: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ============================================================================
# Sentinel-leak audit on committed cassettes.
# ============================================================================


def test_committed_codex_mcp_cassettes_have_zero_sentinel_leaks() -> None:
    """Every committed cassette under ``tests/integrations/cassettes/
    codex_mcp_pattern_review/`` MUST contain ZERO matches for the
    sentinel-leak patterns the recording script enforces. This mirrors
    ``scripts/record_codex_mcp_pattern_review_cassettes.py --audit-sentinels``
    at test-suite time so a regression caught here fails CI immediately.
    """
    cassettes = sorted(_CASSETTE_DIR.glob("*.yaml"))
    assert cassettes, (
        "No cassettes under tests/integrations/cassettes/"
        "codex_mcp_pattern_review/ - T-A.1.8 must commit at least the "
        "disagreement_vcp_t2sb1 + snap_reproducibility_variance_t2sb1 "
        "fixtures."
    )
    for cassette in cassettes:
        text = cassette.read_text(encoding="utf-8")
        for label, pattern in _SENTINEL_PATTERNS:
            match = pattern.search(text)
            assert match is None, (
                f"sentinel leak in {cassette.name}: {label} pattern matched "
                f"at {match.group()!r}. Re-record cassette via "
                f"scripts/record_codex_mcp_pattern_review_cassettes.py + "
                f"verify the sanitization filter chain at "
                f"tests/integrations/_cassette_sanitization.py runs."
            )


# ============================================================================
# E2E: silver -> 15% Codex sample -> disagreement -> codex_silver row.
# ============================================================================


@pytest.mark.slow
def test_codex_mcp_disagreement_end_to_end_via_cassette(
    conn: sqlite3.Connection,
) -> None:
    """Full E2E: plant silver via fire_claude_silver_label + force random
    fire via deterministic RNG + invoke fire_codex_review_for_silver_row
    with a codex_dispatch sourced from the synthetic disagreement cassette
    + verify codex_silver row inserted with parent_exemplar_id linkage.

    Verifies the production data-derivation path (cassette YAML ->
    CodexReviewResponse dataclass via __post_init__ coercion ->
    fire_codex_review_for_silver_row -> pattern_exemplars INSERT) per the
    Phase 13 T1.SB0 gate-fix lesson on "production-path regression tests".
    """
    cassette = _load_cassette("disagreement_vcp_t2sb1")
    interaction = cassette["interaction"]
    response_body = interaction["response"]["body"]

    # Plant a claude_silver parent row first (mirrors the operator-paired
    # T-A.1.7 workflow at swing/cli.py:label_exemplars_cmd persist path).
    def initial_subagent(**_kwargs: object) -> SilverLabelResponse:
        return SilverLabelResponse(
            evaluation="confirmed",
            confidence="high",
            structural_evidence_json={"placeholder": "vcp-confirmed-silver"},
            geometric_evidence_narrative=(
                "Stage 2 uptrend; 3 contractions; T3 5%."
            ),
        )

    parent_id = fire_claude_silver_label(
        conn,
        ticker="SYNTHETICTICKER",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        pattern_class="vcp",
        window_payload={"ticker": "SYNTHETICTICKER", "bars": []},
        rule_criteria={},
        structural_evidence_schema={},
        ai_labeler_version="claude-sonnet-4-6",
        dispatch_subagent=initial_subagent,
    )

    # Codex dispatch consumes the cassette response body verbatim;
    # CodexReviewResponse's __post_init__ coerces dict-shaped alternatives
    # to canonical JSON strings (defense-in-depth per T-A.1.5b R1 M#4).
    def codex_dispatch_from_cassette(
        **_kwargs: object,
    ) -> CodexReviewResponse:
        return CodexReviewResponse(
            agreed=response_body["agreed"],
            alternative_evaluation=response_body[
                "alternative_evaluation"
            ],
            alternative_confidence=response_body[
                "alternative_confidence"
            ],
            alternative_structural_evidence_json=response_body[
                "alternative_structural_evidence_json"
            ],
            alternative_labeler_evidence_json=response_body[
                "alternative_labeler_evidence_json"
            ],
        )

    codex_id = fire_codex_review_for_silver_row(
        conn,
        exemplar_id=parent_id,
        phase="t2_sb1",
        ai_labeler_version="gpt-5-codex-dispatch",
        codex_dispatch=codex_dispatch_from_cassette,
        rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.001]),
    )

    assert codex_id is not None
    assert codex_id != parent_id

    # Parent: codex_reviewed=1 + codex_agreement=0; label_source preserved.
    parent_after = exemplars_repo.get_exemplar_by_id(conn, parent_id)
    assert parent_after is not None
    assert parent_after.codex_reviewed == 1
    assert parent_after.codex_agreement == 0
    assert parent_after.label_source == "claude_silver"

    # Codex disagreement row: label_source='codex_silver' + parent linkage
    # + final_decision mirrors the cassette response.
    codex_row = exemplars_repo.get_exemplar_by_id(conn, codex_id)
    assert codex_row is not None
    assert codex_row.label_source == "codex_silver"
    assert codex_row.parent_exemplar_id == parent_id
    assert codex_row.final_decision == response_body["alternative_evaluation"]
    assert codex_row.proposed_pattern_class == "vcp"
    assert codex_row.created_by == "codex_dispatch"

    # Structural evidence persisted as canonical sort_keys JSON string
    # (T-A.1.5b R1 M#4 coercion at __post_init__ time).
    persisted_evidence = json.loads(codex_row.structural_evidence_json)
    assert persisted_evidence == response_body[
        "alternative_structural_evidence_json"
    ]


# ============================================================================
# SNAP reproducibility variance discriminating test.
# ============================================================================


@pytest.mark.slow
def test_snap_reproducibility_variance_both_passes_fire_codex_independently(
    conn: sqlite3.Connection,
) -> None:
    """Per closer brief section 1.2 banked observation + T-A.1.7 paired
    session: same window dispatched twice yielded opposite labels
    (rejected vs watch). The cassette plants two silver rows for the
    same window + verifies BOTH fire Codex disagreement chains
    INDEPENDENTLY (each codex_silver row carries its OWN
    parent_exemplar_id pointing at the row it disagreed with).
    """
    cassette = _load_cassette("snap_reproducibility_variance_t2sb1")
    interactions = cassette["interactions"]
    assert len(interactions) == 2, "SNAP cassette must capture 2 passes"

    parent_ids: list[int] = []
    codex_child_ids: list[int] = []

    for pass_idx, interaction in enumerate(interactions):
        silver_label = interaction["silver_label"]
        codex_response_data = interaction["codex_review_response"]

        def _silver_dispatch(
            silver_label=silver_label,  # bind per-iteration
            **_kwargs: object,
        ) -> SilverLabelResponse:
            return SilverLabelResponse(
                evaluation=silver_label["evaluation"],
                confidence=silver_label["confidence"],
                structural_evidence_json=silver_label[
                    "structural_evidence_json"
                ],
                geometric_evidence_narrative=silver_label[
                    "labeler_evidence_narrative"
                ],
            )

        parent_id = fire_claude_silver_label(
            conn,
            ticker="SNAP",
            timeframe="daily",
            start_date="2020-07-01",
            end_date="2020-10-01",
            pattern_class="vcp",
            window_payload={"ticker": "SNAP", "bars": []},
            rule_criteria={},
            structural_evidence_schema={},
            ai_labeler_version=f"claude-sonnet-4-6-pass{pass_idx + 1}",
            dispatch_subagent=_silver_dispatch,
        )
        parent_ids.append(parent_id)

        def _codex_dispatch(
            data=codex_response_data,  # bind per-iteration
            **_kwargs: object,
        ) -> CodexReviewResponse:
            return CodexReviewResponse(
                agreed=data["agreed"],
                alternative_evaluation=data["alternative_evaluation"],
                alternative_confidence=data["alternative_confidence"],
                alternative_structural_evidence_json=data[
                    "alternative_structural_evidence_json"
                ],
                alternative_labeler_evidence_json=data[
                    "alternative_labeler_evidence_json"
                ],
            )

        codex_id = fire_codex_review_for_silver_row(
            conn,
            exemplar_id=parent_id,
            phase="t2_sb1",
            ai_labeler_version="gpt-5-codex-dispatch",
            codex_dispatch=_codex_dispatch,
            rng=_SeededRng([CODEX_RANDOM_SAMPLE_PROBABILITY - 0.001]),
        )
        assert codex_id is not None, (
            f"pass {pass_idx + 1}: should_fire_codex returned False under "
            "forced sub-threshold rng - regression in policy gate."
        )
        codex_child_ids.append(codex_id)

    # The two passes produced distinct parent rows + distinct codex children.
    assert len(set(parent_ids)) == 2
    assert len(set(codex_child_ids)) == 2

    # Each codex child points back at the CORRECT pass-specific parent
    # (not cross-linked). This is the discriminating assertion: a naive
    # implementation might race the parent_exemplar_id linkage across
    # passes if it pulled the parent from a process-global cache.
    for parent_id, codex_id, interaction in zip(
        parent_ids, codex_child_ids, interactions, strict=True,
    ):
        codex_row = exemplars_repo.get_exemplar_by_id(conn, codex_id)
        assert codex_row is not None
        assert codex_row.parent_exemplar_id == parent_id
        assert codex_row.final_decision == interaction[
            "codex_review_response"
        ]["alternative_evaluation"]

    # Both passes' parents flipped to codex_reviewed=1 + codex_agreement=0.
    for parent_id in parent_ids:
        parent = exemplars_repo.get_exemplar_by_id(conn, parent_id)
        assert parent is not None
        assert parent.codex_reviewed == 1
        assert parent.codex_agreement == 0

    # The two passes' codex alternatives are OPPOSITE (operator's
    # reproducibility variance observation): pass 1 -> 'watch', pass 2 ->
    # 'confirmed'. If the alternatives become identical, the cassette has
    # drifted from the observation it's meant to encode.
    pass_1_alternative = interactions[0]["codex_review_response"][
        "alternative_evaluation"
    ]
    pass_2_alternative = interactions[1]["codex_review_response"][
        "alternative_evaluation"
    ]
    assert pass_1_alternative != pass_2_alternative, (
        "cassette must preserve the opposite-labels reproducibility "
        "variance observation (operator T-A.1.7 paired session)."
    )
