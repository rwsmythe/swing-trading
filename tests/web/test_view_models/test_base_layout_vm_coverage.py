"""Phase 10 Sub-bundle A T-A.7 — base-layout VM coverage regression.

Enforces plan §A.8 + §I.5 LOCK: every Phase 10 metrics-page VM in
``swing/web/view_models/metrics/*.py`` extends ``BaseLayoutVM`` and
therefore carries the 5 base-layout field names + the Phase 10
``unresolved_material_discrepancies_count`` field.

Excluded from the check (per plan §A.7 wording):
- ``BaseLayoutVM`` itself — that's the source-of-truth mixin.
- ``ConfidenceBadgeVM``, ``ProvisionalBadgeVM``, ``SuppressionRowVM`` —
  these are SUB-VMs (composed into page VMs), not page VMs themselves.

Cross-bundle pin (per plan §A.18 + dispatch brief §0.5 #13):
``test_existing_dashboard_vm_has_unresolved_material_field`` is SKIPPED in
Sub-bundle A; un-skipped in Sub-bundle E T-E.3 after the 6 existing
base-layout VMs are retrofit with the new field.
"""
from __future__ import annotations

import dataclasses
import importlib
import pkgutil

import pytest

from swing.web.view_models import metrics as metrics_vm_pkg

_REQUIRED_BASE_LAYOUT_FIELDS: tuple[str, ...] = (
    "session_date",
    "stale_banner",
    "price_source_degraded",
    "price_source_degraded_until",
    "ohlcv_source_degraded",
)

_PHASE10_BANNER_FIELD: str = "unresolved_material_discrepancies_count"

# Per plan §A.7 wording: SUB-VMs composed into page VMs are excluded from
# the base-layout-field check. Add to this set as new sub-VMs land in
# Sub-bundles B-E.
_SUB_VM_EXCLUSIONS: frozenset[str] = frozenset({
    "BaseLayoutVM",            # the mixin itself
    "ConfidenceBadgeVM",
    "ProvisionalBadgeVM",
    "SuppressionRowVM",
    # Sub-bundle B sub-VMs (composed into TradeProcessCardVM /
    # HypothesisProgressCardVM page VMs):
    "CohortTabVM",             # per-cohort tab descriptor on trade-process card
    "CohortProgressVM",        # per-cohort row on hypothesis-progress card
    # Sub-bundle C did NOT introduce any new sub-VMs ending in `VM` —
    # cohort-level data lives in :class:`swing.metrics.tier.CohortStatistics`
    # (outside the view_models/metrics auto-discovery scope), and
    # TierComparisonVM / DeviationOutcomeVM are themselves PAGE VMs
    # (extend BaseLayoutVM).
})


def _enumerate_metrics_page_vms() -> list[type]:
    """Return all @dataclass-decorated classes ending in `VM` across
    `swing/web/view_models/metrics/*.py`, excluding sub-VMs per
    ``_SUB_VM_EXCLUSIONS``.

    Discovery via ``pkgutil.iter_modules`` so subsequent sub-bundles
    landing new VMs (TradeProcessCardVM in B, etc.) are auto-included.
    """
    pkg_path = metrics_vm_pkg.__path__
    pkg_prefix = metrics_vm_pkg.__name__ + "."
    found: list[type] = []
    for module_info in pkgutil.iter_modules(pkg_path, prefix=pkg_prefix):
        mod = importlib.import_module(module_info.name)
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not isinstance(attr, type):
                continue
            if not dataclasses.is_dataclass(attr):
                continue
            if not attr_name.endswith("VM"):
                continue
            if attr_name in _SUB_VM_EXCLUSIONS:
                continue
            found.append(attr)
    return found


def test_all_metrics_vms_have_base_layout_fields():
    """Every metrics-page VM has all 5 base-layout fields + the Phase 10
    discrepancy-banner field. Auto-enumerates so future sub-bundles inherit
    the regression."""
    vms = _enumerate_metrics_page_vms()
    # At end of Sub-bundle A, only ``MetricsIndexVM`` exists (after T-A.8).
    # During Sub-bundle A intermediate landings (before T-A.8) the list may
    # be empty — the test then passes vacuously, which is by-design:
    # the discriminating behavior fires when ANY metrics-page VM is added.
    for vm_cls in vms:
        field_names = {f.name for f in dataclasses.fields(vm_cls)}
        for required in _REQUIRED_BASE_LAYOUT_FIELDS:
            assert required in field_names, (
                f"{vm_cls.__module__}.{vm_cls.__name__} missing required "
                f"base-layout field: {required}"
            )
        assert _PHASE10_BANNER_FIELD in field_names, (
            f"{vm_cls.__module__}.{vm_cls.__name__} missing Phase 10 banner "
            f"field: {_PHASE10_BANNER_FIELD}"
        )


@pytest.mark.skip(
    reason=(
        "Sub-bundle E T-E.3 adds unresolved_material_discrepancies_count to "
        "DashboardVM/PipelineVM/JournalVM/WatchlistVM/ConfigVM/PageErrorVM "
        "per plan §A.18 + §I.5; this test is the cross-bundle pin — "
        "un-skipped + verified passing in Sub-bundle E."
    ),
)
def test_existing_dashboard_vm_has_unresolved_material_field():
    """Cross-bundle pin per plan §A.18 + §I.5.

    Sub-bundle E T-E.3 adds the ``unresolved_material_discrepancies_count``
    field to the 6 existing base-layout VMs and un-skips this test. The
    skip reason names the un-skip schedule explicitly.
    """
    from swing.web.view_models.dashboard import DashboardVM
    field_names = {f.name for f in dataclasses.fields(DashboardVM)}
    assert _PHASE10_BANNER_FIELD in field_names, (
        f"DashboardVM missing Phase 10 banner field: {_PHASE10_BANNER_FIELD}"
    )
