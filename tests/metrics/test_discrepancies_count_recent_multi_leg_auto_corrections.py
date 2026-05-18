"""Phase 12.5 #1 T-1.7 — count_recent_multi_leg_auto_corrections helper tests.

Covers spec §8.2 + plan §A T-1.7 + plan §F invariant F18 (COUNT(DISTINCT)
LOGICAL semantic) + Phase 10 lesson #26 deterministic-tiebreaker ORDER BY.

The helper counts DISTINCT discrepancy_id (NOT correction rows) in the
latest completed reconciliation_run whose discrepancy carries
``resolved_by='auto_tier1_multi_leg'``. A single multi-leg auto-redirect
emits N+1 correction rows (1 anchor + N partials per
``_handle_split_into_partials``), all linked to ONE discrepancy_id — a
naive COUNT(*) on corrections would inflate by N+1.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import insert_discrepancy, insert_run
from swing.metrics.discrepancies import count_recent_multi_leg_auto_corrections


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase12_5_multi_leg_count.db")


def _seed_trade(
    conn: sqlite3.Connection, *, trade_id: int, ticker: str | None = None,
) -> None:
    ticker = ticker or f"TST{trade_id}"
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, '2026-05-12', 10.0, 100, "
        "9.0, 9.0, 'entered', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'A+ baseline')",
        (trade_id, ticker),
    )
    conn.commit()


def _new_run(
    conn: sqlite3.Connection,
    *,
    state: str = "completed",
    started_ts: str = "2026-05-12T09:00:00.000",
    finished_ts: str | None = "2026-05-12T09:00:01.000",
) -> int:
    run_id = insert_run(
        conn,
        source="manual",
        started_ts=started_ts,
        state=state,
        finished_ts=finished_ts,
    )
    conn.commit()
    return run_id


def _emit_discrepancy(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    resolution: str = "operator_resolved_ambiguity",
    ambiguity_kind: str | None = "multi_partial_vs_consolidated",
    resolved_by: str = "auto_tier1_multi_leg",
    discrepancy_type: str = "unmatched_open_fill",
) -> int:
    # Insert with neutral 'unresolved' resolution first (repo helper does
    # not expose ambiguity_kind; cross-column CHECK requires pairing) then
    # update via direct SQL to land the (resolution, ambiguity_kind,
    # resolved_by) tuple atomically.
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type=discrepancy_type,
        field_name="fill_match",
        material_to_review=1,
        created_at="2026-05-12T09:00:00.000",
        trade_id=trade_id,
        ticker="TST",
        resolution="unresolved",
    )
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, ambiguity_kind = ?, "
        "resolved_by = ?, resolved_at = ? "
        "WHERE discrepancy_id = ?",
        (
            resolution, ambiguity_kind, resolved_by,
            "2026-05-12T09:00:00.500", did,
        ),
    )
    conn.commit()
    return did


def _insert_correction(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    run_id: int,
    affected_table: str = "fills",
    affected_row_id: int = 1,
    field_name: str = "__insert__",
    correction_action: str = "operator_resolved_ambiguity",
    applied_by: str = "auto",
) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, correction_choice, "
        "affected_table, affected_row_id, field_name, "
        "pre_correction_value_json, applied_value_json, applied_at, "
        "applied_by, reconciliation_run_id"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            discrepancy_id, correction_action, "split_into_partials",
            affected_table, affected_row_id, field_name,
            '{"price": 5.30}', '{"price": 5.30}',
            "2026-05-12T09:00:00.600", applied_by, run_id,
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def test_count_recent_multi_leg_auto_corrections_returns_zero_when_no_runs(
    conn: sqlite3.Connection,
):
    """Empty reconciliation_runs table → 0."""
    assert count_recent_multi_leg_auto_corrections(conn) == 0


def test_count_recent_multi_leg_auto_corrections_returns_zero_when_no_completed_runs(
    conn: sqlite3.Connection,
):
    """Only ``state='running'`` rows → 0."""
    _seed_trade(conn, trade_id=1)
    _ = _new_run(conn, state="running", finished_ts=None)
    assert count_recent_multi_leg_auto_corrections(conn) == 0


def test_count_recent_multi_leg_auto_corrections_counts_distinct_discrepancies(
    conn: sqlite3.Connection,
):
    """F18 LOCK: 1 discrepancy with 4 correction rows (1 anchor + 3 partials)
    → returns 1 (NOT 4)."""
    _seed_trade(conn, trade_id=1)
    run_id = _new_run(conn)
    did = _emit_discrepancy(conn, run_id=run_id, trade_id=1)
    # 1 anchor (deletion) + 3 partials → 4 correction rows for ONE discrepancy.
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id,
        field_name="__delete__", affected_row_id=10,
    )
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id,
        field_name="__insert__", affected_row_id=11,
    )
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id,
        field_name="__insert__", affected_row_id=12,
    )
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id,
        field_name="__insert__", affected_row_id=13,
    )
    assert count_recent_multi_leg_auto_corrections(conn) == 1


def test_count_recent_multi_leg_auto_corrections_ignores_prior_runs(
    conn: sqlite3.Connection,
):
    """Banner-clears semantic per spec §8.4: prior multi-leg auto-correction
    on run #1 + ZERO on run #2 → returns 0."""
    _seed_trade(conn, trade_id=1)
    run_1 = _new_run(
        conn, finished_ts="2026-05-12T09:00:01.000",
    )
    did_1 = _emit_discrepancy(conn, run_id=run_1, trade_id=1)
    _insert_correction(conn, discrepancy_id=did_1, run_id=run_1)
    # Later completed run with ZERO multi-leg discrepancies.
    _new_run(
        conn,
        started_ts="2026-05-12T10:00:00.000",
        finished_ts="2026-05-12T10:00:01.000",
    )
    assert count_recent_multi_leg_auto_corrections(conn) == 0


