"""Phase 7 dataclass shape regression tests.

Verifies T3 + C.14 outcomes:
- Trade drops status; gains state + ~24 new fields.
- Fill dataclass mirrors fills schema.
- Exit dataclass DELETED (C.14): see ``test_phase7_shim_removal`` for
  the ImportError discriminating regression tests.
"""
from __future__ import annotations

from dataclasses import fields

from swing.data.models import Fill, Trade


def test_trade_dataclass_drops_status_adds_state():
    """Trade no longer has status; has state + 23 Phase 7 fields."""
    field_names = {f.name for f in fields(Trade)}
    assert "status" not in field_names, "status must be dropped"
    assert "state" in field_names
    expected_phase7_fields = {
        "trade_origin", "pre_trade_locked_at", "current_size", "current_avg_cost",
        "last_fill_at", "thesis", "why_now", "invalidation_condition",
        "expected_scenario", "premortem_technical", "premortem_market_sector",
        "premortem_execution", "premortem_additional",
        "event_risk_present", "event_handling", "event_type", "event_date",
        "gap_risk_present", "gap_risk_handling", "emotional_state_pre_trade",
        "market_regime", "catalyst", "catalyst_other_description",
    }
    missing = expected_phase7_fields - field_names
    assert not missing, f"missing Phase 7 fields: {sorted(missing)}"


def test_fill_dataclass_shape():
    """Fill mirrors fills schema (16 fields post-Phase-13 T2.SB1 widening).

    Phase 13 T2.SB1 (migration 0020) added 4 Theme 3 auto-fill provenance
    fields: ``fill_origin`` + ``schwab_source_value_json`` +
    ``operator_corrected_value_json`` + ``auto_fill_audit_at`` per spec
    §3.4 + §6.4 + plan §A.14 paired-atomic-landing LOCK.
    """
    field_names = {f.name for f in fields(Fill)}
    expected = {
        "fill_id", "trade_id", "fill_datetime", "action", "quantity", "price",
        "reason", "rule_based", "fees", "manual_entry_confidence",
        "reconciliation_status", "tos_match_id",
        # Phase 13 T2.SB1 widening:
        "fill_origin", "schwab_source_value_json",
        "operator_corrected_value_json", "auto_fill_audit_at",
    }
    assert field_names == expected


# Phase 7 Sub-C C.14: the ``Exit`` dataclass stub was DELETED. The
# regression test asserting its removal lives in
# ``tests/data/test_phase7_shim_removal.py`` (ImportError discriminating).
