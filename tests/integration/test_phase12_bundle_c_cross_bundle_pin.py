"""Phase 12 Sub-bundle C cross-bundle forward-binding pin tests.

These tests pin the BINDING INTERFACE contracts that Sub-sub-bundle C.B
implements:

  - ``swing/trades/reconciliation_classifier.py:classify_discrepancy(...)``
    signature + ``ClassificationResult`` shape (lands at C.B T-B.1).
  - ``swing/trades/reconciliation_validators.py:default_validator_chain(conn)``
    signature (lands at C.B T-B.2 / T-B.13).

Both modules ship in Sub-sub-bundle C.B; the ``@pytest.mark.skip``
decorators from the C.A foundation lay-down have been removed at T-B.14
per plan §C.14.

Codex R1 Major #3: tests strengthened from vacuous existence/callability
checks to discriminating regression tests that pin BEHAVIOR — the
classifier emits the spec §10.1 CVGI 41 walkthrough result shape for
the persisted-JSON-only contract; the validator chain dispatches on
``affected_table`` and exercises the underlying validator end-to-end
against a live schema-v19 connection.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    classify_discrepancy,
)
from swing.trades.reconciliation_validators import (
    default_validator_chain,
    validate_cash_movement_correction,
    validate_fill_correction,
    validate_snapshot_correction,
    validate_trade_correction,
)
from tests.conftest import insert_trade_with_entry_fill, make_trade


def test_classifier_module_exists_and_returns_classification_result() -> None:
    """Discriminating regression pin (Codex R1 Major #3).

    Strengthened from a callability/dataclass-fields existence check to
    an end-to-end invocation that pins the LOCKED ``classify_discrepancy``
    signature ``(discrepancy, *, source_payload, journal_row,
    validator_chain)`` AND the BINDING tier-1 emission shape per spec
    §10.1 CVGI 41 walkthrough (persisted-JSON-only contract).
    """
    assert callable(classify_discrepancy)
    assert ClassificationResult is not None
    # Pin the 6-field dataclass shape per plan §C.1 acceptance #2;
    # `auto_redirect_recipe` added by Phase 12.5 #1 T-1.2 per spec §5.1 LOCK.
    field_names = {f.name for f in ClassificationResult.__dataclass_fields__.values()}
    assert field_names == {
        "tier",
        "ambiguity_kind",
        "correction_target",
        "correction_reason",
        "candidate_choices",
        "auto_redirect_recipe",
    }

    # Behavior pin: spec §10.1 CVGI 41 walkthrough end-to-end.
    discrepancy = ReconciliationDiscrepancy(
        discrepancy_id=41,
        run_id=1,
        discrepancy_type="entry_price_mismatch",
        trade_id=1,
        fill_id=9,
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
        journal_row={"price": 5.23, "quantity": 100, "ticker": "CVGI"},
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.ambiguity_kind is None
    assert result.correction_target == {"price": 5.30}
    assert result.correction_reason  # non-empty
    assert result.candidate_choices is None
    # Phase 12.5 #1 T-1.2: tier-1 non-multi-leg emits MUST default to None
    # per spec §5.1 LOCK (recipe-field discipline preserves existing paths).
    assert result.auto_redirect_recipe is None


@pytest.fixture
def conn_pin_v19(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Schema-v19 in-disk connection (tmp_path) for chain dispatch pin tests.

    Codex R2 Minor #1 — yields + closes the connection on teardown to
    release the SQLite file handle before pytest's ``tmp_path`` cleanup
    runs. Windows file-handle hygiene around tmp_path-backed SQLite
    databases (open handles can block cleanup on slower runners).
    """
    db_path = tmp_path / "test_cross_bundle_pin.db"
    conn = ensure_schema(db_path)
    try:
        yield conn
    finally:
        conn.close()


def test_validator_chain_dispatches_on_affected_table(
    conn_pin_v19: sqlite3.Connection,
) -> None:
    """Discriminating regression pin (Codex R1 Major #3).

    Strengthened from a 4-validator-callable existence check to an
    end-to-end dispatch invocation against a live schema-v19 connection
    with a planted fills row. Exercises the ``affected_table``-keyed
    routing AND the underlying ``validate_fill_correction`` predicate
    (positive case: valid price; discriminating negative case: negative
    price triggers schema-CHECK-mirror rejection).
    """
    # Existence pins for all 4 shipped validators per plan §C.2 acceptance #1.
    assert callable(default_validator_chain)
    assert callable(validate_fill_correction)
    assert callable(validate_trade_correction)
    assert callable(validate_cash_movement_correction)
    assert callable(validate_snapshot_correction)

    # Plant a CVGI-shaped trade + entry fill so fill_id=1 exists.
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
        conn_pin_v19, trade, event_ts="2026-04-27T10:00:00",
    )

    chain = default_validator_chain(conn_pin_v19)

    # Positive case: valid price update passes via 'fills' dispatch.
    passes, reason = chain(
        {"price": 5.30}, affected_table="fills", affected_row_id=1,
    )
    assert passes is True
    assert reason is None

    # Discriminating negative case: negative price → schema-CHECK-mirror
    # rejection via the SAME dispatcher path.
    passes, reason = chain(
        {"price": -1.0}, affected_table="fills", affected_row_id=1,
    )
    assert passes is False
    assert "price" in (reason or "").lower()
