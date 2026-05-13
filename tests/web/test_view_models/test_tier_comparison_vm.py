"""Phase 10 Sub-bundle C T-C.2 — TierComparisonVM tests."""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.tier import (
    APLUS_COHORT,
    SUB_APLUS_COHORT,
    TAXONOMY_COHORTS,
    TierComparisonResult,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.metrics.tier_comparison import (
    TierComparisonVM,
    build_tier_comparison_vm,
)


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_tc.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    realized_pnl_dollars: float,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    last_fill_at: str = "2026-04-08T15:30:00",
) -> None:
    exit_price = entry_price + (realized_pnl_dollars / initial_shares)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, last_fill_at) VALUES "
        "(?, ?, '2026-04-01', ?, ?, ?, ?, 'closed', 'S', 'I', "
        "'manual_off_pipeline', '2026-04-01T09:30:00', ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, initial_shares, hypothesis_label, last_fill_at,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, '2026-04-01T09:30:00', "
        "'entry', ?, ?, 'unreconciled')",
        (trade_id, initial_shares, entry_price),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, ?, 'exit', ?, ?, "
        "'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )


# ---------------------------------------------------------------------------
# Structure + base layout integration
# ---------------------------------------------------------------------------

def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_tier_comparison_vm(cfg=cfg)
    assert isinstance(vm, TierComparisonVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.session_date
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0


def test_vm_result_is_tier_comparison_result(cfg) -> None:
    vm = build_tier_comparison_vm(cfg=cfg)
    assert isinstance(vm.result, TierComparisonResult)


def test_vm_renders_4_cohort_columns_in_taxonomy_order(cfg) -> None:
    """Per dispatch brief §0.5 #4 BINDING: taxonomy-locked to 4 cohorts."""
    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.result is not None
    seen = tuple(c.cohort_name for c in vm.result.cohorts)
    assert seen == TAXONOMY_COHORTS


def test_vm_requires_result_field() -> None:
    """TierComparisonVM rejects construction without a result."""
    with pytest.raises(ValueError, match="result must be supplied"):
        TierComparisonVM(session_date="2026-05-13")


# ---------------------------------------------------------------------------
# At-zero-trades rendering (spec §4.3 worked example)
# ---------------------------------------------------------------------------

def test_vm_at_zero_trades_all_cohorts_have_suppressed_cells(cfg) -> None:
    """Worked example from spec §4.3: at n=0 every cohort cell is
    suppressed + descriptor placeholder text fires."""
    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.result is not None
    for cohort in vm.result.cohorts:
        from swing.metrics.honesty import SuppressedMetric
        assert isinstance(cohort.win_rate, SuppressedMetric)
        assert isinstance(cohort.expectancy, SuppressedMetric)
    assert vm.result.overlap_descriptor_suppressed is True


def test_vm_at_zero_trades_relative_to_aplus_pct_all_none(cfg) -> None:
    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.result is not None
    for cohort_name in TAXONOMY_COHORTS:
        assert vm.result.cohort_relative_to_aplus_pct[cohort_name] is None


# ---------------------------------------------------------------------------
# With trades: cohort_relative_to_aplus_pct rendering
# ---------------------------------------------------------------------------

def test_vm_renders_relative_to_aplus_when_both_n_at_least_5(cfg, conn) -> None:
    """A+ n=5 with 2.0R per trade; Sub-A+ n=5 with 0.5R per trade.
    Bootstrap CI point of identical 2.0 samples is 2.0; ratio is 25%.
    """
    with conn:
        for i in range(5):
            _seed_trade(
                conn, trade_id=i + 1, ticker=f"A{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=200.0,  # 2.0R (risk_budget=$100)
                last_fill_at=f"2026-04-{i + 1:02d}T15:30:00",
            )
        for i in range(5):
            _seed_trade(
                conn, trade_id=100 + i, ticker=f"S{i}",
                hypothesis_label=SUB_APLUS_COHORT,
                realized_pnl_dollars=50.0,  # 0.5R
                last_fill_at=f"2026-04-{10 + i:02d}T15:30:00",
            )
    conn.close()

    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.result is not None
    sub_aplus_pct = vm.result.cohort_relative_to_aplus_pct[SUB_APLUS_COHORT]
    assert sub_aplus_pct == pytest.approx(25.0, abs=0.01)


# ---------------------------------------------------------------------------
# Orphan-cohort exclusion (taxonomy lock; dispatch brief §0.5 #4)
# ---------------------------------------------------------------------------

def test_vm_does_not_surface_orphan_labeled_trades_as_columns(cfg, conn) -> None:
    """Per dispatch brief §0.5 #4 + spec §4.3: orphan-labeled closed
    trades are EXCLUDED from the tier-comparison surface (visible only
    on the trade-process card per Sub-bundle B convention)."""
    with conn:
        _seed_trade(
            conn, trade_id=999, ticker="ORP",
            hypothesis_label="orphan-cohort",
            realized_pnl_dollars=100.0,
        )
    conn.close()
    vm = build_tier_comparison_vm(cfg=cfg)
    assert vm.result is not None
    cohort_names = {c.cohort_name for c in vm.result.cohorts}
    assert "orphan-cohort" not in cohort_names
    assert len(vm.result.cohorts) == 4
