"""Near-trigger detection — asymmetric window from legacy briefing rule.

Default window: -1.0% to +0.5% from pivot. Asymmetric because >0.5% above pivot
is already extended/chase territory (entry there means worse R:R).
"""
from __future__ import annotations


def pct_from_pivot(*, price: float, entry_target: float) -> float:
    if entry_target <= 0:
        raise ValueError(f"entry_target must be > 0, got {entry_target}")
    return (price - entry_target) / entry_target * 100


def is_near_trigger(
    *, price: float, entry_target: float,
    above_pct: float = 0.5, below_pct: float = 1.0,
) -> bool:
    pct = pct_from_pivot(price=price, entry_target=entry_target)
    return -below_pct <= pct <= above_pct
