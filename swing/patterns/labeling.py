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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
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

# T-T4.SB.4 Sub-task 4A: explicit allowlist for rule_criteria element
# status field (per CLAUDE.md gotcha "Literal[...] type hints are NOT
# runtime-enforced"; validated in SilverLabelResponse.__post_init__).
_VALID_RULE_CRITERIA_STATUSES: frozenset[str] = frozenset(("pass", "fail"))


def _validate_rule_criteria(value: object) -> None:
    """T-T4.SB.4 Sub-task 4A: runtime-validate the rule_criteria payload.

    Contract per plan section B.4 + Codex R3 M#2 LOCK:
      - None is valid (back-compat default; existing fixtures unchanged).
      - Empty list is valid (degenerate: zero criteria evaluated).
      - Each non-empty element MUST be a dict with:
        - ``name``: non-empty string.
        - ``status``: one of ``{"pass", "fail"}``.
      - Optional ``evidence_value`` / ``threshold`` / ``tolerance`` keys
        are NOT type-validated in V1 (deviation banked in return report;
        VM parser at swing/web/view_models/patterns/exemplars.py coerces
        defensively at the read path).
    """
    if value is None:
        return
    if not isinstance(value, list):
        raise ValueError(
            "SilverLabelResponse.rule_criteria must be a list of dicts "
            f"when provided; got {type(value).__name__}"
        )
    for i, elem in enumerate(value):
        if not isinstance(elem, dict):
            raise ValueError(
                f"SilverLabelResponse.rule_criteria[{i}] must be a dict; "
                f"got {type(elem).__name__}"
            )
        name = elem.get("name")
        if not (isinstance(name, str) and name):
            raise ValueError(
                f"SilverLabelResponse.rule_criteria[{i}].name must be a "
                f"non-empty string; got {name!r}"
            )
        status = elem.get("status")
        if status not in _VALID_RULE_CRITERIA_STATUSES:
            raise ValueError(
                f"SilverLabelResponse.rule_criteria[{i}].status must be "
                f"one of {sorted(_VALID_RULE_CRITERIA_STATUSES)}; got "
                f"{status!r}"
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
    # T-T4.SB.4 Sub-task 4A (additive; back-compat default=None): optional
    # per-criterion PASS/FAIL payload per plan section B.4 + Codex R3 M#2
    # LOCK. When present, persisted to envelope by fire_claude_silver_label;
    # consumed by swing/web/view_models/patterns/exemplars.py:_parse_criterion_rows.
    rule_criteria: list[dict] | None = None

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
        # T-T4.SB.4 Sub-task 4A: validate rule_criteria shape.
        _validate_rule_criteria(self.rule_criteria)


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


# ============================================================================
# retroactive_codex_evaluation_against_corpus (T-A.3.7)
# ============================================================================
#
# Per spec section 5.9 step 4 lines 749-751 (binding contract):
#
#   "At T2.SB3+/SB4 (rule detectors shipped at T2.SB3 + T2.SB4): random 15%
#    sample CONTINUES PLUS the high-stakes individual labels - Claude silver
#    confidence == 'high' AND rule-tier `geometric_score < 0.5` (rule/silver
#    disagreement A direction); OR Claude silver confidence == 'low' AND
#    rule-tier `geometric_score >= 0.8` (rule/silver disagreement B
#    direction). The full SELECTIVE policy ACTIVATES retroactively against
#    the T2.SB1 corpus when T2.SB3+/SB4 evaluators have access to recompute
#    `geometric_score` against the existing exemplars."
#
# V1 architectural disposition (per implementer recon at T-A.3.7):
#   - The T-A.1.7 corpus dump at
#     ``data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl`` carries
#     ``structural_evidence_json.geometric_score`` for every Claude silver
#     row (Claude labeler emits the score per the 8-criteria pass table per
#     pattern class). The corpus does NOT carry OHLCV bars, so a V1
#     in-process detector re-invocation would require a yfinance fetch per
#     row (network-bound; non-deterministic test surface).
#   - V1 helper therefore reads geometric_score from each row's
#     ``structural_evidence_json`` as the default rule-tier score input to
#     the high-stakes predicate. An optional ``geometric_score_recompute``
#     callable is exposed for the operator-paired session at T-A.3.7+ to
#     wire actual detector invocation when bars are fetched (yfinance via
#     ``swing.patterns.labeling_bars.autofetch_bars_for_labeling`` + the 5
#     V1 detectors at ``swing/patterns/{vcp,flat_base,cup_with_handle,
#     high_tight_flag,double_bottom_w}.py`` - HTF + DBW added at T2.SB4
#     T-A.4.1 + T-A.4.2; high-stakes clause activation extended to all 5
#     classes at T2.SB4 T-A.4.5 per spec section 5.9 step 4 lines 745-751
#     + OQ-5 BINDING); when supplied, the callable's return value
#     OVERRIDES the corpus score for the predicate evaluation. The
#     function itself is CLASS-AGNOSTIC - it reads geometric_score from
#     structural_evidence_json regardless of proposed_pattern_class, so
#     T2.SB4 HTF + DBW corpus rows are processed identically to the 3
#     T2.SB3 classes (see tests/patterns/test_retroactive_codex_
#     evaluation.py::test_retroactive_codex_evaluation_invokes_all_5_
#     detector_classes for the locked discriminating coverage).
#
# LOCKs (per dispatch brief section 6 + plan G.4):
#   - L2: function does NOT write directly. Per-row firing delegates to
#     ``fire_codex_review_for_silver_row`` (existing labeling.py write
#     path); transaction discipline is owned there.
#   - L7: ``RetroactiveCodexSelection`` is a frozen dataclass with
#     ``__post_init__`` runtime validation against an explicit allowed-
#     value frozenset (CLAUDE.md gotcha "Literal[...] type hints are NOT
#     runtime-enforced").
#   - CLAUDE.md gotcha "SELECT-first idempotency MUST precede payload
#     validation" (Phase 12 C.C R1 Major #2): each candidate's
#     ``codex_reviewed`` flag is read BEFORE the random-sample roll OR
#     high-stakes predicate evaluation - if already reviewed, the row is
#     reported as ``already_reviewed`` + skipped.
#
# ASCII-only (Windows cp1252 stdout safety; CLAUDE.md gotcha).


_RETROACTIVE_SELECTION_REASONS: frozenset[str] = frozenset(
    (
        "random_sample",
        "high_stakes_a",
        "high_stakes_b",
        "not_selected",
        "already_reviewed",
        "missing_score",
    )
)


@dataclass(frozen=True)
class RetroactiveCodexSelection:
    """Per-row diagnostic record from
    ``retroactive_codex_evaluation_against_corpus``.

    Returned for EVERY claude_silver row scanned (not just fired rows) so
    the caller (operator-paired session OR future automation) can log the
    full triage table + cross-reference against the corpus dump.

    Fields:
      - ``exemplar_id``: ``pattern_exemplars.id`` for the candidate.
      - ``ticker``: candidate ticker (for log readability).
      - ``confidence``: Claude silver confidence ('high' / 'medium' /
        'low'); None when the labeler_evidence_json was malformed +
        the row was skipped.
      - ``geometric_score``: the score used for predicate evaluation
        (either the recomputed value when ``geometric_score_recompute``
        was supplied, OR the corpus structural_evidence_json value);
        None when the corpus row carried no embedded score AND no
        recompute callable was supplied.
      - ``fired``: True if Codex dispatch was invoked for this row.
      - ``reason``: one of the values in
        ``_RETROACTIVE_SELECTION_REASONS``; ``__post_init__``-validated.
      - ``codex_row_id``: when ``fired`` AND Codex DISAGREED, the new
        codex_silver row's id; None otherwise (including agreement case).
    """
    exemplar_id: int
    ticker: str
    confidence: str | None
    geometric_score: float | None
    fired: bool
    reason: str
    codex_row_id: int | None = None

    def __post_init__(self) -> None:
        if self.reason not in _RETROACTIVE_SELECTION_REASONS:
            raise ValueError(
                "RetroactiveCodexSelection.reason must be one of "
                f"{sorted(_RETROACTIVE_SELECTION_REASONS)}; got "
                f"{self.reason!r}"
            )


def _extract_corpus_row_fields(
    row: dict[str, Any] | PatternExemplar,
) -> tuple[int, str, str | None, float | None, str | None, int]:
    """Pull the fields needed for retroactive evaluation out of a row.

    Returns (exemplar_id, ticker, confidence, geometric_score,
    label_source, codex_reviewed). ``label_source`` is returned so the
    caller can filter claude_silver-only without re-reading.
    """
    if isinstance(row, PatternExemplar):
        labeler = row.labeler_evidence_json
        structural = row.structural_evidence_json
        exemplar_id = row.id
        ticker = row.ticker
        label_source = row.label_source
        codex_reviewed = row.codex_reviewed
    else:
        labeler = row.get("labeler_evidence_json")
        structural = row.get("structural_evidence_json")
        exemplar_id = row["id"]
        ticker = row["ticker"]
        label_source = row.get("label_source")
        codex_reviewed = int(row.get("codex_reviewed", 0))

    confidence: str | None = None
    if labeler:
        try:
            decoded = json.loads(labeler) if isinstance(labeler, str) else labeler
            if isinstance(decoded, dict):
                conf_value = decoded.get("confidence")
                if isinstance(conf_value, str):
                    confidence = conf_value
        except json.JSONDecodeError:
            confidence = None

    geometric_score: float | None = None
    if structural:
        try:
            decoded_s = (
                json.loads(structural) if isinstance(structural, str)
                else structural
            )
            if isinstance(decoded_s, dict):
                score_value = decoded_s.get("geometric_score")
                if isinstance(score_value, (int, float)):
                    geometric_score = float(score_value)
        except json.JSONDecodeError:
            geometric_score = None

    if exemplar_id is None:
        raise ValueError(
            "retroactive_codex_evaluation: row carries id=None; corpus "
            "rows MUST have a stable integer id"
        )

    return (
        int(exemplar_id),
        str(ticker),
        confidence,
        geometric_score,
        label_source if isinstance(label_source, str) else None,
        int(codex_reviewed),
    )


def _iter_corpus_rows(
    conn: sqlite3.Connection,
    corpus_path: Path | None,
) -> Iterable[dict[str, Any] | PatternExemplar]:
    """Source claude_silver rows from corpus JSONL dump OR DB.

    When ``corpus_path`` is supplied + exists, parse JSONL line-by-line
    + yield each row dict. Otherwise yield PatternExemplar rows from the
    DB filtered to ``label_source='claude_silver'`` (deterministic id
    order via list_exemplars' ORDER BY id ASC).
    """
    if corpus_path is not None:
        with corpus_path.open("r", encoding="utf-8") as fh:
            for line_no, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"retroactive_codex_evaluation: corpus_path "
                        f"{corpus_path} line {line_no} is not valid JSON: "
                        f"{exc}"
                    ) from exc
        return

    # DB-sourced path: claude_silver rows only.
    yield from exemplars_repo.list_exemplars(
        conn, label_source="claude_silver",
    )


