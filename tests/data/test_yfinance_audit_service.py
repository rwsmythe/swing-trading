from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from swing.data import yfinance_audit as svc
from swing.data.db import open_connection, run_migrations
from swing.data.repos import yfinance_calls as repo
from swing.data.yfinance_audit_context import YfinanceAuditContext


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    run_migrations(c, target_version=30, backup_dir=tmp_path)
    c.close()
    return str(p)


def _conn(db_path: str) -> sqlite3.Connection:
    return open_connection(db_path, busy_timeout_ms=0)


def _ctx(db_path: str, **over) -> YfinanceAuditContext:
    base = dict(db_path=db_path, pipeline_run_id=None, surface="cli")
    base.update(over)
    return YfinanceAuditContext(**base)


# ---- record_call_start / record_call_finish ----

def test_record_call_start_inserts_in_flight(db_path):
    conn = _conn(db_path)
    call_id = svc.record_call_start(
        conn, ts="2026-06-14T00:00:00", call_type="download_single",
        ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
    )
    row = repo.get_call(conn, call_id=call_id)
    assert row.status == "in_flight"
    conn.close()


def test_record_call_finish_sets_terminal(db_path):
    conn = _conn(db_path)
    call_id = svc.record_call_start(
        conn, ts="2026-06-14T00:00:00", call_type="download_single",
        ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
    )
    svc.record_call_finish(
        conn, call_id=call_id, response_time_ms=5, status="success",
        rows_returned=3, error_message=None,
    )
    row = repo.get_call(conn, call_id=call_id)
    assert (row.status, row.response_time_ms, row.rows_returned) == ("success", 5, 3)
    conn.close()


def test_start_and_finish_reject_caller_held_tx(db_path):
    conn = _conn(db_path)
    conn.execute("BEGIN")
    with pytest.raises(svc.CallerHeldTransactionError):
        svc.record_call_start(
            conn, ts="2026-06-14T00:00:00", call_type="download_single",
            ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
        )
    conn.rollback()
    # finish too
    conn.execute("BEGIN")
    with pytest.raises(svc.CallerHeldTransactionError):
        svc.record_call_finish(
            conn, call_id=1, response_time_ms=1, status="success",
            rows_returned=0, error_message=None,
        )
    conn.rollback()
    conn.close()


def test_finish_rejects_in_flight_status(db_path):
    conn = _conn(db_path)
    call_id = svc.record_call_start(
        conn, ts="2026-06-14T00:00:00", call_type="download_single",
        ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
    )
    with pytest.raises(ValueError):
        svc.record_call_finish(
            conn, call_id=call_id, response_time_ms=1, status="in_flight",
            rows_returned=0, error_message=None,
        )
    conn.close()


def test_sanitize_error_collapses_and_truncates():
    msg = "line one\n\tline two   with    spaces  " + ("x" * 400)
    out = svc._sanitize_error(Exception(msg))
    assert "\n" not in out and "\t" not in out
    assert "  " not in out
    assert len(out) <= 200


# ---- _record_yf_download unit tests (explicit ctx snapshot) ----

def test_record_success(db_path):
    import pandas as pd
    df = pd.DataFrame({"Close": [1, 2, 3]})
    out = svc._record_yf_download(
        ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
        ticker_count=None, fetch_fn=lambda: df,
    )
    assert out is df
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, rows_returned, response_time_ms FROM yfinance_calls"
    ).fetchone()
    assert row[0] == "success" and row[1] == 3 and row[2] >= 0
    conn.close()


def test_record_empty(db_path):
    import pandas as pd
    out = svc._record_yf_download(
        ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
        ticker_count=None, fetch_fn=lambda: pd.DataFrame(),
    )
    assert out.empty
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, rows_returned FROM yfinance_calls").fetchone()
    assert row == ("empty", 0)
    conn.close()


def test_record_raising_fetch_records_error_and_reraises(db_path):
    def boom():
        raise RuntimeError("network down")
    with pytest.raises(RuntimeError):
        svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
            ticker_count=None, fetch_fn=boom,
        )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, error_message FROM yfinance_calls").fetchone()
    assert row[0] == "error" and "network down" in row[1]
    conn.close()


