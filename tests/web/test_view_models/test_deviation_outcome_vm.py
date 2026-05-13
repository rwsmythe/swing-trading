"""Phase 10 Sub-bundle C T-C.3 — DeviationOutcomeVM tests."""
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
    DeviationOutcomeResult,
)
from swing.web.view_models.metrics.deviation_outcome import (
    DeviationOutcomeVM,
    build_deviation_outcome_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_do.db"
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
    last_fill_at: str = "2026-04-08T15:30:00",
) -> None:
    entry_price = 10.0
    initial_stop = 9.0
    initial_shares = 100
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
# Structure + base-layout integration
# ---------------------------------------------------------------------------

def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert isinstance(vm, DeviationOutcomeVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_renders_4_cohort_rows_in_taxonomy_order(cfg) -> None:
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.result is not None
    assert isinstance(vm.result, DeviationOutcomeResult)
    seen = tuple(r.cohort_name for r in vm.result.rows)
    assert seen == TAXONOMY_COHORTS


def test_vm_at_zero_trades_renders_all_rows_visible_but_row_suppressed(
    cfg,
) -> None:
    """Per spec §4.7 SURFACE LOCK: cohort row stays VISIBLE at n<5 (the
    operator needs to see the registered cohort even at n<5); only the
    relative-pct cell is suppressed."""
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.result is not None
    for row in vm.result.rows:
        assert row.row_suppressed is True
        assert row.expectancy_relative_to_aplus_pct is None
        # Decision-criterion text + doctrine-deviation class still rendered.
        assert row.decision_criterion_evaluation_text
        assert row.doctrine_deviation_class


def test_vm_requires_result_field() -> None:
    with pytest.raises(ValueError, match="result must be supplied"):
        DeviationOutcomeVM(session_date="2026-05-13")


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.session_date
    assert vm.stale_banner is None
    assert vm.unresolved_material_discrepancies_count == 0


# ---------------------------------------------------------------------------
# Decision-criterion seed text (spec §3.7 R1 M4 LOCK)
# ---------------------------------------------------------------------------

def test_vm_decision_criterion_text_is_seed_text_verbatim(cfg) -> None:
    """Migration 0008 seed text rendered verbatim — no automated synthesis."""
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.result is not None
    by_name = {r.cohort_name: r for r in vm.result.rows}
    assert by_name[APLUS_COHORT].decision_criterion_evaluation_text == (
        "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
    )
    assert by_name[SUB_APLUS_COHORT].decision_criterion_evaluation_text == (
        "Confirm negative mean R-multiple"
    )


# ---------------------------------------------------------------------------
# With trades: expectancy_relative_to_aplus_pct delta rendering
# ---------------------------------------------------------------------------

def test_vm_renders_relative_pct_as_negative_delta_below_baseline(
    cfg, conn,
) -> None:
    """A+ expectancy=2.0R; Sub-A+ expectancy=0.5R → delta = -75.0%."""
    with conn:
        for i in range(5):
            _seed_trade(
                conn, trade_id=i + 1, ticker=f"A{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=200.0,
                last_fill_at=f"2026-04-{i + 1:02d}T15:30:00",
            )
        for i in range(5):
            _seed_trade(
                conn, trade_id=100 + i, ticker=f"S{i}",
                hypothesis_label=SUB_APLUS_COHORT,
                realized_pnl_dollars=50.0,
                last_fill_at=f"2026-04-{10 + i:02d}T15:30:00",
            )
    conn.close()
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.result is not None
    sub_aplus = next(
        r for r in vm.result.rows if r.cohort_name == SUB_APLUS_COHORT
    )
    assert sub_aplus.row_suppressed is False
    assert sub_aplus.expectancy_relative_to_aplus_pct == pytest.approx(
        -75.0, abs=0.01,
    )


def test_vm_does_not_surface_orphan_labeled_trades_as_rows(cfg, conn) -> None:
    """Per dispatch brief §0.5 #4 BINDING: orphan-labeled trades NOT
    rendered."""
    with conn:
        _seed_trade(
            conn, trade_id=999, ticker="ORP",
            hypothesis_label="orphan-cohort",
            realized_pnl_dollars=100.0,
        )
    conn.close()
    vm = build_deviation_outcome_vm(cfg=cfg)
    assert vm.result is not None
    seen = {r.cohort_name for r in vm.result.rows}
    assert "orphan-cohort" not in seen
    assert len(vm.result.rows) == 4
