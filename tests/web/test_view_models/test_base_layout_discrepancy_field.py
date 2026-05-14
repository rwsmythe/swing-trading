"""Phase 10 Sub-bundle E Task T-E.3 — per-VM unresolved-material field tests.

Each of the 6 EXISTING base-layout VMs (DashboardVM / PipelineVM /
JournalVM / WatchlistVM / ConfigPageVM / PageErrorVM) MUST carry the
``unresolved_material_discrepancies_count: int = 0`` field per plan §A.18
+ §I.5 LOCK + dispatch brief §0.11.

Additional VMs whose templates extend ``base.html.j2`` (ReviewVM /
CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM) also gain the
field as defense-in-depth per the CLAUDE.md "base.html.j2 is shared"
gotcha.
"""
from __future__ import annotations

import dataclasses

from swing.web.view_models.config import ConfigPageVM
from swing.web.view_models.dashboard import DashboardVM
from swing.web.view_models.error import PageErrorVM
from swing.web.view_models.journal import JournalVM
from swing.web.view_models.pipeline import PipelineVM
from swing.web.view_models.trades import (
    CadenceCompleteVM,
    ReviewsPendingVM,
    ReviewVM,
    TradeDetailVM,
)
from swing.web.view_models.watchlist import WatchlistVM

_FIELD: str = "unresolved_material_discrepancies_count"


def _field_names(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def test_dashboard_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(DashboardVM)


def test_pipeline_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(PipelineVM)


def test_journal_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(JournalVM)


def test_watchlist_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(WatchlistVM)


def test_config_vm_carries_unresolved_material_count():
    """Class name is ``ConfigPageVM`` (dispatch brief §0.11 said ``ConfigVM``)."""
    assert _FIELD in _field_names(ConfigPageVM)


def test_error_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(PageErrorVM)


# Additional VMs extending base.html.j2 (defense-in-depth):

def test_review_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(ReviewVM)


def test_cadence_complete_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(CadenceCompleteVM)


def test_reviews_pending_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(ReviewsPendingVM)


def test_trade_detail_vm_carries_unresolved_material_count():
    assert _FIELD in _field_names(TradeDetailVM)
