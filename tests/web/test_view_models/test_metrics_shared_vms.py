"""Phase 10 Sub-bundle A T-A.6 — shared metric VM dataclasses tests."""
from __future__ import annotations

import dataclasses

import pytest

from swing.web.view_models.metrics.shared import (
    BaseLayoutVM,
    ConfidenceBadgeVM,
    ProvisionalBadgeVM,
    SuppressionRowVM,
)


# ---------------------------------------------------------------------------
# BaseLayoutVM
# ---------------------------------------------------------------------------

def test_base_layout_vm_default_values():
    """All fields besides session_date have defaults."""
    vm = BaseLayoutVM(session_date="2026-05-13")
    assert vm.session_date == "2026-05-13"
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.price_source_degraded_until is None
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0


def test_base_layout_vm_carries_all_5_legacy_base_fields():
    """Field-name regression — every field name the existing
    base.html.j2 template dereferences must be present."""
    field_names = {f.name for f in dataclasses.fields(BaseLayoutVM)}
    for required in (
        "session_date",
        "stale_banner",
        "price_source_degraded",
        "price_source_degraded_until",
        "ohlcv_source_degraded",
    ):
        assert required in field_names, f"missing: {required}"


def test_base_layout_vm_carries_phase10_unresolved_material_field():
    """Per plan §A.18: new Phase 10 banner field on BaseLayoutVM."""
    field_names = {f.name for f in dataclasses.fields(BaseLayoutVM)}
    assert "unresolved_material_discrepancies_count" in field_names


def test_base_layout_vm_unresolved_material_field_default_zero():
    vm = BaseLayoutVM(session_date="2026-05-13")
    assert vm.unresolved_material_discrepancies_count == 0


def test_base_layout_vm_unresolved_material_field_populates():
    vm = BaseLayoutVM(
        session_date="2026-05-13",
        unresolved_material_discrepancies_count=5,
    )
    assert vm.unresolved_material_discrepancies_count == 5


def test_base_layout_vm_rejects_empty_session_date():
    with pytest.raises(ValueError, match="session_date must be non-empty"):
        BaseLayoutVM(session_date="")


def test_base_layout_vm_rejects_negative_discrepancy_count():
    with pytest.raises(ValueError, match="must be >= 0"):
        BaseLayoutVM(
            session_date="2026-05-13",
            unresolved_material_discrepancies_count=-1,
        )


def test_base_layout_vm_frozen():
    vm = BaseLayoutVM(session_date="2026-05-13")
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.session_date = "2026-05-14"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConfidenceBadgeVM
# ---------------------------------------------------------------------------

def test_confidence_badge_text_format():
    vm = ConfidenceBadgeVM(
        low_confidence=True,
        confidence_floor_warning=False,
        text="low confidence (n=4)",
    )
    assert vm.low_confidence is True
    assert vm.confidence_floor_warning is False
    assert vm.text == "low confidence (n=4)"


def test_confidence_badge_window_not_full_flag_default_false():
    """Codex R2 Minor #1: ConfidenceBadgeVM carries the spec §5.4
    'rolling window not yet at N' cadence flag with default False so
    Class A/B/C surfaces don't need to populate it."""
    vm = ConfidenceBadgeVM(
        low_confidence=False,
        confidence_floor_warning=False,
        text="",
    )
    assert vm.window_not_full_warning is False


def test_confidence_badge_window_not_full_flag_set_true():
    """When set True, the field renders the spec §5.4 cadence-only badge."""
    vm = ConfidenceBadgeVM(
        low_confidence=False,
        confidence_floor_warning=True,
        text="rolling window not yet at N=10",
        window_not_full_warning=True,
    )
    assert vm.window_not_full_warning is True


def test_confidence_badge_both_flags_compatible():
    """At our current n=5..20 state, BOTH flags can be True simultaneously.

    Spec §5 R3 M2 + R4 M1 decoupling discipline: low_confidence_warning
    (3 <= n < 5 band) and confidence_floor_warning (n < global floor)
    serve different purposes; their composition is up to the VM layer.
    """
    vm = ConfidenceBadgeVM(
        low_confidence=True,
        confidence_floor_warning=True,
        text="below confidence floor (n<20)",
    )
    assert vm.low_confidence is True
    assert vm.confidence_floor_warning is True


# ---------------------------------------------------------------------------
# ProvisionalBadgeVM
# ---------------------------------------------------------------------------

def test_provisional_badge_text_format():
    vm = ProvisionalBadgeVM(
        is_provisional=True,
        text="PROVISIONAL: $7,500 floor used as live-capital fallback "
             "(no snapshot ≤ 2026-05-13)",
    )
    assert vm.is_provisional is True
    assert "PROVISIONAL" in vm.text
    assert "$7,500" in vm.text


def test_provisional_badge_live_state():
    vm = ProvisionalBadgeVM(is_provisional=False, text="LIVE")
    assert vm.is_provisional is False
    assert vm.text == "LIVE"


# ---------------------------------------------------------------------------
# SuppressionRowVM
# ---------------------------------------------------------------------------

def test_suppression_row_format():
    vm = SuppressionRowVM(
        metric_name="win_rate",
        placeholder_text="[win_rate: n too low (current: 2, need: ≥3)]",
    )
    assert vm.metric_name == "win_rate"
    assert "n too low" in vm.placeholder_text


def test_suppression_row_rejects_empty_placeholder():
    with pytest.raises(ValueError, match="placeholder_text must be non-empty"):
        SuppressionRowVM(metric_name="win_rate", placeholder_text="")
