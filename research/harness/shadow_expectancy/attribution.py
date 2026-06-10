from __future__ import annotations

from collections.abc import Iterable

from swing.data.models import Candidate, HypothesisRegistryEntry
from swing.recommendations.hypothesis import match_candidate_to_hypotheses


def attribute_hypotheses(
    candidate: Candidate, *, registry: Iterable[HypothesisRegistryEntry],
) -> list[str]:
    """Post-hoc hypothesis names this signal advances (spec 6/6.1).

    Thin wrapper over the production matcher (pure, keyword-only registry).
    A signal with zero matches is the caller's responsibility to bucket
    (unattributed is a FUNNEL concern, decided in funnel.py / run.py).
    """
    matches = match_candidate_to_hypotheses(
        candidate, registry=list(registry), include_baseline=True,
    )
    return [m.hypothesis_name for m in matches]
