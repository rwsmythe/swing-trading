"""Phase 12.5 #2 T-2.7 — Pass A retrofit regression tests.

Verifies that ``BaseLayoutVM`` AND the 13 standalone-field VMs (plus the
2 already-shipped reconcile VMs) declare a ``banner_resolve_link`` field
with default ``None`` and validate the field shape (None OR non-empty
path starting with ``/``).

Per L-W5 LOCK: the field is additive default-None so existing callers
continue to work without change. The validator additionally rejects
empty string + non-slash-prefixed strings + non-str/non-None types.
"""
from __future__ import annotations

import dataclasses

import pytest


# ---------------------------------------------------------------------------
# 1. BaseLayoutVM direct assertions.
# ---------------------------------------------------------------------------


def test_base_layout_vm_banner_resolve_link_defaults_to_none() -> None:
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    vm = BaseLayoutVM(session_date="2026-05-18")
    assert vm.banner_resolve_link is None


def test_base_layout_vm_banner_resolve_link_post_init_accepts_url() -> None:
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    vm = BaseLayoutVM(
        session_date="2026-05-18",
        banner_resolve_link="/reconcile/discrepancy/99/resolve",
    )
    assert vm.banner_resolve_link == "/reconcile/discrepancy/99/resolve"


def test_base_layout_vm_banner_resolve_link_post_init_rejects_empty_string() -> None:
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    with pytest.raises(ValueError, match="banner_resolve_link"):
        BaseLayoutVM(session_date="2026-05-18", banner_resolve_link="")


def test_base_layout_vm_banner_resolve_link_post_init_rejects_non_slash_prefix() -> None:
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    with pytest.raises(ValueError, match="banner_resolve_link"):
        BaseLayoutVM(
            session_date="2026-05-18",
            banner_resolve_link="reconcile/discrepancy/99/resolve",
        )


def test_base_layout_vm_banner_resolve_link_post_init_rejects_non_str_type() -> None:
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    with pytest.raises(TypeError, match="banner_resolve_link"):
        BaseLayoutVM(session_date="2026-05-18", banner_resolve_link=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Parametrized field-presence + default introspection across 13 standalone
#    VMs (those not inheriting BaseLayoutVM) + the 2 already-shipped reconcile
#    VMs.
# ---------------------------------------------------------------------------


def _all_standalone_vm_classes() -> list[type]:
    """Return the (class, module-friendly-name) for every standalone VM."""
    from swing.web.view_models.config import ConfigPageVM
    from swing.web.view_models.dashboard import DashboardVM
    from swing.web.view_models.error import PageErrorVM
    from swing.web.view_models.journal import JournalVM
    from swing.web.view_models.pipeline import PipelineVM
    from swing.web.view_models.reconcile import (
        ReconcileDiscrepancyErrorVM,
        ReconcileDiscrepancyResolveVM,
    )
    from swing.web.view_models.schwab import (
        SchwabSetupErrorVM,
        SchwabSetupVM,
        SchwabStatusVM,
    )
    from swing.web.view_models.trades import (
        CadenceCompleteVM,
        ReviewVM,
        ReviewsPendingVM,
        TradeDetailVM,
    )
    from swing.web.view_models.watchlist import WatchlistVM

    return [
        WatchlistVM,
        ConfigPageVM,
        ReviewVM,
        CadenceCompleteVM,
        ReviewsPendingVM,
        TradeDetailVM,
        JournalVM,
        DashboardVM,
        PageErrorVM,
        PipelineVM,
        SchwabSetupVM,
        SchwabStatusVM,
        SchwabSetupErrorVM,
        # Already shipped at T-2.2 + T-2.5 — should still satisfy this contract.
        ReconcileDiscrepancyResolveVM,
        ReconcileDiscrepancyErrorVM,
    ]


@pytest.mark.parametrize("vm_cls", _all_standalone_vm_classes(), ids=lambda c: c.__name__)
def test_standalone_vm_has_banner_resolve_link_field_with_default_none(
    vm_cls: type,
) -> None:
    """Every standalone-field VM declares ``banner_resolve_link: str | None = None``.

    Asserted via ``dataclasses.fields`` introspection so the field shape is
    pinned independent of constructor argument order.
    """
    fields_by_name = {f.name: f for f in dataclasses.fields(vm_cls)}
    assert "banner_resolve_link" in fields_by_name, (
        f"{vm_cls.__name__} missing required banner_resolve_link field "
        f"(Phase 12.5 #2 T-2.7 Pass A retrofit)"
    )
    field = fields_by_name["banner_resolve_link"]
    assert field.default is None, (
        f"{vm_cls.__name__}.banner_resolve_link default must be None; "
        f"got {field.default!r}"
    )


def test_base_layout_vm_has_banner_resolve_link_field_with_default_none() -> None:
    """``BaseLayoutVM`` itself also carries the field (inheriting VMs inherit
    it; standalone VMs declare it explicitly per F11/F21 LOCK)."""
    from swing.web.view_models.metrics.shared import BaseLayoutVM

    fields_by_name = {f.name: f for f in dataclasses.fields(BaseLayoutVM)}
    assert "banner_resolve_link" in fields_by_name
    assert fields_by_name["banner_resolve_link"].default is None
