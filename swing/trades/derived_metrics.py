"""Pure derived-metric formulas for fills-based PnL accounting.

Replaces stored exits.realized_pnl + exits.r_multiple columns with
on-the-fly computation from fill data. Forces formula change to flow
through one place; eliminates drift between stored aggregates and live
math.
"""
from __future__ import annotations


def initial_risk_per_share(*, entry_price: float, initial_stop: float) -> float:
    """Per-share risk in dollars (long-only assumption: entry > stop)."""
    return entry_price - initial_stop


def realized_pnl(*, entry_price: float, exit_price: float, quantity: float) -> float:
    """Long-only realized PnL on a closed quantity."""
    return (exit_price - entry_price) * quantity


def r_multiple(
    *,
    realized_pnl: float,
    initial_risk_per_share: float,
    quantity: float,
) -> float:
    """Realized PnL expressed in initial-risk units.

    r_multiple = realized_pnl / (initial_risk_per_share * quantity).
    """
    risk_dollars = initial_risk_per_share * quantity
    if risk_dollars == 0:
        raise ValueError(
            "initial_risk_per_share * quantity is zero; r_multiple undefined"
        )
    return realized_pnl / risk_dollars
