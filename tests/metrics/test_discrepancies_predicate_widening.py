"""Phase 12 Sub-sub-bundle C.D T-D.10 — banner predicate widening.

Per plan §E.10 + OQ-7 LOCK: the Phase 10 dashboard banner predicate
widens from ``WHERE d.resolution = 'unresolved'`` to
``WHERE d.resolution IN ('unresolved', 'pending_ambiguity_resolution')``
so tier-2 ambiguity-pending discrepancies appear in the operator's
banner count + per-trade indicator alongside true unresolved rows.

Auto-corrected (``auto_corrected_from_schwab``) + operator-resolved
(``operator_resolved_ambiguity``) + acknowledged_immaterial /
journal_corrected / dispute_open remain EXCLUDED — the banner only
surfaces what still requires operator attention.

Discriminating coverage:
- ``count_unresolved_material`` (transitively via the two repo helpers)
- ``list_unresolved_material_for_active_trades`` (Phase 9 §5.1 #1)
- ``list_unresolved_material_for_closed_trades`` (Phase 9 §5.1 #2)
- ``list_unresolved_material_for_trade`` (Phase 10 T-E.6 per-trade)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import (
    insert_discrepancy,
    insert_run,
    list_unresolved_material_for_active_trades,
    list_unresolved_material_for_closed_trades,
)
from swing.metrics.discrepancies import (
    count_unresolved_material,
    list_unresolved_material_for_trade,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase12_t_d_10.db")


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
        source="manual",
        started_ts="2026-05-12T09:00:00.000",
        state="completed",
        finished_ts="2026-05-12T09:00:01.000",
    )
    conn.commit()
    return run_id


def _emit(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int | None,
    material: int = 1,
    resolution: str = "unresolved",
    ambiguity_kind: str | None = None,
    discrepancy_type: str = "stop_mismatch",
) -> int:
    """Insert a discrepancy row with optional ambiguity_kind.

    ``insert_discrepancy`` repo helper does not (yet) expose
    ``ambiguity_kind`` as a kwarg; T-D.10 only widens the SELECT
    predicates, not the INSERT helper. To plant a
    ``pending_ambiguity_resolution`` row (which the cross-column CHECK
    requires ``ambiguity_kind IS NOT NULL`` for), we INSERT via plain
    SQL bypassing the helper. This mirrors the C.C apply-tier2 service's
    direct INSERT pattern.
    """
    if resolution == "unresolved" and ambiguity_kind is None:
        did = insert_discrepancy(
            conn,
            run_id=run_id,
            discrepancy_type=discrepancy_type,
            field_name="current_stop",
            material_to_review=material,
            created_at="2026-05-12T09:00:00.000",
            trade_id=trade_id,
            ticker="TST",
            resolution=resolution,
        )
    else:
        cur = conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, trade_id, ticker, field_name, "
            "material_to_review, resolution, ambiguity_kind, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, discrepancy_type, trade_id, "TST",
                "current_stop", material, resolution, ambiguity_kind,
                "2026-05-12T09:00:00.000",
            ),
        )
        did = cur.lastrowid
    conn.commit()
    return did


# ---------------------------------------------------------------------------
# count_unresolved_material — widened predicate
# ---------------------------------------------------------------------------


def test_count_includes_pending_ambiguity_resolution_on_active_trade(
    conn: sqlite3.Connection,
):
    """T-D.10 binding: 1 unresolved + 1 pending_ambiguity_resolution +
    1 auto_corrected_from_schwab on a SINGLE active trade → count = 2.

    The auto-corrected row stays EXCLUDED (it's terminal-state; no
    operator action remaining).
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(
        conn, run_id=run_id, trade_id=1,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    _emit(
        conn, run_id=run_id, trade_id=1,
        resolution="auto_corrected_from_schwab",
    )
    assert count_unresolved_material(conn) == 2


def test_count_includes_pending_ambiguity_resolution_on_closed_trade(
    conn: sqlite3.Connection,
):
    """Closed-trade path also widens (covers
    ``list_unresolved_material_for_closed_trades``).
    """
    _seed_trade(conn, trade_id=1, state="closed")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(
        conn, run_id=run_id, trade_id=1,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    assert count_unresolved_material(conn) == 2


def test_count_excludes_terminal_resolutions(conn: sqlite3.Connection):
    """Terminal-state resolutions remain EXCLUDED:
    ``auto_corrected_from_schwab`` / ``operator_resolved_ambiguity`` /
    ``operator_overridden`` / ``acknowledged_immaterial`` /
    ``journal_corrected``.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1,
          resolution="auto_corrected_from_schwab")
    # operator_resolved_ambiguity REQUIRES ambiguity_kind per the
    # cross-column CHECK introduced by migration 0019.
    _emit(conn, run_id=run_id, trade_id=1,
          resolution="operator_resolved_ambiguity",
          ambiguity_kind="unsupported")
    _emit(conn, run_id=run_id, trade_id=1,
          resolution="operator_overridden")
    _emit(conn, run_id=run_id, trade_id=1,
          resolution="acknowledged_immaterial")
    _emit(conn, run_id=run_id, trade_id=1,
          resolution="journal_corrected")
    assert count_unresolved_material(conn) == 0


def test_count_still_respects_material_to_review(conn: sqlite3.Connection):
    """material_to_review=0 → still EXCLUDED even when resolution is
    ``pending_ambiguity_resolution``.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(
        conn, run_id=run_id, trade_id=1,
        material=0,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    assert count_unresolved_material(conn) == 0


# ---------------------------------------------------------------------------
# list_unresolved_material_for_active_trades — widened predicate
# ---------------------------------------------------------------------------


def test_active_trades_helper_includes_pending_ambiguity_resolution(
    conn: sqlite3.Connection,
):
    """Helper returns BOTH unresolved + pending_ambiguity_resolution rows
    on active-trade attribution.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    _seed_trade(conn, trade_id=2, state="managing", ticker="TST2")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(
        conn, run_id=run_id, trade_id=2,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    rows = list_unresolved_material_for_active_trades(conn)
    assert len(rows) == 2
    resolutions = {r.resolution for r in rows}
    assert resolutions == {"unresolved", "pending_ambiguity_resolution"}


# ---------------------------------------------------------------------------
# list_unresolved_material_for_closed_trades — widened predicate
# ---------------------------------------------------------------------------


def test_closed_trades_helper_includes_pending_ambiguity_resolution(
    conn: sqlite3.Connection,
):
    _seed_trade(conn, trade_id=1, state="closed")
    _seed_trade(conn, trade_id=2, state="reviewed", ticker="TST2")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(
        conn, run_id=run_id, trade_id=2,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    rows = list_unresolved_material_for_closed_trades(conn)
    assert len(rows) == 2
    resolutions = {r.resolution for r in rows}
    assert resolutions == {"unresolved", "pending_ambiguity_resolution"}


# ---------------------------------------------------------------------------
# list_unresolved_material_for_trade — widened predicate (Phase 10 T-E.6)
# ---------------------------------------------------------------------------


def test_per_trade_helper_includes_pending_ambiguity_resolution(
    conn: sqlite3.Connection,
):
    """T-E.6 per-trade indicator: surfaces tier-2 ambiguity-pending
    alongside true unresolved rows for the operator on /trades/{id}.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(
        conn, run_id=run_id, trade_id=1,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    _emit(
        conn, run_id=run_id, trade_id=1,
        resolution="auto_corrected_from_schwab",
    )
    rows = list_unresolved_material_for_trade(conn, 1)
    assert len(rows) == 2
    resolutions = {r.resolution for r in rows}
    assert resolutions == {"unresolved", "pending_ambiguity_resolution"}


def test_per_trade_helper_excludes_other_trade_ids(
    conn: sqlite3.Connection,
):
    """Per-trade scoping: pending-ambiguity rows attributed to trade 2
    do NOT surface on trade 1 list.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    _seed_trade(conn, trade_id=2, state="entered", ticker="TST2")
    run_id = _new_run(conn)
    _emit(
        conn, run_id=run_id, trade_id=2,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
    )
    rows = list_unresolved_material_for_trade(conn, 1)
    assert rows == []