def test_count_recent_multi_leg_auto_corrections_ignores_manual_split_into_partials(
    conn: sqlite3.Connection,
):
    """``resolved_by='operator'`` split correction on latest run → returns 0
    (operator-driven, not auto-redirect)."""
    _seed_trade(conn, trade_id=1)
    run_id = _new_run(conn)
    did = _emit_discrepancy(
        conn, run_id=run_id, trade_id=1,
        resolution="operator_resolved_ambiguity",
        ambiguity_kind="multi_partial_vs_consolidated",
        resolved_by="operator",
    )
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id, applied_by="operator",
    )
    assert count_recent_multi_leg_auto_corrections(conn) == 0


def test_count_recent_multi_leg_auto_corrections_ignores_tier1_pass_1_corrections(
    conn: sqlite3.Connection,
):
    """``resolved_by='auto'`` (Pass-1 entry_price_mismatch auto-correct
    via apply_tier1_correction) → returns 0 (NOT a multi-leg auto-redirect)."""
    _seed_trade(conn, trade_id=1)
    run_id = _new_run(conn)
    did = _emit_discrepancy(
        conn, run_id=run_id, trade_id=1,
        resolution="auto_corrected_from_schwab",
        ambiguity_kind=None,
        resolved_by="auto",
        discrepancy_type="entry_price_mismatch",
    )
    _insert_correction(
        conn, discrepancy_id=did, run_id=run_id,
        correction_action="auto_applied",
        field_name="price",
    )
    assert count_recent_multi_leg_auto_corrections(conn) == 0


def test_count_recent_multi_leg_auto_corrections_tiebreaks_on_run_id_descending(
    conn: sqlite3.Connection,
):
    """Phase 10 lesson #26: two completed runs with identical ``finished_ts``
    → uses the one with the higher ``run_id`` (deterministic tiebreaker)."""
    _seed_trade(conn, trade_id=1)
    # Both runs have identical finished_ts; without the tiebreaker, SQLite's
    # ORDER BY ordering would be implementation-defined.
    run_a = _new_run(
        conn,
        started_ts="2026-05-12T09:00:00.000",
        finished_ts="2026-05-12T10:00:00.000",
    )
    # run_a (earlier insertion → lower run_id) carries a multi-leg auto-redirect.
    did_a = _emit_discrepancy(conn, run_id=run_a, trade_id=1)
    _insert_correction(conn, discrepancy_id=did_a, run_id=run_a)
    # run_b (later insertion → higher run_id, same finished_ts) carries NONE.
    run_b = _new_run(
        conn,
        started_ts="2026-05-12T09:30:00.000",
        finished_ts="2026-05-12T10:00:00.000",
    )
    assert run_b > run_a
    # Higher run_id wins the tiebreak → that run has ZERO multi-leg → returns 0.
    assert count_recent_multi_leg_auto_corrections(conn) == 0
