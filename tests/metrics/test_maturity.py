"""Phase 10 Sub-bundle D T-D.3 — maturity-stage (spec §3.5) tests.

Plan §G T-D.3 discriminating tests:
- per-position grouping over open trades.
- NULL ``planned_target_R`` → row renders with field=None (template
  shows "—" placeholder per spec §4.5).
- NULL ``trail_MA_candidate_price`` → ``trail_MA_eligibility_flag`` is
  None (NOT False).
- aggregate count by stage.
- zero open positions → empty list + empty count.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.maturity import (
    MaturityStageResult,
    MaturityStageRow,
    compute_maturity_stage,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_maturity.db")


def _seed_open_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    planned_target_R: float | None = None,  # noqa: N803
    current_stop: float = 9.0,
    current_size: float = 100.0,
    current_avg_cost: float = 10.0,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost, planned_target_R) VALUES (?, ?, '2026-05-01', "
        "10.0, 100, 9.0, ?, 'managing', 'S', 'I', "
        "'manual_off_pipeline', '2026-05-01T09:30:00', ?, ?, ?)",
        (trade_id, ticker, current_stop, current_size, current_avg_cost,
         planned_target_R),
    )


def _seed_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    data_asof_session: str = "2026-05-11",
    review_date: str = "2026-05-12",
    maturity_stage: str | None = "pre_+1.5R",
    open_MFE_R_to_date: float | None = 0.5,  # noqa: N803
    open_MAE_R_to_date: float | None = 0.3,  # noqa: N803  — stored as absolute value
    trail_MA_candidate_price: float | None = None,  # noqa: N803
    position_capital_utilization_pct: float | None = None,  # noqa: N803
    position_portfolio_heat_contribution_dollars: float | None = 100.0,  # noqa: N803
) -> None:
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, "
        " created_at, mfe_mae_precision_level, is_superseded, "
        " current_stop, current_size, current_avg_cost, "
        " open_MFE_R_to_date, open_MAE_R_to_date, "
        " position_capital_utilization_pct, "
        " position_portfolio_heat_contribution_dollars, "
        " maturity_stage, trail_MA_candidate_price) "
        "VALUES (?, 'daily_snapshot', ?, ?, ?, 'daily_approximate', 0, "
        " 9.0, 100, 10.0, ?, ?, ?, ?, ?, ?)",
        (
            trade_id, review_date, data_asof_session,
            review_date + "T08:00:00",
            open_MFE_R_to_date, open_MAE_R_to_date,
            position_capital_utilization_pct,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
        ),
    )


# ---------------------------------------------------------------------------
# Discriminating tests per plan §G T-D.3
# ---------------------------------------------------------------------------

def test_compute_maturity_stage_zero_open_returns_empty_list(conn):
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert isinstance(result, MaturityStageResult)
    assert result.rows == ()
    assert result.count_by_stage == {}


def test_compute_maturity_stage_per_position_groups(conn):
    """Each open trade yields exactly one row."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_open_trade(conn, trade_id=2, ticker="BBB")
    _seed_snapshot(conn, trade_id=1, maturity_stage="pre_+1.5R")
    _seed_snapshot(conn, trade_id=2, maturity_stage="+1.5R_to_+2R")
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert len(result.rows) == 2
    by_id = {r.trade_id: r for r in result.rows}
    assert by_id[1].maturity_stage == "pre_+1.5R"
    assert by_id[2].maturity_stage == "+1.5R_to_+2R"


def test_compute_maturity_stage_handles_null_planned_target_r(conn):
    """NULL planned_target_R → row.planned_target_R is None (template
    renders "—")."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA", planned_target_R=None)
    _seed_snapshot(conn, trade_id=1)
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert len(result.rows) == 1
    assert result.rows[0].planned_target_R is None


def test_compute_maturity_stage_renders_planned_target_r_when_set(conn):
    """Discriminating: 2.5 → exactly 2.5 (not the None branch)."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA", planned_target_R=2.5)
    _seed_snapshot(conn, trade_id=1)
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.rows[0].planned_target_R == 2.5


def test_compute_maturity_stage_handles_null_trail_ma_candidate_price(conn):
    """Plan §G T-D.3: NULL trail_MA_candidate_price → eligibility None,
    NOT False."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_snapshot(conn, trade_id=1, trail_MA_candidate_price=None,
                   open_MFE_R_to_date=2.5)  # mfe meets threshold
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    row = result.rows[0]
    assert row.trail_MA_eligibility_flag is None, (
        "Plan §G T-D.3 BINDING: returns None (NOT False) when "
        f"trail_MA_candidate_price is NULL; got: {row.trail_MA_eligibility_flag!r}"
    )


def test_compute_maturity_stage_trail_ma_eligibility_true(conn):
    """Discriminating: MFE>=2.0R AND stop<trail_ma_candidate → True."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA", current_stop=10.5)
    _seed_snapshot(conn, trade_id=1, open_MFE_R_to_date=2.5,
                   trail_MA_candidate_price=11.0)
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.rows[0].trail_MA_eligibility_flag is True


