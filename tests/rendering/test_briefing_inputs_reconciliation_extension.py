"""T-C.8 — BriefingInputs.reconciliation_* fields tests.

Per plan §D.8 — 2 new optional fields default to 0; back-compat with
existing call sites preserved.
"""
from __future__ import annotations

from swing.rendering.briefing import BriefingInputs


def _make_minimal_inputs(**overrides) -> BriefingInputs:
    base = dict(
        action_session_date="2026-05-16",
        data_asof_date="2026-05-15",
        generated_at="2026-05-16T08:00:00",
        weather=None,
        weather_is_stale=True,
        equity=2000.0,
        open_count=0,
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="never",
        pipeline_is_stale=True,
        current_session_match=False,
        recommendations=[],
        open_trades=[],
    )
    base.update(overrides)
    return BriefingInputs(**base)


def test_briefing_inputs_default_reconciliation_counters_zero() -> None:
    """Existing call sites that don't pass the new fields work unchanged."""
    inputs = _make_minimal_inputs()
    assert inputs.reconciliation_pending_count == 0
    assert inputs.reconciliation_tier1_recent_count == 0


def test_briefing_inputs_pending_count_setter() -> None:
    inputs = _make_minimal_inputs(reconciliation_pending_count=3)
    assert inputs.reconciliation_pending_count == 3
    assert inputs.reconciliation_tier1_recent_count == 0


def test_briefing_inputs_tier1_recent_count_setter() -> None:
    inputs = _make_minimal_inputs(reconciliation_tier1_recent_count=7)
    assert inputs.reconciliation_tier1_recent_count == 7
    assert inputs.reconciliation_pending_count == 0


def test_briefing_inputs_both_counters_set() -> None:
    inputs = _make_minimal_inputs(
        reconciliation_pending_count=2,
        reconciliation_tier1_recent_count=5,
    )
    assert inputs.reconciliation_pending_count == 2
    assert inputs.reconciliation_tier1_recent_count == 5
