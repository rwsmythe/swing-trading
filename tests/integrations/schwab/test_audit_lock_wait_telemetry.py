import logging
import time
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.integrations.schwab import audit_service


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_failed_acquisition_logs_warning(tmp_path, caplog):
    # An external connection holds BEGIN IMMEDIATE; the audit conn has a TINY
    # busy_timeout -> record_call_start's BEGIN IMMEDIATE raises OperationalError;
    # on the way out a WARNING reports the wait + busy_timeout.
    db = _db(tmp_path)
    holder = open_connection(db, busy_timeout_ms=30000)
    holder.execute("BEGIN IMMEDIATE")
    holder.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, surface, environment, status) "
        "VALUES ('2026-06-06T00:00:00Z','marketdata.pricehistory','pipeline','production','in_flight')"
    )  # holds the write lock
    audit_conn = open_connection(db, busy_timeout_ms=1)  # 1 ms -> will time out
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            with pytest.raises(sqlite3.OperationalError):
                audit_service.record_call_start(
                    audit_conn, ts="2026-06-06T00:00:01Z", endpoint="marketdata.pricehistory",
                    pipeline_run_id=None, surface="pipeline", environment="production",
                )
        msgs = [r.getMessage() for r in caplog.records]
        assert any("FAILED" in m and "busy_timeout" in m for m in msgs)
        # redaction-irrelevant: no exc_info / traceback attached
        assert all(r.exc_info is None for r in caplog.records)
    finally:
        holder.rollback()
        holder.close()
        audit_conn.close()


def test_slow_success_logs_warning(tmp_path, caplog, monkeypatch):
    # Force a slow BEGIN IMMEDIATE by monkeypatching the timer so the measured
    # wait exceeds the threshold even though the write succeeds.
    db = _db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=30000)
    seq = iter([0.0, 2.0])  # t0=0.0 before BEGIN, t1=2.0 after -> 2.0s wait

    real_monotonic = time.monotonic

    def fake_monotonic():
        try:
            return next(seq)
        except StopIteration:
            return real_monotonic()

    monkeypatch.setattr(audit_service.time, "monotonic", fake_monotonic)
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="marketdata.pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
        msgs = [r.getMessage() for r in caplog.records]
        assert any("slow" in m.lower() and "busy_timeout" in m for m in msgs)
    finally:
        conn.close()


def test_fast_success_does_not_log(tmp_path, caplog):
    db = _db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=30000)
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="marketdata.pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
        assert [r for r in caplog.records if "BEGIN IMMEDIATE" in r.getMessage()] == []
    finally:
        conn.close()
