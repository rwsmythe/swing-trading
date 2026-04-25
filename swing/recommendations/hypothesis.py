"""Hypothesis recommendation engine: matcher + prioritizer + tripwire.

Per `docs/hypothesis-recommendation-backend-brief.md` §4.2-§4.4. Three
pure(-ish) compute units:

1. `match_candidate_to_hypotheses` — given a `Candidate` and the active
   subset of the `hypothesis_registry`, return zero-or-more
   `HypothesisMatch` rows describing which hypotheses this candidate
   would advance.
2. `prioritize_recommendations` — given a flat list of matches across all
   candidates plus current registry/progress, return a display-ordered
   list of `CandidateRecommendation`s (most-investigation-valuable first).
3. `compute_tripwire_status` — given a hypothesis id and a DB connection,
   walk that hypothesis's tagged closed trades and return the consecutive-
   max-loss + absolute-loss tripwire signals.

Everything is dataclasses + pure functions; nothing here mutates DB state.
DB writes (status updates, trade entry) live in their respective repos.

**Doctrine-defensible miss set is FROZEN (brief §0 + Finviz study D1).**
The set is exposed as a module constant and ALSO accepted as a parameter
so tests can verify the matcher behaves correctly for any candidate set
operators future studies might commission. The CALL SITE in production
must use `DOCTRINE_DEFENSIBLE_MISS_SET` directly — overriding it would
require routing through the source-of-truth correction protocol.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable

from swing.data.models import Candidate, HypothesisRegistryEntry


# Frozen at Finviz-pool study D1 (research/studies/finviz-pool-binding-
# constraints.md §"Doctrine-defensible misses"). NOT modifiable post-data
# without an explicit operator-recorded amendment.
DOCTRINE_DEFENSIBLE_MISS_SET: frozenset[str] = frozenset({
    "TT8_rs_rank",
    "risk_feasibility",
    "proximity_20ma",
})

# Hypothesis-name constants. Centralized so the matcher rules and the
# tripwire string-matcher cannot drift; if a NEW migration adds a fifth
# hypothesis, add the name + matcher rule here.
H_APLUS_BASELINE = "A+ baseline"
H_NEAR_APLUS_EXTENSION = "Near-A+ defensible: extension test"
H_SUB_APLUS_VCP = "Sub-A+ VCP-not-formed"
H_CAPITAL_BLOCKED = "Capital-blocked: smaller-position test"


@dataclass(frozen=True)
class HypothesisMatch:
    """Output of `match_candidate_to_hypotheses`. One row per (candidate,
    matched-hypothesis) pair. The same candidate may appear in multiple
    matches if it fits multiple ACTIVE hypotheses."""
    hypothesis_id: int
    hypothesis_name: str
    suggested_label_descriptive: str
    # Numeric prioritization hint within a hypothesis. Lower = better
    # (closer-to-pivot, etc.). Currently derived from candidate metrics
    # the matcher already has.
    priority_hint: float
    # Carry the originating candidate forward so the prioritizer can
    # dedupe / reorder without re-running the matcher.
    candidate_ticker: str = ""


def _non_pass_criterion_names(candidate: Candidate) -> set[str]:
    """Return the set of criterion names whose result is NOT 'pass'.

    Brief §5 watch item: na counts as non-pass (matches `bucket_for`
    which treats na as fail for VCP gating). The matcher inherits that
    semantics so a `na` result on `tightness` does not let an otherwise-
    near-A+ candidate slip through the "extension test" rule.
    """
    return {c.criterion_name for c in candidate.criteria if c.result != "pass"}


def _aplus_baseline_match(candidate: Candidate) -> bool:
    return candidate.bucket == "aplus"


def _near_aplus_extension_match(candidate: Candidate) -> bool:
    """Watch bucket AND non-pass set is exactly {proximity_20ma}."""
    if candidate.bucket != "watch":
        return False
    return _non_pass_criterion_names(candidate) == {"proximity_20ma"}


def _sub_aplus_vcp_not_formed_match(
    candidate: Candidate, doctrine_defensible_set: frozenset[str],
) -> bool:
    """Watch bucket AND (tightness OR vcp_volume_contraction in non-pass)
    AND every non-pass criterion is in (defensible ∪ {tightness, vcp_volume_contraction}).
    """
    if candidate.bucket != "watch":
        return False
    non_pass = _non_pass_criterion_names(candidate)
    triggers = {"tightness", "vcp_volume_contraction"}
    if non_pass & triggers == set():
        return False
    allowed = doctrine_defensible_set | triggers
    return non_pass.issubset(allowed)


def _capital_blocked_match(candidate: Candidate) -> bool:
    """Watch bucket AND non-pass set is exactly {risk_feasibility}.

    Note: `risk_feasibility` is a hard pre-filter in production — a
    candidate that fails it is bucketed `skip`, not `watch`. By the
    matcher rule "watch + only risk_feasibility fails" this hypothesis
    will never fire on real production data today; the rule is preserved
    for future variants where production gating changes (or for replay
    studies that disable the hard filter to characterize the structural
    distribution).
    """
    if candidate.bucket != "watch":
        return False
    return _non_pass_criterion_names(candidate) == {"risk_feasibility"}


def _descriptive_label(
    candidate: Candidate, hypothesis_name: str,
) -> str:
    """Build the suggested hypothesis-tag string. Format pinned because
    `compute_tripwire_status` matches by case-insensitive substring on
    `hypothesis_name`; the descriptive suffix may evolve without breaking
    matching."""
    non_pass = sorted(_non_pass_criterion_names(candidate))
    if non_pass:
        suffix = f"; failed: {', '.join(non_pass)}"
    else:
        suffix = ""
    return f"{hypothesis_name} ({candidate.bucket}){suffix}"


def _priority_hint_for(candidate: Candidate) -> float:
    """Numeric hint, lower = better (matches sort).

    Use closeness-to-pivot when both close and pivot are present (smaller
    is closer-to-trigger and thus more time-sensitive). Falls back to a
    constant so the prioritizer's tie-break can take over.
    """
    if candidate.close is not None and candidate.pivot:
        return abs(1.0 - candidate.close / candidate.pivot)
    return 1.0


def match_candidate_to_hypotheses(
    candidate: Candidate,
    *,
    doctrine_defensible_set: frozenset[str] = DOCTRINE_DEFENSIBLE_MISS_SET,
    registry: Iterable[HypothesisRegistryEntry],
) -> list[HypothesisMatch]:
    """Return zero-or-more `HypothesisMatch` rows for this candidate.

    Multi-match is allowed: a candidate that fits two ACTIVE hypotheses
    surfaces both. The downstream prioritizer decides which (if any) to
    surface to the operator.
    """
    active_by_name: dict[str, HypothesisRegistryEntry] = {
        h.name: h for h in registry if h.status == "active"
    }
    matches: list[HypothesisMatch] = []

    rules: list[tuple[str, callable]] = [
        (H_APLUS_BASELINE, lambda c: _aplus_baseline_match(c)),
        (H_NEAR_APLUS_EXTENSION, lambda c: _near_aplus_extension_match(c)),
        (H_SUB_APLUS_VCP,
         lambda c: _sub_aplus_vcp_not_formed_match(c, doctrine_defensible_set)),
        (H_CAPITAL_BLOCKED, lambda c: _capital_blocked_match(c)),
    ]

    for name, rule in rules:
        h = active_by_name.get(name)
        if h is None:
            continue
        if not rule(candidate):
            continue
        matches.append(HypothesisMatch(
            hypothesis_id=h.id,
            hypothesis_name=h.name,
            suggested_label_descriptive=_descriptive_label(candidate, h.name),
            priority_hint=_priority_hint_for(candidate),
            candidate_ticker=candidate.ticker,
        ))
    return matches
