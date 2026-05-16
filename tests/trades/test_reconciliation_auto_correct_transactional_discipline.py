"""T-C.1 — outer/inner transactional discipline for the auto-correct service.

Pins the spec §5.3 LOCKED contract:
  - Outer fns reject caller-held transactions with
    :class:`CallerHeldTransactionError`.
  - Outer fns own ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``;
    inner fns never call ``conn.commit()`` / ``conn.rollback()``.
  - On inner exception, outer wrapper rolls back + re-raises; post-call
    state is ``conn.in_transaction is False``.

This file pins ONLY the wrapper discipline. The inner-body logic for
each function lands in T-C.2 / T-C.3 / T-C.3.1 / T-C.4 and is tested in
the per-function test modules.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    AlreadySupersededError,
    CallerHeldTransactionError,
    CorrectionResult,
    ValidatorRejectedError,
    _apply_tier1_correction_inner,
    _apply_tier2_resolution_inner,
    _apply_tier3_override_inner,
    _stamp_pending_ambiguity_inner,
    apply_tier1_correction,
    apply_tier2_resolution,
    apply_tier3_override,
    stamp_pending_ambiguity,
)
from swing.trades.reconciliation_classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Empty schema-v19 DB; no planted discrepancies."""
    db_path = tmp_path / "test.db"
    return ensure_schema(db_path)


# ---------------------------------------------------------------------------
# Exceptions surface
# ---------------------------------------------------------------------------


def test_exceptions_are_exception_subclasses() -> None:
    assert issubclass(CallerHeldTransactionError, Exception)
    assert issubclass(ValidatorRejectedError, Exception)
    assert issubclass(AlreadySupersededError, Exception)


# ---------------------------------------------------------------------------
# CorrectionResult dataclass shape
# ---------------------------------------------------------------------------


def test_correction_result_dataclass_shape() -> None:
    """Spec §5.2 — 7 fields."""
    r = CorrectionResult(
        correction_id=123,
        affected_table="fills",
        affected_row_id=9,
        field_name="price",
        applied_value_json='{"price": 5.30}',
        correction_action="auto_applied",
        notes=None,
    )
    assert r.correction_id == 123
    assert r.affected_table == "fills"
    assert r.affected_row_id == 9
    assert r.field_name == "price"
    assert r.applied_value_json == '{"price": 5.30}'
    assert r.correction_action == "auto_applied"
    assert r.notes is None


# ---------------------------------------------------------------------------
# Outer-fn caller-held-tx rejection
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            apply_tier1_correction(
                conn,
                discrepancy_id=1,
                classification=None,
            )
    finally:
        conn.rollback()


def test_apply_tier2_resolution_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            apply_tier2_resolution(
                conn,
                discrepancy_id=1,
                choice_code="keep_journal_as_is",
                operator_reason="caller-tx rejection probe",
            )
    finally:
        conn.rollback()


def test_apply_tier3_override_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            apply_tier3_override(
                conn,
                correction_id=1,
                operator_truth_value={"price": 5.25},
                operator_reason="caller-tx rejection probe",
            )
    finally:
        conn.rollback()


def test_stamp_pending_ambiguity_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            stamp_pending_ambiguity(
                conn,
                discrepancy_id=1,
                ambiguity_kind="unsupported",
                resolution_reason="caller-tx rejection probe",
            )
    finally:
        conn.rollback()


# ---------------------------------------------------------------------------
# Inner-fn caller-tx contract — inner skeletons raise NotImplementedError
# rather than CallerHeldTransactionError. The outer wrapper is the one
# that enforces the no-caller-tx invariant; inner accepts any state.
# ---------------------------------------------------------------------------


