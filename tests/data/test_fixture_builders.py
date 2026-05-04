"""Fixture-behavior tests for the canonical make_trade builder.

Lives in test_fixture_builders.py (not conftest.py) per pytest convention:
conftest is support code; test functions belong in test_*.py modules.

Sub-A T0 dual-field window: Trade has BOTH status and state. T3 drops status.
"""
from __future__ import annotations

from tests.conftest import make_trade


def test_make_trade_default_state_entered():
    """Default fixture state is 'entered' — covers the common 'open trade' test
    case that previously relied solely on status='open'."""
    t = make_trade(ticker="TEST")
    assert t.state == "entered"


def test_make_trade_closed_explicit():
    """Caller sets state='closed' for closed-trade fixtures."""
    t = make_trade(ticker="TEST", state="closed")
    assert t.state == "closed"


def test_make_trade_status_alongside_state_in_A0_window():
    """During the A.0–A.3 window, Trade exposes BOTH status and state.
    A.3 will drop status; this test will be MODIFIED in A.3 to assert
    `not hasattr(t, 'status')`."""
    t = make_trade(ticker="TEST", state="entered")
    assert hasattr(t, "status")  # still present during A.0
    assert hasattr(t, "state")
