"""Phase 13 T2.SB6b T-A.6.4 — active-learning prioritization helper.

Per spec section 5.10 lines 796-801 VERBATIM 4-criterion ranking:
  1. Borderline geometric scores (abs(geometric_score - 0.5) < 0.1).
  2. Rule/template disagreement (abs(geometric_score - template_match_score)
     > 0.3).
  3. Underrepresented regimes (low historical exemplar count for current
     weather state).
  4. Failed-rule near-misses (geometric_score in [0.55, 0.70]).

Pure function consumed by ``swing/web/routes/patterns.py:patterns_queue_page``
+ ``swing/web/view_models/patterns/queue.py:build_patterns_queue_vm``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

# Constants per spec section 5.10 lines 796-801 LOCK. Canonical site —
# do NOT redefine inline anywhere downstream (per L1 + Expansion #1 hardcoded-
# duplicate audit discipline).
BORDERLINE_GEOMETRIC_BAND: float = 0.1  # |score - 0.5| < 0.1
RULE_TEMPLATE_DISAGREEMENT_THRESHOLD: float = 0.3
FAILED_RULE_NEAR_MISS_LOW: float = 0.55
FAILED_RULE_NEAR_MISS_HIGH: float = 0.70

_PRIORITY_REASON_VALUES: frozenset[str] = frozenset({
    "borderline_geometric",
    "rule_template_disagreement",
    "underrepresented_regime",
    "failed_rule_near_miss",
})


@dataclass(frozen=True)
class CandidatePriority:
    """One row in the active-learning prioritized queue.

    L6 LOCK: ``priority_reason`` carries a Literal-typed enum; the
    ``__post_init__`` validates against the frozenset above per
    CLAUDE.md gotcha "Literal[...] not runtime-enforced".
    """

    candidate_id: int  # pattern_evaluations.id
    ticker: str
    pattern_class: str
    geometric_score: float
    composite_score: float
    template_match_score: float | None
    priority_reason: Literal[
        "borderline_geometric",
        "rule_template_disagreement",
        "underrepresented_regime",
        "failed_rule_near_miss",
    ]
    priority_score: float  # 0.0..1.0; higher = more urgent review

    def __post_init__(self) -> None:
        if self.priority_reason not in _PRIORITY_REASON_VALUES:
            raise ValueError(
                "CandidatePriority.priority_reason must be one of "
                f"{_PRIORITY_REASON_VALUES}; got {self.priority_reason!r}"
            )
        if not (0.0 <= self.priority_score <= 1.0):
            raise ValueError(
                "CandidatePriority.priority_score must be in [0.0, 1.0]; "
                f"got {self.priority_score!r}"
            )


def _underrepresented_pattern_classes(
    conn: sqlite3.Connection, *, min_count_threshold: int = 5,
) -> frozenset[str]:
    """Pattern classes with fewer than ``min_count_threshold`` rows in
    pattern_exemplars are flagged as underrepresented per spec criterion 3
    (V1 proxy for "low historical exemplar count for current weather state"
    — the weather-state-aware refinement is V2 per spec C.6).
    """
    rows = conn.execute(
        "SELECT proposed_pattern_class, COUNT(*) FROM pattern_exemplars "
        "GROUP BY proposed_pattern_class"
    ).fetchall()
    counts = {row[0]: int(row[1]) for row in rows}
    detector_classes = (
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    )
    out = {
        cls for cls in detector_classes
        if counts.get(cls, 0) < min_count_threshold
    }
    return frozenset(out)


def _classify_priority(
    *,
    geometric_score: float,
    template_match_score: float | None,
    pattern_class: str,
    underrepresented_classes: frozenset[str],
) -> tuple[
    Literal[
        "borderline_geometric",
        "rule_template_disagreement",
        "underrepresented_regime",
        "failed_rule_near_miss",
    ] | None,
    float,
]:
    """Return (priority_reason, priority_score) per the 4-criterion ranking.

    Returns (None, 0.0) when no criterion fires — caller drops the row.
    Criterion priority order is enumerated in spec section 5.10 lines
    796-801. When multiple fire, the first-matched wins:
      1. borderline_geometric
      2. rule_template_disagreement
      3. underrepresented_regime
      4. failed_rule_near_miss
    """
    # Criterion 1: borderline geometric.
    if abs(geometric_score - 0.5) < BORDERLINE_GEOMETRIC_BAND:
        # Higher priority closer to 0.5 (more borderline).
        priority_score = 1.0 - (abs(geometric_score - 0.5)
                                / BORDERLINE_GEOMETRIC_BAND)
        return ("borderline_geometric", priority_score)
    # Criterion 2: rule/template disagreement.
    if (
        template_match_score is not None
        and abs(geometric_score - template_match_score)
        > RULE_TEMPLATE_DISAGREEMENT_THRESHOLD
    ):
        # Score = min(1.0, disagreement / (2 * threshold)).
        disagreement = abs(geometric_score - template_match_score)
        priority_score = min(
            1.0, disagreement / (2.0 * RULE_TEMPLATE_DISAGREEMENT_THRESHOLD),
        )
        return ("rule_template_disagreement", priority_score)
    # Criterion 3: underrepresented regime.
    if pattern_class in underrepresented_classes:
        return ("underrepresented_regime", 0.6)
    # Criterion 4: failed-rule near-misses.
    if (
        FAILED_RULE_NEAR_MISS_LOW
        <= geometric_score
        <= FAILED_RULE_NEAR_MISS_HIGH
    ):
        # Higher priority closer to 0.625 (band midpoint).
        midpoint = (
            (FAILED_RULE_NEAR_MISS_LOW + FAILED_RULE_NEAR_MISS_HIGH) / 2.0
        )
        half_width = (
            (FAILED_RULE_NEAR_MISS_HIGH - FAILED_RULE_NEAR_MISS_LOW) / 2.0
        )
        priority_score = 1.0 - (abs(geometric_score - midpoint) / half_width)
        # Lower than criterion 1 baseline; cap at 0.5 to reflect ordering.
        priority_score = min(0.5, priority_score)
        return ("failed_rule_near_miss", priority_score)
    return (None, 0.0)


def prioritize_candidates(
    conn: sqlite3.Connection, *, top_k: int = 20,
) -> list[CandidatePriority]:
    """Return up to ``top_k`` candidates prioritized per spec section 5.10
    4-criterion ranking, sorted by priority_score DESC.

    Consumes the MOST RECENT pipeline_run's pattern_evaluations rows. The
    canonical site for the "most recent run" predicate is the
    ``pipeline_runs.finished_ts DESC`` ordering filtered to
    ``state='complete'`` per CLAUDE.md gotcha "Queries ordered by
    started_ts DESC mask prior completes mid-run".
    """
    latest_run_row = conn.execute(
        "SELECT id FROM pipeline_runs "
        "WHERE state = 'complete' AND finished_ts IS NOT NULL "
        "ORDER BY finished_ts DESC LIMIT 1"
    ).fetchone()
    if latest_run_row is None:
        return []
    latest_run_id = int(latest_run_row[0])

    rows = conn.execute(
        "SELECT id, ticker, pattern_class, geometric_score, "
        "composite_score, template_match_score FROM pattern_evaluations "
        "WHERE pipeline_run_id = ?",
        (latest_run_id,),
    ).fetchall()
    if not rows:
        return []

    underrepresented = _underrepresented_pattern_classes(conn)

    candidates: list[CandidatePriority] = []
    for row in rows:
        (
            candidate_id, ticker, pattern_class,
            geometric_score, composite_score, template_match_score,
        ) = row
        priority_reason, priority_score = _classify_priority(
            geometric_score=float(geometric_score),
            template_match_score=(
                float(template_match_score)
                if template_match_score is not None else None
            ),
            pattern_class=pattern_class,
            underrepresented_classes=underrepresented,
        )
        if priority_reason is None:
            continue
        candidates.append(CandidatePriority(
            candidate_id=int(candidate_id),
            ticker=ticker,
            pattern_class=pattern_class,
            geometric_score=float(geometric_score),
            composite_score=float(composite_score),
            template_match_score=(
                float(template_match_score)
                if template_match_score is not None else None
            ),
            priority_reason=priority_reason,
            priority_score=priority_score,
        ))

    candidates.sort(key=lambda c: c.priority_score, reverse=True)
    return candidates[:top_k]