def _classify_retroactive_selection(
    *,
    phase: SelectivePhase,
    confidence: str | None,
    geometric_score: float | None,
    rng: random.Random,
) -> str:
    """Per spec section 5.9 step 4: emit the selection reason for one
    claude_silver row given its (confidence, geometric_score).

    Returns one of: 'random_sample' / 'high_stakes_a' / 'high_stakes_b'
    / 'not_selected' / 'missing_score'.

    Random roll is consumed UNCONDITIONALLY per row (consistent with
    ``should_fire_codex`` semantics) so deterministic tests can pin the
    rng sequence to exact row positions. High-stakes clauses are checked
    only AFTER the random clause to give 'random_sample' precedence in
    reason reporting when both would fire.
    """
    random_fires = rng.random() < CODEX_RANDOM_SAMPLE_PROBABILITY
    if phase == "t2_sb1":
        return "random_sample" if random_fires else "not_selected"
    if phase != "t2_sb3_or_later":
        raise ValueError(
            f"phase must be 't2_sb1' or 't2_sb3_or_later', got {phase!r}"
        )

    if random_fires:
        return "random_sample"

    if geometric_score is None or confidence is None:
        return "missing_score" if geometric_score is None else "not_selected"

    if confidence == "high" and geometric_score < 0.5:
        return "high_stakes_a"
    if confidence == "low" and geometric_score >= 0.8:
        return "high_stakes_b"
    return "not_selected"


