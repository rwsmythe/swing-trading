"""Field validation — hard-refuse + soft-warn boundaries per V1 field."""
from __future__ import annotations

import pytest

from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_all,
    validate_field,
)


# --- Registry shape ---


def test_registry_has_three_v1_fields():
    paths = {s.path for s in FIELD_REGISTRY}
    assert paths == {
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    }


# --- chase_factor: hard-refuse [0, 0.10]; soft-warn > 0.02 ---

def test_chase_factor_hard_refuse_negative():
    r = validate_field("web.chase_factor", "-0.01")
    assert r.hard_errors and not r.soft_warnings


def test_chase_factor_hard_refuse_above_max():
    r = validate_field("web.chase_factor", "0.11")
    assert r.hard_errors and not r.soft_warnings


def test_chase_factor_inside_hard_bound_soft_warn_above_2pct():
    r = validate_field("web.chase_factor", "0.05")
    assert not r.hard_errors and r.soft_warnings


def test_chase_factor_inside_both_no_issues():
    r = validate_field("web.chase_factor", "0.015")
    assert not r.hard_errors and not r.soft_warnings


# --- chart_top_n_watch: hard-refuse [1, 50]; soft-warn > 25 ---

def test_chart_top_n_watch_hard_refuse_zero():
    r = validate_field("pipeline.chart_top_n_watch", "0")
    assert r.hard_errors


def test_chart_top_n_watch_hard_refuse_above_50():
    r = validate_field("pipeline.chart_top_n_watch", "51")
    assert r.hard_errors


def test_chart_top_n_watch_inside_hard_bound_soft_warn_above_25():
    r = validate_field("pipeline.chart_top_n_watch", "30")
    assert not r.hard_errors and r.soft_warnings


def test_chart_top_n_watch_inside_both_no_issues():
    r = validate_field("pipeline.chart_top_n_watch", "20")
    assert not r.hard_errors and not r.soft_warnings


# --- risk_equity_floor: hard-refuse < 0; soft-warn outside [1000, 25000] ---

def test_risk_equity_floor_hard_refuse_negative():
    r = validate_field("account.risk_equity_floor", "-1.0")
    assert r.hard_errors


def test_risk_equity_floor_soft_warn_below_1000():
    r = validate_field("account.risk_equity_floor", "500.0")
    assert not r.hard_errors and r.soft_warnings


def test_risk_equity_floor_soft_warn_above_25000():
    r = validate_field("account.risk_equity_floor", "30000.0")
    assert not r.hard_errors and r.soft_warnings


def test_risk_equity_floor_inside_both_no_issues():
    r = validate_field("account.risk_equity_floor", "10000.0")
    assert not r.hard_errors and not r.soft_warnings


# --- Coercion ---

def test_coerce_chase_factor_str_to_float():
    assert coerce_value("web.chase_factor", "0.02") == 0.02
    assert isinstance(coerce_value("web.chase_factor", "0.02"), float)


def test_coerce_chart_top_n_str_to_int():
    assert coerce_value("pipeline.chart_top_n_watch", "15") == 15
    assert isinstance(coerce_value("pipeline.chart_top_n_watch", "15"), int)


def test_coerce_int_field_rejects_non_integer_float_string():
    """Codex R1 Major 3 — '15.5' rejected (not integer-valued)."""
    with pytest.raises(ValueError):
        coerce_value("pipeline.chart_top_n_watch", "15.5")


def test_coerce_int_field_accepts_integer_valued_float_string():
    """Codex R1 Major 3 — '15.0' accepted (browser-friendly UX)."""
    assert coerce_value("pipeline.chart_top_n_watch", "15.0") == 15
    assert isinstance(coerce_value("pipeline.chart_top_n_watch", "15.0"), int)


def test_coerce_invalid_string_raises():
    with pytest.raises(ValueError):
        coerce_value("web.chase_factor", "not-a-number")


# --- validate_all (form submit: all 3 at once) ---

def test_validate_all_happy_path():
    r = validate_all({
        "web.chase_factor": "0.015",
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    })
    assert not r.hard_errors and not r.soft_warnings


def test_validate_all_first_hard_refuse_short_circuits_write():
    """All hard errors are reported; write must still be refused at the route layer."""
    r = validate_all({
        "web.chase_factor": "0.5",  # hard fail
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    })
    assert r.hard_errors
    assert any("chase_factor" in e.field for e in r.hard_errors)


def test_validate_all_collects_multiple_hard_errors():
    r = validate_all({
        "web.chase_factor": "0.5",
        "pipeline.chart_top_n_watch": "100",
        "account.risk_equity_floor": "10000.0",
    })
    assert len(r.hard_errors) == 2
