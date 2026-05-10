"""Composite weighted focus ranking for A+ candidates (legacy parity).

Inputs normalized to [0, 1] across the set:
  closeness_to_pivot = 1 - clamp(|close - pivot| / pivot)
  adr_norm = adr / max_adr
  trend_norm = trend / max_trend
Score = sum(w * normalized).
Ties broken by ticker alpha (deterministic).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from swing.data.models import Candidate


@dataclass(frozen=True)
class FocusWeights:
    closeness_to_pivot: float
    adr: float
    prior_trend: float


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def rank_focus(candidates: Iterable[Candidate], *, weights: FocusWeights) -> list[Candidate]:
    cands = list(candidates)
    if not cands:
        return []

    closenesses = []
    adrs = []
    trends = []
    for c in cands:
        if c.pivot and c.pivot > 0 and c.close is not None:
            dist = abs(c.close - c.pivot) / c.pivot
            closenesses.append(max(0.0, 1.0 - dist))
        else:
            closenesses.append(0.0)
        adrs.append(c.adr_pct or 0.0)
        trends.append(c.prior_trend_pct or 0.0)

    max_adr = max(adrs) if adrs else 0.0
    max_trend = max(trends) if trends else 0.0

    scored: list[tuple[float, str, Candidate]] = []
    for c, cl, a, t in zip(cands, closenesses, adrs, trends, strict=False):
        score = (
            weights.closeness_to_pivot * cl
            + weights.adr * _safe_div(a, max_adr)
            + weights.prior_trend * _safe_div(t, max_trend)
        )
        scored.append((score, c.ticker, c))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, _, c in scored]
