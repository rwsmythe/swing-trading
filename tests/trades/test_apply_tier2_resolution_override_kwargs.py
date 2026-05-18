"""Phase 12.5 #1 T-1.4 — override kwarg parameterization of
``apply_tier2_resolution`` + shared ``_validate_override_combo`` helper +
``InvalidOverrideComboError`` typed exception.

Pins:
  - F3 invariant: pre-existing call paths (no overrides) preserve
    ``applied_by='operator'`` + ``correction_action='operator_resolved_ambiguity'``
    + ``resolved_by='operator'`` shape byte-for-byte.
  - F15 hybrid-row invariant: the auto-redirect triple
    (``applied_by_override='auto'``, ``correction_action_override='auto_applied'``,
    ``resolved_by_override='auto_tier1_multi_leg'``) is propagated to ALL
    correction rows + the parent discrepancy.
  - F7 invariant: ``resolved_by`` is free TEXT — no ``_RESOLVED_BY_VALUES``
    constant; only the single literal ``'auto_tier1_multi_leg'`` is
    validator-checked.
  - Spec §7.3.1.a R5 M1 LOCK: ``choice_code`` MUST be
    ``'split_into_partials'`` when the auto-redirect triple is set.
  - Spec §7.3.1.a R6 M1 LOCK: shape-aware idempotency rejects re-invoking
    auto-redirect against a terminal-state discrepancy that was resolved
    manually (``resolved_by != 'auto_tier1_multi_leg'``).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    _AUTO_REDIRECT_SANCTIONED_CHOICE_CODE,
    InvalidOverrideComboError,
    _validate_override_combo,
    apply_tier2_resolution,
)


# ---------------------------------------------------------------------------
# _validate_override_combo unit tests (pure; no DB)
# ---------------------------------------------------------------------------


def test_validate_override_combo_accepts_legacy_default_none_triple() -> None:
    """F3 LOCK — legacy default (all overrides None) MUST pass through."""
    _validate_override_combo(
        choice_code="acknowledge",
        applied_by_override=None,
        correction_action_override=None,
        resolved_by_override=None,
    )
    # No raise.


def test_validate_override_combo_accepts_full_auto_redirect_triple() -> None:
    """Spec §7.3.1.a — the canonical auto-redirect triple under the
    sanctioned ``split_into_partials`` choice MUST pass.
    """
    _validate_override_combo(
        choice_code="split_into_partials",
        applied_by_override="auto",
        correction_action_override="auto_applied",
        resolved_by_override="auto_tier1_multi_leg",
    )
    # No raise.


def test_validate_override_combo_raises_on_partial_auto_missing_resolved_by() -> None:
    """``applied_by='auto'`` + ``correction_action='auto_applied'`` without
    ``resolved_by='auto_tier1_multi_leg'`` is an invalid hybrid shape.
    """
    with pytest.raises(InvalidOverrideComboError) as excinfo:
        _validate_override_combo(
            choice_code="split_into_partials",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override=None,
        )
    msg = str(excinfo.value)
    # Forensic clarity: error message cites all 4 inputs.
    assert "split_into_partials" in msg
    assert "auto" in msg
    assert "auto_applied" in msg
    assert "None" in msg or "none" in msg.lower()


def test_validate_override_combo_raises_on_partial_auto_resolved_by_operator() -> None:
    """``applied_by='auto'`` + ``resolved_by='operator'`` is mismatched
    intent — system-applied write but operator-recorded resolution.
    """
    with pytest.raises(InvalidOverrideComboError) as excinfo:
        _validate_override_combo(
            choice_code="split_into_partials",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override="operator",
        )
    msg = str(excinfo.value)
    assert "operator" in msg
    assert "auto" in msg


def test_validate_override_combo_raises_on_resolved_by_auto_but_applied_by_none() -> None:
    """Symmetric guard — ``resolved_by='auto_tier1_multi_leg'`` requires
    ``applied_by='auto'`` AND ``correction_action='auto_applied'``.
    """
    with pytest.raises(InvalidOverrideComboError) as excinfo:
        _validate_override_combo(
            choice_code="split_into_partials",
            applied_by_override=None,
            correction_action_override=None,
            resolved_by_override="auto_tier1_multi_leg",
        )
    msg = str(excinfo.value)
    assert "auto_tier1_multi_leg" in msg


def test_validate_override_combo_raises_on_resolved_by_auto_choice_code_not_split_into_partials() -> None:
    """Spec §7.3.1.a R5 M1 LOCK — the auto-redirect triple is ONLY valid
    under ``choice_code='split_into_partials'``.
    """
    with pytest.raises(InvalidOverrideComboError) as excinfo:
        _validate_override_combo(
            choice_code="keep_journal_as_is",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override="auto_tier1_multi_leg",
        )
    msg = str(excinfo.value)
    assert "keep_journal_as_is" in msg
    assert _AUTO_REDIRECT_SANCTIONED_CHOICE_CODE in msg


def test_invalid_override_combo_error_is_value_error_subclass() -> None:
    """Exception-specificity ordering pin — existing generic ValueError
    catches still see InvalidOverrideComboError, but specific catches MUST
    place it BEFORE any generic ValueError catch.
    """
    assert issubclass(InvalidOverrideComboError, ValueError) is True


# ---------------------------------------------------------------------------
# DB fixture — plant a pending_ambiguity_resolution discrepancy of kind
# multi_partial_vs_consolidated against a single consolidated fill.
# Mirrors the test_apply_tier2_resolution.py ``_seed_dhc_pending`` shape.
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
    """Two partials summing to qty=39 — matches _seed_pending_multi_partial."""
    return [
        {"qty": 20.0, "price": 7.57, "fill_datetime": fill_datetime},
        {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
    ]


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# F3 LOCK — legacy default (no overrides) preserves byte-for-byte shape
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending_multi_partial(conn)
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=_split_partials_payload(),
        operator_reason="manual operator resolution",
    )
    # All N+1 correction rows carry the operator shape.
    rcs = conn.execute(
        "SELECT applied_by, correction_action FROM reconciliation_corrections "
        "WHERE discrepancy_id = ? ORDER BY correction_id ASC",
        (seed["discrepancy_id"],),
    ).fetchall()
    assert len(rcs) == 3  # 1 anchor (delete) + 2 inserts
    for applied_by, correction_action in rcs:
        assert applied_by == "operator"
        assert correction_action == "operator_resolved_ambiguity"
    # Parent discrepancy carries the operator resolved_by.
    drow = conn.execute(
        "SELECT resolved_by, resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "operator"
    assert drow[1] == "operator_resolved_ambiguity"


# ---------------------------------------------------------------------------
# F15 hybrid-row invariant — auto-redirect triple propagates to ALL rows
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_auto_redirect_triple_writes_hybrid_shape(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending_multi_partial(conn)
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=_split_partials_payload(),
        operator_reason="auto-redirect: multi-leg execution synthesized",
        applied_by_override="auto",
        correction_action_override="auto_applied",
        resolved_by_override="auto_tier1_multi_leg",
    )
    # All N+1 correction rows carry the hybrid (auto-applied) shape.
    rcs = conn.execute(
        "SELECT applied_by, correction_action FROM reconciliation_corrections "
        "WHERE discrepancy_id = ? ORDER BY correction_id ASC",
        (seed["discrepancy_id"],),
    ).fetchall()
    assert len(rcs) == 3  # 1 anchor (delete) + 2 inserts
    for applied_by, correction_action in rcs:
        assert applied_by == "auto"
        assert correction_action == "auto_applied"
    # Parent discrepancy carries the auto resolved_by.
    drow = conn.execute(
        "SELECT resolved_by, resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "auto_tier1_multi_leg"
    # resolution stays operator_resolved_ambiguity (the tier-2 sink state);
    # the auto-redirect-ness is conveyed via resolved_by.
    assert drow[1] == "operator_resolved_ambiguity"


# ---------------------------------------------------------------------------
# Outer-fn validation paths — mismatched intent
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_raises_on_mismatched_intent_combo(
    conn: sqlite3.Connection,
) -> None:
    """Outer-fn invocation with ``applied_by='auto'`` + ``resolved_by='operator'``
    surfaces InvalidOverrideComboError BEFORE any DB I/O (no transaction,
    no correction rows, discrepancy unchanged).
    """
    seed = _seed_pending_multi_partial(conn)
    with pytest.raises(InvalidOverrideComboError):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=_split_partials_payload(),
            operator_reason="invalid mix",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override="operator",
        )
    # No correction rows written (validation runs before any DB I/O).
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 0
    # Discrepancy still in pending state.
    res = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert res == "pending_ambiguity_resolution"


# ---------------------------------------------------------------------------
# Shape-aware idempotency — auto vs manual terminal-state
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_raises_on_auto_against_manual_operator_resolved_terminal(
    conn: sqlite3.Connection,
) -> None:
    """Spec §7.3.1.a R6 M1 LOCK — auto-redirect override against a
    discrepancy already terminally resolved by an OPERATOR (the chain head
    is human-decided) MUST raise InvalidOverrideComboError, not silently
    no-op via the legacy terminal-state idempotency.
    """
    seed = _seed_pending_multi_partial(conn)
    # First, resolve via the legacy operator path (no overrides).
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=_split_partials_payload(),
        operator_reason="operator-decided split via broker statement",
    )
    # Sanity: discrepancy now in terminal state with resolved_by='operator'.
    drow = conn.execute(
        "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "operator_resolved_ambiguity"
    assert drow[1] == "operator"
    # Now try to re-invoke with auto-redirect overrides — MUST raise.
    with pytest.raises(InvalidOverrideComboError):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=_split_partials_payload(),
            operator_reason="auto-redirect after operator decision (illegal)",
            applied_by_override="auto",
            correction_action_override="auto_applied",
            resolved_by_override="auto_tier1_multi_leg",
        )


def test_apply_tier2_resolution_idempotent_return_on_auto_against_auto_terminal(
    conn: sqlite3.Connection,
) -> None:
    """When a prior auto-redirect already resolved the discrepancy (chain
    head ``resolved_by='auto_tier1_multi_leg'``), a re-invocation with the
    same auto-redirect overrides returns the existing CorrectionResult
    idempotently (no raise, no new rows).
    """
    seed = _seed_pending_multi_partial(conn)
    first = apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=_split_partials_payload(),
        operator_reason="auto-redirect (first invocation)",
        applied_by_override="auto",
        correction_action_override="auto_applied",
        resolved_by_override="auto_tier1_multi_leg",
    )
    assert first.correction_id is not None
    count_before = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    # Re-invoke with the same auto overrides — idempotent return; no raise.
    second = apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=_split_partials_payload(),
        operator_reason="auto-redirect (re-invocation; idempotent)",
        applied_by_override="auto",
        correction_action_override="auto_applied",
        resolved_by_override="auto_tier1_multi_leg",
    )
    count_after = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert count_after == count_before  # no new rows
    # Idempotent return surfaces an existing correction id (one of the
    # N+1 rows; spec §5.3 picks the chain head).
    assert second.correction_id is not None
