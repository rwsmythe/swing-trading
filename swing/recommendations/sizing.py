"""Risk-based + position-cap position sizing.

Two constraints (binding constraint reported in `constraint`):
  - Risk: shares <= max_risk_dollars / risk_per_share
  - Position cap: shares <= (equity * position_pct_cap) / entry_price

Floor of zero shares with feasible=False if even 1 share exceeds max risk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SizingResult:
    shares: int
    risk_dollars: float
    risk_pct: float
    notional: float
    notional_pct: float
    feasible: bool
    constraint: str


def compute_shares(
    *, entry: float, stop: float, equity: float,
    max_risk_pct: float, position_pct_cap: float,
) -> SizingResult:
    if stop >= entry:
        raise ValueError(f"stop must be < entry; got entry={entry}, stop={stop}")

    if equity <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="no_equity",
        )

    rps = entry - stop
    max_risk_dollars = equity * max_risk_pct
    shares_by_risk = math.floor(max_risk_dollars / rps) if rps > 0 else 0
    shares_by_cap = math.floor((equity * position_pct_cap) / entry) if entry > 0 else 0
    shares = min(shares_by_risk, shares_by_cap)

    if shares <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="infeasible",
        )

    risk_dollars = shares * rps
    notional = shares * entry
    constraint = "risk" if shares_by_risk <= shares_by_cap else "position_cap"
    return SizingResult(
        shares=shares,
        risk_dollars=risk_dollars,
        risk_pct=risk_dollars / equity * 100,
        notional=notional,
        notional_pct=notional / equity * 100,
        feasible=True,
        constraint=constraint,
    )
