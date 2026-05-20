"""Phase 13 T2.SB1 task T-A.1.3 — dev-time pattern labeling glue.

Provides the two BINDING entry points for the dev-time labeling pipeline
per spec §5.9 + plan §G.1 T-A.1.3:

  - ``fire_claude_silver_label`` — dispatch the ``pattern-labeler`` Claude
    Code subagent for one (window, pattern_class) seed tuple + persist the
    silver-tier label to ``pattern_exemplars``.
  - ``fire_codex_review_for_silver_row`` — selective Codex 2nd-reviewer
    operationalization per L9 + OQ-5 phased rollout:
      * T2.SB1 phase: random 15% sampling ONLY.
      * T2.SB3+/SB4 phase: random 15% + high-stakes clause + low-confidence-
        high-geometric inverse (re-evaluated retroactively per spec §5.9
        step 4).

Both functions accept an injectable dispatch callable so pytest fixtures can
monkeypatch the subagent / Codex MCP invocation deterministically. Per
Codex R4 M#1 closure (plan §G.1 T-A.1.3): the production-recognized env-var
mock gate ``PHASE13_TEST_MOCK_SUBAGENT`` is FORBIDDEN — mock injection
happens via in-process pytest ``monkeypatch`` ONLY (production data-
integrity footgun).

Per L1 LOCK + v2 brief §1 introspection HARD constraint: this module is
DEV-TIME ONLY. The pipeline (``swing/pipeline/runner.py``) MUST NEVER
import + invoke these functions.
"""
from __future__ import annotations

import json
import random
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from swing.data.models import DETECTOR_PATTERN_CLASSES, PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo

# Phased Codex policy per OQ-5 + spec §5.9 step 4 + §A.6.
SelectivePhase = Literal["t2_sb1", "t2_sb3_or_later"]

# Probability threshold for random-sample Codex 2nd review (both phases).
CODEX_RANDOM_SAMPLE_PROBABILITY: float = 0.15


class LabelingDispatchError(RuntimeError):
    """Raised when the subagent dispatch callable is not provided in a
    code path that requires real labeling.

    Production-facing default for ``fire_claude_silver_label`` raises this
    rather than silently no-oping or returning a synthetic stub. Tests
    inject a deterministic ``dispatch_subagent`` via kwarg.
    """


_VALID_SILVER_EVALUATIONS_NON_RELABEL: frozenset[str] = frozenset(
    ("confirmed", "watch", "rejected")
)
_VALID_SILVER_CONFIDENCES: frozenset[str] = frozenset(
    ("high", "medium", "low")
)


def _validate_silver_evaluation(value: object) -> None:
    """Codex R3 M#1 closure - runtime validate the evaluation field per
    the .claude/agents/pattern-labeler.md contract:
    'confirmed' | 'watch' | 'rejected' | 'relabel:<other_class>'.
    """
    if not isinstance(value, str):
        raise ValueError(
            "SilverLabelResponse.evaluation must be a str; got "
            f"{type(value).__name__}"
        )
    if value in _VALID_SILVER_EVALUATIONS_NON_RELABEL:
        return
    if value.startswith("relabel:"):
        target = value.split(":", 1)[1]
        if target not in DETECTOR_PATTERN_CLASSES:
            raise ValueError(
                "SilverLabelResponse.evaluation 'relabel:<other>' "
                f"target {target!r} must be one of "
                f"{sorted(DETECTOR_PATTERN_CLASSES)}"
            )
        return
    raise ValueError(
        "SilverLabelResponse.evaluation must be one of "
        f"{sorted(_VALID_SILVER_EVALUATIONS_NON_RELABEL)} "
        "OR 'relabel:<other_class>'; got "
        f"{value!r}"
    )


