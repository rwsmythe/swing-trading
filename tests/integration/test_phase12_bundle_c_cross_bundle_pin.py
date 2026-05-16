"""Phase 12 Sub-bundle C cross-bundle forward-binding pin tests.

These tests pin the BINDING INTERFACE contracts that Sub-sub-bundle C.B will
implement:

  - ``swing/trades/reconciliation_classifier.py:classify_discrepancy(...)``
    signature + ``ClassificationResult`` shape (lands at C.B T-B.1).
  - ``swing/trades/reconciliation_validators.py:default_validator_chain(conn)``
    signature (lands at C.B T-B.2 / T-B.13).

Both modules are not present at C.A-foundation ship time; the tests are
``@pytest.mark.skip``-decorated until the C.B implementer un-skips them at
T-B.1 + T-B.2 landing. See plan §F.1 BINDING INTERFACE table.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="forward-binding; un-skip at C.B T-B.1 + T-B.2 landing — "
           "classifier + validator-shim modules ship in Sub-sub-bundle C.B"
)
def test_classifier_module_exists_and_returns_classification_result():
    from swing.trades.reconciliation_classifier import (
        ClassificationResult,
        classify_discrepancy,
    )
    # placeholder; full discriminating test built at C.B T-B.1.
    assert callable(classify_discrepancy)
    assert ClassificationResult is not None


@pytest.mark.skip(
    reason="forward-binding; un-skip at C.B T-B.2 landing — "
           "validator-shim module ships in Sub-sub-bundle C.B"
)
def test_validator_chain_dispatches_on_affected_table():
    from swing.trades.reconciliation_validators import (
        default_validator_chain,
    )
    assert callable(default_validator_chain)
