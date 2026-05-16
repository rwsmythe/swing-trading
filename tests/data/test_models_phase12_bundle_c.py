"""Tests for Phase 12 Sub-bundle C dataclass extensions (T-A.2).

Covers:
- NEW ``ReconciliationCorrection`` dataclass (20 columns matching migration
  0019 ``reconciliation_corrections`` table verbatim).
- ``ReconciliationDiscrepancy.ambiguity_kind`` extension.
- ``ReviewLog.superseded_by_correction_id`` extension.
- ``SchwabApiCall.linked_correction_id`` extension (the dataclass lives at
  ``swing/data/models.py``; plan §A.7.4 grep targeted
  ``swing/integrations/schwab/models.py`` and matched no file, so this is a
  superset of the plan's acceptance criterion #4 — the column ALTER landed at
  T-A.1 and the dataclass exists, so the field is added here).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from swing.data.models import (
    ReconciliationCorrection,
    ReconciliationDiscrepancy,
    ReviewLog,
    SchwabApiCall,
)

# ---------------------------------------------------------------------------
# ReconciliationCorrection — NEW dataclass (plan §B.2 Step 2)
# ---------------------------------------------------------------------------


def _make_correction(**overrides):
    """Helper: construct a baseline ReconciliationCorrection."""
    base = dict(
        correction_id=1,
        discrepancy_id=41,
        correction_action="auto_applied",
        correction_choice=None,
        affected_table="fills",
        affected_row_id=9,
        field_name="price",
        pre_correction_value_json='{"price": 5.23}',
        source_canonical_value_json='{"price": 5.30}',
        applied_value_json='{"price": 5.30}',
        operator_truth_value_json=None,
        applied_at="2026-05-15T12:00:00.000",
        applied_by="auto",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=5,
        schwab_api_call_id=38,
        reconciliation_run_id=10,
        correction_reason="tier-1 auto-correct",
        notes=None,
    )
    base.update(overrides)
    return ReconciliationCorrection(**base)


def test_reconciliation_correction_dataclass_field_set():
    """All 20 fields of ReconciliationCorrection are populated + readable."""
    rc = _make_correction()

    assert rc.correction_id == 1
    assert rc.discrepancy_id == 41
    assert rc.correction_action == "auto_applied"
    assert rc.correction_choice is None
    assert rc.affected_table == "fills"
    assert rc.affected_row_id == 9
    assert rc.field_name == "price"
    assert rc.pre_correction_value_json == '{"price": 5.23}'
    assert rc.source_canonical_value_json == '{"price": 5.30}'
    assert rc.applied_value_json == '{"price": 5.30}'
    assert rc.operator_truth_value_json is None
    assert rc.applied_at == "2026-05-15T12:00:00.000"
    assert rc.applied_by == "auto"
    assert rc.correction_set_id is None
    assert rc.superseded_by_correction_id is None
    assert rc.risk_policy_id_at_correction == 5
    assert rc.schwab_api_call_id == 38
    assert rc.reconciliation_run_id == 10
    assert rc.correction_reason == "tier-1 auto-correct"
    assert rc.notes is None


def test_reconciliation_correction_has_exactly_20_columns():
    """Field count parity with migration 0019 ``reconciliation_corrections``
    (20 columns; spec §3.1 header said 19 but T-A.1 LOCKED 20 — V2.1 §VII.F
    amendment §I.16 banked)."""
    from dataclasses import fields

    field_names = [f.name for f in fields(ReconciliationCorrection)]
    assert len(field_names) == 20, (
        f"Expected 20 fields, got {len(field_names)}: {field_names}"
    )

    # Spot-check the exact field set + order matches plan §B.2 Step 2 lines
    # 805-824.
    expected = [
        "correction_id",
        "discrepancy_id",
        "correction_action",
        "correction_choice",
        "affected_table",
        "affected_row_id",
        "field_name",
        "pre_correction_value_json",
        "source_canonical_value_json",
        "applied_value_json",
        "operator_truth_value_json",
        "applied_at",
        "applied_by",
        "correction_set_id",
        "superseded_by_correction_id",
        "risk_policy_id_at_correction",
        "schwab_api_call_id",
        "reconciliation_run_id",
        "correction_reason",
        "notes",
    ]
    assert field_names == expected


def test_reconciliation_correction_is_frozen():
    """Audit/state-record dataclasses are frozen per project convention."""
    rc = _make_correction()
    with pytest.raises(FrozenInstanceError):
        rc.correction_id = 999  # type: ignore[misc]


def test_reconciliation_correction_operator_overridden_variant():
    """The three-tier resolution model: operator override path populates
    operator_truth_value_json + correction_choice."""
    rc = _make_correction(
        correction_id=2,
        correction_action="operator_overridden",
        correction_choice="operator_truth_overrides_schwab",
        operator_truth_value_json='{"price": 5.25}',
        applied_value_json='{"price": 5.25}',
        applied_by="operator",
        correction_set_id=1,
        correction_reason="operator-verified fill price differs from Schwab",
        notes="off-platform fill confirmation via brokerage statement screenshot",
    )
    assert rc.correction_action == "operator_overridden"
    assert rc.applied_by == "operator"
    assert rc.operator_truth_value_json == '{"price": 5.25}'
    assert rc.correction_set_id == 1


def test_reconciliation_correction_tier2_ambiguity_resolution_variant():
    """Tier-2 path: operator_resolved_ambiguity carries correction_choice."""
    rc = _make_correction(
        correction_id=3,
        correction_action="operator_resolved_ambiguity",
        correction_choice="schwab_canonical",
        applied_by="operator",
        correction_reason="operator picked schwab side after ambiguity prompt",
    )
    assert rc.correction_action == "operator_resolved_ambiguity"
    assert rc.correction_choice == "schwab_canonical"


# ---------------------------------------------------------------------------
# ReconciliationDiscrepancy — ambiguity_kind extension
# ---------------------------------------------------------------------------


def _make_discrepancy(**overrides):
    base = dict(
        discrepancy_id=None,
        run_id=10,
        discrepancy_type="entry_price_mismatch",
        trade_id=9,
        fill_id=12,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="DHC",
        field_name="price",
        expected_value_json='{"price": 5.23}',
        actual_value_json='{"price": 5.30}',
        delta_text="+$0.07",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T12:00:00.000",
    )
    base.update(overrides)
    return ReconciliationDiscrepancy(**base)


def test_reconciliation_discrepancy_ambiguity_kind_default_is_none():
    """``ambiguity_kind`` defaults to None (NULL in DB per migration 0019)."""
    d = _make_discrepancy()
    assert d.ambiguity_kind is None


def test_reconciliation_discrepancy_ambiguity_kind_can_be_set():
    """``ambiguity_kind`` is settable to any string value (CHECK enum
    enforcement lives at the SQL layer; the dataclass keeps the field open
    for future enum additions)."""
    d = _make_discrepancy(ambiguity_kind="multi_candidate_match")
    assert d.ambiguity_kind == "multi_candidate_match"


# ---------------------------------------------------------------------------
# ReviewLog — superseded_by_correction_id extension
# ---------------------------------------------------------------------------


def _make_review_log(**overrides):
    base = dict(
        review_id=1,
        review_type="weekly",
        period_start="2026-05-08",
        period_end="2026-05-15",
        scheduled_date="2026-05-15",
        completed_date="2026-05-15",
        skipped=False,
        duration_minutes=30,
        n_trades_reviewed=4,
        total_mistake_cost_R=0.5,
        total_lucky_violation_R=0.0,
        primary_lesson="watch volume on entry",
        next_period_focus="trail stops tighter",
        created_at="2026-05-15T18:00:00.000",
    )
    base.update(overrides)
    return ReviewLog(**base)


def test_review_log_superseded_by_correction_id_default_is_none():
    """``superseded_by_correction_id`` defaults to None."""
    rl = _make_review_log()
    assert rl.superseded_by_correction_id is None


def test_review_log_superseded_by_correction_id_can_be_set():
    """Field accepts positive int FK to reconciliation_corrections.correction_id."""
    rl = _make_review_log(superseded_by_correction_id=42)
    assert rl.superseded_by_correction_id == 42


# ---------------------------------------------------------------------------
# SchwabApiCall — linked_correction_id extension (plan §A.7.4 SchwabApiCall
# dataclass lives at ``swing/data/models.py`` — plan grep on
# ``swing/integrations/schwab/models.py`` would have missed it; the column
# ALTER landed at T-A.1, so the dataclass extension is in-scope here).
# ---------------------------------------------------------------------------


def _make_schwab_api_call(**overrides):
    base = dict(
        call_id=1,
        ts="2026-05-15T12:00:00.000",
        endpoint="accounts.linked",
        http_status=200,
        response_time_ms=150,
        rate_limit_remaining=119,
        signature_hash=None,
        status="success",
        error_message=None,
        linked_snapshot_id=None,
        linked_reconciliation_run_id=None,
        pipeline_run_id=None,
        surface="cli",
        environment="production",
    )
    base.update(overrides)
    return SchwabApiCall(**base)


def test_schwab_api_call_linked_correction_id_default_is_none():
    """``linked_correction_id`` defaults to None per migration 0019 column add."""
    call = _make_schwab_api_call()
    assert call.linked_correction_id is None


def test_schwab_api_call_linked_correction_id_can_be_set():
    """Field accepts positive int FK to reconciliation_corrections.correction_id."""
    call = _make_schwab_api_call(linked_correction_id=7)
    assert call.linked_correction_id == 7
