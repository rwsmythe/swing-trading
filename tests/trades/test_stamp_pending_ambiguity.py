"""T-C.3.1 — `stamp_pending_ambiguity` service helper tests.

Per plan §D.3.1 — backfill orchestrator + flow pivot helper. Pins:
  - Caller-held-tx rejected (covered in transactional_discipline tests).
  - Default idempotent on repeat `pending_ambiguity_resolution` rows
    (allow_pending_update=False, the default).
  - `allow_pending_update=True` REPLACES ambiguity_kind +
    resolution_reason on an already-pending row.
  - Terminal state guard: invocation against a terminal-state
    discrepancy raises ValueError.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import stamp_pending_ambiguity


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_discrepancy(
    conn: sqlite3.Connection,
    *,
    resolution: str,
    ambiguity_kind: str | None = None,
    resolution_reason: str | None = None,
) -> int:
    """Plant a minimal discrepancy in the requested state."""
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
        INSERT INTO fills (trade_id, fill_datetime, action, quantity, price)
        VALUES (?, ?, ?, ?, ?)
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
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, "AAA", "price",
            '{"price": 10.0}', '{"price": 10.10}', "+$0.10", 1,
            resolution, ambiguity_kind, resolution_reason,
            "2026-05-15T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    return discrepancy_id


def test_stamp_pending_ambiguity_unresolved_to_pending(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(conn, resolution="unresolved")
    stamp_pending_ambiguity(
        conn,
        discrepancy_id=did,
        ambiguity_kind="unsupported",
        resolution_reason="classifier dispositioned as unsupported",
    )
    row = conn.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (did,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "unsupported"
    assert "unsupported" in (row[2] or "")


def test_stamp_pending_ambiguity_default_idempotent_on_already_pending(
    conn: sqlite3.Connection,
) -> None:
    did = _seed_discrepancy(
        conn,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="schwab_returned_no_match",
        resolution_reason="initial reason",
    )
    # Default allow_pending_update=False; no-op on repeat invocation.
    stamp_pending_ambiguity(
        conn,
        discrepancy_id=did,
        ambiguity_kind="unsupported",
        resolution_reason="should-be-ignored reason",
    )
    row = conn.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (did,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    # Unchanged from the seeded state.
    assert row[1] == "schwab_returned_no_match"
    assert row[2] == "initial reason"


def test_stamp_pending_ambiguity_allow_update_replaces_pending_kind(
    conn: sqlite3.Connection,
) -> None:
    """T-D.9 --retry-pass-2-failures path: allow_pending_update=True
    overwrites the ambiguity_kind + resolution_reason on a pending row
    whose initial classification was 'unsupported' (Pass-2 failed)."""
    did = _seed_discrepancy(
        conn,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason="Pass 2 re-fetch failed: timeout",
    )
    stamp_pending_ambiguity(
        conn,
        discrepancy_id=did,
        ambiguity_kind="multi_match_within_window",
        resolution_reason="Pass 2 retry succeeded; 2 candidate matches",
        allow_pending_update=True,
    )
    row = conn.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (did,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    # REPLACED — not retained alongside.
    assert row[1] == "multi_match_within_window"
    assert "Pass 2 retry succeeded" in (row[2] or "")
    assert "Pass 2 re-fetch failed" not in (row[2] or "")


def test_stamp_pending_ambiguity_rejects_terminal_state(
    conn: sqlite3.Connection,
) -> None:
    """Terminal-state guard — invocation against an already-resolved
    discrepancy raises ValueError."""
    did = _seed_discrepancy(
        conn,
        resolution="auto_corrected_from_schwab",
        resolution_reason="prior tier-1 apply",
    )
    with pytest.raises(ValueError, match="terminal"):
        stamp_pending_ambiguity(
            conn,
            discrepancy_id=did,
            ambiguity_kind="unsupported",
            resolution_reason="should-fail probe",
        )


def test_stamp_pending_ambiguity_writes_no_correction_row(
    conn: sqlite3.Connection,
) -> None:
    """spec §5.6 prelude — no journal mutation, no audit row write."""
    did = _seed_discrepancy(conn, resolution="unresolved")
    stamp_pending_ambiguity(
        conn,
        discrepancy_id=did,
        ambiguity_kind="unsupported",
        resolution_reason="x",
    )
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (did,),
    ).fetchone()[0]
    assert n == 0


def test_stamp_pending_ambiguity_raises_on_unknown_discrepancy_id(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="discrepancy_id"):
        stamp_pending_ambiguity(
            conn,
            discrepancy_id=999_999,
            ambiguity_kind="unsupported",
            resolution_reason="x",
        )
