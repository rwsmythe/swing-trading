"""Sub-bundle 1 T-1.13 — End-to-end integration test against operator-
recorded Schwab cassettes + hand-rolled fixtures (MARKET BUY + Path B
sentinel + synthetic Shape C typo).

Per plan §A.1.13 acceptance criteria. 6 tests covering 3 cassette-driven
order types (LIMIT BUY + LIMIT SELL + STOP FIRED) + 3 hand-rolled
fixtures (MARKET BUY + synthetic typo Shape C + Path B sentinel).

CASSETTE DEVIATION (per operator cassette session 2026-05-16; banked at
commit ec498fe): operator history contains no MARKET BUY and no
STOP_LIMIT FIRED fills. The 4th REQUIRED cassette is therefore replaced
with a hand-rolled MARKET BUY fixture; STOP_LIMIT FIRED is skipped per
plan §F.1 stretch lock.

Each test asserts:
- Comparator emit shape (no false-positive for matched-execution-price
  cases; 1 Shape C discrepancy for legitimate-typo case).
- Classifier disposition (tier-1 with execution-grain correction_target
  for legitimate-typo case).
- Audit-key persistence on discrepancy row via
  `SELECT json_extract(actual_value_json, '$.execution_legs') FROM
  reconciliation_discrepancies WHERE id = ?`.

Marked `slow` because the cassette-driven paths exercise the full
reconciliation pipeline end-to-end against persisted YAML fixtures.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

try:
    import yaml
except ImportError:
    yaml = None

from swing.data.db import ensure_schema
from swing.integrations.schwab.mappers import map_orders_to_fill_candidates
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.reconciliation_classifier import (
    _SHAPE_C_EXPECTED_KEYS,
    classify_discrepancy,
)
from swing.trades.schwab_reconciliation import run_schwab_reconciliation


pytestmark = pytest.mark.slow


CASSETTE_DIR = (
    Path(__file__).resolve().parents[1]
    / "integrations" / "cassettes" / "schwab"
)


# ---------------------------------------------------------------------------
# Cassette load + order extraction helpers.
# ---------------------------------------------------------------------------


def _load_cassette_orders(cassette_path: Path) -> list[dict[str, Any]]:
    """Load a vcrpy YAML cassette + return the response body's `orders` list.

    Operator-recorded cassettes ship at
    `tests/integrations/cassettes/schwab/test_e2e_<order_type>.yaml`. Each
    contains exactly one `account_orders(...)` HTTP interaction whose
    response body is a JSON array of Schwab order dicts.
    """
    if yaml is None:
        pytest.skip("PyYAML not installed; cassette load skipped")
    if not cassette_path.exists():
        pytest.skip(f"cassette absent: {cassette_path.name}")
    with cassette_path.open(encoding="utf-8") as f:
        cassette = yaml.safe_load(f)
    interactions = cassette.get("interactions", [])
    if not interactions:
        pytest.skip(f"cassette {cassette_path.name} has zero interactions")
    body_str = interactions[0]["response"]["body"]["string"]
    return json.loads(body_str)


def _first_matching_order(
    orders: list[dict[str, Any]],
    *,
    order_type: tuple[str, ...],
    instruction: tuple[str, ...],
) -> dict[str, Any] | None:
    """Find the first FILLED order matching the type+instruction predicate
    AND carrying at least one executionLegs entry."""
    for order in orders:
        if not isinstance(order, dict):
            continue
        if order.get("status") != "FILLED":
            continue
        if order.get("orderType") not in order_type:
            continue
        legs = order.get("orderLegCollection", [])
        if not isinstance(legs, list) or not legs:
            continue
        leg0 = legs[0] if isinstance(legs[0], dict) else {}
        if leg0.get("instruction") not in instruction:
            continue
        activities = order.get("orderActivityCollection", [])
        if not isinstance(activities, list):
            continue
        for act in activities:
            if isinstance(act, dict) and act.get("activityType") == "EXECUTION":
                exec_legs = act.get("executionLegs", [])
                if isinstance(exec_legs, list) and len(exec_legs) >= 1:
                    return order
    return None


# ---------------------------------------------------------------------------
# Shared journal + reconciliation infrastructure.
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


class _Account:
    def __init__(self, nlv: float = 2000.0):
        self.net_liquidating_value = nlv
        self.positions: list = []


def _seed_fill(
    conn: sqlite3.Connection, *,
    ticker: str, price: float, qty: float, action: str = "entry",
) -> tuple[int, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", price, int(qty), price * 0.9, price * 0.9,
         "managing", "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", action, qty, price, "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id, fill_id


def _list_discrepancies(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT discrepancy_id, discrepancy_type, field_name, "
        "actual_value_json, expected_value_json, delta_text, resolution "
        "FROM reconciliation_discrepancies WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return [
        {
            "discrepancy_id": r[0],
            "discrepancy_type": r[1],
            "field_name": r[2],
            "actual_value_json": r[3],
            "expected_value_json": r[4],
            "delta_text": r[5],
            "resolution": r[6],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Test 1 — LIMIT BUY cassette (operator-recorded; CVGI family path).
# ---------------------------------------------------------------------------


def test_e2e_limit_buy_no_false_positive(conn) -> None:
    """Operator-recorded LIMIT BUY cassette: journal records execution
    price → comparator emits NO false-positive entry_price_mismatch
    (V1 limit-vs-fill defect closed)."""
    cassette = CASSETTE_DIR / "test_e2e_limit_buy.yaml"
    raw_orders = _load_cassette_orders(cassette)
    raw_order = _first_matching_order(
        raw_orders,
        order_type=("LIMIT",),
        instruction=("BUY", "BUY_TO_OPEN"),
    )
    if raw_order is None:
        pytest.skip("cassette contains no matching LIMIT BUY with executionLegs[]")
    mapped = map_orders_to_fill_candidates([raw_order])
    assert len(mapped) == 1
    so = mapped[0]
    assert so.executions is not None and len(so.executions) >= 1
    # Use the leg's price as the journal fill price (operator records exec
    # price — what we want).
    exec_price = so.executions[0].price
    qty = so.executions[0].quantity
    _seed_fill(conn, ticker=so.instrument_symbol, price=exec_price, qty=qty)
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "unmatched_open_fill")]
    assert price_emits == [], (
        f"unexpected emit(s) for LIMIT BUY: {price_emits}"
    )


# ---------------------------------------------------------------------------
# Test 2 — LIMIT SELL cassette (operator-recorded; LION family path).
# ---------------------------------------------------------------------------


def test_e2e_limit_sell_no_false_positive(conn) -> None:
    cassette = CASSETTE_DIR / "test_e2e_limit_sell.yaml"
    raw_orders = _load_cassette_orders(cassette)
    raw_order = _first_matching_order(
        raw_orders,
        order_type=("LIMIT",),
        instruction=("SELL", "SELL_TO_CLOSE"),
    )
    if raw_order is None:
        pytest.skip(
            "cassette contains no matching LIMIT SELL with executionLegs[]",
        )
    mapped = map_orders_to_fill_candidates([raw_order])
    assert len(mapped) == 1
    so = mapped[0]
    assert so.executions is not None and len(so.executions) >= 1
    exec_price = so.executions[0].price
    qty = so.executions[0].quantity
    _seed_fill(
        conn, ticker=so.instrument_symbol, price=exec_price, qty=qty,
        action="exit",
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("close_price_mismatch", "unmatched_close_fill")]
    assert price_emits == [], (
        f"unexpected emit(s) for LIMIT SELL: {price_emits}"
    )


# ---------------------------------------------------------------------------
# Test 3 — STOP FIRED cassette (operator-recorded; OQ-D Path A).
# ---------------------------------------------------------------------------


def test_e2e_stop_fired_no_false_positive(conn) -> None:
    """FIRED STOP: order.price = stop trigger; executionLegs[].price = actual
    execution price (may diverge). Journal records exec price → NO emit
    (comparator uses execution-grain not trigger per OQ-D Path A LOCK)."""
    cassette = CASSETTE_DIR / "test_e2e_stop_fired.yaml"
    raw_orders = _load_cassette_orders(cassette)
    raw_order = _first_matching_order(
        raw_orders,
        order_type=("STOP", "TRAILING_STOP"),
        instruction=("SELL", "SELL_TO_CLOSE", "BUY_TO_CLOSE"),
    )
    if raw_order is None:
        pytest.skip(
            "cassette contains no matching FIRED STOP with executionLegs[]",
        )
    mapped = map_orders_to_fill_candidates([raw_order])
    assert len(mapped) == 1
    so = mapped[0]
    assert so.executions is not None and len(so.executions) >= 1
    exec_price = so.executions[0].price
    qty = so.executions[0].quantity
    _seed_fill(
        conn, ticker=so.instrument_symbol, price=exec_price, qty=qty,
        action="exit",
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("close_price_mismatch", "unmatched_close_fill")]
    assert price_emits == [], (
        f"unexpected emit(s) for STOP FIRED: {price_emits}"
    )


# ---------------------------------------------------------------------------
# Test 4 — MARKET BUY hand-rolled fixture (cassette session deviation;
# operator history has no MARKET BUY).
# ---------------------------------------------------------------------------


def test_e2e_market_buy_no_false_positive(conn) -> None:
    """Hand-rolled MARKET BUY per cassette session deviation. Verifies the
    candidate-pool guard admits MARKET fill with `price=None` when
    executions populated (V1 filter would have excluded this; T-1.6
    widening accepts it)."""
    so = SchwabOrderResponse(
        order_id="ORD-MKT-1",
        status="FILLED",
        enter_time="2026-04-27T14:23:00.000Z",
        instrument_symbol="MKT",
        instruction="BUY",
        quantity=100.0,
        order_type="MARKET",
        price=None,  # MARKET fills surface no order-grain price
        executions=[
            SchwabExecutionLeg(
                leg_id=1, price=15.0042, quantity=100.0,
                mismarked_quantity=0.0, instrument_id=None,
                time="2026-04-27T14:23:01.000Z",
            ),
        ],
    )
    _seed_fill(conn, ticker="MKT", price=15.0042, qty=100.0)
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    price_emits = [d for d in discrepancies if d["discrepancy_type"]
                   in ("entry_price_mismatch", "unmatched_open_fill")]
    assert price_emits == [], (
        f"unexpected MARKET BUY emit(s) (candidate-pool widening broke?): "
        f"{price_emits}"
    )


# ---------------------------------------------------------------------------
# Test 5 — Synthetic Shape C typo: journal records WRONG price → tier-1
# emit with execution-grain correction_target + audit-key persistence.
# ---------------------------------------------------------------------------


def test_e2e_legitimate_typo_emits_shape_c_tier_1(conn) -> None:
    """Plant a journal fill at the WRONG price (operator typed-from-memory
    fill); Schwab carries correct execution-grain data. Expected:
    Shape C discrepancy emit + classifier tier-1 with
    correction_target={'price': exec_price}; audit keys persist."""
    so = SchwabOrderResponse(
        order_id="ORD-TYPO-1",
        status="FILLED",
        enter_time="2026-04-27T14:23:00.000Z",
        instrument_symbol="TYP",
        instruction="BUY",
        quantity=100.0,
        order_type="LIMIT",
        price=10.30,  # LIMIT order trigger
        executions=[
            SchwabExecutionLeg(
                leg_id=1, price=10.2244, quantity=100.0,
                mismarked_quantity=0.0, instrument_id=None,
                time="2026-04-27T14:23:01.000Z",
            ),
        ],
    )
    # Journal records WRONG price (operator typo $10.00 instead of $10.22).
    _, fill_id = _seed_fill(conn, ticker="TYP", price=10.00, qty=100.0)
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    # The pivot already classified + auto-corrected by run-end (per Sub-
    # bundle C.C flow pivot). Find the entry_price_mismatch:
    typo_emits = [d for d in discrepancies
                  if d["discrepancy_type"] == "entry_price_mismatch"]
    assert len(typo_emits) == 1
    emit = typo_emits[0]
    # Shape C key-set persisted on the discrepancy row.
    actual = json.loads(emit["actual_value_json"])
    assert frozenset(actual.keys()) == _SHAPE_C_EXPECTED_KEYS
    # Audit-key persistence verified via JSON-extract.
    row = conn.execute(
        "SELECT json_extract(actual_value_json, '$.execution_legs') "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (emit["discrepancy_id"],),
    ).fetchone()
    assert row is not None and row[0] is not None
    extracted_legs = json.loads(row[0])
    assert len(extracted_legs) == 1
    assert extracted_legs[0]["price"] == 10.2244
    # Auto-corrected resolution (tier-1 fired end-to-end via the pivot).
    assert emit["resolution"] == "auto_corrected_from_schwab"
    # Journal fill UPDATEd to execution-grain price.
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()
    assert fp[0] == 10.2244


# ---------------------------------------------------------------------------
# Test 6 — Path B execution_unavailable hand-rolled fixture (Codex R1 M#5
# binding per spec §5.2 + §10.5 + plan §A.1.13 line 616).
# ---------------------------------------------------------------------------


def test_e2e_path_b_execution_unavailable_full_pipeline(conn) -> None:
    """Hand-rolled Schwab orders fixture with executions=None (mapper
    coherence-check collapse case OR legacy V1 mapper path). Comparator
    Path B emits unmatched_open_fill with `execution_unavailable=true`
    sentinel; classifier T-1.9 routes to tier-2 unsupported with clearer
    correction_reason citing the sentinel. Verifies _handle_no_mutation_audit
    does NOT raise on synthetic field_name='fill_match' (C.D gate-fix #2
    family regression smoke)."""
    so = SchwabOrderResponse(
        order_id="ORD-PB-1",
        status="FILLED",
        enter_time="2026-04-27T14:23:00.000Z",
        instrument_symbol="PATHB",
        instruction="BUY",
        quantity=100.0,
        order_type="LIMIT",
        price=25.00,  # order-grain price populated; executions=None
        executions=None,  # Path B
    )
    _, fill_id = _seed_fill(conn, ticker="PATHB", price=25.00, qty=100.0)
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[so], schwab_transactions=[],
        schwab_account=_Account(),
    )
    discrepancies = _list_discrepancies(conn, run.run_id)
    path_b_emits = [d for d in discrepancies
                    if d["discrepancy_type"] == "unmatched_open_fill"]
    assert len(path_b_emits) == 1
    emit = path_b_emits[0]
    actual = json.loads(emit["actual_value_json"])
    assert actual.get("execution_unavailable") is True
    assert actual.get("schwab_order_id") == "ORD-PB-1"
    assert actual.get("schwab_order_price") == 25.00
    # Classifier T-1.9 routes to tier-2 pending_ambiguity_resolution.
    assert emit["resolution"] == "pending_ambiguity_resolution"
    # Journal fill UNCHANGED (Path B does NOT auto-correct).
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()
    assert fp[0] == 25.00
