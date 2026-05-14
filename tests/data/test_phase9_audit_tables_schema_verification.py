"""Phase 9 Sub-bundle C T-C.0 — consumer-side schema verification.

This is a CONSUMER-SIDE verification gate: Sub-bundle C builds repo + service
+ CLI surfaces on top of migration 0017 (landed atomically by Sub-bundle A).
Before any Bundle C repo/service code exists, this test asserts the two
tables Bundle C consumes are shaped exactly as Bundle C expects.

Scope:
  - ``hypothesis_status_history`` — 7 columns, 2 indexes (1 partial-unique
    on (hypothesis_id) WHERE effective_to IS NULL, 1 plain on
    (hypothesis_id, effective_from)); FK CASCADE to hypothesis_registry(id).
  - ``account_equity_snapshots`` — 8 columns, 2 indexes (1 unique on
    (snapshot_date, source), 1 plain on (snapshot_date)); CHECK enum on
    ``source``; CHECK > 0 on ``equity_dollars``.

Overlaps with ``tests/data/test_migration_0017.py`` by design — that test is
authored from the migration-runner perspective; this one is authored from
Bundle C's consumer perspective and asserts only the Bundle-C-binding
invariants. If a future migration edit breaks Bundle C's assumptions, this
test fails with Bundle-C-shaped error messages.

See plan §F T-C.0 acceptance criteria + dispatch brief §0.5 #5.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "bundle_c_consumer.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — hypothesis_status_history (consumer-binding shape)
# ============================================================================


_HSH_EXPECTED_COLS: frozenset[str] = frozenset({
    "history_id",
    "hypothesis_id",
    "status",
    "effective_from",
    "effective_to",
    "change_reason",
    "recorded_at",
})


def test_hypothesis_status_history_has_seven_columns_for_consumer(
    conn: sqlite3.Connection,
) -> None:
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(hypothesis_status_history)"
    ).fetchall()}
    assert cols == _HSH_EXPECTED_COLS, (
        f"Bundle C consumer schema drift on hypothesis_status_history; "
        f"missing={_HSH_EXPECTED_COLS - cols}; extra={cols - _HSH_EXPECTED_COLS}"
    )
    assert len(cols) == 7


def test_hypothesis_status_history_pk_is_history_id_autoincrement(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(hypothesis_status_history)")
    pk_cols = [r[1] for r in cur.fetchall() if r[5] == 1]
    assert pk_cols == ["history_id"]


def test_hypothesis_status_history_partial_unique_current_index(
    conn: sqlite3.Connection,
) -> None:
    """ux_hypothesis_status_history_current: ONE open-interval row per hypothesis."""
    idx_rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name='hypothesis_status_history'"
    ).fetchall()
    by_name = {r[0]: r[1] for r in idx_rows}
    assert "ux_hypothesis_status_history_current" in by_name
    assert "ix_hypothesis_status_history_hyp" in by_name
    partial_sql = by_name["ux_hypothesis_status_history_current"] or ""
    assert "WHERE effective_to IS NULL" in partial_sql
    assert "UNIQUE" in partial_sql.upper()


def test_hypothesis_status_history_fk_cascade_to_registry(
    conn: sqlite3.Connection,
) -> None:
    fks = conn.execute(
        "PRAGMA foreign_key_list(hypothesis_status_history)"
    ).fetchall()
    # Find the FK whose "from" column is hypothesis_id.
    hyp_fk = [f for f in fks if f[3] == "hypothesis_id"]
    assert len(hyp_fk) == 1, f"expected exactly one FK on hypothesis_id; got {fks}"
    fk = hyp_fk[0]
    # PRAGMA foreign_key_list columns: id, seq, table, from, to, on_update,
    # on_delete, match.
    assert fk[2] == "hypothesis_registry"
    assert fk[4] == "id"
    assert fk[6] == "CASCADE"


def test_hypothesis_status_history_status_check_enum_matches_registry(
    conn: sqlite3.Connection,
) -> None:
    """CHECK enum on status matches hypothesis_registry.status vocabulary."""
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO hypothesis_status_history ("
            "hypothesis_id, status, effective_from, recorded_at) "
            "VALUES (1, 'invalid_status', "
            "'2026-05-12T00:00:00.000', '2026-05-12T00:00:00.000')"
        )


# ============================================================================
# §2 — account_equity_snapshots (consumer-binding shape)
# ============================================================================


_AES_EXPECTED_COLS: frozenset[str] = frozenset({
    "snapshot_id",
    "snapshot_date",
    "equity_dollars",
    "source",
    "source_artifact_path",
    "recorded_at",
    "recorded_by",
    "notes",
    # Phase 11 (migration 0018) ALTER ADD COLUMN: schwab_account_hash TEXT
    # NULLABLE. Audit-side attribution to schwab_api_calls. Bundle C
    # consumer-side contract retained (the 8 originals still present); new
    # column is additive.
    "schwab_account_hash",
})


def test_account_equity_snapshots_has_eight_columns_for_consumer(
    conn: sqlite3.Connection,
) -> None:
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(account_equity_snapshots)"
    ).fetchall()}
    assert cols == _AES_EXPECTED_COLS, (
        f"Bundle C consumer schema drift on account_equity_snapshots; "
        f"missing={_AES_EXPECTED_COLS - cols}; extra={cols - _AES_EXPECTED_COLS}"
    )
    # Phase 11 (migration 0018) added schwab_account_hash → 9 columns.
    assert len(cols) == 9


def test_account_equity_snapshots_pk_is_snapshot_id_autoincrement(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(account_equity_snapshots)")
    pk_cols = [r[1] for r in cur.fetchall() if r[5] == 1]
    assert pk_cols == ["snapshot_id"]


def test_account_equity_snapshots_unique_date_source_index(
    conn: sqlite3.Connection,
) -> None:
    idx_rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name='account_equity_snapshots'"
    ).fetchall()
    by_name = {r[0]: r[1] for r in idx_rows}
    assert "ux_account_equity_snapshots_date_source" in by_name
    assert "ix_account_equity_snapshots_date" in by_name
    unique_sql = (by_name["ux_account_equity_snapshots_date_source"] or "").upper()
    assert "UNIQUE" in unique_sql
    assert "SNAPSHOT_DATE" in unique_sql
    assert "SOURCE" in unique_sql


def test_account_equity_snapshots_source_enum_v1_v2_reserved(
    conn: sqlite3.Connection,
) -> None:
    """CHECK enum must include the three sources Bundle C / D / V2 reserve."""
    # Manual works (Bundle C V1 cadence).
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-05-12', 1300.0, 'manual', "
        "'2026-05-12T00:00:00.000', 'operator')"
    )
    # tos_csv reserved.
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-05-12', 1301.0, 'tos_csv', "
        "'2026-05-12T00:00:00.001', 'operator')"
    )
    # schwab_api reserved.
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-05-12', 1302.0, 'schwab_api', "
        "'2026-05-12T00:00:00.002', 'operator')"
    )
    # Unreserved source rejected.
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
            "VALUES ('2026-05-12', 1303.0, 'csv_import', "
            "'2026-05-12T00:00:00.003', 'operator')"
        )


def test_account_equity_snapshots_equity_positive_check(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
            "VALUES ('2026-05-12', -1.0, 'manual', "
            "'2026-05-12T00:00:00.000', 'operator')"
        )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
            "VALUES ('2026-05-12', 0.0, 'manual', "
            "'2026-05-12T00:00:00.000', 'operator')"
        )


def test_account_equity_snapshots_unique_date_source_blocks_duplicate(
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-05-12', 1300.0, 'manual', "
        "'2026-05-12T00:00:00.000', 'operator')"
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
            "VALUES ('2026-05-12', 1400.0, 'manual', "
            "'2026-05-12T00:00:00.001', 'operator')"
        )
