"""Tests for ma_stack_short criterion (stack + rising)."""
from __future__ import annotations

from swing.evaluation.criteria.ma_stack_short import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_stack_and_rising_both_pass(sample_config):
    # Clean uptrend: each close higher than last → all MAs stacked and rising
    closes = [10.0 + i * 0.1 for i in range(100)]
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "pass"
    assert rising_r.result == "pass"


def test_stack_fails_when_inverted(sample_config):
    # Declining trend → 50MA > 20MA > 10MA (inverted)
    closes = [50.0 - i * 0.1 for i in range(100)]
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "fail"
    assert rising_r.result == "fail"


def test_na_when_too_short(sample_config):
    closes = [10.0] * 30  # need 55+
    ctx = _ctx_from_closes(closes, sample_config)
    stack_r, rising_r = evaluate(ctx)
    assert stack_r.result == "na"
    assert rising_r.result == "na"
