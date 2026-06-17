"""Phase 18 Arc 18-H.6.1 — untracked_broker_position (orphan) banner/count.

18-H.6 emits the orphan (``untracked_broker_position``, all-FK-null,
``trade_id IS NULL``) but the trade-JOINed banner helpers EXCLUDE it by
construction. 18-H.6.1 Part 1 UNIONs a dedicated orphan reader into
``count_unresolved_material`` + the banner-link set so the topbar material
banner reflects the orphan.

Distinguishing coverage (pre-fix vs post-fix):
- ``count_unresolved_material`` counts the orphan (pre-fix: 0/excluded).
- ``list_pending_ambiguities_in_banner_set`` surfaces it (pre-fix: empty).
- ``fetch_first_pending_ambiguity_resolve_link_path`` points at it.
- A normal (trade-attributed) discrepancy's count/banner is byte-identical
  (the C1 additive lock).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import (
    insert_discrepancy,
    insert_run,
    list_unresolved_material_orphans,
)
from swing.metrics.discrepancies import (
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
    list_pending_ambiguities_in_banner_set,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "h6_1.db")


def _seed_trade(
    conn: sqlite3.Connection, *, trade_id: int, state: str,
    ticker: str | None = None,
) -> None:
    ticker = ticker or f"TST{trade_id}"
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, '2026-05-12', 10.0, 100, "
        "9.0, 9.0, ?, 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'A+ baseline')",
        (trade_id, ticker, state),
    )
    conn.commit()


def _new_run(conn: sqlite3.Connection) -> int:
    run_id = insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-05-12T09:00:00.000",
        state="completed",
        finished_ts="2026-05-12T09:00:01.000",
    )
    conn.commit()
    return run_id


def _emit_orphan(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    ticker: str = "SPCX",
    material: int = 1,
    resolution: str = "unresolved",
) -> int:
    """Insert an all-FK-null untracked_broker_position (orphan) row."""
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="untracked_broker_position",
        field_name="broker_position",
        material_to_review=material,
        created_at="2026-05-12T09:00:00.000",
        trade_id=None,
        ticker=ticker,
        expected_value_json='{"journal_qty": 0}',
        actual_value_json='{"market_value": 411.9, "qty": 2.0}',
        delta_text="SPCX: +2.00 sh @ $+411.90 held at broker, not in journal",
        resolution=resolution,
    )
    conn.commit()
    return did


def _emit_normal(
    conn: sqlite3.Connection, *, run_id: int, trade_id: int,
) -> int:
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="stop_mismatch",
        field_name="current_stop",
        material_to_review=1,
        created_at="2026-05-12T09:00:00.000",
        trade_id=trade_id,
        ticker="TST1",
        resolution="unresolved",
    )
    conn.commit()
    return did


# ---------------------------------------------------------------------------
# Part 1 — orphan repo reader
# ---------------------------------------------------------------------------


def test_orphan_reader_returns_unresolved_material_orphan(
    conn: sqlite3.Connection,
):
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    rows = list_unresolved_material_orphans(conn)
    assert [r.discrepancy_id for r in rows] == [did]
    assert rows[0].trade_id is None
    assert rows[0].discrepancy_type == "untracked_broker_position"


def test_orphan_reader_excludes_resolved_orphan(conn: sqlite3.Connection):
    run_id = _new_run(conn)
    _emit_orphan(conn, run_id=run_id, resolution="acknowledged_immaterial")
    assert list_unresolved_material_orphans(conn) == []


def test_orphan_reader_excludes_immaterial_orphan(conn: sqlite3.Connection):
    run_id = _new_run(conn)
    _emit_orphan(conn, run_id=run_id, material=0)
    assert list_unresolved_material_orphans(conn) == []


def test_orphan_reader_excludes_trade_attributed_rows(
    conn: sqlite3.Connection,
):
    """A trade-attributed discrepancy must NOT appear in the orphan reader."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit_normal(conn, run_id=run_id, trade_id=1)
    assert list_unresolved_material_orphans(conn) == []


def test_orphan_reader_excludes_non_untracked_trade_id_null_types(
    conn: sqlite3.Connection,
):
    """Codex R1 Major #1: the reader is scoped to
    ``discrepancy_type='untracked_broker_position'`` — a different material
    ``trade_id IS NULL`` type (here ``equity_delta``) must NOT leak into the
    orphan arm (the web orphan branch only handles untracked_broker_position;
    a leaked row would make the banner-link point at a 409 page)."""
    run_id = _new_run(conn)
    insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="equity_delta",
        field_name="net_liquidating_value",
        material_to_review=1,
        created_at="2026-05-12T09:00:00.000",
        trade_id=None,
        ticker=None,
        resolution="unresolved",
    )
    conn.commit()
    assert list_unresolved_material_orphans(conn) == []


# ---------------------------------------------------------------------------
# Part 1 — UNION into count + banner set
# ---------------------------------------------------------------------------


def test_count_includes_orphan(conn: sqlite3.Connection):
    """Pre-fix: orphan excluded -> count 0. Post-fix: count 1."""
    run_id = _new_run(conn)
    _emit_orphan(conn, run_id=run_id)
    assert count_unresolved_material(conn) == 1


def test_count_includes_orphan_plus_normal(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit_normal(conn, run_id=run_id, trade_id=1)
    _emit_orphan(conn, run_id=run_id)
    assert count_unresolved_material(conn) == 2


def test_banner_set_includes_orphan(conn: sqlite3.Connection):
    """Pre-fix: banner set empty (orphan not pending_ambiguity + excluded by
    JOIN). Post-fix: orphan present."""
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    banner = list_pending_ambiguities_in_banner_set(conn)
    assert did in [d.discrepancy_id for d in banner]


def test_banner_resolve_link_points_at_orphan(conn: sqlite3.Connection):
    run_id = _new_run(conn)
    did = _emit_orphan(conn, run_id=run_id)
    link = fetch_first_pending_ambiguity_resolve_link_path(conn)
    assert link == f"/reconcile/discrepancy/{did}/resolve"


# ---------------------------------------------------------------------------
# C1 — normal trade-attributed discrepancies byte-identical
# ---------------------------------------------------------------------------


def test_c1_normal_count_unchanged_with_no_orphan(conn: sqlite3.Connection):
    """Normal-only world: count is exactly the trade-attributed total."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit_normal(conn, run_id=run_id, trade_id=1)
    assert count_unresolved_material(conn) == 1


def test_c1_normal_banner_set_excludes_unresolved_non_pending(
    conn: sqlite3.Connection,
):
    """C1 lock: an UNRESOLVED (non-pending) trade-attributed row is NOT in
    the banner set (only pending-ambiguity normal rows are) — the orphan
    UNION must not leak trade-attributed unresolved rows into the banner."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit_normal(conn, run_id=run_id, trade_id=1)
    banner = list_pending_ambiguities_in_banner_set(conn)
    assert banner == []
