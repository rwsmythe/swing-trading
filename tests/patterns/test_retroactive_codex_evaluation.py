"""Phase 13 T2.SB3 T-A.3.7 - selective Codex retroactive evaluation tests.

Per spec section 5.9 step 4 (lines 749-751) + dispatch brief section 4.4
watch items 19-20: at T2.SB3+/SB4 the random 15% sampling CONTINUES PLUS
high-stakes individual labels activate (Claude silver confidence='high'
AND geometric_score < 0.5; OR confidence='low' AND geometric_score >=
0.8). The full SELECTIVE policy ACTIVATES retroactively against the
T2.SB1 corpus when T2.SB3+/SB4 evaluators have access to recompute
geometric_score against the existing exemplars.

These tests pin the BEHAVIOR of
``retroactive_codex_evaluation_against_corpus`` against the T-A.1.7
corpus (data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl) via:
  - deterministic seed -> reproducible random-sample subset selection;
  - injectable geometric_score recompute -> tests can plant in-band /
    out-of-band scores without OHLCV bar fetches;
  - mock codex_dispatch -> no real Codex MCP fires;
  - SELECT-first idempotency check -> second invocation skips already-
    reviewed parent rows (codex_reviewed = 1).

LOCKs honored (per dispatch brief section 6 + plan G.4 + spec section 5.9):
  - L2: helper does NOT write directly; it delegates to
    ``fire_codex_review_for_silver_row`` (existing labeling.py write path).
  - L7: ``RetroactiveCodexSelection`` is a frozen dataclass (constructed
    by the helper for diagnostic / return-value purposes).
  - CLAUDE.md gotcha "SELECT-first idempotency MUST precede payload
    validation" - the helper SELECTs each candidate's codex_reviewed
    flag BEFORE any per-row payload work.

ASCII-only (Windows cp1252 stdout safety).
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
    CodexReviewResponse,
    retroactive_codex_evaluation_against_corpus,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb3_retroactive.db"
    return ensure_schema(db_path)


def _plant_claude_silver_row(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    pattern_class: str = "vcp",
    confidence: str = "medium",
    geometric_score: float = 0.5,
    evaluation: str = "watch",
    final_decision: str = "watch",
    final_pattern_class: str | None = None,
) -> int:
    """Insert a claude_silver pattern_exemplars row with embedded
    geometric_score + confidence for retroactive-evaluation tests.

    Avoids fire_claude_silver_label's dispatch dependency; rows go in
    via the repo directly so the test controls every field.
    """
    from swing.data.models import PatternExemplar

    structural_evidence = {
        "geometric_score": geometric_score,
        "base_top_price": 100.0,
        "criteria_pass": {},
    }
    labeler_evidence = {
        "evaluation": evaluation,
        "confidence": confidence,
        "geometric_evidence_narrative": "test fixture narrative ascii only",
    }
    exemplar = PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class=pattern_class,
        final_decision=final_decision,
        label_source="claude_silver",
        structural_evidence_json=json.dumps(
            structural_evidence, sort_keys=True
        ),
        created_at="2026-05-20T00:00:00+00:00",
        created_by="claude_dispatch",
        final_pattern_class=final_pattern_class,
        ai_labeler_version="claude-code-pattern-labeler-v1",
        gold_validated_at=None,
        codex_reviewed=0,
        codex_agreement=None,
        geometric_score_json=None,
        labeler_evidence_json=json.dumps(labeler_evidence, sort_keys=True),
        quality_grade=None,
        notes=None,
        parent_exemplar_id=None,
    )
    with conn:
        return exemplars_repo.insert_exemplar(conn, exemplar)


class _SeededRng(random.Random):
    """Random with explicit value sequence (mirrors test_labeling.py)."""

    def __init__(self, values: list[float]) -> None:
        super().__init__()
        self._values = list(values)
        self._index = 0

    def random(self) -> float:  # type: ignore[override]
        value = self._values[self._index]
        self._index = (self._index + 1) % len(self._values)
        return value


# ============================================================================
# Test 1: random 15% CONTINUES + high-stakes clause activated at T2.SB3+.
# ============================================================================


def test_retroactive_random_15pct_continues_and_high_stakes_activates(
    conn: sqlite3.Connection,
) -> None:
    """Per spec section 5.9 step 4 lines 749-751: at T2.SB3+/SB4 the
    random 15% sampling CONTINUES PLUS high-stakes clauses activate.

    Plants 4 claude_silver rows covering:
      (1) high confidence + geometric_score = 0.30 -> high-stakes A fires;
      (2) low confidence + geometric_score = 0.85 -> high-stakes B fires;
      (3) medium confidence + geometric_score = 0.55 -> neither high-stakes
          nor random (rng above threshold) -> SKIP;
      (4) high confidence + geometric_score = 0.95 -> neither high-stakes A
          (score not < 0.5) nor B (confidence is 'high' not 'low');
          random rolls BELOW threshold -> RANDOM sample fires.
    """
    id_high_stakes_a = _plant_claude_silver_row(
        conn, ticker="AAA",
        confidence="high", geometric_score=0.30,
    )
    id_high_stakes_b = _plant_claude_silver_row(
        conn, ticker="BBB",
        confidence="low", geometric_score=0.85,
    )
    id_skip = _plant_claude_silver_row(
        conn, ticker="CCC",
        confidence="medium", geometric_score=0.55,
    )
    id_random = _plant_claude_silver_row(
        conn, ticker="DDD",
        confidence="high", geometric_score=0.95,
    )

    # Track which rows codex_dispatch fired for.
    dispatched_ids: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        dispatched_ids.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    # Deterministic random sequence: high (0.99) for AAA, BBB, CCC -> they
    # only fire via high-stakes clause. For DDD, low (0.01) -> random fire.
    # Row iteration order is by id ASC per list_exemplars.
    rng = _SeededRng([0.99, 0.99, 0.99, 0.01])

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="gpt-5-codex-dispatch-retroactive",
        codex_dispatch=codex_dispatch,
        rng=rng,
    )

    # AAA, BBB, DDD fire; CCC skips.
    fired_ids = sorted(
        sel.exemplar_id for sel in selections if sel.fired
    )
    assert fired_ids == sorted(
        [id_high_stakes_a, id_high_stakes_b, id_random]
    )
    assert id_skip not in fired_ids

    # codex_dispatch invoked exactly 3 times.
    assert sorted(dispatched_ids) == sorted(
        [id_high_stakes_a, id_high_stakes_b, id_random]
    )

    # Verify selection reasons reflect high-stakes vs random fairly.
    by_id = {sel.exemplar_id: sel for sel in selections}
    assert by_id[id_high_stakes_a].reason == "high_stakes_a"
    assert by_id[id_high_stakes_b].reason == "high_stakes_b"
    assert by_id[id_random].reason == "random_sample"
    assert by_id[id_skip].fired is False
    assert by_id[id_skip].reason == "not_selected"

    # Parent rows that fired now carry codex_reviewed=1 + codex_agreement=1.
    for fired_id in fired_ids:
        row = exemplars_repo.get_exemplar_by_id(conn, fired_id)
        assert row is not None
        assert row.codex_reviewed == 1
        assert row.codex_agreement == 1


# ============================================================================
# Test 2: SELECT-first idempotency - second invocation skips reviewed rows.
# ============================================================================


def test_retroactive_select_first_idempotency(
    conn: sqlite3.Connection,
) -> None:
    """Per cumulative CLAUDE.md gotcha 'SELECT-first idempotency MUST
    precede payload validation' (Phase 12 C.C R1 Major #2) + dispatch
    brief watch item 20: re-invoking the helper against rows already
    reviewed (codex_reviewed = 1) MUST skip them - NOT double-fire.
    """
    parent_id = _plant_claude_silver_row(
        conn, ticker="IDP",
        confidence="high", geometric_score=0.30,  # high-stakes A
    )

    first_calls: list[int] = []

    def codex_dispatch_first(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        first_calls.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    rng1 = _SeededRng([0.99])  # high - random does NOT fire; only high-stakes.
    first = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch_first,
        rng=rng1,
    )
    fired_first = [sel for sel in first if sel.fired]
    assert len(fired_first) == 1
    assert fired_first[0].exemplar_id == parent_id
    assert fired_first[0].reason == "high_stakes_a"
    assert first_calls == [parent_id]

    row = exemplars_repo.get_exemplar_by_id(conn, parent_id)
    assert row is not None
    assert row.codex_reviewed == 1

    # Second invocation: same rng + same dispatch + same predicate, but
    # SELECT-first idempotency MUST exclude the now-reviewed row.
    second_calls: list[int] = []

    def codex_dispatch_second(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        second_calls.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    rng2 = _SeededRng([0.99])
    second = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch_second,
        rng=rng2,
    )
    fired_second = [sel for sel in second if sel.fired]
    assert fired_second == []
    assert second_calls == []  # codex_dispatch NOT invoked on second pass.

    # The diagnostics row for parent_id should reflect already_reviewed.
    by_id = {sel.exemplar_id: sel for sel in second}
    assert by_id[parent_id].fired is False
    assert by_id[parent_id].reason == "already_reviewed"


# ============================================================================
# Test 3: helper only operates on claude_silver rows; gold + codex skipped.
# ============================================================================


def test_retroactive_only_claude_silver_rows_considered(
    conn: sqlite3.Connection,
) -> None:
    """The retroactive evaluation pass MUST scope to label_source=
    'claude_silver' only. curated_gold + codex_silver rows are NOT
    candidates for retroactive Codex review (gold rows are operator-
    promoted; codex_silver rows are themselves Codex's disagreement
    output - reviewing them would create infinite-recursion chains
    forbidden by spec).
    """
    from swing.data.models import PatternExemplar

    # Plant 1 gold row + 1 claude_silver row.
    silver_id = _plant_claude_silver_row(
        conn, ticker="SLV",
        confidence="high", geometric_score=0.30,  # high-stakes A
    )

    gold = PatternExemplar(
        id=None,
        ticker="GLD",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class="vcp",
        final_decision="confirmed",
        label_source="curated_gold",
        structural_evidence_json=json.dumps(
            {"geometric_score": 0.30, "criteria_pass": {}}, sort_keys=True,
        ),
        created_at="2026-05-20T00:00:00+00:00",
        created_by="operator",
        final_pattern_class=None,
        ai_labeler_version=None,
        gold_validated_at="2026-05-20T00:00:00+00:00",
        codex_reviewed=0,
        codex_agreement=None,
        geometric_score_json=None,
        labeler_evidence_json=json.dumps(
            {"evaluation": "confirmed", "confidence": "high",
             "geometric_evidence_narrative": "operator gold"},
            sort_keys=True,
        ),
        quality_grade=5,
        notes=None,
        parent_exemplar_id=None,
    )
    with conn:
        gold_id = exemplars_repo.insert_exemplar(conn, gold)

    fired: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        fired.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch,
        rng=_SeededRng([0.99]),
    )

    # Silver row fired (high-stakes A); gold row NOT in selections at all.
    fired_selections = [sel for sel in selections if sel.fired]
    assert [sel.exemplar_id for sel in fired_selections] == [silver_id]
    assert fired == [silver_id]
    assert all(sel.exemplar_id != gold_id for sel in selections)


# ============================================================================
# Test 4: geometric_score_recompute callable overrides corpus score.
# ============================================================================


def test_retroactive_geometric_score_recompute_overrides_corpus(
    conn: sqlite3.Connection,
) -> None:
    """The helper accepts an optional ``geometric_score_recompute``
    callable that returns the rule-tier geometric_score per row (when the
    operator has wired bar-fetch + detector invocation). When provided,
    the recompute result OVERRIDES the value embedded in the corpus
    ``structural_evidence_json``; the high-stakes predicate evaluates
    against the recomputed value.

    This pins the V1 architectural contract: corpus's embedded score is
    the default fallback (path c per implementer disposition); the
    recompute callable is the path that surfaces actual T2.SB3 detector
    output when bars are available.
    """
    parent_id = _plant_claude_silver_row(
        conn, ticker="REC",
        confidence="high",
        geometric_score=0.95,  # corpus score - would FAIL high-stakes A
    )

    # Recompute callable returns 0.30 -> NOW activates high-stakes A.
    def recompute(exemplar) -> float:  # noqa: ANN001
        return 0.30

    fired: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        fired.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch,
        rng=_SeededRng([0.99]),  # random does NOT fire
        geometric_score_recompute=recompute,
    )

    fired_selections = [sel for sel in selections if sel.fired]
    assert [sel.exemplar_id for sel in fired_selections] == [parent_id]
    assert fired_selections[0].reason == "high_stakes_a"
    # The recomputed score is the one surfaced in diagnostics, not 0.95.
    assert fired_selections[0].geometric_score == pytest.approx(0.30)
    assert fired == [parent_id]


# ============================================================================
# Codex R1 Minor #2: recompute callable must enforce finite + [0.0, 1.0].
# ============================================================================


def test_retroactive_recompute_rejects_nan_or_out_of_range(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Minor #2 - ``geometric_score_recompute`` documented to
    return a float in [0, 1] but the helper did not enforce it. A NaN or
    out-of-range value can silently affect high-stakes selection.

    Post-fix: the helper raises ValueError mentioning the offending
    value when recompute returns NaN OR a value outside [0.0, 1.0]; an
    in-range value (e.g. 0.5) proceeds normally.
    """
    import math

    _plant_claude_silver_row(
        conn, ticker="REC",
        confidence="high",
        geometric_score=0.95,
    )

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        return CodexReviewResponse(agreed=True)

    # NaN -> ValueError mentioning the value.
    with pytest.raises(ValueError, match="finite"):
        retroactive_codex_evaluation_against_corpus(
            conn,
            phase="t2_sb3_or_later",
            ai_labeler_version="codex-retro-v1",
            codex_dispatch=codex_dispatch,
            rng=_SeededRng([0.99]),
            geometric_score_recompute=lambda _row: math.nan,
        )

    # Out-of-range (1.5) -> ValueError mentioning the [0.0, 1.0] bound.
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        retroactive_codex_evaluation_against_corpus(
            conn,
            phase="t2_sb3_or_later",
            ai_labeler_version="codex-retro-v1",
            codex_dispatch=codex_dispatch,
            rng=_SeededRng([0.99]),
            geometric_score_recompute=lambda _row: 1.5,
        )

    # Out-of-range (-0.1) also rejected.
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        retroactive_codex_evaluation_against_corpus(
            conn,
            phase="t2_sb3_or_later",
            ai_labeler_version="codex-retro-v1",
            codex_dispatch=codex_dispatch,
            rng=_SeededRng([0.99]),
            geometric_score_recompute=lambda _row: -0.1,
        )

    # In-range value (0.5) MUST NOT raise.
    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch,
        rng=_SeededRng([0.99]),
        geometric_score_recompute=lambda _row: 0.5,
    )
    assert isinstance(selections, list)


