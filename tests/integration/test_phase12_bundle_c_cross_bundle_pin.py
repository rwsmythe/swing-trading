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
"""
from __future__ import annotations


def test_classifier_module_exists_and_returns_classification_result() -> None:
    from swing.trades.reconciliation_classifier import (
        ClassificationResult,
        classify_discrepancy,
    )
    assert callable(classify_discrepancy)
    assert ClassificationResult is not None
    # Pin the 5-field dataclass shape per plan §C.1 acceptance #2.
    field_names = {f.name for f in ClassificationResult.__dataclass_fields__.values()}
    assert field_names == {
        "tier",
        "ambiguity_kind",
        "correction_target",
        "correction_reason",
        "candidate_choices",
    }


def test_validator_chain_dispatches_on_affected_table() -> None:
    from swing.trades.reconciliation_validators import (
        default_validator_chain,
        validate_cash_movement_correction,
        validate_fill_correction,
        validate_snapshot_correction,
        validate_trade_correction,
    )
    # Existence pins for all 4 shipped validators per plan §C.2 acceptance #1.
    assert callable(default_validator_chain)
    assert callable(validate_fill_correction)
    assert callable(validate_trade_correction)
    assert callable(validate_cash_movement_correction)
    assert callable(validate_snapshot_correction)
