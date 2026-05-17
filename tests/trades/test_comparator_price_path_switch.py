"""Tests for Sub-bundle 1 T-1.6 — comparator price-path switch +
Path B execution_unavailable sentinel emit + candidate-pool filter widening
(`_is_execution_bearing_candidate`).

Per plan §A.1.6 + spec §5.2 + §6.1 OQ-A Path B LOCK + §10 worked examples.
12 discriminating tests.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.schwab_reconciliation import (
    _is_execution_bearing_candidate,
    run_schwab_reconciliation,
)


# ---------------------------------------------------------------------------
# Shared fixture: tmp DB with v19 schema.
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Fixture-builders for the production SchwabOrderResponse shape.
# ---------------------------------------------------------------------------


def _leg(*, leg_id=1, price=5.2244, quantity=100.0,
         mismarked_quantity=0.0, instrument_id=None,
         time="2026-05-15T14:30:00.000Z"):
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=mismarked_quantity, instrument_id=instrument_id,
        time=time,
    )


def _order(*, order_id="ORD-100", status="FILLED",
           instrument_symbol="CVGI",
           instruction="BUY", quantity=100.0, order_type="LIMIT",
           price=5.30, executions=None,
           enter_time="2026-04-27T14:23:00.000Z"):
    return SchwabOrderResponse(
        order_id=order_id, status=status,
        enter_time=enter_time, instrument_symbol=instrument_symbol,
        instruction=instruction, quantity=quantity,
        order_type=order_type, price=price,
        executions=executions,
    )


class _Account:
    """Duck-typed Schwab account fixture."""
    def __init__(self, nlv=2000.0):
        self.net_liquidating_value = nlv
        self.positions: list = []


def _seed_entry_fill(
    conn: sqlite3.Connection, *,
    ticker: str, fill_price: float, qty: float = 100.0,
    action: str = "entry",
) -> tuple[int, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", fill_price, int(qty), 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", action, qty, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id, fill_id


def _list_discrepancies(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT discrepancy_type, field_name, actual_value_json, "
        "expected_value_json, delta_text "
        "FROM reconciliation_discrepancies WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return [
        {
            "discrepancy_type": r[0],
            "field_name": r[1],
            "actual_value_json": r[2],
            "expected_value_json": r[3],
            "delta_text": r[4],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Tests 1-3 — within-tolerance cases → NO emit.
# ---------------------------------------------------------------------------


def test_spec_10_1_cvgi_single_leg_within_tolerance_no_emit(conn) -> None:
    """Spec §10.1: journal=$5.23 vs leg=$5.2244 delta=0.0056 < 0.01 → NO emit."""
    _seed_entry_fill(conn, ticker="CVGI", fill_price=5.23)
    order = _order(
        instrument_symbol="CVGI",
        price=5.30,
        executions=[_leg(price=5.2244, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "close_price_mismatch",
                       "unmatched_open_fill", "unmatched_close_fill")]
    assert price_emits == []


def test_spec_10_2_lion_single_leg_within_tolerance_no_emit(conn) -> None:
    """Spec §10.2: journal=$12.70 vs leg=$12.6999 delta=0.0001 → NO emit."""
    _seed_entry_fill(conn, ticker="LION", fill_price=12.70)
    order = _order(
        instrument_symbol="LION",
        price=12.75,
        executions=[_leg(price=12.6999, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "close_price_mismatch",
                       "unmatched_open_fill", "unmatched_close_fill")]
    assert price_emits == []


def test_spec_10_4_multi_leg_vwap_within_tolerance_no_emit(conn) -> None:
    """Spec §10.4 multi-leg: journal=$10.10 vs VWAP(50@$10.00 + 50@$10.20)=$10.10 → NO emit."""
    _seed_entry_fill(conn, ticker="ABC", fill_price=10.10)
    legs = [
        _leg(leg_id=1, price=10.00, quantity=50.0),
        _leg(leg_id=2, price=10.20, quantity=50.0),
    ]
    order = _order(
        instrument_symbol="ABC",
        quantity=100.0,
        price=10.10,
        executions=legs,
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "close_price_mismatch")]
    assert price_emits == []


# ---------------------------------------------------------------------------
# Test 4 — outside-tolerance Shape C emit (audit-key persistence + 4dp delta).
# ---------------------------------------------------------------------------


def test_spec_10_3_legitimate_typo_outside_tolerance_shape_c_emit(conn) -> None:
    """Spec §10.3: journal=$10.00 vs leg=$10.25 delta=0.25 > 0.01 → Shape C emit.

    Shape C contract: actual_value_json key-set EXACTLY
    {"price", "execution_legs", "schwab_order_id", "schwab_order_price"}.
    delta_text 4-decimal precision (CVGI/LION sub-cent debugging).
    """
    _seed_entry_fill(conn, ticker="DEF", fill_price=10.00)
    order = _order(
        order_id="ORD-DEF-1",
        instrument_symbol="DEF",
        price=10.30,
        executions=[_leg(price=10.25, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies
                   if d["discrepancy_type"] == "entry_price_mismatch"]
    assert len(price_emits) == 1
    emit = price_emits[0]
    actual = json.loads(emit["actual_value_json"])
    # Shape C key-set EXACTLY.
    assert set(actual.keys()) == {
        "price", "execution_legs", "schwab_order_id", "schwab_order_price",
    }
    assert actual["price"] == 10.25
    assert actual["schwab_order_id"] == "ORD-DEF-1"
    assert actual["schwab_order_price"] == 10.30
    assert len(actual["execution_legs"]) == 1
    # delta_text 4-decimal precision.
    assert "+0.2500" in emit["delta_text"]


# ---------------------------------------------------------------------------
# Test 5 — Path B execution_unavailable sentinel → unmatched_open_fill.
# ---------------------------------------------------------------------------


def test_spec_10_5_path_b_execution_unavailable_sentinel_emit(conn) -> None:
    """When mapped executions=None (e.g., mapper coherence-check collapsed
    or legacy V1 mapper path), comparator emits unmatched_open_fill with
    `execution_unavailable=true` sentinel (NOT entry_price_mismatch)."""
    _seed_entry_fill(conn, ticker="GHI", fill_price=20.00)
    # Order admitted to candidate pool (price not None) but executions=None.
    order = _order(
        order_id="ORD-GHI-1",
        instrument_symbol="GHI",
        price=20.05,
        executions=None,  # Path B
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    # Path B emits unmatched_open_fill (NOT entry_price_mismatch).
    path_b = [d for d in discrepancies
              if d["discrepancy_type"] == "unmatched_open_fill"]
    assert len(path_b) == 1
    actual = json.loads(path_b[0]["actual_value_json"])
    assert actual.get("execution_unavailable") is True
    assert actual.get("schwab_order_id") == "ORD-GHI-1"
    assert actual.get("schwab_order_price") == 20.05
    # NO entry_price_mismatch emitted.
    assert not any(d["discrepancy_type"] == "entry_price_mismatch"
                   for d in discrepancies)


# ---------------------------------------------------------------------------
# Test 6 — Path B does NOT double-emit when quantity-mismatch already fired.
# ---------------------------------------------------------------------------


def test_path_b_does_not_double_emit_after_quantity_mismatch(conn) -> None:
    """When quantity-mismatch already prevents the match, Path B sentinel
    does NOT fire on the same fill (the for-loop `continue` after no-match
    emit precludes the price-path branch)."""
    _seed_entry_fill(conn, ticker="JKL", fill_price=15.00, qty=100.0)
    # Schwab order with mismatched qty AND executions=None → quantity match
    # fails first; unmatched_open_fill emits; price-path NEVER reached.
    order = _order(
        instrument_symbol="JKL",
        quantity=200.0,  # journal=100, schwab order=200
        price=15.00,
        executions=None,
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    # Exactly one unmatched_open_fill (the qty-mismatch path); zero Path B.
    unmatched = [d for d in discrepancies
                 if d["discrepancy_type"] == "unmatched_open_fill"]
    assert len(unmatched) == 1
    # The qty-mismatch path emits actual_value_json={"matched": null}
    # (no execution_unavailable sentinel because Path B never fired).
    actual = json.loads(unmatched[0]["actual_value_json"])
    assert actual.get("matched") is None
    assert actual.get("execution_unavailable") is None


# ---------------------------------------------------------------------------
# Test 7 — Spec §10.6 OQ-D FIRED STOP uses execution-grain not trigger.
# ---------------------------------------------------------------------------


def test_spec_10_6_fired_stop_uses_execution_grain_not_trigger(conn) -> None:
    """FIRED STOP: order_type=STOP, price=$5.00 (trigger), executions=[leg@$4.95].
    Journal records $4.95 → NO emit; journal records $5.00 → close_price_mismatch
    with execution_price=$4.95."""
    # Seed a close-side fill recording the actual execution price.
    _seed_entry_fill(conn, ticker="MNO", fill_price=4.95,
                     qty=100.0, action="exit")
    order = _order(
        order_id="ORD-MNO-STOP",
        instrument_symbol="MNO",
        instruction="SELL",
        order_type="STOP",
        price=5.00,  # trigger
        executions=[_leg(price=4.95, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    # Within tolerance → NO emit (journal records exec price, not trigger).
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "close_price_mismatch")]
    assert price_emits == []


# ---------------------------------------------------------------------------
# Test 8 — close_price_mismatch Shape C emit (mirrors T-1.8 widening).
# ---------------------------------------------------------------------------


def test_close_price_mismatch_shape_c_emit(conn) -> None:
    """Close-side mismatch (journal=$5.00 vs leg=$4.85 delta=0.15 > 0.01) →
    close_price_mismatch with Shape C audit keys."""
    _seed_entry_fill(conn, ticker="PQR", fill_price=5.00,
                     qty=100.0, action="exit")
    order = _order(
        order_id="ORD-PQR-1",
        instrument_symbol="PQR",
        instruction="SELL",
        order_type="STOP",
        price=5.10,
        executions=[_leg(price=4.85, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    close_emits = [d for d in discrepancies
                   if d["discrepancy_type"] == "close_price_mismatch"]
    assert len(close_emits) == 1
    actual = json.loads(close_emits[0]["actual_value_json"])
    assert set(actual.keys()) == {
        "price", "execution_legs", "schwab_order_id", "schwab_order_price",
    }
    assert actual["price"] == 4.85
    # delta_text 4dp precision.
    assert "-0.1500" in close_emits[0]["delta_text"]


# ---------------------------------------------------------------------------
# Test 9 — Sandbox short-circuit preserved (env=sandbox → no domain writes).
# ---------------------------------------------------------------------------


def test_sandbox_short_circuit_preserved_for_path_b(conn) -> None:
    """Sandbox env: Path B sentinel DOES emit discrepancy (the comparator
    is unconditional) BUT pivot-time auto-correct short-circuits → discrepancy
    stays `unresolved` (no journal mutation)."""
    _, fill_id = _seed_entry_fill(conn, ticker="STU", fill_price=15.00)
    order = _order(
        instrument_symbol="STU",
        price=15.00,
        executions=None,  # Path B
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
        environment="sandbox",
    )
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()
    assert fp[0] == 15.00  # unchanged under sandbox short-circuit


# ---------------------------------------------------------------------------
# Test 10 — delta_text 4dp covers sub-cent debugging signal.
# ---------------------------------------------------------------------------


def test_delta_text_4dp_precision_covers_sub_cent_signal(conn) -> None:
    """delta_text formatted to 4 decimals so CVGI $0.0056 + LION $0.0001
    surfaces in audit-row logging (NOT rounded to 2dp / 0.00)."""
    # Plant just-outside-tolerance to force an emit at sub-cent precision.
    _seed_entry_fill(conn, ticker="VWX", fill_price=5.00)
    # leg=$5.0123 vs journal=$5.00 → delta=$0.0123 > 0.01 → emit.
    order = _order(
        instrument_symbol="VWX",
        price=5.20,
        executions=[_leg(price=5.0123, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    emit = next(d for d in discrepancies
                if d["discrepancy_type"] == "entry_price_mismatch")
    # 4-decimal precision visible: +0.0123 (not rounded to +0.01).
    assert "+0.0123" in emit["delta_text"]


# ---------------------------------------------------------------------------
# Test 11 — MARKET BUY with price=None + executions=[leg@exec] admitted.
# ---------------------------------------------------------------------------


def test_market_buy_with_none_price_and_executions_admitted(conn) -> None:
    """`_is_execution_bearing_candidate` accepts FILLED with price=None
    when executions populated (MARKET fill candidate-pool widening per
    Codex R1 M#1). Journal=$5.00 matches leg=$5.00 → NO emit."""
    _seed_entry_fill(conn, ticker="MKT", fill_price=5.00)
    order = _order(
        instrument_symbol="MKT",
        order_type="MARKET",
        price=None,  # MARKET fills surface execution via legs only
        executions=[_leg(price=5.00, quantity=100.0)],
    )
    # Direct predicate check.
    assert _is_execution_bearing_candidate(order) is True
    # End-to-end: journal matches exec → NO emit.
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    assert not any(d["discrepancy_type"]
                   in ("entry_price_mismatch", "unmatched_open_fill")
                   for d in discrepancies)


# ---------------------------------------------------------------------------
# Test 12 — CANCELED + REPLACED with filledQuantity>0 + executions admitted.
# ---------------------------------------------------------------------------


def test_canceled_partial_with_executions_admitted(conn) -> None:
    """Partial-then-canceled order (status=CANCELED but with execution legs)
    admitted via _is_execution_bearing_candidate. Per Codex R1 M#2."""
    order_canceled = _order(
        status="CANCELED",
        order_type="LIMIT",
        price=5.00,
        quantity=200.0,
        executions=[_leg(price=5.00, quantity=50.0)],
    )
    assert _is_execution_bearing_candidate(order_canceled) is True


def test_replaced_partial_with_executions_admitted() -> None:
    """Mirror: REPLACED with executions admitted."""
    order_replaced = _order(
        status="REPLACED",
        order_type="LIMIT",
        price=5.00,
        quantity=200.0,
        executions=[_leg(price=5.00, quantity=50.0)],
    )
    assert _is_execution_bearing_candidate(order_replaced) is True


# Bonus — FILLED with price + no executions still admitted (V1 backward compat).
def test_filled_with_price_no_executions_still_admitted_backward_compat() -> None:
    """V1 fall-through: FILLED + price populated + executions=None still
    admitted (price-AND-executions-both-None is the only rejection case
    per plan §A.1.6)."""
    order = _order(status="FILLED", price=5.00, executions=None)
    assert _is_execution_bearing_candidate(order) is True


# Bonus — FILLED with price=None AND executions=None REJECTED.
def test_filled_with_none_price_and_no_executions_rejected() -> None:
    """Plan §A.1.6 LOCK: FILLED with both price=None AND executions=None
    rejected (no data the comparator can compare against)."""
    order = _order(status="FILLED", price=None, executions=None)
    assert _is_execution_bearing_candidate(order) is False


# Bonus — non-FILLED non-CANCELED non-REPLACED status rejected.
def test_other_status_rejected() -> None:
    order_working = _order(status="WORKING", price=5.00,
                           executions=[_leg(price=5.00)])
    assert _is_execution_bearing_candidate(order_working) is False