# ============================================================================
# Test 5: T-A.1.7 corpus parsing - real-corpus dump opens + iterates.
# ============================================================================


def test_retroactive_against_t_a17_corpus_dump_via_corpus_path(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Smoke test: when ``corpus_path`` points at a JSONL dump (per
    plan G.4 T-A.3.7 step 2 + dispatch brief watch item 19 + recon doc),
    the helper reads candidate rows from the dump for the selection-
    predicate evaluation while still routing per-row fires through the
    existing DB-backed ``fire_codex_review_for_silver_row`` write path
    (the DB is the authoritative store; the corpus dump is the
    enumeration source).

    The operator workflow at T-A.3.7+ is: load the corpus dump into the
    DB (already done at T-A.1.7) THEN invoke the retroactive helper.
    The corpus_path argument lets the helper consume the dump file
    rather than ``list_exemplars`` when the operator wants to enumerate
    rows offline (e.g., from a fresh checkout where the DB was
    re-initialized).

    The test plants the same 2 rows into BOTH the DB (so
    ``fire_codex_review_for_silver_row`` can UPDATE them) AND the JSONL
    dump (so the helper's enumeration path reads them) - covering one
    high-stakes A row + one out-of-band row + verifying fire on the
    high-stakes row only.
    """
    # First plant the rows in the DB so the fire path can UPDATE them.
    silver_id_alpha = _plant_claude_silver_row(
        conn, ticker="ALPHA",
        confidence="high", geometric_score=0.25,  # high-stakes A fires
    )
    silver_id_beta = _plant_claude_silver_row(
        conn, ticker="BETA",
        confidence="medium", geometric_score=0.55,  # neither high-stakes
    )

    # Build the matching dump file (carrying the same id values).
    rows = [
        {
            "id": silver_id_alpha,
            "ticker": "ALPHA",
            "timeframe": "daily",
            "start_date": "2020-01-01",
            "end_date": "2020-02-01",
            "proposed_pattern_class": "vcp",
            "final_decision": "rejected",
            "final_pattern_class": None,
            "label_source": "claude_silver",
            "structural_evidence_json": json.dumps(
                {"geometric_score": 0.25, "criteria_pass": {}},
                sort_keys=True,
            ),
            "created_at": "2026-05-19T22:00:00+00:00",
            "created_by": "claude_dispatch",
            "ai_labeler_version": "claude-code-pattern-labeler-v1",
            "gold_validated_at": None,
            "codex_reviewed": 0,
            "codex_agreement": None,
            "geometric_score_json": None,
            "labeler_evidence_json": json.dumps(
                {"evaluation": "rejected", "confidence": "high",
                 "geometric_evidence_narrative": "ascii narrative"},
                sort_keys=True,
            ),
            "quality_grade": None,
            "notes": None,
            "parent_exemplar_id": None,
        },
        {
            "id": silver_id_beta,
            "ticker": "BETA",
            "timeframe": "daily",
            "start_date": "2020-03-01",
            "end_date": "2020-04-01",
            "proposed_pattern_class": "flat_base",
            "final_decision": "watch",
            "final_pattern_class": None,
            "label_source": "claude_silver",
            "structural_evidence_json": json.dumps(
                {"geometric_score": 0.55, "criteria_pass": {}},
                sort_keys=True,
            ),
            "created_at": "2026-05-19T22:01:00+00:00",
            "created_by": "claude_dispatch",
            "ai_labeler_version": "claude-code-pattern-labeler-v1",
            "gold_validated_at": None,
            "codex_reviewed": 0,
            "codex_agreement": None,
            "geometric_score_json": None,
            "labeler_evidence_json": json.dumps(
                {"evaluation": "watch", "confidence": "medium",
                 "geometric_evidence_narrative": "ascii narrative 2"},
                sort_keys=True,
            ),
            "quality_grade": None,
            "notes": None,
            "parent_exemplar_id": None,
        },
    ]

    dump_path = tmp_path / "synthetic_corpus_dump.jsonl"
    with dump_path.open("w", encoding="ascii") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    # When corpus_path is provided, the helper reads rows from there
    # rather than the DB. The DB is still used as the SELECT-first
    # idempotency store - but for this test the DB is empty so no
    # rows are flagged as already_reviewed.
    fired_ids: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        fired_ids.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-v1",
        codex_dispatch=codex_dispatch,
        rng=_SeededRng([0.99, 0.99]),  # random does NOT fire either row
        corpus_path=dump_path,
    )

    # ALPHA fires via high-stakes A (high + 0.25); BETA does not fire
    # (medium + 0.55 + random above threshold).
    fired_selections = [sel for sel in selections if sel.fired]
    assert len(fired_selections) == 1
    assert fired_selections[0].ticker == "ALPHA"
    assert fired_selections[0].reason == "high_stakes_a"
    # codex_dispatch invoked exactly once.
    assert len(fired_ids) == 1


# ============================================================================
# Phase 13 T2.SB4 T-A.4.5: high-stakes clause activates for HTF + DBW
# (ALL 5 detectors covered).
# ============================================================================
#
# Per spec section 5.9 step 4 lines 745-751 + OQ-5 BINDING: at T2.SB4+
# the high-stakes disagreement clause covers ALL 5 V1 detector pattern
# classes (T2.SB3's vcp + flat_base + cup_with_handle PLUS T2.SB4's
# high_tight_flag + double_bottom_w). The retroactive helper is data-
# driven (consumes the per-row geometric_score regardless of
# proposed_pattern_class), so the activation is achieved by the corpus
# carrying HTF + DBW rows + the operator wiring detector recompute when
# bars are available. These tests pin the BEHAVIOR for the 2 new pattern
# classes; the V1 default path (corpus-embedded geometric_score) is the
# same one exercised for vcp / flat_base / cup_with_handle above.


def test_retroactive_codex_evaluation_invokes_all_5_detector_classes(
    conn: sqlite3.Connection,
) -> None:
    """All 5 V1 detector pattern classes (T2.SB3 vcp/flat_base/
    cup_with_handle + T2.SB4 high_tight_flag/double_bottom_w) MUST be
    evaluable by the retroactive helper - the function is class-agnostic
    (data-driven from structural_evidence_json) so a row with
    proposed_pattern_class='high_tight_flag' or 'double_bottom_w' is
    processed identically to the T2.SB3 classes.

    Plants 1 claude_silver row per pattern class with confidence='medium'
    + geometric_score=0.55 (in the no-fire band) and seeds the rng above
    threshold so none fire. Asserts every row appears in selections
    (none silently skipped); confirms 5 detector classes covered.
    """
    pattern_classes = [
        "vcp",
        "flat_base",
        "cup_with_handle",
        "high_tight_flag",
        "double_bottom_w",
    ]
    planted_ids = {}
    for idx, pclass in enumerate(pattern_classes):
        ticker = f"P{idx}"
        planted_ids[pclass] = _plant_claude_silver_row(
            conn, ticker=ticker, pattern_class=pclass,
            confidence="medium", geometric_score=0.55,
        )

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        return CodexReviewResponse(agreed=True)

    # 5 rng values all above 0.15 threshold -> random NEVER fires.
    rng = _SeededRng([0.99, 0.99, 0.99, 0.99, 0.99])

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-t2sb4-coverage",
        codex_dispatch=codex_dispatch,
        rng=rng,
    )

    # Every planted pattern class must appear in selections (no class
    # silently skipped). The reason should be 'not_selected' (medium +
    # 0.55 + random above threshold) for all 5.
    selection_ids = {sel.exemplar_id for sel in selections}
    for pclass, exemplar_id in planted_ids.items():
        assert exemplar_id in selection_ids, (
            f"pattern_class={pclass!r} (exemplar_id={exemplar_id}) was "
            f"silently skipped by retroactive_codex_evaluation_against_"
            f"corpus; the function MUST be class-agnostic per spec "
            f"section 5.9 step 4"
        )

    # All 5 should report 'not_selected' (none fire).
    fired = [sel for sel in selections if sel.fired]
    assert fired == []


def test_retroactive_codex_high_stakes_fires_on_htf_disagreement_a(
    conn: sqlite3.Connection,
) -> None:
    """Per spec section 5.9 step 4 lines 745-751 + OQ-5 BINDING: T2.SB4
    activates the HIGH-STAKES disagreement clause for HTF corpus rows.

    Plants an HTF claude_silver row with confidence='high' + rule-tier
    geometric_score=0.30 (high-stakes A disagreement direction); asserts
    Codex high-stakes dispatch fires + the row in codex_dispatch payload
    carries proposed_pattern_class='high_tight_flag'.
    """
    htf_id = _plant_claude_silver_row(
        conn, ticker="HTF", pattern_class="high_tight_flag",
        confidence="high", geometric_score=0.30,
    )

    dispatched_classes: list[str] = []
    dispatched_ids: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        dispatched_ids.append(parent.id)  # type: ignore[union-attr]
        dispatched_classes.append(
            parent.proposed_pattern_class  # type: ignore[union-attr]
        )
        return CodexReviewResponse(agreed=True)

    rng = _SeededRng([0.99])  # random does NOT fire; only high-stakes.

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-t2sb4-htf",
        codex_dispatch=codex_dispatch,
        rng=rng,
    )

    fired = [sel for sel in selections if sel.fired]
    assert len(fired) == 1
    assert fired[0].exemplar_id == htf_id
    assert fired[0].reason == "high_stakes_a"
    assert dispatched_ids == [htf_id]
    assert dispatched_classes == ["high_tight_flag"]


def test_retroactive_codex_high_stakes_fires_on_dbw_disagreement_b(
    conn: sqlite3.Connection,
) -> None:
    """Per spec section 5.9 step 4 lines 745-751 + OQ-5 BINDING: T2.SB4
    activates the HIGH-STAKES disagreement clause for DBW corpus rows.

    Plants a DBW claude_silver row with confidence='low' + rule-tier
    geometric_score=0.85 (high-stakes B disagreement direction); asserts
    Codex high-stakes dispatch fires + payload carries
    proposed_pattern_class='double_bottom_w'.
    """
    dbw_id = _plant_claude_silver_row(
        conn, ticker="DBW", pattern_class="double_bottom_w",
        confidence="low", geometric_score=0.85,
    )

    dispatched_classes: list[str] = []
    dispatched_ids: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        dispatched_ids.append(parent.id)  # type: ignore[union-attr]
        dispatched_classes.append(
            parent.proposed_pattern_class  # type: ignore[union-attr]
        )
        return CodexReviewResponse(agreed=True)

    rng = _SeededRng([0.99])  # random does NOT fire; only high-stakes B.

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-t2sb4-dbw",
        codex_dispatch=codex_dispatch,
        rng=rng,
    )

    fired = [sel for sel in selections if sel.fired]
    assert len(fired) == 1
    assert fired[0].exemplar_id == dbw_id
    assert fired[0].reason == "high_stakes_b"
    assert dispatched_ids == [dbw_id]
    assert dispatched_classes == ["double_bottom_w"]


def test_retroactive_codex_high_stakes_does_not_fire_when_dbw_agrees(
    conn: sqlite3.Connection,
) -> None:
    """The high-stakes clause MUST NOT fire when Claude silver +
    rule-tier AGREE - DBW row with confidence='high' AND geometric_score
    >= 0.8 is the agreement direction (both 'this is a strong DBW'); no
    Codex dispatch.

    Pre-empts a regression where the high-stakes predicate could fire
    on agreement (e.g., a typo flipping the comparator), silently
    burning Codex MCP quota on agreement cases.
    """
    dbw_id = _plant_claude_silver_row(
        conn, ticker="DBW2", pattern_class="double_bottom_w",
        confidence="high", geometric_score=0.85,
    )

    dispatched: list[int] = []

    def codex_dispatch(**kwargs: object) -> CodexReviewResponse:
        parent = kwargs["parent"]
        dispatched.append(parent.id)  # type: ignore[union-attr]
        return CodexReviewResponse(agreed=True)

    rng = _SeededRng([0.99])  # random does NOT fire.

    selections = retroactive_codex_evaluation_against_corpus(
        conn,
        phase="t2_sb3_or_later",
        ai_labeler_version="codex-retro-t2sb4-dbw-agree",
        codex_dispatch=codex_dispatch,
        rng=rng,
    )

    fired = [sel for sel in selections if sel.fired]
    assert fired == []
    assert dispatched == []
    # The row was scanned but reason should be 'not_selected'.
    by_id = {sel.exemplar_id: sel for sel in selections}
    assert by_id[dbw_id].fired is False
    assert by_id[dbw_id].reason == "not_selected"
