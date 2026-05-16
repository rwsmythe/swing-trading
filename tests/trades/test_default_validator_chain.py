"""T-B.13 — ``default_validator_chain`` dispatcher.

Spec §5.5 + plan §C.13. Discriminating tests:
- builds a chain for CVGI 41 case (affected_table='fills', affected_row_id=9);
  invokes with {"price": 5.30}; asserts (True, None).
- same fill_id; invokes with {"price": -1.0}; asserts (False, "price ...").
- demonstrates ``functools.partial`` composition with ``classify_discrepancy``'s
  ``validator_chain`` argument shape (single positional arg).
"""
from __future__ import annotations

import functools
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy
from swing.trades.reconciliation_validators import default_validator_chain
from tests.conftest import insert_trade_with_entry_fill, make_trade


@pytest.fixture
def conn_with_planted_cvgi_for_chain_test(
    tmp_path: Path,
) -> sqlite3.Connection:
    """Plant CVGI-shaped trade + entry fill for chain dispatch tests."""
    db_path = tmp_path / "test_chain.db"
    conn = ensure_schema(db_path)
    trade = make_trade(
        ticker="CVGI",
        entry_date="2026-04-27",
        entry_price=5.23,
        initial_shares=100,
        initial_stop=4.50,
        current_stop=4.50,
        state="entered",
    )
    insert_trade_with_entry_fill(
        conn, trade, event_ts="2026-04-27T10:00:00",
    )
    return conn


# ---------------------------------------------------------------------------
# Chain dispatches on affected_table to the right validator
# ---------------------------------------------------------------------------


def test_chain_dispatches_to_fills_validator_passes(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    passes, reason = chain(
        {"price": 5.30},
        affected_table="fills",
        affected_row_id=1,
    )
    assert passes is True
    assert reason is None


def test_chain_dispatches_to_fills_validator_rejects_negative_price(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    passes, reason = chain(
        {"price": -1.0},
        affected_table="fills",
        affected_row_id=1,
    )
    assert passes is False
    assert "price" in (reason or "").lower()


def test_chain_dispatches_to_trades_validator(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    passes, _ = chain(
        {"current_stop": 5.0},
        affected_table="trades",
        affected_row_id=1,
    )
    assert passes is True
    passes2, reason2 = chain(
        {"current_stop": -1.0},
        affected_table="trades",
        affected_row_id=1,
    )
    assert passes2 is False
    assert "current_stop" in (reason2 or "").lower()


def test_chain_dispatches_to_cash_movement_validator(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    """Plant a cash_movement + invoke chain via cash_movements route."""
    conn = conn_with_planted_cvgi_for_chain_test
    conn.execute(
        "INSERT INTO cash_movements (id, date, kind, amount) "
        "VALUES (1, '2026-04-27', 'deposit', 1000.0)"
    )
    conn.commit()
    chain = default_validator_chain(conn)
    passes, _ = chain(
        {"amount": 1500.0},
        affected_table="cash_movements",
        affected_row_id=1,
    )
    assert passes is True
    passes2, reason2 = chain(
        {"amount": -1.0},
        affected_table="cash_movements",
        affected_row_id=1,
    )
    assert passes2 is False
    assert "amount" in (reason2 or "").lower()


def test_chain_dispatches_to_snapshot_validator(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_for_chain_test
    conn.execute(
        """
        INSERT INTO account_equity_snapshots
          (snapshot_id, snapshot_date, equity_dollars, source,
           source_artifact_path, recorded_at, recorded_by, notes)
        VALUES (1, '2026-04-27', 2000.0, 'manual', NULL,
                '2026-04-27T10:00:00', 'operator', NULL)
        """
    )
    conn.commit()
    chain = default_validator_chain(conn)
    passes, _ = chain(
        {"equity_dollars": 2500.0},
        affected_table="account_equity_snapshots",
        affected_row_id=1,
    )
    assert passes is True
    passes2, reason2 = chain(
        {"equity_dollars": 0.0},
        affected_table="account_equity_snapshots",
        affected_row_id=1,
    )
    assert passes2 is False
    assert "equity_dollars" in (reason2 or "").lower()


def test_chain_rejects_unknown_affected_table(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    passes, reason = chain(
        {"x": 1},
        affected_table="bogus_table",
        affected_row_id=1,
    )
    assert passes is False
    assert "bogus_table" in (reason or "")


# ---------------------------------------------------------------------------
# functools.partial composition with classify_discrepancy
# ---------------------------------------------------------------------------


def test_chain_composes_with_classify_via_functools_partial(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    """Plan §C.13 #4 — callers bind ``affected_table`` + ``affected_row_id``
    via ``functools.partial`` at C.C construction time; the partial then
    matches ``classify_discrepancy``'s ``validator_chain`` arg shape."""
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    bound_for_cvgi_41 = functools.partial(
        chain,
        affected_table="fills",
        affected_row_id=1,
    )

    discrepancy = ReconciliationDiscrepancy(
        discrepancy_id=41,
        run_id=1,
        discrepancy_type="entry_price_mismatch",
        trade_id=1,
        fill_id=1,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="CVGI",
        field_name="price",
        expected_value_json='{"price": 5.23}',
        actual_value_json='{"price": 5.30}',
        delta_text="+$0.07 (schwab minus journal)",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )

    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100, "trade_id": 1},
        validator_chain=bound_for_cvgi_41,
    )
    # Validator passes → tier-1 result preserved.
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_chain_composes_with_classify_via_partial_rejection_downgrades(
    conn_with_planted_cvgi_for_chain_test: sqlite3.Connection,
) -> None:
    """Partial-bound chain that would reject (negative price proposal) →
    dispatcher downgrades to tier-2 validator_rejected."""
    conn = conn_with_planted_cvgi_for_chain_test
    chain = default_validator_chain(conn)
    # Plant a bound chain for a fill that exists; the proposal carries a
    # negative price which the fills validator rejects.
    bound = functools.partial(
        chain,
        affected_table="fills",
        affected_row_id=1,
    )

    # Build a synthetic discrepancy whose sub-classifier emits tier-1 with
    # a negative price (use entry_price_mismatch + source_payload).
    discrepancy = ReconciliationDiscrepancy(
        discrepancy_id=999,
        run_id=1,
        discrepancy_type="entry_price_mismatch",
        trade_id=1,
        fill_id=1,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="CVGI",
        field_name="price",
        expected_value_json='{"price": 5.23}',
        actual_value_json='{"price": -1.0}',
        delta_text=None,
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": -1.0},
        journal_row={"price": 5.23},
        validator_chain=bound,
    )
    # Sub-classifier emitted tier-1; chain rejects → downgrade.
    assert result.tier == 2
    assert result.ambiguity_kind == "validator_rejected"
