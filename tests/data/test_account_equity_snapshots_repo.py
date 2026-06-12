"""Phase 9 Sub-bundle C T-C.2 — account_equity_snapshots repo tests.

Per plan §B file map + spec §3.5 + §4.4:

  - insert_snapshot / upsert_snapshot (SELECT-then-UPDATE-or-INSERT;
    NOT INSERT OR REPLACE per CLAUDE.md SQLite REPLACE gotcha) preserve PK
    across re-record for same (snapshot_date, source).
  - get_latest_snapshot_on_or_before implements source-ladder precedence
    schwab_api > tos_csv > manual at the same snapshot_date; falls back
    through dates when missing.
  - with_provenance=True returns (winner, suppressed_rows) per spec §3.5
    R4 Minor #3.
  - list_snapshots returns rows ordered newest-snapshot_date-first.
  - Repo functions DO NOT call conn.commit() (Finviz I1 lesson).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import AccountEquitySnapshot
from swing.data.repos.account_equity_snapshots import (
    get_latest_snapshot_on_or_before,
    insert_snapshot,
    list_snapshots,
    upsert_snapshot,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aes_repo.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — insert_snapshot
# ============================================================================


def test_insert_snapshot_returns_assigned_snapshot_id(
    conn: sqlite3.Connection,
) -> None:
    sid = insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    assert isinstance(sid, int)
    assert sid >= 1


def test_insert_snapshot_persists_all_fields(
    conn: sqlite3.Connection,
) -> None:
    recorded = now_ms()
    sid = insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1234.56,
        source="manual",
        source_artifact_path="/tmp/x.csv",
        recorded_at=recorded,
        recorded_by="operator",
        notes="test note",
    basis="net_liq",
    )
    row = conn.execute(
        "SELECT snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes FROM account_equity_snapshots "
        "WHERE snapshot_id = ?",
        (sid,),
    ).fetchone()
    assert row == ("2026-05-12", 1234.56, "manual", "/tmp/x.csv",
                   recorded, "operator", "test note")


# ============================================================================
# §2 — upsert_snapshot: SELECT-then-UPDATE-or-INSERT (PK preservation)
# ============================================================================


def test_upsert_snapshot_first_call_inserts(conn: sqlite3.Connection) -> None:
    sid = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    assert sid >= 1
    row = conn.execute(
        "SELECT equity_dollars FROM account_equity_snapshots "
        "WHERE snapshot_id = ?", (sid,),
    ).fetchone()
    assert row[0] == 1300.0


def test_upsert_snapshot_second_call_updates_same_pk(
    conn: sqlite3.Connection,
) -> None:
    """PK preserved across re-record per CLAUDE.md SQLite REPLACE gotcha.

    Spec §3.5: SELECT-then-UPDATE-or-INSERT keyed on (snapshot_date, source).
    """
    first = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at="2026-05-12T10:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    second = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1400.0,
        source="manual",
        source_artifact_path=None,
        recorded_at="2026-05-12T11:00:00.000",
        recorded_by="operator",
        notes="updated",
    basis="net_liq",
    )
    assert first == second, (
        "PK must be preserved on re-record (no DELETE+INSERT semantics)"
    )
    # Updated content reflects the second call.
    row = conn.execute(
        "SELECT equity_dollars, recorded_at, notes "
        "FROM account_equity_snapshots WHERE snapshot_id = ?",
        (second,),
    ).fetchone()
    assert row == (1400.0, "2026-05-12T11:00:00.000", "updated")


def test_upsert_snapshot_distinct_sources_for_same_date_are_separate_rows(
    conn: sqlite3.Connection,
) -> None:
    """Unique index is (snapshot_date, source). Different sources coexist."""
    manual_id = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    tos_id = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1301.5,
        source="tos_csv",
        source_artifact_path="/tmp/tos.csv",
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    schwab_id = upsert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1302.0,
        source="schwab_api",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    assert len({manual_id, tos_id, schwab_id}) == 3
    rows = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots "
        "WHERE snapshot_date = '2026-05-12'"
    ).fetchone()[0]
    assert rows == 3


# ============================================================================
# §3 — get_latest_snapshot_on_or_before: source-ladder precedence
# ============================================================================


def test_get_latest_returns_none_when_empty(conn: sqlite3.Connection) -> None:
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-12")
    assert result is None


def test_get_latest_returns_only_snapshot(conn: sqlite3.Connection) -> None:
    insert_snapshot(
        conn,
        snapshot_date="2026-05-10",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-12")
    assert isinstance(result, AccountEquitySnapshot)
    assert result.snapshot_date == "2026-05-10"
    assert result.equity_dollars == 1300.0


def test_get_latest_skips_dates_after_asof(conn: sqlite3.Connection) -> None:
    insert_snapshot(
        conn,
        snapshot_date="2026-05-10",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-20",
        equity_dollars=1400.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-15")
    assert result is not None
    assert result.snapshot_date == "2026-05-10"
    assert result.equity_dollars == 1300.0


def test_get_latest_source_ladder_schwab_beats_tos_beats_manual(
    conn: sqlite3.Connection,
) -> None:
    """Same-date source ladder: schwab_api > tos_csv > manual (spec §3.5)."""
    # Insert in REVERSE precedence order to ensure ordering is by source,
    # not insertion.
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at="2026-05-12T10:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1301.0,
        source="tos_csv",
        source_artifact_path=None,
        recorded_at="2026-05-12T11:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1302.0,
        source="schwab_api",
        source_artifact_path=None,
        recorded_at="2026-05-12T12:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-12")
    assert result is not None
    assert result.source == "schwab_api"
    assert result.equity_dollars == 1302.0


def test_get_latest_source_ladder_tos_beats_manual_when_no_schwab(
    conn: sqlite3.Connection,
) -> None:
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at="2026-05-12T10:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1301.0,
        source="tos_csv",
        source_artifact_path=None,
        recorded_at="2026-05-12T11:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-12")
    assert result is not None
    assert result.source == "tos_csv"


def test_get_latest_with_provenance_returns_winner_and_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.5 R4 Minor #3: with_provenance returns (winner, suppressed).

    Suppressed rows are those at the same snapshot_date as the winner that
    lost the source-ladder precedence contest. The operator-meaningful
    display: "TOS CSV from <ts> superseded my manual <ts> entry".
    """
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at="2026-05-12T10:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1301.0,
        source="tos_csv",
        source_artifact_path=None,
        recorded_at="2026-05-12T11:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1302.0,
        source="schwab_api",
        source_artifact_path=None,
        recorded_at="2026-05-12T12:00:00.000",
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(
        conn, asof_date="2026-05-12", with_provenance=True,
    )
    assert result is not None
    winner, suppressed = result
    assert winner.source == "schwab_api"
    suppressed_sources = sorted(s.source for s in suppressed)
    assert suppressed_sources == ["manual", "tos_csv"]