def retroactive_codex_evaluation_against_corpus(
    conn: sqlite3.Connection,
    *,
    phase: SelectivePhase = "t2_sb3_or_later",
    ai_labeler_version: str,
    codex_dispatch: Callable[..., CodexReviewResponse],
    rng: random.Random | None = None,
    corpus_path: Path | None = None,
    geometric_score_recompute: (
        Callable[[PatternExemplar | dict[str, Any]], float] | None
    ) = None,
    now_fn: Callable[[], str] = _default_now_iso,
) -> list[RetroactiveCodexSelection]:
    """Apply spec section 5.9 step 4 retroactively to existing
    claude_silver exemplars.

    For each claude_silver candidate:
      1. SELECT-first idempotency check: if ``codex_reviewed = 1``
         already, emit ``already_reviewed`` + skip (no Codex fire, no DB
         write).
      2. Extract ``confidence`` (from labeler_evidence_json) + the
         rule-tier ``geometric_score`` (either via
         ``geometric_score_recompute(exemplar)`` when supplied OR from
         the corpus row's ``structural_evidence_json.geometric_score``
         as the V1 fallback).
      3. Apply the phased selection predicate per
         ``_classify_retroactive_selection``: random 15% sample OR
         high-stakes A (high confidence + low score) OR high-stakes B
         (low confidence + high score).
      4. When selected, call ``fire_codex_review_for_silver_row`` against
         the corresponding DB row (the corpus dump is the SOURCE of
         exemplar_id; the DB row's transactional update lives in the
         existing labeling.py write path).

    Parameters
    ----------
    conn : sqlite3.Connection
        DB connection; used for SELECT-first idempotency reads via
        ``exemplars_repo.get_exemplar_by_id`` + transactional writes via
        ``fire_codex_review_for_silver_row``. Caller MUST NOT hold an
        open transaction (per Phase 8 transactional discipline lesson
        family).
    phase : SelectivePhase
        ``'t2_sb1'`` (random only) OR ``'t2_sb3_or_later'`` (random +
        high-stakes clauses). Default is the T2.SB3+ phase since this
        helper EXISTS for the retroactive activation at T2.SB3+.
    ai_labeler_version : str
        Stamped on any inserted codex_silver disagreement-chain row.
    codex_dispatch : Callable
        Codex MCP dispatch callable; required (no production default).
    rng : random.Random | None
        Source for the random 15% roll. None -> ``random.SystemRandom()``.
    corpus_path : Path | None
        If supplied, source claude_silver rows from this JSONL dump
        (each line a row dict matching ``pattern_exemplars``' field
        set, e.g. the shape at
        ``data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl``).
        When None, source rows directly from the DB (via
        ``list_exemplars(label_source='claude_silver')``).
    geometric_score_recompute : Callable | None
        Optional per-row recomputer; when supplied, its return value
        OVERRIDES the corpus row's embedded geometric_score for the
        predicate evaluation. The callable receives the corpus row
        (PatternExemplar OR dict; whichever shape the iterator
        produced) and must return a float in [0, 1] (V1 unenforced).
    now_fn : Callable
        Injectable now() for deterministic created_at stamping in the
        disagreement-chain write path.

    Returns
    -------
    list[RetroactiveCodexSelection]
        One row per claude_silver candidate scanned; reason field
        distinguishes fired (random_sample / high_stakes_a /
        high_stakes_b) from skipped (not_selected / already_reviewed
        / missing_score). When ``fired`` AND Codex DISAGREED,
        ``codex_row_id`` carries the new codex_silver row's id.

    Raises
    ------
    ValueError
        On invalid phase, malformed corpus row (missing id), unparseable
        corpus JSONL line.
    LabelingDispatchError
        If ``codex_dispatch`` raises an upstream LabelingDispatchError
        (e.g., misconfigured Codex MCP).
    """
    rng_actual = rng if rng is not None else random.SystemRandom()

    selections: list[RetroactiveCodexSelection] = []

    for raw_row in _iter_corpus_rows(conn, corpus_path):
        (
            exemplar_id,
            ticker,
            confidence,
            corpus_score,
            label_source,
            codex_reviewed_corpus,
        ) = _extract_corpus_row_fields(raw_row)

        # When corpus_path is supplied, the corpus row may carry any
        # label_source - filter to claude_silver only here.
        if label_source is not None and label_source != "claude_silver":
            continue

        # SELECT-first idempotency: ALWAYS consult the DB for the
        # canonical codex_reviewed flag (the corpus JSONL is a
        # point-in-time snapshot - the DB may have been updated since).
        # If the row doesn't exist in the DB at all (corpus_path mode
        # against an empty DB OR a row-id mismatch), the corpus flag
        # is the fallback.
        db_row = exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
        if db_row is not None:
            already_reviewed = bool(db_row.codex_reviewed)
        else:
            already_reviewed = bool(codex_reviewed_corpus)

        if already_reviewed:
            selections.append(
                RetroactiveCodexSelection(
                    exemplar_id=exemplar_id,
                    ticker=ticker,
                    confidence=confidence,
                    geometric_score=corpus_score,
                    fired=False,
                    reason="already_reviewed",
                )
            )
            continue

        # Resolve the geometric_score for predicate evaluation. The
        # recompute callable wins when supplied; otherwise use the
        # corpus row's embedded score.
        if geometric_score_recompute is not None:
            try:
                score = float(geometric_score_recompute(raw_row))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "geometric_score_recompute must return a float-coercible "
                    f"value; got error: {exc}"
                ) from exc
            # Codex R1 Minor #2: enforce the documented [0.0, 1.0] +
            # finite contract at the callsite. Without enforcement NaN
            # or out-of-range recompute values could silently affect
            # high-stakes selection.
            import math as _math
            if not _math.isfinite(score) or not (0.0 <= score <= 1.0):
                raise ValueError(
                    f"geometric_score_recompute returned {score!r}; "
                    f"must be finite and in [0.0, 1.0]"
                )
        else:
            score = corpus_score

        reason = _classify_retroactive_selection(
            phase=phase,
            confidence=confidence,
            geometric_score=score,
            rng=rng_actual,
        )

        if reason in ("not_selected", "missing_score"):
            selections.append(
                RetroactiveCodexSelection(
                    exemplar_id=exemplar_id,
                    ticker=ticker,
                    confidence=confidence,
                    geometric_score=score,
                    fired=False,
                    reason=reason,
                )
            )
            continue

        # Fire Codex via the existing labeling.py write path.
        # IMPORTANT: ``fire_codex_review_for_silver_row`` consumes its
        # own rng for the random roll - to prevent double-counting we
        # pass a Random subclass that always returns 0.0 (forcing fire)
        # since the retroactive helper has already decided to fire by
        # this point.
        forced_rng = _AlwaysFireRng()
        codex_row_id = fire_codex_review_for_silver_row(
            conn,
            exemplar_id=exemplar_id,
            phase="t2_sb1",  # neutralize high-stakes re-eval in callee
            silver_confidence=None,
            geometric_score=None,
            ai_labeler_version=ai_labeler_version,
            codex_dispatch=codex_dispatch,
            rng=forced_rng,
            now_fn=now_fn,
        )

        selections.append(
            RetroactiveCodexSelection(
                exemplar_id=exemplar_id,
                ticker=ticker,
                confidence=confidence,
                geometric_score=score,
                fired=True,
                reason=reason,
                codex_row_id=codex_row_id,
            )
        )

    return selections


class _AlwaysFireRng(random.Random):
    """Internal RNG subclass that always returns 0.0 from ``random()`` so
    ``should_fire_codex`` evaluates ``0.0 < 0.15`` -> True unconditionally.

    Used by ``retroactive_codex_evaluation_against_corpus`` to force
    ``fire_codex_review_for_silver_row`` to fire when the retroactive
    helper has already made the selection decision.
    """

    def random(self) -> float:  # type: ignore[override]
        return 0.0


__all__ = [
    "CODEX_RANDOM_SAMPLE_PROBABILITY",
    "CodexReviewResponse",
    "LabelingDispatchError",
    "RetroactiveCodexSelection",
    "SilverLabelResponse",
    "fire_claude_silver_label",
    "fire_codex_review_for_silver_row",
    "retroactive_codex_evaluation_against_corpus",
    "should_fire_codex",
]
