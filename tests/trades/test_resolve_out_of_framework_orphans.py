"""SPCX out-of-framework carve-out — Task 3 scoped existing-row resolve tests.

``resolve_out_of_framework_orphans`` clears the EXISTING declared-ticker SPCX
``untracked_broker_position`` orphan rows (``unresolved`` /
``pending_ambiguity_resolution``) to ``acknowledged_immaterial`` with an
audited reason — SCOPED to declared tickers ONLY (C3 / L3), idempotent,
atomic via the existing ``resolve_discrepancy`` service.

Pre-existing orphan rows are planted via RAW ``conn.execute`` INSERT (the
cross-arc write-barrier discipline + full control over ``ambiguity_kind`` to
satisfy the 0031 cross-column CHECK on insert).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import resolve_out_of_framework_orphans


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "resolve_oof.db")


def _new_run(conn: sqlite3.Connection, *, unresolved: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs "
        "(source, state, started_ts, finished_ts, "
        " unresolved_discrepancies_count) VALUES "
        "('schwab_api', 'completed', '2026-06-15T09:00:00.000', "
        "'2026-06-15T09:00:01.000', ?)",
        (unresolved,),
    )
    conn.commit()
    return int(cur.lastrowid)


def _plant_orphan(
    conn: sqlite3.Connection, *, run_id: int, ticker: str,
    resolution: str = "unresolved", ambiguity_kind: str | None = None,
) -> int:
    """RAW INSERT of a pre-existing untracked_broker_position orphan row.

    The 0031 cross-column CHECK requires ambiguity_kind IS NOT NULL <-> a
    pending_ambiguity_resolution/operator_resolved_ambiguity resolution, so a
    pending row carries a real ambiguity_kind here.
    """
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, ticker, "
        " expected_value_json, actual_value_json, delta_text, "
        " material_to_review, resolution, ambiguity_kind, created_at) "
        "VALUES (?, 'untracked_broker_position', 'broker_position', ?, "
        " '{\"journal_qty\": 0}', '{\"qty\": 2.0, \"market_value\": 412.0}', "
        " ?, 1, ?, ?, '2026-06-15T09:00:00.000')",
        (run_id, ticker,
         f"{ticker}: +2.00 sh @ $+412.00 held at broker, not in journal",
         resolution, ambiguity_kind),
    )
    conn.commit()
    return int(cur.lastrowid)


def _row(conn: sqlite3.Connection, did: int) -> tuple:
    return conn.execute(
        "SELECT resolution, resolution_reason, resolved_by, resolved_at, "
        "ambiguity_kind FROM reconciliation_discrepancies WHERE "
        "discrepancy_id=?",
        (did,),
    ).fetchone()


def test_resolve_clears_declared_unresolved_orphan(conn):
    """An unresolved declared SPCX orphan clears to acknowledged_immaterial
    with an audited reason; return value == 1.

    Pre-fix: function does not exist (ImportError). Post-fix: row cleared.
    """
    run_id = _new_run(conn)
    did = _plant_orphan(conn, run_id=run_id, ticker="SPCX")
    n = resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=("SPCX",)
    )
    assert n == 1
    resolution, reason, resolved_by, resolved_at, _ = _row(conn, did)
    assert resolution == "acknowledged_immaterial"
    assert reason and "out-of-framework" in reason.lower() and "SPCX" in reason
    assert resolved_by
    assert resolved_at


def test_resolve_clears_pending_ambiguity_orphan_and_clears_ambiguity_kind(conn):
    """The live-ID-68 path: a pending_ambiguity_resolution orphan with a
    non-NULL ambiguity_kind resolves to acknowledged_immaterial AND
    ambiguity_kind IS NULL (the 0031 cross-column CHECK would reject otherwise).
    """
    run_id = _new_run(conn)
    did = _plant_orphan(
        conn, run_id=run_id, ticker="SPCX",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    n = resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=("SPCX",)
    )
    assert n == 1
    resolution, _, _, _, ambiguity_kind = _row(conn, did)
    assert resolution == "acknowledged_immaterial"
    assert ambiguity_kind is None


def test_resolve_does_not_touch_undeclared_orphan(conn):
    """Scope / L3: declared SPCX cleared; UNDECLARED FOO stays unresolved.

    Pre-fix: function absent. Post-fix: SPCX-only cleared.
    """
    run_id = _new_run(conn, unresolved=2)
    spcx = _plant_orphan(conn, run_id=run_id, ticker="SPCX")
    foo = _plant_orphan(conn, run_id=run_id, ticker="FOO")
    n = resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=("SPCX",)
    )
    assert n == 1
    assert _row(conn, spcx)[0] == "acknowledged_immaterial"
    assert _row(conn, foo)[0] == "unresolved"


def test_resolve_is_idempotent(conn):
    """C3: a second call finds zero matching rows -> returns 0, no further
    state change.
    """
    run_id = _new_run(conn)
    did = _plant_orphan(conn, run_id=run_id, ticker="SPCX")
    assert resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=("SPCX",)
    ) == 1
    before = _row(conn, did)
    assert resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=("SPCX",)
    ) == 0
    assert _row(conn, did) == before


def test_resolve_empty_declared_set_noop(conn):
    """Empty-set short-circuit: returns 0, touches nothing even with an
    unrelated unresolved orphan present.
    """
    run_id = _new_run(conn)
    did = _plant_orphan(conn, run_id=run_id, ticker="SPCX")
    assert resolve_out_of_framework_orphans(
        conn, out_of_framework_tickers=()
    ) == 0
    assert _row(conn, did)[0] == "unresolved"


def test_resolve_decrements_run_unresolved_counter(conn):
    """The run's unresolved_discrepancies_count decrements via
    resolve_discrepancy's existing decrement (C3).
    """
    run_id = _new_run(conn, unresolved=1)
    _plant_orphan(conn, run_id=run_id, ticker="SPCX")
    resolve_out_of_framework_orphans(conn, out_of_framework_tickers=("SPCX",))
    count = conn.execute(
        "SELECT unresolved_discrepancies_count FROM reconciliation_runs "
        "WHERE run_id=?",
        (run_id,),
    ).fetchone()[0]
    assert count == 0
