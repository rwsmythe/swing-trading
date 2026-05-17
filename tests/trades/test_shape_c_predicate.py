"""Tests for Sub-bundle 1 T-1.8 — Shape C predicate at Pass-1 classifiers
(`_classify_entry_price_mismatch` + `_classify_close_price_mismatch`).

Per plan §A.1.8 + spec §3.2 + §5.2 + §10.3-§10.6. 12 discriminating cases
covering:
- _EXECUTION_AUDIT_KEYS constant
- entry/close Shape A preserved (C.B contract)
- entry/close Shape B preserved
- entry/close Shape C newly recognized → tier-1
- short correction_reason (does NOT stringify execution_legs[])
- audit-key persistence (downstream SQL JSON-extract works)
- mixed/partial Shape C → tier-2
- Pass-2 sanity (unmatched_open_fill with audit-shape STILL tier-2)
- C.B 6-case Pass-2-tier-1-FORBIDDEN test regression smoke (un-importable here
  but pinned indirectly via the public classify_discrepancy contract)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    _EXECUTION_AUDIT_KEYS,
    _SHAPE_C_EXPECTED_KEYS,
    _classify_close_price_mismatch,
    _classify_entry_price_mismatch,
    classify_discrepancy,
)


def _disc(
    *,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    ticker: str = "CVGI",
    trade_id: int = 1,
    fill_id: int | None = 9,
    cash_movement_id: int | None = None,
    actual_value_json: str | None = None,
    expected_value_json: str | None = None,
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=1,
        run_id=1,
        discrepancy_type=discrepancy_type,
        field_name=field_name,
        trade_id=trade_id,
        fill_id=fill_id,
        cash_movement_id=cash_movement_id,
        ticker=ticker,
        expected_value_json=expected_value_json,
        actual_value_json=actual_value_json,
        delta_text=None,
        material_to_review=1,
        created_at="2026-05-16T12:00:00",
        resolution="unresolved",
        resolved_by=None,
        resolved_at=None,
        resolution_reason=None,
        ambiguity_kind=None,
        linked_daily_management_record_id=None,
        mistake_tag_assigned=None,
    )


# Test 1 — _EXECUTION_AUDIT_KEYS constant shape.
def test_execution_audit_keys_constant() -> None:
    assert isinstance(_EXECUTION_AUDIT_KEYS, frozenset)
    assert _EXECUTION_AUDIT_KEYS == frozenset({
        "execution_legs", "schwab_order_id", "schwab_order_price",
    })
    assert isinstance(_SHAPE_C_EXPECTED_KEYS, frozenset)
    assert _SHAPE_C_EXPECTED_KEYS == frozenset({"price"}) | _EXECUTION_AUDIT_KEYS


# Test 2 — _classify_entry_price_mismatch Shape A {price} preserved (C.B).
def test_entry_shape_a_preserved() -> None:
    result = _classify_entry_price_mismatch(
        discrepancy=_disc(),
        source_payload={"price": 5.30},
        journal_row={"fill_id": 9, "trade_id": 1, "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 5.23},
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


# Test 3 — _classify_entry_price_mismatch Shape B full match-tuple preserved.
def test_entry_shape_b_preserved() -> None:
    result = _classify_entry_price_mismatch(
        discrepancy=_disc(ticker="CVGI"),
        source_payload={
            "price": 5.30, "ticker": "CVGI",
            "quantity": 100, "fill_datetime": "2026-05-15T14:23:00",
        },
        journal_row={
            "fill_id": 9, "trade_id": 1,
            "fill_datetime": "2026-05-15T14:23:00",
            "action": "entry", "quantity": 100, "price": 5.23,
            "ticker": "CVGI",
        },
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


# Test 4 — _classify_entry_price_mismatch Shape C audit-bearing → tier-1.
def test_entry_shape_c_tier_1() -> None:
    payload = {
        "price": 5.2244,
        "execution_legs": [
            {"leg_id": 1, "price": 5.2244, "quantity": 100,
             "time": "2026-05-15T14:30:00.000Z"},
        ],
        "schwab_order_id": "ORD-CVGI-1",
        "schwab_order_price": 5.30,
    }
    result = _classify_entry_price_mismatch(
        discrepancy=_disc(),
        source_payload=payload,
        journal_row={
            "fill_id": 9, "trade_id": 1, "fill_datetime": "2026-05-15",
            "action": "entry", "quantity": 100, "price": 5.23,
        },
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.2244}


# Test 5 — Shape C correction_reason is SHORT (no execution_legs[] stringified).
def test_entry_shape_c_correction_reason_short() -> None:
    payload = {
        "price": 5.2244,
        "execution_legs": [
            {"leg_id": i, "price": 5.2244, "quantity": 100,
             "time": "2026-05-15T14:30:00.000Z"}
            for i in range(50)  # 50 legs — would be large stringified
        ],
        "schwab_order_id": "ORD-CVGI-1",
        "schwab_order_price": 5.30,
    }
    result = _classify_entry_price_mismatch(
        discrepancy=_disc(),
        source_payload=payload,
        journal_row={"fill_id": 9, "trade_id": 1, "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 5.23},
    )
    assert len(result.correction_reason) < 500, (
        f"correction_reason too long ({len(result.correction_reason)}); "
        "should NOT stringify execution_legs[]"
    )
    # Verify execution_legs content NOT in the reason.
    assert "leg_id" not in result.correction_reason
    assert "[{" not in result.correction_reason  # no list literal


# Test 6 — Shape C audit-key persistence end-to-end (via classify_discrepancy +
# tmp DB SELECT).
def test_shape_c_audit_key_persistence(tmp_path: Path) -> None:
    """When the comparator emits Shape C actual_value_json + classifier
    routes to tier-1, the persisted JSON column carries the audit keys
    queryable via JSON-extract."""
    conn = ensure_schema(tmp_path / "test.db")
    actual = {
        "price": 5.2244,
        "execution_legs": [
            {"leg_id": 1, "price": 5.2244, "quantity": 100,
             "time": "2026-05-15T14:30:00.000Z"},
        ],
        "schwab_order_id": "ORD-X",
        "schwab_order_price": 5.30,
    }
    # Plant a discrepancy carrying Shape C actual_value_json.
    cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, state, started_ts, period_start, period_end,
            source_artifact_path, finished_ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("schwab_api", "completed", "2026-05-15T12:00:00",
         "2026-05-15", "2026-05-15", "schwab_api:run", "2026-05-15T12:01:00"),
    )
    run_id = int(cur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, field_name, material_to_review,
            created_at, actual_value_json, expected_value_json,
            resolution
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, "entry_price_mismatch", "price", 1,
         "2026-05-15T12:00:01",
         json.dumps(actual, sort_keys=True),
         json.dumps({"price": 5.23}, sort_keys=True),
         "unresolved"),
    )
    disc_id = int(dcur.lastrowid)
    conn.commit()
    # JSON-extract `$.execution_legs` returns non-NULL.
    row = conn.execute(
        "SELECT json_extract(actual_value_json, '$.execution_legs') "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row is not None and row[0] is not None
    extracted = json.loads(row[0])
    assert isinstance(extracted, list)
    assert len(extracted) == 1
    assert extracted[0]["leg_id"] == 1


# Test 7 — mixed/partial Shape C (e.g., {price, execution_legs} only) → tier-2.
def test_entry_mixed_partial_shape_c_tier_2() -> None:
    """Strict-set predicate per spec §11 watch item #19 determinism: a
    payload that has SOME Shape C keys but not all must NOT match Shape C.

    {price, execution_legs} → 2 keys, neither Shape A {price} nor Shape B
    (no ticker/quantity/date) nor Shape C (missing schwab_order_id +
    schwab_order_price). MUST be tier-2 unsupported."""
    payload = {
        "price": 5.2244,
        "execution_legs": [{"leg_id": 1, "price": 5.2244, "quantity": 100,
                            "time": "x"}],
    }
    result = _classify_entry_price_mismatch(
        discrepancy=_disc(),
        source_payload=payload,
        journal_row={"fill_id": 9, "trade_id": 1, "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 5.23},
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"


# Test 8 — _classify_close_price_mismatch Shape C → tier-1.
def test_close_shape_c_tier_1() -> None:
    """Spec §3.2 + §10.6 OQ-D walkthrough — close-side Shape C tier-1."""
    payload = {
        "price": 4.95,
        "execution_legs": [{"leg_id": 1, "price": 4.95, "quantity": 100,
                            "time": "2026-05-15T15:00:00.000Z"}],
        "schwab_order_id": "ORD-STOP-1",
        "schwab_order_price": 5.00,  # trigger
    }
    result = _classify_close_price_mismatch(
        discrepancy=_disc(discrepancy_type="close_price_mismatch",
                          ticker="MNO"),
        source_payload=payload,
        journal_row={"id": 1, "ticker": "MNO", "current_stop": 4.50},
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 4.95}


# Test 9 — _classify_close_price_mismatch Shape A-only → tier-2 (legacy V1).
def test_close_shape_a_only_falls_through_to_v1_tier_2() -> None:
    """V1 fall-through preserved for non-Shape-C payloads (e.g., legacy
    OHLCV-snapshot future consumers)."""
    result = _classify_close_price_mismatch(
        discrepancy=_disc(discrepancy_type="close_price_mismatch"),
        source_payload={"price": 4.95},  # Shape A — not Shape C
        journal_row=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unknown_schwab_subtype"


# Test 10 — _classify_close_price_mismatch mixed/partial Shape C → tier-2.
def test_close_mixed_partial_shape_c_tier_2() -> None:
    payload = {
        "price": 4.95,
        "execution_legs": [{"leg_id": 1, "price": 4.95, "quantity": 100,
                            "time": "x"}],
        # missing schwab_order_id + schwab_order_price
    }
    result = _classify_close_price_mismatch(
        discrepancy=_disc(discrepancy_type="close_price_mismatch"),
        source_payload=payload,
        journal_row=None,
    )
    assert result.tier == 2


# Test 11 — Pass-2 sanity: unmatched_open_fill with audit-shape STILL tier-2.
def test_pass_2_unmatched_open_fill_with_audit_shape_still_tier_2() -> None:
    """V1 LIFT scope = Pass-1 only (spec §1.5 + §6.6). Even if a Pass-2
    discrepancy's actual_value_json carries Shape C audit keys (which it
    won't in V1 — Path B emits sentinel-shape, not Shape C), the Pass-2
    classifier path MUST still emit tier-2 unsupported per Pass-2-tier-1-
    FORBIDDEN LOCK."""
    actual = {
        "matched": None,
        "execution_unavailable": True,
        "schwab_order_id": "ORD-X",
        "schwab_order_price": 5.30,
    }
    disc = _disc(
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        actual_value_json=json.dumps(actual, sort_keys=True),
        expected_value_json=json.dumps(
            {"qty": 100, "price": 5.23, "action": "entry"}, sort_keys=True,
        ),
    )
    result = classify_discrepancy(
        disc,
        source_payload=None,  # unmatched → source_payload is None
        journal_row={"fill_id": 9, "trade_id": 1, "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 5.23},
    )
    assert result.tier == 2  # NO Pass-2 LIFT


# Test 12 — Sub-bundle C.B 6-case Pass-2-tier-1-FORBIDDEN regression smoke.
def test_cb_pass_2_tier_1_forbidden_regression_smoke() -> None:
    """C.B's parametrized test exercises 6 distinct Pass-2 shapes that MUST
    all classify as tier-2 (Pass-2-tier-1-FORBIDDEN LOCK from spec §1.5 +
    §6.6). Re-exercise the most discriminating one — single-record list
    that resembles tier-1-eligible — to pin no regression at T-1.8 ship."""
    actual = {"matched": None}
    disc = _disc(
        discrepancy_type="unmatched_close_fill",
        field_name="fill_match",
        actual_value_json=json.dumps(actual, sort_keys=True),
        expected_value_json=json.dumps(
            {"qty": 100, "price": 5.23, "action": "exit"}, sort_keys=True,
        ),
    )
    # Even with a single Schwab record source_payload, classifier MUST emit
    # tier-2 for unmatched_*_fill (V1 LIFT scope = Pass-1 only).
    result = classify_discrepancy(
        disc,
        source_payload=[{"price": 5.30, "ticker": "X", "quantity": 100}],
        journal_row={"fill_id": 10, "trade_id": 2, "fill_datetime": "2026-05-15",
                     "action": "exit", "quantity": 100, "price": 5.23},
    )
    assert result.tier == 2
