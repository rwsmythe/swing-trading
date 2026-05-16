"""T-C.3 — `apply_tier2_resolution` outer + inner happy paths.

Pins the spec §5.6 contract:
  - 17 exact-key handlers + 1 parametric-prefix (pick_schwab_record_<N>).
  - Incompatible (ambiguity_kind, choice_code) raises ValueError.
  - Required `--custom-value` payloads enforced per handler.
  - 'no journal mutation' choices STILL write an audit row with
    applied_value_json == pre_correction_value_json.
  - Split-into-partials writes (N+1) correction rows in one
    correction_set_id via the spec §3.1.1 anchor-self-reference pattern.
  - Custom is audit-only V1 (no journal mutation regardless of payload).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    CorrectionResult,
    apply_tier2_resolution,
)


# ---------------------------------------------------------------------------
# Fixture — plant DHC 39 / VSAT 40 shape: trade with a single consolidated
# entry fill of qty=39 + price=7.50 + a pending_ambiguity_resolution
# discrepancy of ambiguity_kind='multi_partial_vs_consolidated'.
# ---------------------------------------------------------------------------


def _seed_dhc_pending(
    conn: sqlite3.Connection,
    *,
    ambiguity_kind: str = "multi_partial_vs_consolidated",
    discrepancy_id: int = 39,
    fill_id: int = 2,
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
        ("DHC", "2026-04-27", price, int(qty), 6.0, 6.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO fills (
            fill_id, trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (fill_id, trade_id, "2026-04-27T14:23:00", "entry", qty, price,
         "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running", "2026-04-27", "2026-04-27"),
    )
    run_id = int(run_cur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
            ticker, field_name, expected_value_json, actual_value_json,
            delta_text, material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            discrepancy_id, run_id, "entry_price_mismatch", trade_id, fill_id,
            "DHC", "price", json.dumps({"price": price}),
            json.dumps({"_multi_match": True, "count": 2}), "+$0.08",
            1, "pending_ambiguity_resolution", ambiguity_kind,
            "Schwab returned 2 partial orders summing to journal qty",
            "2026-05-15T12:00:00",
        ),
    )
    conn.commit()
    return {
        "trade_id": trade_id,
        "fill_id": fill_id,
        "run_id": run_id,
        "discrepancy_id": discrepancy_id,
        "pre_price": price,
        "pre_qty": qty,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


@pytest.fixture
def dhc_world(conn: sqlite3.Connection) -> dict[str, Any]:
    return _seed_dhc_pending(conn)


# ---------------------------------------------------------------------------
# consolidate_using_operator_vwap happy path
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_consolidate_using_operator_vwap(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="consolidate_using_operator_vwap",
        operator_custom_payload={"price": 7.58},
        operator_reason="Schwab broker statement shows 2 partials; VWAP=7.58",
    )
    # fills.price updated.
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (dhc_world["fill_id"],),
    ).fetchone()
    assert fp[0] == 7.58
    # Correction row with operator_resolved_ambiguity:
    rc = conn.execute(
        "SELECT correction_action, correction_choice, applied_by, "
        "applied_value_json, pre_correction_value_json "
        "FROM reconciliation_corrections WHERE discrepancy_id = ?",
        (dhc_world["discrepancy_id"],),
    ).fetchone()
    assert rc[0] == "operator_resolved_ambiguity"
    assert rc[1] == "consolidate_using_operator_vwap"
    assert rc[2] == "operator"
    assert json.loads(rc[3]) == {"price": 7.58}
    assert json.loads(rc[4]) == {"price": 7.50}
    # Discrepancy resolution flipped:
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (dhc_world["discrepancy_id"],),
    ).fetchone()
    assert d[0] == "operator_resolved_ambiguity"
    # CorrectionResult shape.
    assert isinstance(result, CorrectionResult)
    assert result.correction_action == "operator_resolved_ambiguity"


# ---------------------------------------------------------------------------
# split_into_partials — anchor self-reference + correction_set_id grouping
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_split_into_partials_writes_set(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    payload = [
        {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
        {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
    ]
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=payload,
        operator_reason="Schwab broker statement shows 2 partial executions",
    )
    # Original fill deleted; 2 new fills inserted (sum qty 39).
    fills = conn.execute(
        "SELECT quantity, price FROM fills "
        "WHERE trade_id = ? AND action = 'entry' "
        "ORDER BY fill_datetime ASC, fill_id ASC",
        (dhc_world["trade_id"],),
    ).fetchall()
    assert len(fills) == 2
    assert fills[0] == (20.0, 7.57)
    assert fills[1] == (19.0, 7.59)
    # 3 correction rows in same correction_set:
    rcs = conn.execute(
        "SELECT correction_id, correction_set_id, field_name "
        "FROM reconciliation_corrections WHERE discrepancy_id = ? "
        "ORDER BY correction_id ASC",
        (dhc_world["discrepancy_id"],),
    ).fetchall()
    assert len(rcs) == 3
    anchor_id = rcs[0][0]
    # All three share the same correction_set_id = anchor_id (spec §3.1.1
    # anchor-self-reference: anchor's correction_set_id = anchor's correction_id).
    assert rcs[0][1] == anchor_id
    assert rcs[1][1] == anchor_id
    assert rcs[2][1] == anchor_id
    assert rcs[0][2] == "__delete__"
    assert rcs[1][2] == "__insert__"
    assert rcs[2][2] == "__insert__"
    # CorrectionResult points to the anchor (delete) row.
    assert result.correction_id == anchor_id
    # Aggregates recomputed exactly once across the (delete + N inserts):
    sz = conn.execute(
        "SELECT current_size FROM trades WHERE id = ?",
        (dhc_world["trade_id"],),
    ).fetchone()
    assert sz[0] == 39.0


# ---------------------------------------------------------------------------
# Required `--custom-value` rejection
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_rejects_missing_custom_value(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    with pytest.raises(ValueError) as excinfo:
        apply_tier2_resolution(
            conn,
            discrepancy_id=dhc_world["discrepancy_id"],
            choice_code="consolidate_using_operator_vwap",
            operator_custom_payload=None,
            operator_reason="forgot the payload",
        )
    msg = str(excinfo.value).lower()
    assert "custom-value" in msg or "operator_custom_payload" in msg


# ---------------------------------------------------------------------------
# keep_journal_as_is — no mutation BUT audit row written
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_keep_journal_as_is_writes_audit_no_mutation(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    pre = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (dhc_world["fill_id"],),
    ).fetchone()[0]
    apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="keep_journal_as_is",
        operator_custom_payload=None,
        operator_reason="aggregation intentional",
    )
    post = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (dhc_world["fill_id"],),
    ).fetchone()[0]
    assert pre == post
    rc = conn.execute(
        "SELECT correction_action, correction_choice, applied_value_json, "
        "pre_correction_value_json "
        "FROM reconciliation_corrections WHERE discrepancy_id = ?",
        (dhc_world["discrepancy_id"],),
    ).fetchone()
    assert rc[0] == "operator_resolved_ambiguity"
    assert rc[1] == "keep_journal_as_is"
    # No-mutation marker: applied == pre (bytewise).
    assert rc[2] == rc[3]


# ---------------------------------------------------------------------------
# Incompatible (ambiguity_kind, choice_code) rejected
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_rejects_incompatible_choice_code(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    # dhc_world is multi_partial_vs_consolidated; pick_schwab_record is
    # only valid for multi_match_within_window.
    with pytest.raises(ValueError) as excinfo:
        apply_tier2_resolution(
            conn,
            discrepancy_id=dhc_world["discrepancy_id"],
            choice_code="pick_schwab_record_1",
            operator_custom_payload={"price": 7.58, "quantity": 39},
            operator_reason="wrong-kind probe",
        )
    msg = str(excinfo.value).lower()
    assert "incompatible" in msg or "ambiguity_kind" in msg


# ---------------------------------------------------------------------------
# Custom is audit-only V1 (no journal mutation)
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_custom_is_audit_only_v1(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    pre = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (dhc_world["fill_id"],),
    ).fetchone()[0]
    apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="custom",
        operator_custom_payload={
            "audit_only": True,
            "operator_intent": "V2 will widen this case",
        },
        operator_reason="needs V2 work",
    )
    post = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?",
        (dhc_world["fill_id"],),
    ).fetchone()[0]
    assert pre == post
    rc = conn.execute(
        "SELECT correction_choice, applied_value_json, "
        "pre_correction_value_json, correction_reason "
        "FROM reconciliation_corrections WHERE discrepancy_id = ?",
        (dhc_world["discrepancy_id"],),
    ).fetchone()
    assert rc[0] == "custom"
    # applied == pre bytewise (no mutation marker).
    assert rc[1] == rc[2]
    # operator_intent surfaced in correction_reason.
    assert "V2 will widen this case" in (rc[3] or "")


# ---------------------------------------------------------------------------
# Idempotency on terminal state
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_is_idempotent_on_terminal_state(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    first = apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="keep_journal_as_is",
        operator_custom_payload=None,
        operator_reason="x",
    )
    assert first.correction_id is not None
    # Second invocation on terminal-state discrepancy returns the existing row.
    second = apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="keep_journal_as_is",
        operator_custom_payload=None,
        operator_reason="repeat",
    )
    assert second.correction_id == first.correction_id


# ---------------------------------------------------------------------------
# Unresolved discrepancy (not yet stamped) raises
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_raises_when_discrepancy_unresolved(
    conn: sqlite3.Connection,
) -> None:
    """Discrepancies must be in pending_ambiguity_resolution state before
    a tier-2 resolution can land. Unresolved → ValueError."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("AAA", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 10.0),
    )
    fill_id = int(fcur.lastrowid)
    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running"),
    )
    run_id = int(rcur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, "entry_price_mismatch", trade_id, fill_id, "AAA", "price",
         '{"price": 10.0}', '{"price": 10.10}', "+$0.10", 1, "unresolved",
         "2026-05-15T12:00:00"),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    with pytest.raises(ValueError, match="pending_ambiguity_resolution"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=discrepancy_id,
            choice_code="keep_journal_as_is",
            operator_custom_payload=None,
            operator_reason="should-fail probe",
        )


# ---------------------------------------------------------------------------
# Trade_events emitted PER inserted fill on split-into-partials
# ---------------------------------------------------------------------------


def test_apply_tier2_resolution_split_emits_one_event_per_inserted_fill(
    conn: sqlite3.Connection, dhc_world: dict[str, Any],
) -> None:
    payload = [
        {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
        {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
    ]
    apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_world["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=payload,
        operator_reason="x",
    )
    events = conn.execute(
        "SELECT event_type FROM trade_events WHERE trade_id = ? "
        "AND event_type = 'reconciliation_auto_correct'",
        (dhc_world["trade_id"],),
    ).fetchall()
    # spec §9.3 — one event per resulting fill (the deletion sentinel
    # does NOT emit; only the N __insert__ rows do).
    assert len(events) == 2