def test_compute_maturity_stage_trail_ma_eligibility_false_below_threshold(conn):
    """MFE<2.0R → False."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA", current_stop=10.5)
    _seed_snapshot(conn, trade_id=1, open_MFE_R_to_date=1.0,
                   trail_MA_candidate_price=11.0)
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.rows[0].trail_MA_eligibility_flag is False


def test_compute_maturity_stage_aggregates_count_by_stage(conn):
    """count_by_stage groups rows by maturity_stage value."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_open_trade(conn, trade_id=2, ticker="BBB")
    _seed_open_trade(conn, trade_id=3, ticker="CCC")
    _seed_snapshot(conn, trade_id=1, maturity_stage="pre_+1.5R")
    _seed_snapshot(conn, trade_id=2, maturity_stage="pre_+1.5R")
    _seed_snapshot(conn, trade_id=3, maturity_stage="+1.5R_to_+2R")
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.count_by_stage["pre_+1.5R"] == 2
    assert result.count_by_stage["+1.5R_to_+2R"] == 1


def test_compute_maturity_stage_open_trade_without_snapshot_renders_row(conn):
    """Edge case: open trade exists but no daily_management snapshot yet."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    # No snapshot row.
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.maturity_stage is None
    assert row.open_MFE_R_to_date is None
    assert row.trail_MA_eligibility_flag is None
    assert row.current_stop == 9.0  # from trades row
    # Capital-friction PROVISIONAL fallback applies.
    assert row.capital_denominator_badge == "PROVISIONAL"
    assert row.position_capital_utilization_pct is not None
    # 10.0 * 100 / 7500 * 100 = 13.333%
    assert abs(row.position_capital_utilization_pct - 13.333) < 0.01


def test_compute_maturity_stage_rows_sorted_by_stage(conn):
    """Rows ordered: pre_+1.5R, +1.5R_to_+2R, >=+2R_trail_eligible, closed."""
    _seed_open_trade(conn, trade_id=10, ticker="AAA")
    _seed_open_trade(conn, trade_id=20, ticker="BBB")
    _seed_open_trade(conn, trade_id=30, ticker="CCC")
    _seed_snapshot(conn, trade_id=10, maturity_stage=">=+2R_trail_eligible")
    _seed_snapshot(conn, trade_id=20, maturity_stage="pre_+1.5R")
    _seed_snapshot(conn, trade_id=30, maturity_stage="+1.5R_to_+2R")
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    order = [r.trade_id for r in result.rows]
    # 20 (pre) → 30 (mid) → 10 (>=+2R)
    assert order == [20, 30, 10]


def test_dataclass_post_init_rejects_invalid_inputs():
    """Lesson #1: __post_init__ validators reject NaN/inf + bad badge."""
    base_kwargs = dict(
        trade_id=1,
        ticker="AAA",
        maturity_stage="pre_+1.5R",
        open_MFE_R_to_date=None,
        open_MAE_R_to_date=None,
        current_stop=9.0,
        planned_target_R=None,
        trail_MA_candidate_price=None,
        trail_MA_eligibility_flag=None,
        position_capital_utilization_pct=None,
        position_portfolio_heat_contribution_dollars=None,
        capital_denominator_badge="PROVISIONAL",
    )
    with pytest.raises(ValueError, match="finite"):
        MaturityStageRow(
            **{**base_kwargs, "open_MFE_R_to_date": float("nan")}
        )
    with pytest.raises(ValueError, match="badge"):
        MaturityStageRow(
            **{**base_kwargs, "capital_denominator_badge": "BOGUS"}
        )
    with pytest.raises(ValueError, match="trade_id"):
        MaturityStageRow(**{**base_kwargs, "trade_id": 0})
    with pytest.raises(ValueError, match="ticker"):
        MaturityStageRow(**{**base_kwargs, "ticker": ""})


def test_compute_maturity_stage_returns_asof_date_field(conn):
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.asof_date == "2026-05-12"


def test_maturity_stage_row_provisional_badge_present_without_snapshot_row(conn):
    """Plan §A.6 §4.5 row-level resolution: no account_equity_snapshots
    row → PROVISIONAL badge."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_snapshot(conn, trade_id=1)
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.rows[0].capital_denominator_badge == "PROVISIONAL"


def test_maturity_stage_row_live_badge_when_snapshot_present(conn):
    """Plan §A.6 §4.5: snapshot row covers row_asof → LIVE."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_snapshot(conn, trade_id=1, data_asof_session="2026-05-11")
    conn.execute(
        "INSERT INTO account_equity_snapshots (snapshot_date, equity_dollars, "
        "source, recorded_at, recorded_by) VALUES (?, 2000.0, 'manual', ?, "
        "'test')",
        ("2026-05-11", "2026-05-11T08:00:00"),
    )
    result = compute_maturity_stage(conn, asof_date=date(2026, 5, 12))
    assert result.rows[0].capital_denominator_badge == "LIVE"
