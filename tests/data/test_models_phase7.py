"""Phase 7 dataclass shape regression tests.

Verifies T3 outcomes:
- Trade drops status; gains state + ~24 new fields.
- Fill dataclass mirrors fills schema.
- Exit dataclass removed (or stub raising RuntimeError; T6 finalizes).
"""
from __future__ import annotations

from dataclasses import fields

import pytest

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
    """Fill mirrors fills schema (12 fields)."""
    field_names = {f.name for f in fields(Fill)}
    expected = {
        "fill_id", "trade_id", "fill_datetime", "action", "quantity", "price",
        "reason", "rule_based", "fees", "manual_entry_confidence",
        "reconciliation_status", "tos_match_id",
    }
    assert field_names == expected


def test_exit_dataclass_removed():
    """Exit dataclass is removed in T3; data migrated to Fill via 0014.

    Stub-form decision: many production modules (`swing/journal/flags.py`,
    `swing/journal/stats.py`, `swing/trades/exit.py`, `swing/trades/equity.py`,
    `swing/trades/review.py`, `swing/data/repos/trades.py`) still
    `from swing.data.models import Exit` at import-time. Removing the symbol
    cleanly would ImportError at test-collection across many modules,
    blocking T6's incremental rewrite. Instead T3 leaves a stub class whose
    constructor raises RuntimeError; T6 owns the consumer rewrites and the
    final stub deletion.
    """
    from swing.data import models as mod

    assert hasattr(mod, "Exit"), "Exit symbol retained as stub for T6 incremental rewrite"
    with pytest.raises(RuntimeError, match="removed"):
        mod.Exit(
            id=None, trade_id=1, exit_date="2026-01-01", exit_price=10.0,
            shares=1, reason="test", realized_pnl=0.0, r_multiple=0.0, notes=None,
        )
