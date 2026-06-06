import threading
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, connect, open_connection
from swing.integrations.schwab import audit_service
from swing.integrations.schwab.audit_service import CallerHeldTransactionError


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_caller_held_tx_still_rejected(tmp_path):
    db = _db(tmp_path)
    conn = connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")  # caller holds a tx
        with pytest.raises(CallerHeldTransactionError):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="marketdata.pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
    finally:
        conn.rollback()
        conn.close()


def test_record_call_start_commits_in_flight_row_before_return(tmp_path):
    # In-flight visibility contract: the row is committed (visible from a SECOND
    # connection) immediately after record_call_start returns, before any finish.
    db = _db(tmp_path)
    writer = connect(db)
    reader = connect(db)
    try:
        call_id = audit_service.record_call_start(
            writer, ts="2026-06-06T00:00:00Z", endpoint="marketdata.pricehistory",
            pipeline_run_id=None, surface="pipeline", environment="production",
        )
        row = reader.execute(
            "SELECT status FROM schwab_api_calls WHERE call_id=?", (call_id,)
        ).fetchone()
        assert row is not None  # committed + visible
    finally:
        writer.close()
        reader.close()


def test_shared_connection_concurrent_starts_all_land(tmp_path):
    # POST-FIX: ONE shared connection (check_same_thread=False) + the module lock
    # -> N concurrent record_call_start calls all land, zero OperationalError.
    db = _db(tmp_path)
    shared = open_connection(db, check_same_thread=False)
    errors = []
    ids = []
    lock_for_ids = threading.Lock()

    def worker(i):
        try:
            cid = audit_service.record_call_start(
                shared, ts="2026-06-06T00:00:00Z", endpoint="marketdata.pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
            with lock_for_ids:
                ids.append(cid)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert errors == []
        assert len(ids) == 16
        count = shared.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
        assert count == 16
    finally:
        shared.close()


def test_link_reconciliation_run_still_rejects_caller_held_tx(tmp_path):
    # The caller-held-tx rejection must survive the move inside the lock for the
    # link-* functions too (Codex R1 major #2: all 4 tx-owning fns wrapped).
    db = _db(tmp_path)
    conn = connect(db)
    try:
        call_id = audit_service.record_call_start(
            conn, ts="2026-06-06T00:00:00Z", endpoint="accounts.orders.list",
            pipeline_run_id=None, surface="cli", environment="production",
        )
        conn.execute("BEGIN IMMEDIATE")  # caller holds a tx
        with pytest.raises(CallerHeldTransactionError):
            audit_service.link_reconciliation_run(
                conn, call_id=call_id, reconciliation_run_id=1,
            )
    finally:
        conn.rollback()
        conn.close()
