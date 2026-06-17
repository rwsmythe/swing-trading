"""Phase 18 Arc 18-H.6.1 Part 2 — FK-null-safe terminal resolution of an
``untracked_broker_position`` orphan via the manual ``resolve_discrepancy``
service (reusing ``acknowledged_immaterial`` — no new schema, C2).

The orphan carries ALL FK columns NULL (``trade_id``/``fill_id``/
``cash_movement_id`` all NULL). The manual resolver clears it cleanly to the
terminal ``acknowledged_immaterial`` resolution; a normal trade-attributed
discrepancy's resolve path is byte-identical (C1).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import (
    get_discrepancy,
    insert_discrepancy,
    insert_run,
    list_unresolved_material_orphans,
)
from swing.trades.reconciliation import (
    DiscrepancyResolutionStateError,
    resolve_discrepancy,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "resolve_orphan.db")


def _new_run(conn: sqlite3.Connection) -> int:
    run_id = insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-06-15T09:00:00.000",
        state="completed",
        finished_ts="2026-06-15T09:00:01.000",
        unresolved_discrepancies_count=1,
    )
    conn.commit()
    return run_id


def _emit_orphan(conn: sqlite3.Connection, *, run_id: int) -> int:
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="untracked_broker_position",
        field_name="broker_position",
        material_to_review=1,
        created_at="2026-06-15T09:00:00.000",
        trade_id=None,
        ticker="SPCX",
        expected_value_json='{"journal_qty": 0}',
        actual_value_json='{"market_value": 411.9, "qty": 2.0}',
        delta_text="SPCX: +2.00 sh @ $+411.90 held at broker, not in journal",
        resolution="unresolved",
    )
    conn.commit()
    return did


def _seed_trade(conn: sqlite3.Connection, *, trade_id: int) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, 'TST1', '2026-05-12', 10.0, 100, "
        "9.0, 9.0, 'entered', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'A+ baseline')",
        (trade_id,),
    )
    conn.commit()


def test_resolve_orphan_acknowledged_immaterial_clears_it(
    conn: sqlite3.Connection,
):
    """The all-FK-null orphan resolves cleanly to acknowledged_immaterial."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    assert [r.discrepancy_id for r in list_unresolved_material_orphans(conn)] == [
        did
    ]

    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
        resolution_reason="Journaled SPCX IPO shares; untracked holding known.",
    )

    disc = get_discrepancy(conn, did)
    assert disc.resolution == "acknowledged_immaterial"
    assert disc.resolved_by == "operator"
    assert disc.resolved_at is not None
    # No longer surfaces in the banner/count.
    assert list_unresolved_material_orphans(conn) == []


def test_resolve_orphan_with_all_fk_null_does_not_raise(
    conn: sqlite3.Connection,
):
    """Defensive: all FK columns NULL must not raise on the resolve path."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    disc = get_discrepancy(conn, did)
    assert disc.trade_id is None
    assert disc.fill_id is None
    assert disc.cash_movement_id is None
    # Must not raise.
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
    )
    assert get_discrepancy(conn, did).resolution == "acknowledged_immaterial"


def test_resolve_orphan_decrements_run_unresolved_counter(
    conn: sqlite3.Connection,
):
    """Clearing the orphan decrements the parent run's unresolved counter."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
    )
    row = conn.execute(
        "SELECT unresolved_discrepancies_count FROM reconciliation_runs "
        "WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] == 0


def test_require_current_resolution_raises_on_mismatch_no_overwrite(
    conn: sqlite3.Connection,
):
    """Codex R1 Major #2 — when ``require_current_resolution`` does not match
    the row's CURRENT state, the resolve RAISES (TOCTOU close) and does NOT
    overwrite the existing audit metadata.

    Distinguishing: simulate the race-loser by first resolving the orphan,
    then a second resolve with ``require_current_resolution='unresolved'``
    must raise DiscrepancyResolutionStateError and leave the FIRST
    resolution's metadata intact (pre-fix: the second resolve silently
    overwrote resolution_reason/resolved_by and returned success)."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    # First (winning) resolve.
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
        resolution_reason="winner",
        resolved_by="operator_web",
    )
    # Second (losing) resolve with the guard set to the now-stale state.
    with pytest.raises(DiscrepancyResolutionStateError):
        resolve_discrepancy(
            conn,
            discrepancy_id=did,
            resolution="acknowledged_immaterial",
            resolution_reason="loser-should-not-stick",
            resolved_by="other",
            require_current_resolution="unresolved",
        )
    disc = get_discrepancy(conn, did)
    # The winner's metadata is intact (no overwrite by the loser).
    assert disc.resolution == "acknowledged_immaterial"
    assert disc.resolution_reason == "winner"
    assert disc.resolved_by == "operator_web"


def test_require_current_resolution_match_proceeds(
    conn: sqlite3.Connection,
):
    """When the guard matches the current state, the resolve proceeds."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
        require_current_resolution="unresolved",
    )
    assert get_discrepancy(conn, did).resolution == "acknowledged_immaterial"


