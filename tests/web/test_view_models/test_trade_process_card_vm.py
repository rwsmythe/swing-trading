"""Phase 10 Sub-bundle B T-B.2 — TradeProcessCardVM tests."""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.honesty import SuppressedMetric
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.metrics.trade_process_card import (
    ALL_COHORTS_KEY,
    CohortTabVM,
    TradeProcessCardVM,
    build_trade_process_card_vm,
)


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_tpc.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


@pytest.fixture
def conn_factory(cfg):
    def _factory():
        return sqlite3.connect(cfg.paths.db_path)
    return _factory


def _seed_full_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    exit_price: float,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    state: str = "closed",
    pre_trade_locked_at: str = "2026-04-01T09:30:00",
    last_fill_at: str = "2026-04-08T15:30:00",
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, last_fill_at) VALUES "
        "(?, ?, '2026-04-01', ?, ?, ?, ?, ?, 'S', 'I', "
        "'manual_off_pipeline', ?, ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, state, pre_trade_locked_at, initial_shares,
            hypothesis_label, last_fill_at,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, ?, 'entry', ?, ?, 'unreconciled')",
        (trade_id, pre_trade_locked_at, initial_shares, entry_price),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, ?, 'exit', ?, ?, 'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )
    conn.commit()


def test_vm_renders_4_cohort_tabs_plus_all_toggle(cfg, conn_factory) -> None:
    """4 hypothesis_registry cohorts + 1 All toggle = 5 tabs."""
    vm = build_trade_process_card_vm(cfg=cfg)
    assert isinstance(vm, TradeProcessCardVM)
    assert len(vm.cohort_tabs) == 6
    keys = [t.cohort_key for t in vm.cohort_tabs]
    assert ALL_COHORTS_KEY in keys
    # The 5 registered names appear in the tabs.
    registered = {t.cohort_key for t in vm.cohort_tabs if t.cohort_key != ALL_COHORTS_KEY}
    assert registered == {
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
        "Broad-watch baseline",
    }


def test_vm_default_active_tab_is_first_cohort(cfg, conn_factory) -> None:
    """Per spec §4.1 + plan §E Task B.2: default active = first cohort,
    NOT the "All closed trades" toggle."""
    vm = build_trade_process_card_vm(cfg=cfg)
    # The first cohort tab is active; the All toggle is non-default.
    active_tabs = [t for t in vm.cohort_tabs if t.is_active]
    assert len(active_tabs) == 1
    assert active_tabs[0].cohort_key != ALL_COHORTS_KEY
    # Specifically the first registry cohort (A+ baseline per migration 0008).
    assert active_tabs[0].cohort_key == "A+ baseline"
    assert vm.active_cohort_key == "A+ baseline"


def test_vm_operator_can_select_all_cohorts_via_query_param(
    cfg, conn_factory,
) -> None:
    """Per plan §E + §A.9: operator selects an active cohort via
    query-string. ``active_cohort_key=ALL_COHORTS_KEY`` selects the All
    toggle as active."""
    vm = build_trade_process_card_vm(
        cfg=cfg, active_cohort_key=ALL_COHORTS_KEY,
    )
    assert vm.active_cohort_key == ALL_COHORTS_KEY
    active_tabs = [t for t in vm.cohort_tabs if t.is_active]
    assert active_tabs[0].cohort_key == ALL_COHORTS_KEY


def test_vm_unknown_active_cohort_key_falls_back_to_first(
    cfg, conn_factory,
) -> None:
    """Operator-supplied cohort key that does not match any tab falls
    back to FIRST cohort (defensive — query-string tampering / stale
    bookmarks)."""
    vm = build_trade_process_card_vm(
        cfg=cfg, active_cohort_key="completely-unknown-cohort",
    )
    assert vm.active_cohort_key == "A+ baseline"


def test_vm_empty_cohorts_render_suppression_per_tab(cfg, conn_factory) -> None:
    """Per spec §A.16 + §I.14: every tab renders gracefully at n=0;
    every Class A/B/C metric is suppressed."""
    vm = build_trade_process_card_vm(cfg=cfg)
    # All 5 tabs at n=0 (no trades seeded) — each metric on each tab is
    # a SuppressedMetric.
    for tab in vm.cohort_tabs:
        assert tab.n_closed == 0
        assert isinstance(tab.metrics.realized_R.value, SuppressedMetric)
        assert isinstance(tab.metrics.win_rate.value, SuppressedMetric)
        assert isinstance(tab.metrics.profit_factor.value, SuppressedMetric)


def test_vm_carries_base_layout_fields(cfg, conn_factory) -> None:
    """BaseLayoutVM mixin coverage regression — every base-layout field
    is present + has its safe default OR populated value."""
    vm = build_trade_process_card_vm(cfg=cfg)
    assert isinstance(vm, BaseLayoutVM)
    # Required by BaseLayoutVM:
    assert vm.session_date  # non-empty
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.price_source_degraded_until is None
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0  # empty DB


def test_vm_tab_reflects_per_cohort_metrics(cfg, conn_factory) -> None:
    """Seed 5 trades in A+ baseline; assert the A+ tab carries the
    aggregate while other cohort tabs remain at n=0."""
    conn = conn_factory()
    with conn:
        for i in range(1, 6):
            _seed_full_trade(
                conn, trade_id=i, ticker=f"T{i}",
                hypothesis_label="A+ baseline",
                exit_price=11.0 + i * 0.1,
            )
    conn.close()

    vm = build_trade_process_card_vm(cfg=cfg)
    aplus_tab = next(t for t in vm.cohort_tabs if t.cohort_key == "A+ baseline")
    assert aplus_tab.n_closed == 5
    sub_tab = next(t for t in vm.cohort_tabs if t.cohort_key == "Sub-A+ VCP-not-formed")
    assert sub_tab.n_closed == 0
    # All tab aggregates: n_closed=5 (only A+ has trades).
    all_tab = next(t for t in vm.cohort_tabs if t.cohort_key == ALL_COHORTS_KEY)
    assert all_tab.n_closed == 5


def test_vm_unresolved_material_discrepancies_count_populated(
    cfg, conn_factory,
) -> None:
    """Per plan §A.18 + §I.5: VM populates the cross-bundle pin field
    via :func:`count_unresolved_material`."""
    conn = conn_factory()
    # Seed 1 open trade + 1 unresolved material discrepancy on it.
    with conn:
        _seed_full_trade(
            conn, trade_id=1, ticker="DSC",
            hypothesis_label="A+ baseline",
            exit_price=11.0, state="entered",  # open, not closed
        )
        # Insert a minimal reconciliation_run + a discrepancy row.
        conn.execute(
            "INSERT INTO reconciliation_runs (started_ts, source, "
            "state, period_start, period_end) VALUES "
            "('2026-05-12T09:00:00.000', 'manual', 'completed', "
            "'2026-05-01', '2026-05-12')",
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(run_id, discrepancy_type, trade_id, field_name, "
            "material_to_review, resolution, created_at) VALUES "
            "(?, 'stop_mismatch', 1, 'current_stop', "
            "1, 'unresolved', '2026-05-12T09:00:00.000')",
            (run_id,),
        )
    conn.close()

    vm = build_trade_process_card_vm(cfg=cfg)
    assert vm.unresolved_material_discrepancies_count == 1
