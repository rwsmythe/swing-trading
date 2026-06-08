# research/harness/minervini_exemplar_recall/scorecard.py
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Sequence

_SURFACED = {"surfaced_aplus", "surfaced_watch"}
_ATTRITION = {"skip_insufficient_history", "no_data"}


@dataclass(frozen=True)
class WilsonInterval:
    lower: float
    upper: float
    p_hat: float
    n: int


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float
    upper: float
    b: int


def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
    if n == 0:
        return WilsonInterval(0.0, 1.0, 0.0, 0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return WilsonInterval(lower=center - half, upper=center + half, p_hat=p, n=n)


def _clustered_resample(rng: random.Random, by_ticker: dict[str, list]) -> list:
    tickers = sorted(by_ticker)
    drawn = [rng.choice(tickers) for _ in tickers]
    rows: list = []
    for t in drawn:
        rows.extend(by_ticker[t])  # whole ticker's rows move together
    return rows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = q / 100.0 * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def ticker_clustered_bootstrap(
    rows: Sequence[tuple], value_fn: Callable[[Sequence[tuple]], float], *, b: int, base_seed: int
) -> BootstrapInterval:
    by_ticker: dict[str, list] = {}
    for row in rows:
        by_ticker.setdefault(row[0], []).append(row)
    rng = random.Random(base_seed)
    stats = [value_fn(_clustered_resample(rng, by_ticker)) for _ in range(b)]
    return BootstrapInterval(lower=_percentile(stats, 2.5), upper=_percentile(stats, 97.5), b=b)


def screening_recall(outcomes: Sequence[str]) -> tuple[float, float]:
    """Returns (full_set_recall, screenable_subset_recall)."""
    n_total = len(outcomes)
    surfaced = sum(1 for o in outcomes if o in _SURFACED)
    screenable = sum(1 for o in outcomes if o not in _ATTRITION)
    full = surfaced / n_total if n_total else 0.0
    sub = surfaced / screenable if screenable else 0.0
    return full, sub
