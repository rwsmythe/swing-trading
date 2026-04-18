"""Tests for proximity criterion."""
from __future__ import annotations

from swing.evaluation.criteria.proximity import evaluate
from tests.evaluation.criteria.test_prior_trend import _ctx_from_closes


def test_proximity_pass_when_close_to_20ma(sample_config):
    closes = [100.0] * 30
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_proximity_fail_when_extended(sample_config):
    closes = [100.0] * 25 + [120.0] * 5
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"


def test_proximity_na_too_short(sample_config):
    closes = [100.0] * 10
    ctx = _ctx_from_closes(closes, sample_config)
    r = evaluate(ctx)
    assert r.result == "na"
