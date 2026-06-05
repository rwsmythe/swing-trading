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

from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE

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
    conn: sqlite3.Connection,
    *,
    min_count_threshold: int = 5,
    benchmark_ticker: str = "QQQ",
) -> frozenset[str]:
    """Pattern classes underrepresented for the CURRENT weather state per
    spec section 5.10 line 799 LOCK.

    Phase 13 T2.SB6c T-A.6c.3 — Gap B.6: weather-state-aware variant.
    Per Codex R1 CRITICAL #1 closure: read-side derivation via at-or-before
    JOIN on ``weather_runs`` (NO new column on ``pattern_exemplars``).

    Current weather status fetched via ``swing.data.repos.weather.get_latest``
    (most-recent run_ts; UI-safe per existing CLAUDE.md gotcha
    "Weather lookup in read-only UIs"). Per-exemplar labeling-time weather
    derived via ``(SELECT MAX(run_ts) FROM weather_runs WHERE ticker = ?
    AND run_ts <= px.created_at)`` subquery.

    Confirmed-only filter (``final_decision = 'confirmed'``) keeps the
    cohort to validated exemplars per spec §5.10.

    When NO weather row exists (current_status is None) the function
    returns an EMPTY set — criterion 3 emits zero hits (conservative).
    """
    from swing.data.repos.weather import get_latest

    detector_classes = (
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    )

    current_weather = get_latest(conn, ticker=benchmark_ticker)
    if current_weather is None:
        # No weather signal => conservative no-op on criterion 3.
        return frozenset()
    current_status = current_weather.status

    # Per-pattern_class count of confirmed exemplars whose labeling-time
    # weather status matches the CURRENT market status. The at-or-before
    # JOIN selects each exemplar's most-recent ``weather_runs`` row with
    # ``run_ts <= px.created_at``. Exemplars labeled before any weather
    # row exists for benchmark_ticker have lwr.labeling_status = NULL
    # (excluded by the WHERE filter, conservative count).
    rows = conn.execute(
        """
        SELECT px.proposed_pattern_class, COUNT(*) AS n
        FROM pattern_exemplars px
        INNER JOIN (
            SELECT px2.id AS exemplar_id, wr.status AS labeling_status
            FROM pattern_exemplars px2
            INNER JOIN weather_runs wr
                ON wr.ticker = ?
               AND wr.run_ts = (
                   SELECT MAX(run_ts) FROM weather_runs
                   WHERE ticker = ? AND run_ts <= px2.created_at
               )
        ) lwr ON lwr.exemplar_id = px.id
        WHERE px.final_decision = 'confirmed'
          AND lwr.labeling_status = ?
        GROUP BY px.proposed_pattern_class
        """,
        (benchmark_ticker, benchmark_ticker, current_status),
    ).fetchall()
    counts = {row[0]: int(row[1]) for row in rows}
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
    conn: sqlite3.Connection,
    *,
    top_k: int = 20,
    benchmark_ticker: str = "QQQ",
) -> list[CandidatePriority]:
    """Return up to ``top_k`` candidates prioritized per spec section 5.10
    4-criterion ranking, sorted by priority_score DESC.

    Consumes the MOST RECENT pipeline_run's pattern_evaluations rows. The
    canonical site for the "most recent run" predicate is the
    ``pipeline_runs.finished_ts DESC`` ordering filtered to
    ``state='complete'`` per CLAUDE.md gotcha "Queries ordered by
    started_ts DESC mask prior completes mid-run".

    Phase 13 T2.SB6c T-A.6c.3 — Gap B.6 weather-state-aware criterion 3:
    ``benchmark_ticker`` (default 'QQQ' to match the ``weather_runs``
    schema default at migration 0003 line 8) drives the at-or-before
    JOIN against ``weather_runs`` for current weather status + per-
    exemplar labeling-time status. Caller (``build_patterns_queue_vm``)
    plumbs ``cfg.rs.benchmark_ticker``.
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
        f"SELECT pe.id, pe.ticker, pe.pattern_class, pe.geometric_score, "
        f"pe.composite_score, pe.template_match_score "
        f"FROM pattern_evaluations pe "
        f"WHERE pe.pipeline_run_id = ? AND {PROVABLE_APLUS_PE_PREDICATE}",
        (latest_run_id,),
    ).fetchall()
    if not rows:
        return []

    underrepresented = _underrepresented_pattern_classes(
        conn, benchmark_ticker=benchmark_ticker,
    )

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