def _validate_silver_confidence(value: object) -> None:
    """Codex R3 M#1 closure - runtime validate the confidence field.

    The Literal['high','medium','low'] type hint is not runtime-enforced;
    without this validator, an invalid value would persist garbage into
    labeler_evidence_json.
    """
    if value not in _VALID_SILVER_CONFIDENCES:
        raise ValueError(
            "SilverLabelResponse.confidence must be one of "
            f"{sorted(_VALID_SILVER_CONFIDENCES)}; got {value!r}"
        )


def _coerce_dict_to_canonical_json_str(
    field_name: str, value: object,
) -> str | None:
    """T-A.1.5b Codex R1 M#4 closure - defense-in-depth coercion at
    dataclass construction time.

    Accept dict (subagent's documented contract) OR a JSON-object string
    (existing test fixtures pre-serialized via json.dumps({...})). Reject
    anything else. None passes through (for nullable fields).
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{field_name} string is not valid JSON: {exc}"
            ) from exc
        if not isinstance(decoded, dict):
            raise ValueError(
                f"{field_name} string must decode to a JSON object "
                f"(dict); got {type(decoded).__name__}"
            )
        return json.dumps(decoded, sort_keys=True)
    raise TypeError(
        f"{field_name} must be a JSON object (dict) OR a pre-serialized "
        f"JSON object string OR None; got {type(value).__name__}"
    )


@dataclass(frozen=True)
class SilverLabelResponse:
    """Parsed pattern-labeler subagent response per `.claude/agents/
    pattern-labeler.md` output contract (spec §5.9 step 2).

    The dispatch callable returns one of these (post-JSON-parse). The
    labeling glue maps it to a ``PatternExemplar`` insert.

    T-A.1.5b Codex R1 M#4 closure: ``structural_evidence_json`` accepts
    either a dict (subagent contract) OR a pre-serialized JSON object
    string (existing test fixtures) at construction time; ``__post_init__``
    coerces to canonical sorted-key JSON string for direct sqlite3 binding.
    """
    evaluation: str  # 'confirmed' | 'watch' | 'rejected' | 'relabel:<other_class>'
    confidence: Literal["high", "medium", "low"]
    structural_evidence_json: str  # serialized JSON dict; dict accepted + coerced
    geometric_evidence_narrative: str  # ASCII-only narrative

    def __post_init__(self) -> None:
        # Codex R3 M#1 closure: runtime-validate evaluation + confidence
        # (typed hints don't enforce at runtime; an invalid value would
        # surface later inside _map_silver_evaluation_to_decision as a
        # raw ValueError or persist as garbage inside labeler_evidence_json).
        _validate_silver_evaluation(self.evaluation)
        _validate_silver_confidence(self.confidence)

        coerced = _coerce_dict_to_canonical_json_str(
            "structural_evidence_json", self.structural_evidence_json,
        )
        if coerced is None:
            raise ValueError(
                "SilverLabelResponse.structural_evidence_json must not "
                "be None (the subagent contract requires evidence even "
                "for rejected outcomes per .claude/agents/"
                "pattern-labeler.md output contract)"
            )
        object.__setattr__(self, "structural_evidence_json", coerced)


@dataclass(frozen=True)
class CodexReviewResponse:
    """Parsed Codex 2nd-reviewer response.

    ``agreed=True`` ⇒ Codex confirms Claude's silver label; the parent row's
    ``codex_reviewed`` flips to 1 + ``codex_agreement`` to 1 + NO second row.

    ``agreed=False`` ⇒ Codex disagrees; the parent row's ``codex_reviewed``
    flips to 1 + ``codex_agreement`` to 0, AND a SECOND row is INSERTed
    with ``label_source='codex_silver'`` + ``parent_exemplar_id``
    pointing to the parent (per spec §5.9 step 4 + Codex R4 M#3 closure).

    T-A.1.5b Codex R1 M#4 closure: ``alternative_structural_evidence_json``
    and ``alternative_labeler_evidence_json`` accept dict OR pre-serialized
    JSON object string at construction time + coerce to canonical JSON
    string. Defense-in-depth for any future Codex-review CLI surface that
    parses a JSON file (mirrors the SilverLabelResponse pattern); current
    in-process Codex dispatch path is unaffected.
    """
    agreed: bool
    alternative_evaluation: str | None = None  # required when agreed=False
    alternative_confidence: str | None = None
    alternative_structural_evidence_json: str | None = None
    alternative_labeler_evidence_json: str | None = None

    def __post_init__(self) -> None:
        # T-A.1.8 Codex R1 Major #1 closure (defense-in-depth, mirrors
        # T-A.1.5b R3 M#1 family for Literal[...] runtime-validation):
        # `agreed: bool` type hint is NOT runtime-enforced; without this
        # check a caller passing `agreed='false'` (truthy non-empty
        # string) would record a disagreement as agreement + the
        # service-layer disagreement-chain INSERT would be skipped.
        if not isinstance(self.agreed, bool):
            raise ValueError(
                "CodexReviewResponse.agreed must be a bool; got "
                f"{type(self.agreed).__name__} value={self.agreed!r}"
            )
        for field_name in (
            "alternative_structural_evidence_json",
            "alternative_labeler_evidence_json",
        ):
            current = getattr(self, field_name)
            coerced = _coerce_dict_to_canonical_json_str(
                field_name, current,
            )
            if coerced != current:
                object.__setattr__(self, field_name, coerced)


def _default_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# fire_claude_silver_label
# ============================================================================


def fire_claude_silver_label(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    timeframe: Literal["daily", "weekly"],
    start_date: str,
    end_date: str,
    pattern_class: str,
    window_payload: dict[str, Any],
    rule_criteria: dict[str, Any],
    structural_evidence_schema: dict[str, Any],
    ai_labeler_version: str,
    dispatch_subagent: Callable[..., SilverLabelResponse] | None = None,
    now_fn: Callable[[], str] = _default_now_iso,
) -> int:
    """Dispatch the ``pattern-labeler`` subagent + persist silver label.

    Returns the new ``pattern_exemplars.id``. Caller owns NO outer
    transaction — this function opens its own ``with conn:`` block (per
    spec §5.9 step 3 + ``pattern_exemplars`` audit-trail discipline).

    ``dispatch_subagent`` is injectable for tests; the production default
    raises ``LabelingDispatchError`` (no in-process Agent tool exists
    callable from Python; the operator-paired session at T-A.1.7 wires
    the dispatch from within the Claude Code harness).

    Per Codex R4 M#1 closure: NO ``PHASE13_TEST_MOCK_SUBAGENT`` env-var
    backdoor; pytest injects via ``monkeypatch`` ONLY.
    """
    if pattern_class not in DETECTOR_PATTERN_CLASSES:
        raise ValueError(
            "pattern_class must be one of "
            f"{DETECTOR_PATTERN_CLASSES}, got {pattern_class!r}"
        )
    if dispatch_subagent is None:
        raise LabelingDispatchError(
            "fire_claude_silver_label requires a dispatch_subagent callable. "
            "The Python module cannot itself invoke the Claude Code Agent "
            "tool; the operator-paired session at T-A.1.7 wires the dispatch "
            "from within the Claude Code harness. Tests inject a mock "
            "dispatch via pytest monkeypatch (NOT via env var per Codex R4 "
            "M#1 closure)."
        )

    response = dispatch_subagent(
        window_payload=window_payload,
        pattern_class=pattern_class,
        rule_criteria=rule_criteria,
        structural_evidence_schema=structural_evidence_schema,
    )

    final_decision, final_pattern_class = _map_silver_evaluation_to_decision(
        response.evaluation, pattern_class,
    )

    # Compose the labeler_evidence_json from narrative + raw evaluation.
    labeler_evidence = {
        "evaluation": response.evaluation,
        "confidence": response.confidence,
        "geometric_evidence_narrative": response.geometric_evidence_narrative,
    }
    labeler_evidence_json = json.dumps(labeler_evidence, sort_keys=True)

    exemplar = PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        proposed_pattern_class=pattern_class,
        final_decision=final_decision,
        label_source="claude_silver",
        structural_evidence_json=response.structural_evidence_json,
        created_at=now_fn(),
        created_by="claude_dispatch",
        final_pattern_class=final_pattern_class,
        ai_labeler_version=ai_labeler_version,
        gold_validated_at=None,
        codex_reviewed=0,
        codex_agreement=None,
        geometric_score_json=None,  # rule-tier backfill lands at T2.SB3+
        labeler_evidence_json=labeler_evidence_json,
        quality_grade=None,
        notes=None,
        parent_exemplar_id=None,
    )

    with conn:
        return exemplars_repo.insert_exemplar(conn, exemplar)


def _map_silver_evaluation_to_decision(
    evaluation: str, proposed_pattern_class: str,
) -> tuple[str, str | None]:
    """Map subagent ``evaluation`` to (final_decision, final_pattern_class).

    - 'confirmed' / 'watch' / 'rejected'  -> direct mapping; final_pattern_class=NULL.
    - 'relabel:<other_class>'             -> ('relabeled', other_class).
    """
    if evaluation in ("confirmed", "watch", "rejected"):
        return (evaluation, None)
    if evaluation.startswith("relabel:"):
        other = evaluation.split(":", 1)[1]
        if other not in DETECTOR_PATTERN_CLASSES:
            raise ValueError(
                f"relabel target {other!r} must be one of "
                f"{DETECTOR_PATTERN_CLASSES}"
            )
        if other == proposed_pattern_class:
            raise ValueError(
                "relabel target must differ from proposed_pattern_class "
                f"(both = {other!r})"
            )
        return ("relabeled", other)
    raise ValueError(
        f"unknown evaluation {evaluation!r}; expected one of "
        "'confirmed' / 'watch' / 'rejected' / 'relabel:<other_class>'"
    )


# ============================================================================
# fire_codex_review_for_silver_row
# ============================================================================


def should_fire_codex(
    *,
    phase: SelectivePhase,
    silver_confidence: str | None = None,
    geometric_score: float | None = None,
    rng: random.Random | None = None,
) -> bool:
    """Per spec §5.9 step 4 + §A.6 phased policy.

    T2.SB1 phase: random 15% sampling ONLY (geometric_score is unavailable
    pre-detector-build at T2.SB3+/SB4).

    T2.SB3+/SB4 phase: random 15% sampling PLUS high-stakes clauses:
      - silver_confidence == 'high' AND geometric_score < 0.5 (disagreement A);
      - silver_confidence == 'low'  AND geometric_score >= 0.8 (disagreement B).
    """
    rng = rng if rng is not None else random.Random()
    random_fire = rng.random() < CODEX_RANDOM_SAMPLE_PROBABILITY
    if phase == "t2_sb1":
        return random_fire
    if phase == "t2_sb3_or_later":
        if random_fire:
            return True
        if geometric_score is None or silver_confidence is None:
            return False
        high_stakes_a = silver_confidence == "high" and geometric_score < 0.5
        high_stakes_b = silver_confidence == "low" and geometric_score >= 0.8
        return high_stakes_a or high_stakes_b
    raise ValueError(
        f"phase must be 't2_sb1' or 't2_sb3_or_later', got {phase!r}"
    )


def fire_codex_review_for_silver_row(
    conn: sqlite3.Connection,
    *,
    exemplar_id: int,
    phase: SelectivePhase,
    silver_confidence: str | None = None,
    geometric_score: float | None = None,
    ai_labeler_version: str,
    codex_dispatch: Callable[..., CodexReviewResponse] | None = None,
    rng: random.Random | None = None,
    now_fn: Callable[[], str] = _default_now_iso,
) -> int | None:
    """Maybe fire Codex 2nd review on the silver row identified by exemplar_id.

    Returns the inserted codex_silver row's id IF Codex disagreed and a
    new chain row was inserted; returns ``None`` if Codex did NOT fire
    (per selective policy) OR if Codex fired and agreed (parent row
    UPDATEd in place; no new row).

    Per spec §5.9 step 4 + Codex R4 M#3 + R5 M#2 closure: disagreement
    INSERTs a SECOND row with ``label_source='codex_silver'`` +
    ``parent_exemplar_id`` pointing to the parent.
    """
    if not should_fire_codex(
        phase=phase,
        silver_confidence=silver_confidence,
        geometric_score=geometric_score,
        rng=rng,
    ):
        return None

    if codex_dispatch is None:
        raise LabelingDispatchError(
            "fire_codex_review_for_silver_row requires a codex_dispatch "
            "callable. Tests inject via pytest monkeypatch ONLY (NOT via "
            "env var per Codex R4 M#1 closure)."
        )

    parent = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
    if parent is None:
        raise ValueError(
            f"exemplar_id {exemplar_id} not found in pattern_exemplars"
        )
    if parent.label_source != "claude_silver":
        raise ValueError(
            "Codex 2nd review fires ONLY on claude_silver rows; got "
            f"label_source={parent.label_source!r}"
        )

    response = codex_dispatch(parent=parent)
    agreement = 1 if response.agreed else 0

    with conn:
        # Flip parent's codex_reviewed + codex_agreement (UPDATE-in-place;
        # NO INSERT OR REPLACE per plan §A.15 LOCK; parent row's audit
        # identity is preserved).
        conn.execute(
            "UPDATE pattern_exemplars SET codex_reviewed = 1, "
            "codex_agreement = ? WHERE id = ?",
            (agreement, exemplar_id),
        )

        if response.agreed:
            return None

        # Disagreement: INSERT new codex_silver row pointing back to parent.
        if response.alternative_evaluation is None:
            raise ValueError(
                "CodexReviewResponse.agreed=False requires "
                "alternative_evaluation to be non-None"
            )
        if response.alternative_structural_evidence_json is None:
            raise ValueError(
                "CodexReviewResponse.agreed=False requires "
                "alternative_structural_evidence_json to be non-None"
            )

        final_decision, final_pattern_class = (
            _map_silver_evaluation_to_decision(
                response.alternative_evaluation, parent.proposed_pattern_class,
            )
        )

        codex_labeler_evidence = {
            "evaluation": response.alternative_evaluation,
            "confidence": response.alternative_confidence,
            "parent_exemplar_id": exemplar_id,
            "disagreed_with": "claude_silver",
        }
        if response.alternative_labeler_evidence_json is not None:
            codex_labeler_evidence["original_labeler_evidence_json"] = (
                response.alternative_labeler_evidence_json
            )

        codex_exemplar = PatternExemplar(
            id=None,
            ticker=parent.ticker,
            timeframe=parent.timeframe,
            start_date=parent.start_date,
            end_date=parent.end_date,
            proposed_pattern_class=parent.proposed_pattern_class,
            final_decision=final_decision,
            label_source="codex_silver",
            structural_evidence_json=(
                response.alternative_structural_evidence_json
            ),
            created_at=now_fn(),
            created_by="codex_dispatch",
            final_pattern_class=final_pattern_class,
            ai_labeler_version=ai_labeler_version,
            gold_validated_at=None,
            codex_reviewed=0,
            codex_agreement=None,
            geometric_score_json=None,
            labeler_evidence_json=json.dumps(
                codex_labeler_evidence, sort_keys=True,
            ),
            quality_grade=None,
            notes=None,
            parent_exemplar_id=exemplar_id,
        )
        return exemplars_repo.insert_exemplar(conn, codex_exemplar)


__all__ = [
    "CODEX_RANDOM_SAMPLE_PROBABILITY",
    "CodexReviewResponse",
    "LabelingDispatchError",
    "SilverLabelResponse",
    "fire_claude_silver_label",
    "fire_codex_review_for_silver_row",
    "should_fire_codex",
]
