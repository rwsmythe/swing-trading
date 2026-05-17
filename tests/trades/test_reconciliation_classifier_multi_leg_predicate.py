"""Phase 12.5 #1 T-1.1 — pure predicate + recipe synthesizer for multi-leg
tier-1 auto-redirect.

Spec §4.3 (6 sub-conditions) + §6.1 (recipe shape) + §10 (case fixtures).

Predicate is a PURE function (no DB, no API, no logging). Operates over
``Mapping``-shaped candidates ONLY (F25 / L-W6) — plain dicts with key
``executions`` whose value is ``list[Mapping]`` of leg dicts carrying keys
``leg_id`` / ``price`` / ``quantity`` / ``time``.
"""
from __future__ import annotations

from typing import Any, Mapping

import pytest

from swing.trades.reconciliation_classifier import (
    _MULTI_LEG_PRICE_TOLERANCE,
    _MULTI_LEG_QTY_TOLERANCE,
    _multi_leg_auto_redirect_predicate,
    _synthesize_split_into_partials_recipe,
)


# ---------------------------------------------------------------------------
# Test fixture helpers (plain dict-shaped per F25 / L-W6)
# ---------------------------------------------------------------------------


def _leg(
    *,
    leg_id: int = 1,
    price: Any = 5.30,
    quantity: Any = 100.0,
    time: str = "2026-05-15T14:30:00+00:00",
) -> dict[str, Any]:
    return {
        "leg_id": leg_id,
        "price": price,
        "quantity": quantity,
        "time": time,
    }


