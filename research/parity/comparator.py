"""Per-ticker bucket and per-criterion parity comparator.

The comparator is a pure function over two ``Candidate`` objects (one
production, one harness). It produces a :class:`TickerParity` record per
ticker, then :func:`summarize` aggregates across tickers and applies
D1's frozen tier thresholds (``research/studies/harness-vs-production-parity.md``
§"Decision tiers"):

- Tier 1 — bucket agreement ≥99 % AND per-criterion agreement ≥99 %.
- Tier 2 — 95 % ≤ either rate < 99 %.
- Tier 3 — either rate < 95 %.

Per the D1 §"Comparison primitive" pre-registration, mismatched-presence
of a criterion (present on one side but absent on the other) counts as
a disagreement, not as ``None == None``. The two rates are evaluated
independently; the worse of the two governs the tier.
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.data.models import Candidate, CriterionResult


@dataclass(frozen=True)
class CriterionDisagreement:
    """One per-criterion disagreement record.

    ``prod_result`` / ``harness_result`` are ``None`` when the criterion
    is absent on that side. ``prod_value`` / ``harness_value`` mirror the
    ``CriterionResult.value`` strings (kept as opaque strings — comparing
    structured values is brittle and not what the parity check is for).
    """
    criterion_name: str
    prod_result: str | None
    harness_result: str | None
    prod_value: str | None
    harness_value: str | None


@dataclass(frozen=True)
class TickerParity:
    """Per-ticker comparison outcome.

    ``criterion_total_compared`` is the size of the union of criterion
    names across the two candidates' criteria (so mismatched-presence is
    counted in the denominator). ``criterion_match_count`` counts only
    pairs where the criterion is present on BOTH sides AND ``result``
    matches; everything else contributes to the disagreement set.
    """
    ticker: str
    prod_bucket: str | None
    harness_bucket: str | None
    bucket_match: bool
    criterion_disagreements: tuple[CriterionDisagreement, ...]
    criterion_total_compared: int
    criterion_match_count: int


@dataclass(frozen=True)
class ParitySummary:
    """Aggregate parity statistics + tier classification."""
    bucket_total: int
    bucket_matches: int
    criterion_total: int
    criterion_matches: int
    bucket_agreement_rate: float
    criterion_agreement_rate: float
    tier: int  # 1, 2, or 3 per D1


def _criteria_by_name(crits: tuple[CriterionResult, ...]) -> dict[str, CriterionResult]:
    return {c.criterion_name: c for c in crits}


def compare(
    prod_candidate: Candidate | None,
    harness_candidate: Candidate | None,
) -> TickerParity:
    """Compare a production candidate against a harness candidate.

    Either side may be ``None`` (ticker absent from that side); both
    being ``None`` is a programming error and raises :class:`ValueError`.

    Bucket parity: ``prod_bucket == harness_bucket`` (both must be
    populated). If either side is missing, ``bucket_match`` is False.

    Per-criterion parity: union of criterion names across both sides.
    For each name, both ``result`` strings must match. Mismatched-presence
    (criterion in one but not the other) counts as a disagreement per
    D1 §"Comparison primitive."
    """
    if prod_candidate is None and harness_candidate is None:
        raise ValueError("compare requires at least one non-None candidate")

    if prod_candidate is not None:
        ticker = prod_candidate.ticker
    else:
        assert harness_candidate is not None
        ticker = harness_candidate.ticker

    prod_bucket = prod_candidate.bucket if prod_candidate else None
    harness_bucket = harness_candidate.bucket if harness_candidate else None
    bucket_match = (
        prod_bucket is not None
        and harness_bucket is not None
        and prod_bucket == harness_bucket
    )

    prod_crits = _criteria_by_name(prod_candidate.criteria) if prod_candidate else {}
    harness_crits = _criteria_by_name(harness_candidate.criteria) if harness_candidate else {}

    union_names = sorted(set(prod_crits) | set(harness_crits))
    disagreements: list[CriterionDisagreement] = []
    matches = 0
    for name in union_names:
        p = prod_crits.get(name)
        h = harness_crits.get(name)
        if p is not None and h is not None and p.result == h.result:
            matches += 1
            continue
        disagreements.append(CriterionDisagreement(
            criterion_name=name,
            prod_result=p.result if p else None,
            harness_result=h.result if h else None,
            prod_value=p.value if p else None,
            harness_value=h.value if h else None,
        ))

    return TickerParity(
        ticker=ticker,
        prod_bucket=prod_bucket,
        harness_bucket=harness_bucket,
        bucket_match=bucket_match,
        criterion_disagreements=tuple(disagreements),
        criterion_total_compared=len(union_names),
        criterion_match_count=matches,
    )


def _classify_tier(bucket_rate: float, criterion_rate: float) -> int:
    """Apply D1's frozen tier thresholds.

    The worse of the two rates governs:
    - Both ≥ 0.99 → Tier 1.
    - Either in [0.95, 0.99) (and neither below 0.95) → Tier 2.
    - Either < 0.95 → Tier 3.
    """
    worst = min(bucket_rate, criterion_rate)
    if worst >= 0.99:
        return 1
    if worst >= 0.95:
        return 2
    return 3


def summarize(parities: list[TickerParity]) -> ParitySummary:
    """Aggregate per-ticker parities and apply D1's tier classification."""
    if not parities:
        raise ValueError("summarize requires at least one TickerParity")

    bucket_total = len(parities)
    bucket_matches = sum(1 for p in parities if p.bucket_match)
    criterion_total = sum(p.criterion_total_compared for p in parities)
    criterion_matches = sum(p.criterion_match_count for p in parities)

    bucket_rate = bucket_matches / bucket_total
    criterion_rate = (
        criterion_matches / criterion_total if criterion_total > 0 else 1.0
    )
    tier = _classify_tier(bucket_rate, criterion_rate)

    return ParitySummary(
        bucket_total=bucket_total,
        bucket_matches=bucket_matches,
        criterion_total=criterion_total,
        criterion_matches=criterion_matches,
        bucket_agreement_rate=bucket_rate,
        criterion_agreement_rate=criterion_rate,
        tier=tier,
    )
