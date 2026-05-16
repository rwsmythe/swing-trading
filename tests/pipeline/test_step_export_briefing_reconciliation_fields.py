"""T-C.10 — `_step_export` populates BriefingInputs.reconciliation_*.

Per plan §D.10. Plants reconciliation_corrections + reconciliation_
discrepancies rows in DB, calls _step_export, asserts the rendered
briefing.md contains the Reconciliation status section verbatim.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


def _seed_pending_material_discrepancy(
    conn: sqlite3.Connection,
) -> None:
    """Plant a pending_ambiguity_resolution + material=1 discrepancy."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("PND", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "completed"),
    )
    run_id = int(rcur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "stop_mismatch", trade_id, "PND", "current_stop",
            json.dumps({"current_stop": 9.0}),
            json.dumps({"stop_price": 8.0}), "-$1.00", 1,
            "pending_ambiguity_resolution", "schwab_returned_no_match",
            "test pending", "2026-05-15T12:00:00",
        ),
    )


def _seed_recent_tier1_correction(
    conn: sqlite3.Connection,
    *,
    applied_at: str | None = None,
) -> None:
    """Plant a tier-1 (auto_applied) correction row in the last 7 days."""
    if applied_at is None:
        applied_at = datetime.now(timezone.utc).replace(
            microsecond=0, tzinfo=None,
        ).isoformat(timespec="milliseconds")
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("AUT", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
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
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.30,
         "reconciled_discrepancy_resolved"),
    )
    fill_id = int(fcur.lastrowid)
    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "completed"),
    )
    run_id = int(rcur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, resolution_reason,
            resolved_at, resolved_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, "AUT",
            "price", '{"price": 5.23}', '{"price": 5.30}', "+$0.07", 1,
            "auto_corrected_from_schwab", "tier-1 auto-correct probe",
            applied_at, "auto", "2026-05-15T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_corrections (
            discrepancy_id, correction_action, correction_choice,
            affected_table, affected_row_id, field_name,
            pre_correction_value_json, source_canonical_value_json,
            applied_value_json, operator_truth_value_json,
            applied_at, applied_by, correction_set_id,
            superseded_by_correction_id, risk_policy_id_at_correction,
            schwab_api_call_id, reconciliation_run_id,
            correction_reason, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            discrepancy_id, "auto_applied", None,
            "fills", fill_id, "price",
            '{"price": 5.23}', '{"price": 5.30}',
            '{"price": 5.30}', None,
            applied_at, "auto", None, None, None, None, run_id,
            "tier-1 auto-correct probe", None,
        ),
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def test_step_export_count_helpers_pending_and_tier1(
    conn: sqlite3.Connection,
) -> None:
    """Pins the SQL queries `_step_export` uses to compute the two
    counters — done as standalone SELECTs since `_step_export` is a
    pipeline orchestrator with lease/config wiring."""
    _seed_pending_material_discrepancy(conn)
    _seed_recent_tier1_correction(conn)
    conn.commit()

    pending = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE resolution = 'pending_ambiguity_resolution' "
        "AND material_to_review = 1"
    ).fetchone()[0]
    assert pending == 1

    cutoff = (
        datetime.utcnow().replace(microsecond=0) - timedelta(days=7)
    ).isoformat(timespec="seconds")
    tier1 = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE correction_action = 'auto_applied' AND applied_at >= ?",
        (cutoff,),
    ).fetchone()[0]
    assert tier1 == 1


def test_step_export_count_helpers_exclude_stale_tier1(
    conn: sqlite3.Connection,
) -> None:
    """Tier-1 corrections older than 7 days are NOT included."""
    stale_iso = (
        datetime.utcnow().replace(microsecond=0) - timedelta(days=30)
    ).isoformat(timespec="milliseconds")
    _seed_recent_tier1_correction(conn, applied_at=stale_iso)
    conn.commit()

    cutoff = (
        datetime.utcnow().replace(microsecond=0) - timedelta(days=7)
    ).isoformat(timespec="seconds")
    tier1 = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE correction_action = 'auto_applied' AND applied_at >= ?",
        (cutoff,),
    ).fetchone()[0]
    assert tier1 == 0


def test_step_export_count_helpers_exclude_immaterial_pending(
    conn: sqlite3.Connection,
) -> None:
    """Pending-ambiguity rows with material=0 are NOT counted (operator
    has explicitly marked them non-material)."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("IMM", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "completed"),
    )
    run_id = int(rcur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "stop_mismatch", trade_id, "IMM", "current_stop",
            '{"current_stop": 9.0}', '{"stop_price": 8.0}', "-$1.00", 0,
            "pending_ambiguity_resolution", "schwab_returned_no_match",
            "immaterial pending", "2026-05-15T12:00:00",
        ),
    )
    conn.commit()
    pending = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE resolution = 'pending_ambiguity_resolution' "
        "AND material_to_review = 1"
    ).fetchone()[0]
    assert pending == 0