def test_inner_functions_do_not_raise_caller_held_transaction_error(
    conn: sqlite3.Connection,
) -> None:
    """Inner fns are caller-tx-accepting; they do NOT guard tx state.

    Pins the asymmetric contract — outer wrapper is the enforcement
    site for ``conn.in_transaction``; inner fns accept any tx state.
    Inner fns raise either:
      - their domain-error class (ValueError on unknown discrepancy_id;
        not CallerHeldTransactionError);
      - NotImplementedError for skeletons whose body still lands later.
    """
    conn.execute("BEGIN")
    try:
        # Tier-1 inner body is populated (T-C.2): unknown id → ValueError.
        tier1_classification = ClassificationResult(
            tier=1, ambiguity_kind=None,
            correction_target={"price": 5.30},
            correction_reason="probe",
            candidate_choices=None,
        )
        with pytest.raises(ValueError, match="discrepancy_id"):
            _apply_tier1_correction_inner(
                conn, discrepancy_id=999_999,
                classification=tier1_classification,
            )
        # Tier-2 inner body is populated (T-C.3): unknown id → ValueError.
        with pytest.raises(ValueError, match="discrepancy_id"):
            _apply_tier2_resolution_inner(
                conn,
                discrepancy_id=999_999,
                choice_code="keep_journal_as_is",
                operator_reason="x",
            )
        # Tier-3 + stamp inner bodies still raise NotImplementedError
        # in T-C.3 scope; they land in T-C.3.1 / T-C.4.
        with pytest.raises(NotImplementedError):
            _apply_tier3_override_inner(
                conn,
                correction_id=1,
                operator_truth_value={"price": 5.0},
                operator_reason="x",
            )
        with pytest.raises(NotImplementedError):
            _stamp_pending_ambiguity_inner(
                conn,
                discrepancy_id=1,
                ambiguity_kind="unsupported",
                resolution_reason="x",
            )
    finally:
        conn.rollback()


# ---------------------------------------------------------------------------
# Outer-fn rollback on inner exception
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_rolls_back_on_inner_exception(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inner raises → outer wrapper rolls back + re-raises; tx closed."""
    def _failing_inner(conn_: sqlite3.Connection, **kw):
        raise RuntimeError("rigged inner failure")

    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct._apply_tier1_correction_inner",
        _failing_inner,
    )
    with pytest.raises(RuntimeError, match="rigged inner failure"):
        apply_tier1_correction(
            conn,
            discrepancy_id=1,
            classification=None,
        )
    assert conn.in_transaction is False


def test_apply_tier2_resolution_rolls_back_on_inner_exception(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failing_inner(conn_: sqlite3.Connection, **kw):
        raise RuntimeError("rigged inner failure")

    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct._apply_tier2_resolution_inner",
        _failing_inner,
    )
    with pytest.raises(RuntimeError, match="rigged inner failure"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=1,
            choice_code="keep_journal_as_is",
            operator_reason="rollback probe",
        )
    assert conn.in_transaction is False


def test_apply_tier3_override_rolls_back_on_inner_exception(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failing_inner(conn_: sqlite3.Connection, **kw):
        raise RuntimeError("rigged inner failure")

    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct._apply_tier3_override_inner",
        _failing_inner,
    )
    with pytest.raises(RuntimeError, match="rigged inner failure"):
        apply_tier3_override(
            conn,
            correction_id=1,
            operator_truth_value={"price": 5.25},
            operator_reason="rollback probe",
        )
    assert conn.in_transaction is False


def test_stamp_pending_ambiguity_rolls_back_on_inner_exception(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failing_inner(conn_: sqlite3.Connection, **kw):
        raise RuntimeError("rigged inner failure")

    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct._stamp_pending_ambiguity_inner",
        _failing_inner,
    )
    with pytest.raises(RuntimeError, match="rigged inner failure"):
        stamp_pending_ambiguity(
            conn,
            discrepancy_id=1,
            ambiguity_kind="unsupported",
            resolution_reason="rollback probe",
        )
    assert conn.in_transaction is False


# ---------------------------------------------------------------------------
# Sandbox short-circuit on tier-1 outer (spec §5.9 LOCK)
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_sandbox_short_circuits_at_outer(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture,
) -> None:
    """Sandbox env returns a no-op CorrectionResult BEFORE entering inner."""
    import logging

    with caplog.at_level(logging.WARNING):
        result = apply_tier1_correction(
            conn,
            discrepancy_id=999,  # nonexistent: inner would crash
            classification=None,
            environment="sandbox",
        )
    assert result.correction_id is None
    assert "sandbox" in (result.notes or "").lower()
    # WARNING log emitted with the discrepancy id:
    assert any(
        "sandbox" in r.message.lower()
        and r.levelname == "WARNING"
        and "999" in r.message
        for r in caplog.records
    )
    # No tx held + no row written.
    assert conn.in_transaction is False