def _emit_pending_ambiguity_orphan(
    conn: sqlite3.Connection, *, run_id: int,
) -> int:
    """Plant an orphan in the LEGACY pending_ambiguity_resolution state (the
    pre-18-H.6.1 18-H.6 pivot stamped it 'unsupported'). The cross-column
    CHECK requires ambiguity_kind IS NOT NULL for this resolution, so it is
    inserted via raw SQL with ambiguity_kind set."""
    did = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, trade_id, fill_id, cash_movement_id, "
        "ticker, field_name, expected_value_json, actual_value_json, "
        "delta_text, material_to_review, resolution, ambiguity_kind, "
        "resolution_reason, created_at"
        ") VALUES (?, 'untracked_broker_position', NULL, NULL, NULL, "
        "'SPCX', 'broker_position', '{\"journal_qty\": 0}', "
        "'{\"qty\": 2.0, \"market_value\": 411.9}', "
        "'SPCX held at broker, not in journal', 1, "
        "'pending_ambiguity_resolution', 'unsupported', "
        "'classifier: no sub-classifier', '2026-06-15T09:00:00')",
        (run_id,),
    ).lastrowid
    conn.commit()
    return did


def test_resolve_legacy_pending_ambiguity_orphan_clears_ambiguity_kind(
    conn: sqlite3.Connection,
):
    """Codex R2 Major #1 — the LIVE-ID-68 case: an orphan 18-H.6 already
    swept into pending_ambiguity_resolution (ambiguity_kind NOT NULL) MUST
    be clearable to acknowledged_immaterial. resolve_discrepancy clears
    ambiguity_kind in the same UPDATE so the migration-0031 cross-column
    CHECK permits the transition.

    Distinguishing: pre-fix the UPDATE left ambiguity_kind non-NULL ->
    acknowledged_immaterial + non-NULL ambiguity_kind violates the CHECK ->
    IntegrityError (the orphan is stuck forever). Post-fix it resolves
    cleanly + ambiguity_kind is NULL."""
    run_id = _new_run(conn)
    did = _emit_pending_ambiguity_orphan(conn, run_id=run_id)
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
        resolution_reason="Journaled SPCX; clearing the legacy pending orphan.",
    )
    disc = get_discrepancy(conn, did)
    assert disc.resolution == "acknowledged_immaterial"
    assert disc.ambiguity_kind is None


def test_c1_normal_resolve_path_byte_identical(conn: sqlite3.Connection):
    """C1: a normal trade-attributed discrepancy resolves identically."""
    _seed_trade(conn, trade_id=1)
    run_id = _new_run(conn)
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="stop_mismatch",
        field_name="current_stop",
        material_to_review=1,
        created_at="2026-06-15T09:00:00.000",
        trade_id=1,
        ticker="TST1",
        resolution="unresolved",
    )
    conn.commit()
    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="journal_corrected",
        resolution_reason="fixed the stop in the journal",
    )
    disc = get_discrepancy(conn, did)
    assert disc.resolution == "journal_corrected"
    assert disc.trade_id == 1
