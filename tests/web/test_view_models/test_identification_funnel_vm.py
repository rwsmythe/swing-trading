"""Phase 10 Sub-bundle D T-D.6 — IdentificationFunnelVM tests."""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.funnel import IdentificationFunnelResult
from swing.web.view_models.metrics.capital_friction import (
    HISTORICAL_DISCLOSURE_FOOTNOTE,
)
from swing.web.view_models.metrics.identification_funnel import (
    IdentificationFunnelVM,
    build_identification_funnel_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_if.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_identification_funnel_vm(cfg=cfg)
    assert isinstance(vm, IdentificationFunnelVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_identification_funnel_vm(cfg=cfg)
    assert vm.session_date
    assert vm.unresolved_material_discrepancies_count == 0


def test_vm_result_is_identification_funnel_result(cfg) -> None:
    vm = build_identification_funnel_vm(cfg=cfg)
    assert isinstance(vm.result, IdentificationFunnelResult)


def test_vm_carries_historical_disclosure_footnote_same_as_capital_friction(
    cfg,
) -> None:
    """Plan §A.0.1 + dispatch brief §0.10 BINDING: SAME footnote text as
    CapitalFrictionVM — drift-free parity via the shared constant."""
    vm = build_identification_funnel_vm(cfg=cfg)
    expected = (
        "Trend computed from current trade state; historical points "
        "approximate where state has changed since the run."
    )
    assert vm.historical_disclosure_footnote == expected
    assert HISTORICAL_DISCLOSURE_FOOTNOTE == expected


def test_vm_requires_result_field() -> None:
    with pytest.raises(ValueError, match="result"):
        IdentificationFunnelVM(session_date="2026-05-12", result=None)