def test_get_latest_with_provenance_empty_suppressed_for_single_source(
    conn: sqlite3.Connection,
) -> None:
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(
        conn, asof_date="2026-05-12", with_provenance=True,
    )
    assert result is not None
    winner, suppressed = result
    assert winner.source == "manual"
    assert suppressed == []


def test_get_latest_with_provenance_none_when_empty(
    conn: sqlite3.Connection,
) -> None:
    result = get_latest_snapshot_on_or_before(
        conn, asof_date="2026-05-12", with_provenance=True,
    )
    assert result is None


def test_get_latest_source_ladder_only_within_same_date(
    conn: sqlite3.Connection,
) -> None:
    """A manual row on a LATER date wins over a schwab row on an EARLIER date.

    Source-ladder is a per-date tiebreaker; the primary key is the
    MAX(snapshot_date <= asof_date) selection.
    """
    insert_snapshot(
        conn,
        snapshot_date="2026-05-10",
        equity_dollars=1300.0,
        source="schwab_api",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1500.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    result = get_latest_snapshot_on_or_before(conn, asof_date="2026-05-12")
    assert result is not None
    assert result.snapshot_date == "2026-05-12"
    assert result.source == "manual"


# ============================================================================
# §4 — list_snapshots
# ============================================================================


def test_list_snapshots_returns_newest_date_first(
    conn: sqlite3.Connection,
) -> None:
    for d in ("2026-05-10", "2026-05-12", "2026-05-11"):
        insert_snapshot(
            conn,
            snapshot_date=d,
            equity_dollars=1300.0,
            source="manual",
            source_artifact_path=None,
            recorded_at=now_ms(),
            recorded_by="operator",
            notes=None,
        basis="net_liq",
        )
    rows = list_snapshots(conn)
    dates = [r.snapshot_date for r in rows]
    assert dates == ["2026-05-12", "2026-05-11", "2026-05-10"]


def test_list_snapshots_respects_limit(conn: sqlite3.Connection) -> None:
    for d in ("2026-05-10", "2026-05-11", "2026-05-12"):
        insert_snapshot(
            conn,
            snapshot_date=d,
            equity_dollars=1300.0,
            source="manual",
            source_artifact_path=None,
            recorded_at=now_ms(),
            recorded_by="operator",
            notes=None,
        basis="net_liq",
        )
    rows = list_snapshots(conn, limit=2)
    assert len(rows) == 2


# ============================================================================
# §5 — Repo functions do NOT call conn.commit() (Finviz I1 lesson)
# ============================================================================


def test_repo_does_not_commit(conn: sqlite3.Connection) -> None:
    """Caller-controlled transaction discipline (plan §I item #5)."""
    # Start a transaction; insert; verify in_transaction stays True.
    conn.execute("BEGIN IMMEDIATE")
    assert conn.in_transaction is True
    insert_snapshot(
        conn,
        snapshot_date="2026-05-12",
        equity_dollars=1300.0,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    basis="net_liq",
    )
    assert conn.in_transaction is True, (
        "repo function must NOT commit the caller's transaction"
    )
    conn.rollback()
    row_count = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots"
    ).fetchone()[0]
    assert row_count == 0, "rollback should have removed the inserted row"
