"""Aggregation primitives for the Finviz-pool binding-constraint analysis.

All analytical primitives operate on production ``Candidate`` objects.
Production-gated blocker classification reuses
``research.harness.earnings_proximity.scripts.recompute_binding_prod_gated.production_gated_binding``
(canonical for "what would production's ``bucket_for`` reject this
candidate for, in production gating order").

Frozen at D1 of the study (``research/studies/finviz-pool-binding-constraints.md``):
- The doctrine-defensible miss set membership (see ``doctrine.py``).
- The output schema (see fields on ``AggregateResult``).
- Sample ordering for near-A+ subset reporting (action_session_date DESC,
  ticker ASC).

Phase isolation: research/ only. Reads ``swing.data.models`` and
``swing.evaluation.criteria.trend_template`` indirectly via the
production-gated re-aggregation script; does not modify them.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Literal

from research.finviz_pool_analysis.doctrine import (
    DEFENSIBLE_MISS_SET,
    DOCTRINE_INCOMPATIBLE_SET,
)
from research.harness.earnings_proximity.scripts.recompute_binding_prod_gated import (
    APLUS_KEY,
    production_gated_binding,
)
from swing.data.models import Candidate

NearAplusClass = Literal["defensible", "incompatible", "not_watch"]


def _criteria_to_row(candidate: Candidate) -> dict[str, str]:
    """Build the {criterion_name: result_str} row dict that
    ``production_gated_binding`` consumes."""
    return {c.criterion_name: c.result for c in candidate.criteria}


def production_gated_blocker(candidate: Candidate) -> str:
    """Return the production-gated blocker for one candidate.

    Wraps ``production_gated_binding`` from the candidate-sparsity
    diagnostic's R1 fix (canonical implementation). Returns ``"<aplus>"``
    if all criteria pass under production gating order.

    Note: this is computed from ``candidate.criteria`` alone; it does NOT
    consult ``candidate.bucket``. The two should agree on the A+ row by
    construction (see ``Aggregator._verify_aplus_consistency``).
    """
    return production_gated_binding(_criteria_to_row(candidate))


def classify_near_aplus(candidate: Candidate) -> NearAplusClass:
    """Classify a watch-bucket candidate for the near-A+ subset analysis.

    - ``"defensible"`` if every non-pass criterion is in
      ``DEFENSIBLE_MISS_SET``.
    - ``"incompatible"`` if at least one non-pass criterion is outside
      ``DEFENSIBLE_MISS_SET`` (i.e., in ``DOCTRINE_INCOMPATIBLE_SET`` or
      otherwise unrecognized).
    - ``"not_watch"`` if ``candidate.bucket != "watch"`` — the near-A+
      classification is only defined on the watch bucket per D1.

    A candidate with ZERO non-pass criteria on the watch bucket is a
    pathological case (would be A+ under ``bucket_for``); we classify it
    as ``"defensible"`` to be conservative on the boundary, but flag it
    via ``Aggregator._verify_bucket_consistency`` if encountered.
    """
    if candidate.bucket != "watch":
        return "not_watch"
    non_pass = [c.criterion_name for c in candidate.criteria if c.result != "pass"]
    if all(name in DEFENSIBLE_MISS_SET for name in non_pass):
        return "defensible"
    return "incompatible"


@dataclass(frozen=True)
class NearAplusSample:
    """One row in a near-A+ subset sample."""
    ticker: str
    evaluation_run_id: int
    action_session_date: str
    bucket: str
    failed_criteria: tuple[str, ...]


@dataclass(frozen=True)
class AggregateResult:
    """Frozen output of an aggregation pass over qualifying runs.

    All counts are over the union of evaluations across all qualifying
    runs in this aggregation. Field schema is locked by D1 §"Outputs".
    """
    blocker_counts: Counter[str]                    # incl. "<aplus>" sentinel
    bucket_counts: Counter[str]                     # aplus|watch|skip|error|excluded
    total_evaluations: int                          # sum over qualifying runs
    aplus_count: int                                # = bucket_counts['aplus']
    watch_count: int                                # = bucket_counts['watch']
    watch_aplus_ratio: float | None                 # None iff aplus_count == 0
    near_aplus_defensible_count: int                # subset of watch
    near_aplus_incompatible_count: int              # subset of watch (= watch - defensible)
    defensible_sample: tuple[NearAplusSample, ...]  # ≤10 rows, deterministic
    incompatible_sample: tuple[NearAplusSample, ...]
    per_run_watch_aplus_ratio: dict[int, float | None]  # run_id -> ratio
    consistency_warnings: tuple[str, ...] = field(default_factory=tuple)


def _watch_aplus_ratio(watch: int, aplus: int) -> float | None:
    """Defined as watch / aplus; undefined (None) when aplus == 0.

    The ratio expresses "for each A+ candidate, how many watch-bucket
    candidates does production produce" — undefined on zero-A+ slices.
    """
    if aplus == 0:
        return None
    return watch / aplus


def aggregate_runs(
    runs: list[tuple[int, str, list[Candidate]]],
) -> AggregateResult:
    """Aggregate per-criterion blockers, buckets, and near-A+ subsets.

    Args:
        runs: list of (evaluation_run_id, action_session_date, candidates)
            triples. Each triple is one qualifying evaluation_run with its
            full Candidate list (criteria pre-populated). Order does not
            affect counts; sample-row ordering is computed independently.

    Returns:
        Frozen ``AggregateResult`` with all D1-required output fields.
    """
    blocker_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    per_run_watch_aplus: dict[int, float | None] = {}
    near_aplus_rows: list[tuple[NearAplusClass, NearAplusSample]] = []
    consistency_warnings: list[str] = []
    total = 0
    aplus = 0
    watch = 0
    defensible = 0
    incompatible = 0

    for run_id, action_session_date, candidates in runs:
        per_run_aplus = 0
        per_run_watch = 0
        for cand in candidates:
            total += 1
            bucket_counts[cand.bucket] += 1
            if cand.bucket == "aplus":
                aplus += 1
                per_run_aplus += 1
            if cand.bucket == "watch":
                watch += 1
                per_run_watch += 1

            # Production-gated blocker — defined on every candidate whose
            # criteria are fully populated. 'error' bucket may have empty
            # criteria; we record the blocker as "<error>" so the column
            # sums to total_evaluations.
            if cand.criteria:
                blocker = production_gated_blocker(cand)
            else:
                blocker = "<error>"
            blocker_counts[blocker] += 1

            # Cross-check: the production-gated <aplus> row count should
            # equal the 'aplus' bucket count. We surface drift as a
            # consistency warning rather than a crash because the read
            # of production data must remain robust to legacy anomalies.
            if cand.bucket == "aplus" and blocker != APLUS_KEY:
                consistency_warnings.append(
                    f"run={run_id} ticker={cand.ticker}: bucket=aplus but "
                    f"production-gated blocker={blocker} (re-aggregation drift)"
                )
            if cand.bucket != "aplus" and blocker == APLUS_KEY:
                consistency_warnings.append(
                    f"run={run_id} ticker={cand.ticker}: bucket={cand.bucket} but "
                    f"production-gated blocker=<aplus> (re-aggregation drift)"
                )

            # Near-A+ classification on watch bucket only.
            if cand.bucket == "watch":
                cls = classify_near_aplus(cand)
                if cls == "defensible":
                    defensible += 1
                elif cls == "incompatible":
                    incompatible += 1
                near_aplus_rows.append(
                    (
                        cls,
                        NearAplusSample(
                            ticker=cand.ticker,
                            evaluation_run_id=run_id,
                            action_session_date=action_session_date,
                            bucket=cand.bucket,
                            failed_criteria=tuple(
                                c.criterion_name
                                for c in cand.criteria
                                if c.result != "pass"
                            ),
                        ),
                    )
                )

        per_run_watch_aplus[run_id] = _watch_aplus_ratio(per_run_watch, per_run_aplus)

    # Deterministic sample ordering: action_session_date DESC, ticker ASC.
    # Tie-break on (run_id, ticker) so cross-run duplicates are stable.
    def sort_key(row: NearAplusSample) -> tuple:
        return (
            tuple(-int(p) for p in row.action_session_date.split("-")),
            row.ticker,
            row.evaluation_run_id,
        )

    defensible_rows = sorted(
        (r for cls, r in near_aplus_rows if cls == "defensible"), key=sort_key
    )
    incompatible_rows = sorted(
        (r for cls, r in near_aplus_rows if cls == "incompatible"), key=sort_key
    )

    return AggregateResult(
        blocker_counts=blocker_counts,
        bucket_counts=bucket_counts,
        total_evaluations=total,
        aplus_count=aplus,
        watch_count=watch,
        watch_aplus_ratio=_watch_aplus_ratio(watch, aplus),
        near_aplus_defensible_count=defensible,
        near_aplus_incompatible_count=incompatible,
        defensible_sample=tuple(defensible_rows[:10]),
        incompatible_sample=tuple(incompatible_rows[:10]),
        per_run_watch_aplus_ratio=per_run_watch_aplus,
        consistency_warnings=tuple(consistency_warnings),
    )
