"""Phase 12.5 #1 T-1.6 — sandbox short-circuit on auto-redirect path in
``_apply_tier2_resolution_inner``.

Pins:
  - Spec §7.6.1 LOCK: short-circuit gated on
    ``applied_by_override == 'auto'`` AND ``environment == 'sandbox'``;
    manual operator path under sandbox proceeds to handler.
  - C.C lesson #3: SELECT-first-idempotency contract preserved
    (short-circuit fires AFTER ``_select_discrepancy``; nonexistent
    discrepancy_id raises BEFORE the short-circuit).
  - F-family invariant: ``_SandboxAutoRedirectShortCircuit`` is NOT a
    ``ValueError`` subclass so the pivot loop's
    ``except (ValidatorRejectedError, ValueError)`` catch does NOT
    absorb the sentinel.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    InvalidOverrideComboError,
    _apply_tier2_resolution_inner,
    _SandboxAutoRedirectShortCircuit,
)


# ---------------------------------------------------------------------------
# DB fixture — mirrors test_apply_tier2_resolution_override_kwargs.py shape
# ---------------------------------------------------------------------------


def _seed_pending_multi_partial(
    conn: sqlite3.Connection,
    *,
    ticker: str = "DHC",
    qty: float = 39.0,
    price: float = 7.50,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", price, int(qty), 6.0, 6.0, "managing",
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
        (trade_id, "2026-04-27T14:23:00", "entry", qty, price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running",
         "2026-04-27", "2026-04-27"),
    )
    run_id = int(run_cur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, ticker, "price",
            json.dumps({"price": price}),
            json.dumps({"_multi_match": True, "count": 2}), "+$0.08",
            1, "pending_ambiguity_resolution",
            "multi_partial_vs_consolidated",
            "Schwab returned 2 partial orders summing to journal qty",
            "2026-05-15T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    return {
        "trade_id": trade_id,
        "fill_id": fill_id,
        "run_id": run_id,
        "discrepancy_id": discrepancy_id,
        "pre_price": price,
        "pre_qty": qty,
    }


def _split_partials_payload(
    fill_datetime: str = "2026-04-27T14:23:00",
) -> list[dict[str, Any]]:
    return [
        {"qty": 20.0, "price": 7.57, "fill_datetime": fill_datetime},
        {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
    ]


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Test #1: sandbox + auto-redirect triple → raises sentinel + logs WARNING
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_inner_sandbox_short_circuits_on_auto_override_combo(
    conn: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seed = _seed_pending_multi_partial(conn)
    # Inner is caller-tx — open a transaction up front (mirroring pivot).
    conn.execute("BEGIN")
    try:
        with caplog.at_level(
            logging.WARNING,
            logger="swing.trades.reconciliation_auto_correct",
        ):
            with pytest.raises(_SandboxAutoRedirectShortCircuit) as excinfo:
                _apply_tier2_resolution_inner(
                    conn,
                    discrepancy_id=seed["discrepancy_id"],
                    choice_code="split_into_partials",
                    operator_custom_payload=_split_partials_payload(),
                    operator_reason="auto-redirect under sandbox",
                    applied_by_override="auto",
                    correction_action_override="auto_applied",
                    resolved_by_override="auto_tier1_multi_leg",
                    environment="sandbox",
                )
    finally:
        conn.rollback()
    # Sentinel carries the discrepancy_id.
    assert excinfo.value.args[0] == seed["discrepancy_id"]
    # WARNING log fires before raise, citing the discrepancy_id.
    warnings = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "short-circuited under sandbox" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert str(seed["discrepancy_id"]) in warnings[0].getMessage()
    # No correction rows written (handler never dispatched).
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 0
    # Discrepancy still in pending state (caller-tx semantics — caller
    # decides via SAVEPOINT rollback; here we rolled back the BEGIN).
    res = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert res == "pending_ambiguity_resolution"


# ---------------------------------------------------------------------------
# Test #2: production + auto-redirect triple → proceeds to handler (no raise)
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_inner_production_no_short_circuit_on_auto_override_combo(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending_multi_partial(conn)
    conn.execute("BEGIN")
    try:
        # No raise — proceeds to handler. Handler dispatches
        # split_into_partials which writes correction rows + flips state.
        _apply_tier2_resolution_inner(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=_split_partials_payload(),
            operator_reason="auto-redirect under production",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override="auto_tier1_multi_leg",
            environment="production",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # Handler dispatched — correction rows written; parent flipped to
    # operator_resolved_ambiguity with auto_tier1_multi_leg resolved_by.
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 3  # 1 anchor (delete) + 2 inserts
    res, resolved_by = conn.execute(
        "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert res == "operator_resolved_ambiguity"
    assert resolved_by == "auto_tier1_multi_leg"


# ---------------------------------------------------------------------------
# Test #3: sandbox + manual path (no overrides) → proceeds to handler
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_inner_sandbox_manual_path_no_short_circuit(
    conn: sqlite3.Connection,
) -> None:
    """Manual operator path under sandbox proceeds to the handler so
    operators may test menu choices in sandbox.
    """
    seed = _seed_pending_multi_partial(conn)
    conn.execute("BEGIN")
    try:
        _apply_tier2_resolution_inner(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=_split_partials_payload(),
            operator_reason="manual operator under sandbox",
            # All overrides None (default) — legacy operator shape.
            environment="sandbox",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # Handler dispatched — correction rows written with operator shape.
    rcs = conn.execute(
        "SELECT applied_by, correction_action FROM reconciliation_corrections "
        "WHERE discrepancy_id = ? ORDER BY correction_id ASC",
        (seed["discrepancy_id"],),
    ).fetchall()
    assert len(rcs) == 3
    for applied_by, correction_action in rcs:
        assert applied_by == "operator"
        assert correction_action == "operator_resolved_ambiguity"


# ---------------------------------------------------------------------------
# Test #4: nonexistent discrepancy_id under sandbox + auto-redirect →
# raises ValueError from SELECT-first idempotency BEFORE the short-circuit
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_inner_sandbox_short_circuit_after_select(
    conn: sqlite3.Connection,
) -> None:
    """C.C lesson #3 — SELECT-first idempotency MUST precede the short-
    circuit. Pass a nonexistent discrepancy_id and the SELECT raises
    BEFORE the sandbox short-circuit fires.
    """
    conn.execute("BEGIN")
    try:
        with pytest.raises(ValueError) as excinfo:
            _apply_tier2_resolution_inner(
                conn,
                discrepancy_id=99999,  # nonexistent
                choice_code="split_into_partials",
                operator_custom_payload=_split_partials_payload(),
                operator_reason="nonexistent under sandbox + auto-redirect",
                applied_by_override="auto",
                correction_action_override="auto_applied",
                resolved_by_override="auto_tier1_multi_leg",
                environment="sandbox",
            )
    finally:
        conn.rollback()
    # The raise is from SELECT, NOT _SandboxAutoRedirectShortCircuit.
    assert not isinstance(excinfo.value, _SandboxAutoRedirectShortCircuit)


# ---------------------------------------------------------------------------
# Test #5: mismatched combo under sandbox → InvalidOverrideComboError first
# (validator runs at Step 0 BEFORE the Step 2.6 short-circuit)
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_inner_sandbox_short_circuit_after_validate_override_combo(
    conn: sqlite3.Connection,
) -> None:
    """T-1.4 ``_validate_override_combo`` runs at Step 0 BEFORE the
    Step 2.6 sandbox short-circuit. A mismatched combo raises
    InvalidOverrideComboError regardless of environment.
    """
    seed = _seed_pending_multi_partial(conn)
    conn.execute("BEGIN")
    try:
        with pytest.raises(InvalidOverrideComboError):
            _apply_tier2_resolution_inner(
                conn,
                discrepancy_id=seed["discrepancy_id"],
                choice_code="split_into_partials",
                operator_custom_payload=_split_partials_payload(),
                operator_reason="mismatched combo under sandbox",
                applied_by_override="auto",
                correction_action_override="auto_applied",
                # Mismatch: should be 'auto_tier1_multi_leg'.
                resolved_by_override="operator",
                environment="sandbox",
            )
    finally:
        conn.rollback()


# ---------------------------------------------------------------------------
# Test #6: _SandboxAutoRedirectShortCircuit is NOT a ValueError subclass
# (pivot loop's `except (ValidatorRejectedError, ValueError)` MUST NOT
# absorb it)
# ---------------------------------------------------------------------------


def test_sandbox_auto_redirect_short_circuit_is_not_value_error_subclass() -> None:
    """Pivot loop catch ladder ordering pin — T-1.5's
    ``except (ValidatorRejectedError, ValueError)`` MUST NOT absorb the
    sandbox sentinel (the pivot loop has its own dedicated catch that
    rolls back the SAVEPOINT + increments the sandbox-skipped counter).
    """
    assert not issubclass(_SandboxAutoRedirectShortCircuit, ValueError)
    # Defense-in-depth: also not a subclass of any of the typed C.C
    # exceptions that the pivot loop might explicitly catch.
    from swing.trades.reconciliation_auto_correct import (
        AlreadySupersededError,
        CallerHeldTransactionError,
        InvalidOverrideComboError as _IOCE,
        ValidatorRejectedError,
    )
    assert not issubclass(_SandboxAutoRedirectShortCircuit, ValidatorRejectedError)
    assert not issubclass(_SandboxAutoRedirectShortCircuit, CallerHeldTransactionError)
    assert not issubclass(_SandboxAutoRedirectShortCircuit, AlreadySupersededError)
    assert not issubclass(_SandboxAutoRedirectShortCircuit, _IOCE)
    # Still a plain Exception subclass (catchable when needed).
    assert issubclass(_SandboxAutoRedirectShortCircuit, Exception)
