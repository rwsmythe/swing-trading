"""Phase 10 Sub-bundle D T-D.2 — CapitalFrictionVM tests.

Covers structure + plan §A.18 base-layout integration + plan §A.0.1
historical-disclosure footnote BINDING.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.capital import CapitalFrictionResult
from swing.web.view_models.metrics.capital_friction import (
    HISTORICAL_DISCLOSURE_FOOTNOTE,
    CapitalFrictionVM,
    build_capital_friction_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_cf.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def _seed_open_trade(
    conn: sqlite3.Connection, *, trade_id: int, ticker: str,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost) VALUES (?, ?, '2026-05-01', 10.0, 100, 9.0, "
        "9.0, 'managing', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-01T09:30:00', 100, 10.0)",
        (trade_id, ticker),
    )
    conn.commit()


def _seed_snapshot(conn: sqlite3.Connection) -> None:
    from datetime import datetime as _dt

    from swing.evaluation.dates import last_completed_session
    asof = last_completed_session(_dt.now())
    conn.execute(
        "INSERT INTO account_equity_snapshots (snapshot_date, equity_dollars, "
        "source, recorded_at, recorded_by) VALUES (?, 2500.0, 'manual', ?, "
        "'test')",
        (asof.isoformat(), asof.isoformat() + "T08:00:00"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Structure + base layout integration
# ---------------------------------------------------------------------------

def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_capital_friction_vm(cfg=cfg)
    assert isinstance(vm, CapitalFrictionVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_capital_friction_vm(cfg=cfg)
    assert vm.session_date
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0


def test_vm_result_is_capital_friction_result(cfg) -> None:
    vm = build_capital_friction_vm(cfg=cfg)
    assert isinstance(vm.result, CapitalFrictionResult)


def test_vm_carries_historical_disclosure_footnote_field(cfg) -> None:
    """Plan §A.0.1 + dispatch brief §0.10 BINDING: footnote text is verbatim."""
    vm = build_capital_friction_vm(cfg=cfg)
    expected = (
        "Trend computed from current trade state; historical points "
        "approximate where state has changed since the run."
    )
    assert vm.historical_disclosure_footnote == expected
    assert expected == HISTORICAL_DISCLOSURE_FOOTNOTE


def test_vm_requires_result_field() -> None:
    """Constructor validation rejects None ``result``."""
    with pytest.raises(ValueError, match="result"):
        CapitalFrictionVM(session_date="2026-05-12", result=None)


def test_vm_requires_non_empty_footnote() -> None:
    """Constructor rejects empty footnote text."""
    from datetime import date
    base_result = CapitalFrictionResult(
        asof_date="2026-05-12",
        current_capital_utilization_pct=None,
        current_portfolio_heat_pct=None,
        concurrent_open_positions=0,
        capital_cycle_time_days=None,
        latest_run_id=None,
        risk_feasibility_blocked_rate=None,
        risk_feasibility_blocked_rate_suppressed_text=None,
        capital_feasibility_pressure_index=None,
        capital_denominator_dollars=7500.0,
        capital_denominator_badge="PROVISIONAL",
        capital_denominator_badge_text="PROVISIONAL: placeholder",
        trend_runs=(),
        trend_suppressed=True,
        trend_suppressed_text="placeholder",
    )
    _ = date  # used to keep import for symmetry
    with pytest.raises(ValueError, match="footnote"):
        CapitalFrictionVM(
            session_date="2026-05-12", result=base_result,
            historical_disclosure_footnote="",
        )


# ---------------------------------------------------------------------------
# PROVISIONAL/LIVE dynamic-badge propagation tests
# ---------------------------------------------------------------------------

def test_vm_no_snapshot_renders_provisional_state(cfg, conn) -> None:
    """No snapshot row → result.capital_denominator_badge == PROVISIONAL."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    vm = build_capital_friction_vm(cfg=cfg)
    assert vm.result.capital_denominator_badge == "PROVISIONAL"
    assert vm.result.capital_denominator_dollars == 7500.0


def test_vm_with_snapshot_renders_live_state(cfg, conn) -> None:
    """Snapshot on-or-before today → result.capital_denominator_badge ==
    LIVE."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_snapshot(conn)
    vm = build_capital_friction_vm(cfg=cfg)
    assert vm.result.capital_denominator_badge == "LIVE"
    assert vm.result.capital_denominator_dollars == 2500.0
