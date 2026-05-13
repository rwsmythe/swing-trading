"""Phase 10 Sub-bundle D T-D.4 — MaturityStageVM tests."""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.maturity import MaturityStageResult
from swing.web.view_models.metrics.maturity_stage import (
    MaturityStageVM,
    build_maturity_stage_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_ms.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_maturity_stage_vm(cfg=cfg)
    assert isinstance(vm, MaturityStageVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_maturity_stage_vm(cfg=cfg)
    assert vm.session_date
    assert vm.unresolved_material_discrepancies_count == 0


def test_vm_result_is_maturity_stage_result(cfg) -> None:
    vm = build_maturity_stage_vm(cfg=cfg)
    assert isinstance(vm.result, MaturityStageResult)


def test_vm_requires_result_field() -> None:
    with pytest.raises(ValueError, match="result"):
        MaturityStageVM(session_date="2026-05-12", result=None)


def test_vm_at_zero_open_renders_empty_rows(cfg) -> None:
    vm = build_maturity_stage_vm(cfg=cfg)
    assert vm.result.rows == ()


def test_vm_with_open_trade_populates_row(cfg, conn) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost) VALUES (1, 'AAA', '2026-05-01', 10.0, 100, 9.0, "
        "9.0, 'managing', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-01T09:30:00', 100, 10.0)"
    )
    conn.commit()
    vm = build_maturity_stage_vm(cfg=cfg)
    assert len(vm.result.rows) == 1
    assert vm.result.rows[0].ticker == "AAA"
