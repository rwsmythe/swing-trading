import sqlite3
from pathlib import Path

from swing.data import db
from swing.data.repos import account_equity_snapshots as repo


def _v29(tmp_path: Path) -> sqlite3.Connection:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29)
    return conn


def test_insert_and_read_roundtrips_basis(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        repo.insert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None,
            recorded_at="t", recorded_by="op", notes=None, basis="net_liq")
    snap = repo.get_latest_snapshot_on_or_before(conn, asof_date="2026-06-01")
    assert snap.basis == "net_liq"


def test_get_latest_filters_basis_net_liq(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        repo.insert_snapshot(
            conn, snapshot_date="2026-06-02", equity_dollars=50.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="cash")
        repo.insert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
    # basis-filtered read returns the net_liq row even though the cash row is newer.
    snap = repo.get_latest_snapshot_on_or_before(
        conn, asof_date="2026-06-30", basis="net_liq")
    assert snap.snapshot_date == "2026-06-01" and snap.basis == "net_liq"


def test_upsert_conflict_key_includes_basis(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        a = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
        b = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=90.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="cash")
        c = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=110.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
    assert a != b  # different basis -> distinct rows
    assert a == c  # same (date, source, basis) -> replaced, same id
