"""Near-trigger detection rule (asymmetric window from legacy briefing)."""
from __future__ import annotations

from swing.recommendations.near_trigger import is_near_trigger, pct_from_pivot


def test_within_below_window():
    assert is_near_trigger(price=99.5, entry_target=100.0)


def test_within_above_window():
    assert is_near_trigger(price=100.3, entry_target=100.0)


def test_outside_above_window():
    assert not is_near_trigger(price=100.7, entry_target=100.0)


def test_outside_below_window():
    assert not is_near_trigger(price=98.8, entry_target=100.0)


def test_custom_thresholds():
    assert is_near_trigger(price=100.4, entry_target=100.0, above_pct=0.5, below_pct=2.0)
    assert not is_near_trigger(price=100.6, entry_target=100.0, above_pct=0.5, below_pct=2.0)


def test_pct_from_pivot_signed():
    assert pct_from_pivot(price=99.0, entry_target=100.0) == -1.0
    assert pct_from_pivot(price=101.0, entry_target=100.0) == 1.0
    assert pct_from_pivot(price=100.0, entry_target=100.0) == 0.0


def test_zero_target_raises():
    import pytest
    with pytest.raises(ValueError):
        pct_from_pivot(price=10.0, entry_target=0.0)
