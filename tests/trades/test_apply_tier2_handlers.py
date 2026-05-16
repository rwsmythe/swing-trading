"""T-C.3 — per-(ambiguity_kind, choice_code) handler tests.

Covers the 17 exact-key entries + 1 parametric-prefix entry registered
in ``_TIER2_HANDLERS``. Each handler is small + focused; this file pins
the contract per spec §6.2.1.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    _PICK_SCHWAB_RECORD_PREFIX,
    _TIER2_HANDLERS,
    apply_tier2_resolution,
)


# ---------------------------------------------------------------------------
# Registry shape — 17 exact-key entries + 1 prefix entry
# ---------------------------------------------------------------------------


def test_tier2_handler_registry_has_expected_keys() -> None:
    """The handler registry covers every (ambiguity_kind, choice_code)
    pair enumerated in spec §6.2.1.
    """
    expected_exact_keys = {
        ("multi_partial_vs_consolidated", "keep_journal_as_is"),
        ("multi_partial_vs_consolidated", "consolidate_using_operator_vwap"),
        ("multi_partial_vs_consolidated", "split_into_partials"),
        ("multi_partial_vs_consolidated", "custom"),
        ("multi_match_within_window", _PICK_SCHWAB_RECORD_PREFIX),
        ("multi_match_within_window", "mark_unmatched"),
        ("multi_match_within_window", "custom"),
        ("unknown_schwab_subtype", "acknowledge"),
        ("unknown_schwab_subtype", "operator_truth"),
        ("unknown_schwab_subtype", "custom"),
        ("field_shape_incompatible", "acknowledge"),
        ("field_shape_incompatible", "custom"),
        ("schwab_returned_no_match", "mark_unmatched"),
        ("schwab_returned_no_match", "operator_truth"),
        ("validator_rejected", "acknowledge"),
        ("validator_rejected", "operator_alternative"),
        ("unsupported", "operator_truth"),
        ("unsupported", "acknowledge"),
    }
    assert set(_TIER2_HANDLERS.keys()) == expected_exact_keys
    # Confirm the parametric-prefix sentinel
    assert _PICK_SCHWAB_RECORD_PREFIX == "pick_schwab_record_"


# ---------------------------------------------------------------------------
# Fixture helpers — plant a pending_ambiguity_resolution discrepancy
# under any ambiguity_kind for handler testing.
# ---------------------------------------------------------------------------


_TICKER_COUNTER = [0]


def _seed_pending(
    conn: sqlite3.Connection,
    *,
    ambiguity_kind: str,
    discrepancy_type: str = "entry_price_mismatch",
    ticker: str | None = None,
    qty: float = 100.0,
    price: float = 10.00,
) -> dict[str, Any]:
    if ticker is None:
        _TICKER_COUNTER[0] += 1
        ticker = f"T{_TICKER_COUNTER[0]:04d}"
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", price, int(qty), 9.0, 9.0, "managing",
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
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running"),
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
            run_id, discrepancy_type, trade_id, fill_id, ticker, "price",
            json.dumps({"price": price}), json.dumps({"price": 9.99}),
            "-$0.01", 1, "pending_ambiguity_resolution", ambiguity_kind,
            "test pending", "2026-05-15T12:00:00",
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
        "ticker": ticker,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# pick_schwab_record_<N> — parametric prefix
# ---------------------------------------------------------------------------


def test_pick_schwab_record_N_handler_requires_custom_value(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="multi_match_within_window")
    with pytest.raises(ValueError, match="custom-value"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="pick_schwab_record_1",
            operator_custom_payload=None,
            operator_reason="missing payload probe",
        )


def test_pick_schwab_record_N_handler_applies_operator_payload(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="multi_match_within_window")
    payload = {"price": 9.99, "quantity": 100}
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="pick_schwab_record_2",
        operator_custom_payload=payload,
        operator_reason="picking 2nd Schwab record via broker statement",
    )
    fp = conn.execute(
        "SELECT price, quantity FROM fills WHERE fill_id = ?",
        (seed["fill_id"],),
    ).fetchone()
    assert fp[0] == 9.99
    assert fp[1] == 100.0
    rc = conn.execute(
        "SELECT correction_choice FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    # Operator's exact code retained so audit reflects which Nth record.
    assert rc[0] == "pick_schwab_record_2"


def test_pick_schwab_record_N_handler_rejects_non_integer_suffix(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="multi_match_within_window")
    with pytest.raises(ValueError, match="pick_schwab_record"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="pick_schwab_record_abc",
            operator_custom_payload={"price": 9.99},
            operator_reason="bad N probe",
        )


# ---------------------------------------------------------------------------
# mark_unmatched (multi_match_within_window + schwab_returned_no_match)
# ---------------------------------------------------------------------------


def test_mark_unmatched_no_journal_mutation(
    conn: sqlite3.Connection,
) -> None:
    for kind in ("multi_match_within_window", "schwab_returned_no_match"):
        seed = _seed_pending(conn, ambiguity_kind=kind)
        pre = conn.execute(
            "SELECT price FROM fills WHERE fill_id = ?",
            (seed["fill_id"],),
        ).fetchone()[0]
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="mark_unmatched",
            operator_custom_payload=None,
            operator_reason=f"no broker record under kind {kind}",
        )
        post = conn.execute(
            "SELECT price FROM fills WHERE fill_id = ?",
            (seed["fill_id"],),
        ).fetchone()[0]
        assert pre == post


# ---------------------------------------------------------------------------
# acknowledge (unknown_schwab_subtype + field_shape_incompatible +
# validator_rejected + unsupported)
# ---------------------------------------------------------------------------


def test_acknowledge_no_journal_mutation(
    conn: sqlite3.Connection,
) -> None:
    for kind in (
        "unknown_schwab_subtype",
        "field_shape_incompatible",
        "validator_rejected",
        "unsupported",
    ):
        seed = _seed_pending(conn, ambiguity_kind=kind)
        pre = conn.execute(
            "SELECT price FROM fills WHERE fill_id = ?",
            (seed["fill_id"],),
        ).fetchone()[0]
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="acknowledge",
            operator_custom_payload=None,
            operator_reason=f"acknowledge under kind {kind}",
        )
        post = conn.execute(
            "SELECT price FROM fills WHERE fill_id = ?",
            (seed["fill_id"],),
        ).fetchone()[0]
        assert pre == post
        rc = conn.execute(
            "SELECT correction_action, correction_choice, "
            "applied_value_json, pre_correction_value_json "
            "FROM reconciliation_corrections WHERE discrepancy_id = ?",
            (seed["discrepancy_id"],),
        ).fetchone()
        assert rc[0] == "operator_resolved_ambiguity"
        assert rc[1] == "acknowledge"
        # No-mutation marker.
        assert rc[2] == rc[3]


# ---------------------------------------------------------------------------
# operator_truth — applies operator-supplied field-value payload
# ---------------------------------------------------------------------------


def test_operator_truth_requires_custom_value(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="unknown_schwab_subtype")
    with pytest.raises(ValueError, match="custom-value"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="operator_truth",
            operator_custom_payload=None,
            operator_reason="missing payload",
        )


def test_operator_truth_applies_multi_column_correction(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="schwab_returned_no_match")
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="operator_truth",
        operator_custom_payload={"price": 11.11, "quantity": 100},
        operator_reason="off-Schwab broker statement",
    )
    fp = conn.execute(
        "SELECT price, quantity FROM fills WHERE fill_id = ?",
        (seed["fill_id"],),
    ).fetchone()
    assert fp[0] == 11.11
    assert fp[1] == 100.0


# ---------------------------------------------------------------------------
# operator_alternative (validator_rejected)
# ---------------------------------------------------------------------------


def test_operator_alternative_reruns_validator_chain(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_pending(conn, ambiguity_kind="validator_rejected")
    # First: invalid (negative price) → validator rejects → ValueError.
    with pytest.raises(ValueError, match="validator"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=seed["discrepancy_id"],
            choice_code="operator_alternative",
            operator_custom_payload={"price": -1.0},
            operator_reason="invalid alternative probe",
        )
    # Discrepancy stays pending (validator rejection on tier-2 retry).
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert d[0] == "pending_ambiguity_resolution"

    # Second: valid → applied + discrepancy flipped.
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="operator_alternative",
        operator_custom_payload={"price": 9.50},
        operator_reason="valid alternative",
    )
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (seed["fill_id"],),
    ).fetchone()
    assert fp[0] == 9.50
