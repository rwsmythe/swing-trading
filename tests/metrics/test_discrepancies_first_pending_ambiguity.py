"""Phase 12.5 #2 T-2.9 — banner first-pending-ambiguity helper tests.

Discriminating coverage for the two new helpers in
``swing/metrics/discrepancies.py``:

- :func:`list_pending_ambiguities_in_banner_set` — returns the banner
  trade-set narrowed to ``resolution = 'pending_ambiguity_resolution'``,
  sorted ``discrepancy_id ASC`` per LOCK §1.2 #6.
- :func:`fetch_first_pending_ambiguity_resolve_link_path` — returns the
  resolve-form URL for the oldest pending row, or ``None`` when empty.

Mirrors the seed harness from
``tests/metrics/test_discrepancies_predicate_widening.py``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import insert_discrepancy, insert_run
from swing.metrics.discrepancies import (
    fetch_first_pending_ambiguity_resolve_link_path,
    list_pending_ambiguities_in_banner_set,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase12_5_t_2_9.db")


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    state: str = "entered",
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


def _emit_pending(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int | None,
    explicit_discrepancy_id: int | None = None,
    material: int = 1,
) -> int:
    """INSERT a ``pending_ambiguity_resolution`` row with optional
    explicit ``discrepancy_id`` (so callers can control sort order)."""
    if explicit_discrepancy_id is None:
        cur = conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, trade_id, ticker, field_name, "
            "material_to_review, resolution, ambiguity_kind, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, "stop_mismatch", trade_id, "TST", "current_stop",
                material, "pending_ambiguity_resolution", "unsupported",
                "2026-05-12T09:00:00.000",
            ),
        )
        did = cur.lastrowid
    else:
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "discrepancy_id, run_id, discrepancy_type, trade_id, ticker, "
            "field_name, material_to_review, resolution, ambiguity_kind, "
            "created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                explicit_discrepancy_id, run_id, "stop_mismatch",
                trade_id, "TST", "current_stop", material,
                "pending_ambiguity_resolution", "unsupported",
                "2026-05-12T09:00:00.000",
            ),
        )
        did = explicit_discrepancy_id
    conn.commit()
    return did


def _emit_unresolved(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int | None,
    material: int = 1,
) -> int:
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="stop_mismatch",
        field_name="current_stop",
        material_to_review=material,
        created_at="2026-05-12T09:00:00.000",
        trade_id=trade_id,
        ticker="TST",
        resolution="unresolved",
    )
    conn.commit()
    return did


def test_list_pending_ambiguities_in_banner_set_returns_oldest_first(
    conn: sqlite3.Connection,
) -> None:
    """Seed pending rows with explicit ids (A=10, B=5, C=20) all on
    active trades; helper MUST return them sorted by discrepancy_id ASC
    -> [B(5), A(10), C(20)] per LOCK §1.2 #6.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    a = _emit_pending(conn, run_id=run_id, trade_id=1,
                     explicit_discrepancy_id=10)
    b = _emit_pending(conn, run_id=run_id, trade_id=1,
                     explicit_discrepancy_id=5)
    c = _emit_pending(conn, run_id=run_id, trade_id=1,
                     explicit_discrepancy_id=20)
    result = list_pending_ambiguities_in_banner_set(conn)
    ids = [d.discrepancy_id for d in result]
    assert ids == [b, a, c]
    assert ids == [5, 10, 20]


def test_list_pending_ambiguities_in_banner_set_excludes_orphan_trade_id_null(
    conn: sqlite3.Connection,
) -> None:
    """Discrepancy with ``trade_id IS NULL`` MUST be excluded — mirrors
    banner-count helpers which JOIN on trades."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    on_trade = _emit_pending(conn, run_id=run_id, trade_id=1)
    _emit_pending(conn, run_id=run_id, trade_id=None)
    result = list_pending_ambiguities_in_banner_set(conn)
    ids = [d.discrepancy_id for d in result]
    assert ids == [on_trade]


def test_list_pending_ambiguities_in_banner_set_excludes_immaterial(
    conn: sqlite3.Connection,
) -> None:
    """Pending row with ``material_to_review=0`` MUST be excluded."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    material_id = _emit_pending(
        conn, run_id=run_id, trade_id=1, material=1,
    )
    _emit_pending(conn, run_id=run_id, trade_id=1, material=0)
    result = list_pending_ambiguities_in_banner_set(conn)
    ids = [d.discrepancy_id for d in result]
    assert ids == [material_id]


def test_list_pending_ambiguities_in_banner_set_excludes_unresolved_resolution(
    conn: sqlite3.Connection,
) -> None:
    """The broader banner-count helper includes 'unresolved' for the
    banner count itself; THIS helper is narrower — it returns ONLY
    ``pending_ambiguity_resolution`` rows. A material 'unresolved' row
    on an active trade MUST be excluded.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    pending_id = _emit_pending(conn, run_id=run_id, trade_id=1)
    _emit_unresolved(conn, run_id=run_id, trade_id=1)
    result = list_pending_ambiguities_in_banner_set(conn)
    ids = [d.discrepancy_id for d in result]
    assert ids == [pending_id]


def test_fetch_first_pending_ambiguity_resolve_link_path_returns_none_when_empty(
    conn: sqlite3.Connection,
) -> None:
    """DB with no pending_ambiguity_resolution rows → returns None."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    # Plant only 'unresolved' rows — banner count != 0 but helper returns
    # None because there is no pending-ambiguity row to point at.
    _emit_unresolved(conn, run_id=run_id, trade_id=1)
    assert fetch_first_pending_ambiguity_resolve_link_path(conn) is None


def test_fetch_first_pending_ambiguity_resolve_link_path_returns_oldest_url(
    conn: sqlite3.Connection,
) -> None:
    """DB with 2 pending rows (id=5, id=10) → returns the resolve-form
    path for id=5 (oldest)."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit_pending(conn, run_id=run_id, trade_id=1,
                  explicit_discrepancy_id=10)
    _emit_pending(conn, run_id=run_id, trade_id=1,
                  explicit_discrepancy_id=5)
    result = fetch_first_pending_ambiguity_resolve_link_path(conn)
    assert result == "/reconcile/discrepancy/5/resolve"