def test_audit_start_failure_does_not_break_fetch(tmp_path):
    import pandas as pd
    df = pd.DataFrame({"Close": [1]})
    bad = _ctx(str(tmp_path / "nonexistent_dir" / "x.db"))
    # connect to a path whose parent dir is missing -> start fails; fetch returns
    out = svc._record_yf_download(
        ctx=bad, call_type="download_single", ticker="AAPL",
        ticker_count=None, fetch_fn=lambda: df,
    )
    assert out is df


@pytest.mark.parametrize("status,fetch", [
    ("success", "df"),
    ("empty", "empty"),
    ("error", "raise"),
])
def test_audit_finish_failure_does_not_break_fetch(db_path, monkeypatch, status, fetch):
    import pandas as pd
    df = pd.DataFrame({"Close": [1, 2]})

    def raising_finish(*a, **k):
        raise RuntimeError("record_call_finish blew up")
    # _finish_safe wraps record_call_finish in its own try/except -> the raise is
    # SWALLOWED on every terminal path; the original return / re-raise is intact.
    monkeypatch.setattr(svc, "record_call_finish", raising_finish)

    if fetch == "df":
        out = svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
            ticker_count=None, fetch_fn=lambda: df,
        )
        assert out is df
    elif fetch == "empty":
        out = svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
            ticker_count=None, fetch_fn=lambda: pd.DataFrame(),
        )
        assert out.empty
    else:  # raise
        with pytest.raises(RuntimeError, match="boom-fetch"):
            svc._record_yf_download(
                ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
                ticker_count=None,
                fetch_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom-fetch")),
            )


def test_post_fetch_classification_failure_returns_exact_object(db_path):
    class Hostile:
        @property
        def empty(self):
            raise RuntimeError("hostile .empty")
        def __len__(self):
            raise RuntimeError("hostile __len__")
    obj = Hostile()
    out = svc._record_yf_download(
        ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
        ticker_count=None, fetch_fn=lambda: obj,
    )
    assert out is obj  # EXACT object, unchanged


def test_lock_contention_does_not_delay_fetch(db_path):
    import pandas as pd
    df = pd.DataFrame({"Close": [1]})
    blocker = sqlite3.connect(db_path)
    blocker.execute("BEGIN IMMEDIATE")  # hold the write lock
    try:
        t0 = time.monotonic()
        out = svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
            ticker_count=None, fetch_fn=lambda: df,
        )
        elapsed = time.monotonic() - t0
        assert out is df
        assert elapsed < 2.0  # busy_timeout=0 -> instant-fail, no 30s wait
    finally:
        blocker.rollback()
        blocker.close()


def test_finish_contention_does_not_delay_fetch(db_path):
    import pandas as pd
    df = pd.DataFrame({"Close": [1]})
    holder = {}

    def fetch():
        # acquire an external write lock AFTER the fetch "returns"
        b = sqlite3.connect(db_path)
        b.execute("BEGIN IMMEDIATE")
        holder["b"] = b
        return df
    t0 = time.monotonic()
    out = svc._record_yf_download(
        ctx=_ctx(db_path), call_type="download_single", ticker="AAPL",
        ticker_count=None, fetch_fn=fetch,
    )
    elapsed = time.monotonic() - t0
    holder["b"].rollback()
    holder["b"].close()
    assert out is df
    assert elapsed < 2.0


def test_concurrent_fetches_no_writer_record_all_rows(db_path):
    import pandas as pd
    n = 8

    def one(i):
        svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker=f"T{i}",
            ticker_count=None, fetch_fn=lambda: pd.DataFrame({"Close": [i]}),
        )
    threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM yfinance_calls WHERE status='success'"
    ).fetchone()[0]
    conn.close()
    assert count == n


def test_concurrent_fetches_with_writer_return_within_deadline(db_path):
    import pandas as pd
    n = 8
    blocker = sqlite3.connect(db_path)
    blocker.execute("BEGIN IMMEDIATE")
    results = []

    def one(i):
        out = svc._record_yf_download(
            ctx=_ctx(db_path), call_type="download_single", ticker=f"T{i}",
            ticker_count=None, fetch_fn=lambda: pd.DataFrame({"Close": [i]}),
        )
        results.append(out)
    t0 = time.monotonic()
    threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - t0
    blocker.rollback()
    blocker.close()
    assert len(results) == n  # all fetches returned
    assert elapsed < 5.0  # NOT n x 30s convoy
