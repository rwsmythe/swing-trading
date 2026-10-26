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
    # D84 (CHARC F1 (3), E-a): the one-share risk and the budget that sized
    # this result, set by `compute_shares` on EVERY return from the same
    # expressions that sized it, so every surface states its zero from the
    # SizingResult it sized on. Defaulted: a constructed sentinel with no
    # sizable geometry (build.py's `_sizing_result`) carries None.
    risk_per_share: float | None = None
    max_risk_dollars: float | None = None


def compute_shares(
    *, entry: float, stop: float, equity: float,
    max_risk_pct: float, position_pct_cap: float,
) -> SizingResult:
    if stop >= entry:
        raise ValueError(f"stop must be < entry; got entry={entry}, stop={stop}")

    rps = entry - stop
    max_risk_dollars = equity * max_risk_pct

    if equity <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="no_equity",
            risk_per_share=rps, max_risk_dollars=max_risk_dollars,
        )

    shares_by_risk = math.floor(max_risk_dollars / rps) if rps > 0 else 0
    shares_by_cap = math.floor((equity * position_pct_cap) / entry) if entry > 0 else 0
    shares = min(shares_by_risk, shares_by_cap)

    if shares <= 0:
        return SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="infeasible",
            risk_per_share=rps, max_risk_dollars=max_risk_dollars,
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
        risk_per_share=rps,
        max_risk_dollars=max_risk_dollars,
    )


RISK_FLAG_MARKER = "RISK FLAG"


def risk_bound_zero(sizing: SizingResult) -> bool:
    """Is the RISK leg the zero? (D84 T7.2, landing with T1.)

    True iff the result is zero shares, carries both D84 fields, has a positive
    budget, and `floor(max_risk_dollars / risk_per_share) < 1` -- the SAME
    expression `compute_shares` sizes the risk leg with. `zero_share_line`
    calls this for its risk leg and the latch card's heading calls it too, so
    the line and the heading choose the leg through ONE test.
    """
    if sizing.shares != 0:
        return False
    if sizing.risk_per_share is None or sizing.max_risk_dollars is None:
        return False
    if sizing.max_risk_dollars <= 0 or sizing.risk_per_share <= 0:
        return False
    return math.floor(sizing.max_risk_dollars / sizing.risk_per_share) < 1


def zero_share_line(
    sizing: SizingResult | None = None, *, risk=None,
    basis_label: str | None = None, basis_price: float | None = None,
) -> str | None:
    """THE ONE zero-share formatter, two forms (D84 E-b, P1). Every output is
    ASCII.

    Exactly one of `sizing` / `risk` is given, else `ValueError`.

    MARKER form (`risk=` a `RiskInputs`): returns `RISK_FLAG_MARKER` iff the
    risk layer is FLAGGED, else None -- so a passing layer AND an EMPTY layer
    both return None (E-d reversed). It carries NO sizing numbers (P1).

    STATED-ZERO form (`sizing=`): `basis_label` is always required.
    `basis_price` may be None ONLY on the no-geometry branch, whose line never
    uses it; on any other branch None raises `ValueError`.
      - shares > 0: None (no quantity reads as a mandate);
      - `no_equity`: "0 shares: no equity recorded";
      - no sizable geometry (the D84 fields are None, build.py's sentinel):
        "Sizing infeasible: no valid <basis> basis for this geometry" -- it
        keeps "infeasible", because it is not a risk fail;
      - the RISK leg is the zero (`risk_bound_zero`): CHARC's flag text, the
        budget, the one-share risk, its multiple of the budget, and the basis;
      - otherwise the position cap is the zero leg.
    """
    if (sizing is None) == (risk is None):
        raise ValueError("zero_share_line takes exactly one of sizing= / risk=")
    if risk is not None:
        from swing.evaluation.scoring import risk_layer_flagged

        return RISK_FLAG_MARKER if risk_layer_flagged(risk) else None
    if not basis_label:
        raise ValueError("zero_share_line(sizing=...) requires basis_label")
    no_geometry = sizing.risk_per_share is None or sizing.max_risk_dollars is None
    if basis_price is None and not no_geometry:
        raise ValueError(
            "zero_share_line(sizing=...) requires basis_price unless the result "
            "carries no sizable geometry")
    if sizing.shares > 0:
        return None
    if sizing.constraint == "no_equity":
        return "0 shares: no equity recorded"
    if no_geometry:
        return f"Sizing infeasible: no valid {basis_label} basis for this geometry"
    if risk_bound_zero(sizing):
        budget = sizing.max_risk_dollars
        rps = sizing.risk_per_share
        return (
            f"0 shares at the ${budget:.2f} budget; 1 share risks ${rps:.2f} "
            f"({rps / budget:.1f}x budget) at {basis_label} {basis_price:.2f}; "
            "above budget if you proceed")
    return (
        f"0 shares: one share at {basis_label} {basis_price:.2f} exceeds the "
        "position cap")