def _candidate(
    *,
    order_id: str = "ORDER-1",
    executions: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    return {"order_id": order_id, "executions": executions}


# ---------------------------------------------------------------------------
# Tests — sub-condition coverage + spec §10 fixtures
# ---------------------------------------------------------------------------


def test_predicate_fires_on_n_eq_1_with_3_legs_aligned():
    # Case A: 1 candidate × 3 legs; journal qty=200, price=5.3025; VWAP=5.3025.
    candidates = [
        _candidate(
            order_id="ORDER-A1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.31, quantity=50.0),
                _leg(leg_id=3, price=5.30, quantity=50.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.3025,
    )
    assert ok is True
    assert reason is None


def test_predicate_fires_on_n_eq_2_with_1_leg_each():
    # Case B: 2 candidates × 1 leg each; journal qty=150, price=7.505.
    candidates = [
        _candidate(order_id="ORDER-B1", executions=[_leg(price=7.50, quantity=75.0)]),
        _candidate(order_id="ORDER-B2", executions=[_leg(price=7.51, quantity=75.0)]),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=150.0,
        journal_price=7.505,
    )
    assert ok is True
    assert reason is None


def test_predicate_fires_on_n_eq_2_with_multi_leg_each_5_total():
    # Case I: order #1 [3 legs $5.30/$5.31/$5.30 qty 100/50/50] + order #2
    # [2 legs $5.31/$5.30 qty 100/100]. total_qty=400; VWAP=$5.30375.
    candidates = [
        _candidate(
            order_id="ORDER-I1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.31, quantity=50.0),
                _leg(leg_id=3, price=5.30, quantity=50.0),
            ],
        ),
        _candidate(
            order_id="ORDER-I2",
            executions=[
                _leg(leg_id=1, price=5.31, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=400.0,
        journal_price=5.30375,
    )
    assert ok is True
    assert reason is None


def test_predicate_declines_on_per_leg_outlier():
    # Case C: 3 legs at $5.30, $5.30, $5.34 qty=100 each; journal qty=300,
    # price=5.313. VWAP=(530+530+534)/300=5.31333... ; leg #3 ($5.34) is
    # outside per-leg tolerance vs VWAP.
    candidates = [
        _candidate(
            order_id="ORDER-C1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
                _leg(leg_id=3, price=5.34, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=300.0,
        journal_price=5.313,
    )
    assert ok is False
    assert reason is not None
    assert "leg #3" in reason
    assert "5.34" in reason  # outlier price
    # VWAP delta should be present in reason for forensic transparency.
    assert "VWAP" in reason or "vwap" in reason


def test_predicate_declines_on_qty_sum_mismatch():
    # 2 legs qty=100 + 50 = 150 total; journal qty=200 → mismatch.
    candidates = [
        _candidate(
            order_id="ORDER-D1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=50.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "sum" in reason.lower()


def test_predicate_declines_on_vwap_journal_misalign():
    # Case E: VWAP $7.505 vs journal $7.55 → DECLINES at sub-condition 5.
    candidates = [
        _candidate(order_id="ORDER-E1", executions=[_leg(price=7.50, quantity=75.0)]),
        _candidate(order_id="ORDER-E2", executions=[_leg(price=7.51, quantity=75.0)]),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=150.0,
        journal_price=7.55,
    )
    assert ok is False
    assert reason is not None
    assert "VWAP" in reason or "vwap" in reason
    assert "journal" in reason.lower()
    # Delta value should be present for forensic transparency.
    assert "0.04" in reason or "0.045" in reason or "delta" in reason.lower()


def test_predicate_declines_on_missing_executions_on_one_candidate():
    # Case F: candidate #2 executions=None → DECLINES at sub-condition 1.
    candidates = [
        _candidate(order_id="ORDER-F1", executions=[_leg(price=5.30, quantity=100.0)]),
        _candidate(order_id="ORDER-F2", executions=None),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "ORDER-F2" in reason
    assert "no execution legs" in reason.lower()


def test_predicate_declines_on_empty_executions_on_one_candidate():
    # executions=[] → DECLINES at sub-condition 1.
    candidates = [
        _candidate(order_id="ORDER-G1", executions=[_leg(price=5.30, quantity=100.0)]),
        _candidate(order_id="ORDER-G2", executions=[]),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "ORDER-G2" in reason
    assert "no execution legs" in reason.lower()


def test_predicate_declines_on_bool_price_defensive():
    # Case G: leg.price=True (bool) → DECLINES at sub-condition 3.
    # isinstance(True, int) is True in Python; the predicate must reject bool
    # via explicit isinstance(x, bool) guard BEFORE the numeric check.
    candidates = [
        _candidate(
            order_id="ORDER-H1",
            executions=[
                _leg(leg_id=1, price=True, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "not numeric" in reason.lower()


def test_predicate_declines_on_nan_price_defensive():
    # Case H: leg.price=float('nan') → DECLINES at sub-condition 3.
    candidates = [
        _candidate(
            order_id="ORDER-I1",
            executions=[
                _leg(leg_id=1, price=float("nan"), quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "not positive finite" in reason.lower() or "not finite" in reason.lower()


def test_predicate_declines_on_negative_price_defensive():
    # leg.price=-5.30 → DECLINES at sub-condition 3.
    candidates = [
        _candidate(
            order_id="ORDER-J1",
            executions=[
                _leg(leg_id=1, price=-5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=0.0,
    )
    assert ok is False
    assert reason is not None
    # Must reject at sub-condition 3 (per-leg positive check), NOT at later
    # sub-conditions like VWAP-misalign.
    assert "not positive" in reason.lower() or "positive" in reason.lower()


def test_predicate_declines_on_zero_qty_defensive():
    # leg.quantity=0.0 → DECLINES at sub-condition 3 (positive check).
    candidates = [
        _candidate(
            order_id="ORDER-K1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=0.0),
                _leg(leg_id=2, price=5.30, quantity=100.0),
            ],
        ),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    assert "not positive" in reason.lower() or "positive" in reason.lower()


def test_predicate_declines_on_insufficient_total_legs():
    # n=1 with executions=[1 leg only] → DECLINES at sub-condition 2.
    candidates = [
        _candidate(order_id="ORDER-L1", executions=[_leg(price=5.30, quantity=100.0)]),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
    )
    assert ok is False
    assert reason is not None
    # Reason should cite total leg count or "at least 2" requirement.
    assert (
        "2" in reason
        or "total" in reason.lower()
        or "insufficient" in reason.lower()
    )


def test_predicate_consumes_dict_shaped_executions_only():
    # F25 + L-W6: predicate operates on plain dicts ONLY. Construct dict-shaped
    # candidates + assert predicate fires (positive path; tests the
    # Mapping[str, Any] contract end-to-end).
    candidates: list[Mapping[str, Any]] = [
        {
            "order_id": "ORDER-M1",
            "executions": [
                {
                    "leg_id": 1,
                    "price": 5.30,
                    "quantity": 100.0,
                    "time": "2026-05-15T14:30:00+00:00",
                },
                {
                    "leg_id": 2,
                    "price": 5.30,
                    "quantity": 100.0,
                    "time": "2026-05-15T14:31:00+00:00",
                },
            ],
        },
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.30,
    )
    assert ok is True
    assert reason is None


# ---------------------------------------------------------------------------
# Recipe synthesizer tests
# ---------------------------------------------------------------------------


def test_synthesize_recipe_shape_matches_spec_6_1():
    candidates = [
        _candidate(
            order_id="ORDER-N1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.31, quantity=50.0),
                _leg(leg_id=3, price=5.30, quantity=50.0),
            ],
        ),
    ]
    recipe = _synthesize_split_into_partials_recipe(candidates)
    assert set(recipe.keys()) == {
        "choice_code",
        "resolved_by",
        "applied_by_override",
        "correction_action_override",
        "payload",
    }
    assert recipe["choice_code"] == "split_into_partials"
    assert recipe["resolved_by"] == "auto_tier1_multi_leg"
    assert recipe["applied_by_override"] == "auto"
    assert recipe["correction_action_override"] == "auto_applied"
    payload = recipe["payload"]
    assert isinstance(payload, list)
    assert len(payload) == 3
    for entry in payload:
        assert set(entry.keys()) == {"qty", "price", "fill_datetime"}


def test_synthesize_recipe_payload_preserves_iso_time_string():
    iso_time = "2026-05-15T14:30:00+00:00"
    candidates = [
        _candidate(
            order_id="ORDER-O1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0, time=iso_time),
                _leg(leg_id=2, price=5.30, quantity=100.0, time=iso_time),
            ],
        ),
    ]
    recipe = _synthesize_split_into_partials_recipe(candidates)
    payload = recipe["payload"]
    assert payload[0]["fill_datetime"] == iso_time
    assert payload[1]["fill_datetime"] == iso_time
    assert isinstance(payload[0]["fill_datetime"], str)


def test_synthesize_recipe_payload_iteration_order_matches_concatenated_executions():
    # N=2 candidates with [3 legs]+[2 legs] → payload has 5 entries in
    # concatenation order; leg.quantity values mark order for assertion.
    candidates = [
        _candidate(
            order_id="ORDER-P1",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=10.0),
                _leg(leg_id=2, price=5.30, quantity=20.0),
                _leg(leg_id=3, price=5.30, quantity=30.0),
            ],
        ),
        _candidate(
            order_id="ORDER-P2",
            executions=[
                _leg(leg_id=4, price=5.30, quantity=40.0),
                _leg(leg_id=5, price=5.30, quantity=50.0),
            ],
        ),
    ]
    recipe = _synthesize_split_into_partials_recipe(candidates)
    payload = recipe["payload"]
    assert len(payload) == 5
    assert [entry["qty"] for entry in payload] == [10.0, 20.0, 30.0, 40.0, 50.0]


# ---------------------------------------------------------------------------
# Constants sanity check (cite spec §15.B locks)
# ---------------------------------------------------------------------------


def test_module_constants_match_spec_locks():
    assert _MULTI_LEG_PRICE_TOLERANCE == pytest.approx(0.01)
    assert _MULTI_LEG_QTY_TOLERANCE == pytest.approx(1e-9)
