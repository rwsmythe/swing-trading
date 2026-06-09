from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

# Reuse the FROZEN harness's uncertainty primitives.
from research.harness.minervini_exemplar_recall.scorecard import (
    BootstrapInterval,
    WilsonInterval,
    ticker_clustered_bootstrap,
    wilson_interval,
)


@dataclass(frozen=True)
class RecallFraction:
    successes: int
    n: int
    rate: float
    fired_ids: tuple[str, ...]
    missed_ids: tuple[str, ...]


def recall_fraction(rows: Sequence[tuple[str, bool]]) -> RecallFraction:
    """Raw recall as explicit counts FIRST (R1.m4). rows = (exemplar_id, fired)."""
    fired = tuple(eid for eid, ok in rows if ok)
    missed = tuple(eid for eid, ok in rows if not ok)
    n = len(rows)
    return RecallFraction(len(fired), n, (len(fired) / n if n else 0.0), fired, missed)


def wilson(successes: int, n: int) -> WilsonInterval:
    """A MECHANICAL interval at n~3 (NOT evidence of stable performance) -- labeled in summary.md."""
    return wilson_interval(successes, n)


def bootstrap(rows: Sequence[tuple], *, b: int, base_seed: int) -> BootstrapInterval:
    """Exploratory-only ticker-clustered bootstrap; rows[i][0] MUST be the ticker key."""
    return ticker_clustered_bootstrap(
        rows,
        lambda rs: (sum(1 for r in rs if r[1]) / len(rs)) if rs else 0.0,
        b=b,
        base_seed=base_seed,
    )


def first_rejection_histogram(rows: Sequence[tuple[str, str | None]]) -> dict[str, int]:
    """Per-criterion first-rejection counts across MISSES (criterion is None for a fired row)."""
    return dict(Counter(crit for _eid, crit in rows if crit is not None))


@dataclass(frozen=True)
class PrecisionContrast:
    exemplar_single_fired: bool | None  # None for month-precision rows (sweep-only; no single-session)
    exemplar_window_fired: bool
    control_single_rate: float | None
    control_window_rate: float | None
    primary_estimand: str = "single_session_per_anchor"


def _rate_or_none(flags: Sequence[bool]) -> float | None:
    return (sum(1 for f in flags if f) / len(flags)) if flags else None


def precision_contrast(
    *,
    exemplar_single_fired: bool | None,
    exemplar_window_fired: bool,
    control_single_flags: Sequence[bool],
    control_window_flags: Sequence[bool],
) -> PrecisionContrast:
    return PrecisionContrast(
        exemplar_single_fired=exemplar_single_fired,
        exemplar_window_fired=exemplar_window_fired,
        control_single_rate=_rate_or_none(control_single_flags),
        control_window_rate=_rate_or_none(control_window_flags),
    )
