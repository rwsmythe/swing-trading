import sqlite3
from pathlib import Path

import pytest

from swing.data import db


def _seed_v28(tmp_path: Path) -> sqlite3.Connection:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    # Pre-migration cash_movements: the REAL live 4-row shape (M/D/YY +
    # stray-quote ref on row 1; row 4 ISO/ref=NULL). The pre-v29 table has
    # the legacy 2-kind CHECK + free-text date, so these INSERTs succeed.
    conn.execute("BEGIN")
    conn.executescript(
        """
        INSERT INTO cash_movements (id, date, kind, amount, ref, note) VALUES
          (1, '3/30/26', 'deposit', 100.0, '"115520131470', 'r1 navy fed'),
          (2, '4/29/26', 'deposit', 100.0, '117872135649', 'r2 navy fed'),
          (3, '5/10/26', 'deposit', 600.0, '118723211591', 'r3 usaa'),
          (4, '2026-05-28', 'deposit', 100.0, NULL, 'r4 manual 4a');
        """
    )
    conn.commit()
    return conn


def test_migration_0029_normalizes_dates_and_strips_quote(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    rows = {
        r[0]: (r[1], r[2], r[3], r[4])
        for r in conn.execute(
            "SELECT id, date, kind, amount, ref FROM cash_movements ORDER BY id"
        )
    }
    # REAL live values (verified vs ~/swing-data/swing.db 2026-06-11).
    assert rows[1] == ("2026-03-30", "deposit", 100.0, "115520131470")  # quote stripped
    assert rows[2] == ("2026-04-29", "deposit", 100.0, "117872135649")
    assert rows[3] == ("2026-05-10", "deposit", 600.0, "118723211591")
    assert rows[4] == ("2026-05-28", "deposit", 100.0, None)  # ISO row untouched
    # id=4 preserved so reconciliation_discrepancies 66/67 (cash_movement_id=4) FK survives.
    assert 4 in rows


def test_migration_0029_widens_kind_check_to_five(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    # Each of the 5 kinds now inserts; an unknown kind still raises.
    for k in ("deposit", "withdraw", "interest", "dividend", "fee"):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-01', ?, 1.0, NULL, NULL)",
            (k,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-01', 'bogus', 1.0, NULL, NULL)"
        )


def test_migration_0029_iso_date_check_and_glob(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('6/1/26', 'deposit', 1.0, NULL, NULL)"
        )  # non-ISO rejected


def test_migration_0029_aborts_on_unexpected_noniso_shape(tmp_path):
    # A 5th legacy row with an UNPINNED shape must ABORT (safe-fail), not
    # silently pass through. The GLOB CHECK on the rebuilt table is the gate.
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO cash_movements (id, date, kind, amount, ref, note) "
        "VALUES (5, '03/30/26', 'deposit', 1.0, NULL, 'unexpected shape')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.run_migrations(conn, target_version=29)
    # The migration rolled back: still v28, the table untouched.
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 28


def test_migration_0029_preserves_discrepancy_fk_to_cash_movement(tmp_path):
    # Seed a reconciliation run + a discrepancy referencing cash_movement_id=4
    # (the live 66/67 shape). After the cash_movements rebuild under the
    # runner's foreign_keys=OFF, the FK must still resolve.
    conn = _seed_v28(tmp_path)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO reconciliation_runs (run_id, source, state, started_ts, "
        "period_start, period_end) VALUES (48, 'schwab_api', 'completed', '1', "
        "'2026-05-01', '2026-05-30')"
    )
    # Mirror the live 66/67 shape: a pending_ambiguity_resolution row carries a
    # non-NULL ambiguity_kind (the discrepancy CHECK ties the two together).
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (discrepancy_id, run_id, "
        "discrepancy_type, field_name, cash_movement_id, material_to_review, "
        "created_at, resolution, ambiguity_kind) VALUES (66, 48, "
        "'cash_movement_mismatch', 'net_amount', 4, 1, '1', "
        "'pending_ambiguity_resolution', 'schwab_returned_no_match')"
    )
    conn.commit()
    db.run_migrations(conn, target_version=29)
    cm_id = conn.execute(
        "SELECT cash_movement_id FROM reconciliation_discrepancies "
        "WHERE discrepancy_id=66"
    ).fetchone()[0]
    assert cm_id == 4
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migration_0029_recreates_ux_cash_ref_and_blocks_dup_ref(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ux_cash_ref'"
    ).fetchone()
    assert idx is not None
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-02', 'deposit', 9.0, '115520131470', 'dup')"
        )


def test_migration_0029_backfills_snapshot_basis_net_liq(tmp_path):
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes) "
        "VALUES ('2026-05-01', 1234.0, 'manual', NULL, '2026-05-01T00:00:00', 'op', NULL)"
    )
    conn.commit()
    db.run_migrations(conn, target_version=29)
    basis = conn.execute(
        "SELECT basis FROM account_equity_snapshots WHERE snapshot_date='2026-05-01'"
    ).fetchone()[0]
    assert basis == "net_liq"


def test_migration_0029_snapshot_basis_index_allows_coexisting_basis(tmp_path):
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29)
    # Same date+source, different basis -> BOTH coexist (the widened index).
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes, basis) "
        "VALUES ('2026-06-01', 100.0, 'manual', NULL, 't', 'op', NULL, 'net_liq')"
    )
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes, basis) "
        "VALUES ('2026-06-01', 90.0, 'manual', NULL, 't', 'op', NULL, 'cash')"
    )
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE snapshot_date='2026-06-01'"
    ).fetchone()[0]
    assert n == 2


def test_migration_0029_migrate_twice_is_noop(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    db.run_migrations(conn, target_version=29)  # second pass -- no error, no change
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 29


def test_migration_0029_backup_gate_strict_equality(tmp_path):
    # A v28 file-backed DB fires the gate (writes a backup); a v27->v29 multi-step
    # walk bypasses it (strict ==28). Mirror the prior gates' test shape:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.close()
    backups_before = list(tmp_path.glob("swing-pre-cash-recon-migration-*.db"))
    assert backups_before == []
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29, backup_dir=tmp_path)
    backups_after = list(tmp_path.glob("swing-pre-cash-recon-migration-*.db"))
    assert len(backups_after) == 1
