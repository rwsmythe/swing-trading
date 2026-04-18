"""Tests for pullback criterion."""
from __future__ import annotations

from swing.evaluation.criteria.pullback import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_pullback_pass_shallow(sample_config):
    # Peak at 100, current at 90 → 10% pullback (<25% → pass)
    closes = [50.0] * 50 + list(range(50, 101)) + [95.0] * 10 + [90.0]
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_pullback_fail_deep(sample_config):
    # Peak at 100, current at 70 → 30% pullback
    closes = [50.0] * 50 + list(range(50, 101)) + [100.0] * 5 + [70.0]
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
