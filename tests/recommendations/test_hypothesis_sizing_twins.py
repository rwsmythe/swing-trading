"""Sizing-twin pattern tests for hypothesis-recommendations expansion (Task 5.1).

Documents the discriminating contract that Task 5.2's `build_hyp_recs_expanded`
will use:

  sizing_risk = compute_shares(equity=sizing_equity(real_equity, floor), ...)
                — uses the artificial $7,500 risk floor when real balance < floor.
  sizing_cash = compute_shares(equity=real_equity,                      ...)
                — uses actual balance only (no floor).

When real balance < floor the two return STRICTLY DIFFERENT share counts
(test #1 vs #2). When real balance >= floor they collapse to the same count
(test #3). Remaining tests pin down the boundary cases (`no_equity`,
`infeasible`, `position_cap` binding) that the expanded VM will surface to
the operator.

NO production code is exercised here beyond the existing
`swing.recommendations.sizing.compute_shares` and `swing.trades.equity.sizing_equity`.
"""
from __future__ import annotations

import pytest

from swing.recommendations.sizing import compute_shares
from swing.trades.equity import sizing_equity


# ---------------------------------------------------------------------------
# Discriminating pair (mandatory contract).
#
# Inputs identical EXCEPT how `equity=` is computed. With balance=$1,200 below
# the $7,500 floor:
#   sizing_equity(real=1200, floor=7500) = 7500  → wider aperture for sizing_risk
#   sizing_cash uses 1200 directly               → narrower aperture
#
# Hand-derivation under compute_shares' formula (entry=$25, stop=$24.50,
# rps=$0.50, max_risk_pct=0.005, position_pct_cap=0.15):
#
#   sizing_risk @ equity=7500
#     shares_by_risk = floor(7500 * 0.005 / 0.50) = floor(75)   = 75
#     shares_by_cap  = floor(7500 * 0.15  / 25  ) = floor(45)   = 45
#     shares         = min(75, 45)                              = 45  (position_cap)
#
#   sizing_cash @ equity=1200
#     shares_by_risk = floor(1200 * 0.005 / 0.50) = floor(12)   = 12
#     shares_by_cap  = floor(1200 * 0.15  / 25  ) = floor(7.2)  = 7
#     shares         = min(12, 7)                               = 7   (position_cap)
#
# 45 != 7 — discriminating. Note: the upstream plan body (lines 1670-1856 of
# 2026-04-29-hyp-recs-trade-prep-expansion-plan.md) showed example numbers
# (18 vs 3 shares) that do not match the actual `compute_shares` implementation
# under those inputs; the test inputs here are chosen to produce a CORRECT
# discriminating pair against the live formula. The contract under test —
# sizing_risk.shares > sizing_cash.shares strictly when balance<floor — is
# what matters.
# ---------------------------------------------------------------------------

ENTRY_TWIN = 25.0
STOP_TWIN = 24.50
MAX_RISK_PCT = 0.005
POSITION_PCT_CAP = 0.15
FLOOR = 7500.0


def test_risk_based_uses_max_floor_when_balance_below_floor():
    """sizing_risk uses sizing_equity()=floor when real balance < floor."""
    real_balance = 1200.0
    equity_for_risk = sizing_equity(real_equity=real_balance, floor=FLOOR)
    assert equity_for_risk == FLOOR  # floor wins

    sizing_risk = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=equity_for_risk,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    assert sizing_risk.feasible is True
    assert sizing_risk.shares == 45
    assert sizing_risk.constraint == "position_cap"


def test_cash_feasible_uses_balance_only_not_floor():
    """sizing_cash uses real balance directly — sizing_equity NOT applied."""
    real_balance = 1200.0
    sizing_cash = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=real_balance,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    assert sizing_cash.feasible is True
    assert sizing_cash.shares == 7
    assert sizing_cash.constraint == "position_cap"


def test_discriminating_pair_diverges_when_balance_below_floor():
    """Mandatory invariant: sizing_risk.shares > sizing_cash.shares strictly
    when real balance < floor. This is the core contract Task 5.2 surfaces."""
    real_balance = 1200.0
    sizing_risk = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN,
        equity=sizing_equity(real_equity=real_balance, floor=FLOOR),
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    sizing_cash = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=real_balance,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    assert sizing_risk.shares > sizing_cash.shares
    assert sizing_risk.shares == 45
    assert sizing_cash.shares == 7


def test_balance_above_floor_uses_balance_for_both():
    """When real balance >= floor, sizing_equity passes through and the twins
    collapse to identical results."""
    real_balance = 10_000.0
    assert real_balance > FLOOR
    equity_for_risk = sizing_equity(real_equity=real_balance, floor=FLOOR)
    assert equity_for_risk == real_balance  # passthrough — no floor applied

    sizing_risk = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=equity_for_risk,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    sizing_cash = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=real_balance,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    # Hand-derivation @ equity=10_000:
    #   shares_by_risk = floor(10_000 * 0.005 / 0.50) = 100
    #   shares_by_cap  = floor(10_000 * 0.15  / 25)   = 60
    #   shares = 60 (position_cap)
    assert sizing_risk.shares == sizing_cash.shares == 60
    assert sizing_risk.constraint == sizing_cash.constraint == "position_cap"
    assert sizing_risk.risk_dollars == pytest.approx(sizing_cash.risk_dollars)


def test_infeasible_when_one_share_exceeds_max_risk():
    """entry=$1000, stop=$999, max_risk_pct=0.0001 → max_risk_dollars=$0.12 at
    equity=$1200; rps=$1 → shares_by_risk = floor(0.12) = 0 → infeasible."""
    r = compute_shares(
        entry=1000.0, stop=999.0, equity=1200.0,
        max_risk_pct=0.0001, position_pct_cap=0.15,
    )
    assert r.shares == 0
    assert r.feasible is False
    assert r.constraint == "infeasible"


def test_no_equity_path():
    """equity=0 short-circuits to constraint='no_equity'."""
    r = compute_shares(
        entry=ENTRY_TWIN, stop=STOP_TWIN, equity=0.0,
        max_risk_pct=MAX_RISK_PCT, position_pct_cap=POSITION_PCT_CAP,
    )
    assert r.shares == 0
    assert r.feasible is False
    assert r.constraint == "no_equity"


def test_position_cap_actually_binds():
    """entry=$10, stop=$9.50, max_risk_pct=0.05, equity=$1000:
      shares_by_risk = floor(1000 * 0.05  / 0.50) = floor(100) = 100
      shares_by_cap  = floor(1000 * 0.15  / 10  ) = floor(15)  = 15
      shares = 15 (position_cap binds well below the risk ceiling).
    """
    r = compute_shares(
        entry=10.0, stop=9.50, equity=1000.0,
        max_risk_pct=0.05, position_pct_cap=0.15,
    )
    assert r.feasible is True
    assert r.shares == 15
    assert r.constraint == "position_cap"
    assert r.notional == pytest.approx(150.0)
