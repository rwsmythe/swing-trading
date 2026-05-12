"""Phase 9 Sub-bundle C T-C.3 — hypothesis_status_history dataclass + repo.

Per plan §F T-C.3 + spec §3.4.

Coverage:
  - insert_history persists all fields + returns history_id.
  - update_close_open_interval closes the (single) open row per spec §3.4.
  - get_current_status returns the open-interval row or None.
  - list_history_for_hypothesis returns oldest-first.
  - list_all_history returns newest-first.
  - Repo functions do NOT call conn.commit() (caller-controlled tx).
  - Dataclass __post_init__ validators reject invalid enum + reject
    effective_to < effective_from when both set.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import HypothesisStatusHistory
from swing.data.repos.hypothesis_status_history import (
    get_current_status,
    insert_history,
    list_all_history,
    list_history_for_hypothesis,
    update_close_open_interval,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "hsh.db"
    return ensure_schema(db_path)


def _first_hypothesis_id(conn: sqlite3.Connection) -> int:
    """Helper: pick any seeded hypothesis_registry.id."""
    row = conn.execute(
        "SELECT id FROM hypothesis_registry ORDER BY id LIMIT 1"
    ).fetchone()
    return int(row[0])


# ============================================================================
# §1 — insert_history
# ============================================================================


def test_insert_history_returns_assigned_id(conn: sqlite3.Connection) -> None:
    """Close the seed-row open interval first (partial-unique index)."""
    hyp_id = _first_hypothesis_id(conn)
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T10:00:00.000",
    )
    hid = insert_history(
        conn,
        hypothesis_id=hyp_id,
        status="paused",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason="test",
        recorded_at=now_ms(),
    )
    assert isinstance(hid, int)
    assert hid >= 1


def test_insert_history_persists_all_fields(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    # Close existing open row first (seeded one per hypothesis).
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T10:00:00.000",
    )
    rid = now_ms()
    hid = insert_history(
        conn,
        hypothesis_id=hyp_id,
        status="paused",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason="operator test",
        recorded_at=rid,
    )
    row = conn.execute(
        "SELECT hypothesis_id, status, effective_from, effective_to, "
        "change_reason, recorded_at FROM hypothesis_status_history "
        "WHERE history_id = ?", (hid,),
    ).fetchone()
    assert row == (hyp_id, "paused", "2026-05-12T10:00:00.000", None,
                   "operator test", rid)


# ============================================================================
# §2 — update_close_open_interval
# ============================================================================


def test_close_open_interval_affects_one_row(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    affected = update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T11:00:00.000",
    )
    assert affected == 1


def test_close_open_interval_idempotent_returns_zero(
    conn: sqlite3.Connection,
) -> None:
    """Re-closing already-closed row: 0 rows affected."""
    hyp_id = _first_hypothesis_id(conn)
    first = update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T11:00:00.000",
    )
    assert first == 1
    second = update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T12:00:00.000",
    )
    assert second == 0


def test_close_open_interval_does_not_touch_other_hypotheses(
    conn: sqlite3.Connection,
) -> None:
    """UPDATE is scoped via WHERE hypothesis_id."""
    rows = conn.execute(
        "SELECT id FROM hypothesis_registry ORDER BY id"
    ).fetchall()
    assert len(rows) >= 2, "fixture should have at least two seeded hypotheses"
    first_id = int(rows[0][0])
    second_id = int(rows[1][0])
    update_close_open_interval(
        conn,
        hypothesis_id=first_id,
        effective_to="2026-05-12T11:00:00.000",
    )
    other_open = conn.execute(
        "SELECT effective_to FROM hypothesis_status_history "
        "WHERE hypothesis_id = ?", (second_id,),
    ).fetchone()
    assert other_open[0] is None


# ============================================================================
# §3 — get_current_status
# ============================================================================


def test_get_current_status_returns_seed(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    current = get_current_status(conn, hyp_id)
    assert current is not None
    assert current.hypothesis_id == hyp_id
    assert current.effective_to is None
    # Seed: change_reason is NULL.
    assert current.change_reason is None


def test_get_current_status_returns_none_when_no_open_interval(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T11:00:00.000",
    )
    current = get_current_status(conn, hyp_id)
    assert current is None


def test_get_current_status_unknown_hypothesis_returns_none(
    conn: sqlite3.Connection,
) -> None:
    current = get_current_status(conn, 99999)
    assert current is None


# ============================================================================
# §4 — list_history_for_hypothesis
# ============================================================================


def test_list_history_oldest_first(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    # Close seed, append new row at later effective_from.
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T10:00:00.000",
    )
    insert_history(
        conn,
        hypothesis_id=hyp_id,
        status="paused",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason="test",
        recorded_at=now_ms(),
    )
    rows = list_history_for_hypothesis(conn, hyp_id)
    assert len(rows) == 2
    # First row is the original seed (oldest effective_from).
    assert rows[0].effective_to == "2026-05-12T10:00:00.000"
    assert rows[1].effective_to is None  # new open interval


def test_list_history_empty_for_unknown_hypothesis(
    conn: sqlite3.Connection,
) -> None:
    rows = list_history_for_hypothesis(conn, 99999)
    assert rows == []


# ============================================================================
# §5 — list_all_history
# ============================================================================


def test_list_all_history_newest_first(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T10:00:00.000",
    )
    insert_history(
        conn,
        hypothesis_id=hyp_id,
        status="paused",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason="test",
        recorded_at=now_ms(),
    )
    rows = list_all_history(conn, limit=2)
    assert len(rows) == 2
    # Newest first.
    assert rows[0].effective_from >= rows[1].effective_from


def test_list_all_history_respects_limit(conn: sqlite3.Connection) -> None:
    rows = list_all_history(conn, limit=2)
    assert len(rows) <= 2


def test_list_all_history_unlimited_returns_all(
    conn: sqlite3.Connection,
) -> None:
    seed_count = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    rows = list_all_history(conn)
    assert len(rows) == seed_count


# ============================================================================
# §6 — Repo functions do NOT call conn.commit()
# ============================================================================


def test_repo_functions_do_not_commit(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    conn.execute("BEGIN IMMEDIATE")
    update_close_open_interval(
        conn,
        hypothesis_id=hyp_id,
        effective_to="2026-05-12T10:00:00.000",
    )
    insert_history(
        conn,
        hypothesis_id=hyp_id,
        status="paused",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason="test",
        recorded_at=now_ms(),
    )
    assert conn.in_transaction is True
    conn.rollback()
    # After rollback, seed restored — open interval was never closed.
    current = get_current_status(conn, hyp_id)
    assert current is not None
    assert current.change_reason is None  # original seed


# ============================================================================
# §7 — Dataclass __post_init__ validators
# ============================================================================


def test_dataclass_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status must be one of"):
        HypothesisStatusHistory(
            history_id=None,
            hypothesis_id=1,
            status="bogus",
            effective_from="2026-05-12T00:00:00.000",
            effective_to=None,
            change_reason=None,
            recorded_at="2026-05-12T00:00:00.000",
        )


def test_dataclass_rejects_effective_to_before_effective_from() -> None:
    with pytest.raises(ValueError, match="effective_to.*must be"):
        HypothesisStatusHistory(
            history_id=None,
            hypothesis_id=1,
            status="active",
            effective_from="2026-05-12T11:00:00.000",
            effective_to="2026-05-12T10:00:00.000",
            change_reason=None,
            recorded_at="2026-05-12T00:00:00.000",
        )


def test_dataclass_accepts_equal_effective_from_and_to() -> None:
    """Equal timestamps allowed (instantaneous-interval edge case)."""
    h = HypothesisStatusHistory(
        history_id=None,
        hypothesis_id=1,
        status="active",
        effective_from="2026-05-12T10:00:00.000",
        effective_to="2026-05-12T10:00:00.000",
        change_reason=None,
        recorded_at="2026-05-12T00:00:00.000",
    )
    assert h.effective_to == h.effective_from


def test_dataclass_accepts_open_interval_effective_to_null() -> None:
    h = HypothesisStatusHistory(
        history_id=None,
        hypothesis_id=1,
        status="active",
        effective_from="2026-05-12T10:00:00.000",
        effective_to=None,
        change_reason=None,
        recorded_at="2026-05-12T00:00:00.000",
    )
    assert h.effective_to is None


def test_dataclass_all_four_status_values_accepted() -> None:
    for s in ("active", "paused", "closed-escaped", "closed-target-met"):
        HypothesisStatusHistory(
            history_id=None,
            hypothesis_id=1,
            status=s,
            effective_from="2026-05-12T10:00:00.000",
            effective_to=None,
            change_reason=None,
            recorded_at="2026-05-12T00:00:00.000",
        )
