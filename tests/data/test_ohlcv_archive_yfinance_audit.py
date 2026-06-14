from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import swing.data.ohlcv_archive as arch
from swing.data import yfinance_audit_context as ctxmod
from swing.data.db import run_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    run_migrations(c, target_version=30, backup_dir=tmp_path)
    # seed pipeline_runs id=7 so pipeline-surface audit rows satisfy the FK
    c.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES "
        "(7,'2026-06-14T00:00:00','manual','2026-06-13','2026-06-14','running','tok')"
    )
    c.commit()
    c.close()
    return str(p)


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def _rows(db_path: str) -> list[tuple]:
    c = sqlite3.connect(db_path)
    out = c.execute(
        "SELECT call_type, ticker, ticker_count, status, rows_returned, surface "
        "FROM yfinance_calls ORDER BY call_id"
    ).fetchall()
    c.close()
    return out


# ---- _yf_download_window (single) ----

def test_single_success_records(db_path, monkeypatch):
    captured = {}

    def spy(*a, **k):
        captured["args"] = a
        captured["kwargs"] = k
        return pd.DataFrame(
            {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5],
             "Volume": [100]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
        )
    monkeypatch.setattr(arch.yf, "download", spy)
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    out = arch._yf_download_window("aapl", start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert not out.empty
    # kwargs unchanged (no-measurement-change lock)
    assert captured["kwargs"]["threads"] is False
    assert captured["kwargs"]["auto_adjust"] is False
    assert captured["kwargs"]["actions"] is False
    assert captured["kwargs"]["progress"] is False
    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0][0] == "download_single"
    assert rows[0][1] == "AAPL"  # normalized
    assert rows[0][3] == "success"
    assert rows[0][5] == "cli"


def test_single_empty_records_empty(db_path, monkeypatch):
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: pd.DataFrame())
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    out = arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert out.empty
    rows = _rows(db_path)
    assert rows[0][3] == "empty" and rows[0][4] == 0


def test_single_raise_records_error_and_reraises(db_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("net down")
    monkeypatch.setattr(arch.yf, "download", boom)
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    with pytest.raises(RuntimeError):
        arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    rows = _rows(db_path)
    assert rows[0][3] == "error"


def test_single_no_context_no_row_identical_return(db_path, monkeypatch):
    df = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
    )
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: df.copy())
    # NO context set
    out = arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert not out.empty
    assert _rows(db_path) == []


# ---- _fetch_chunk (batch) ----

def _multi_df(tickers):
    cols = pd.MultiIndex.from_product(
        [tickers, ["Open", "High", "Low", "Close", "Volume"]]
    )
    data = [[1.0] * (len(tickers) * 5)]
    return pd.DataFrame(
        data, columns=cols, index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")])
    )


def test_batch_one_row_with_ticker_count(db_path, monkeypatch):
    captured = {}

    def spy(*a, **k):
        captured["kwargs"] = k
        return _multi_df(["AAA", "BBB", "CCC"])
    monkeypatch.setattr(arch.yf, "download", spy)
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=7, surface="pipeline")
    arch._fetch_chunk(["AAA", "BBB", "CCC"], start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert captured["kwargs"]["threads"] is True
    assert captured["kwargs"]["group_by"] == "ticker"
    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0][0] == "download_batch"
    assert rows[0][1] is None
    assert rows[0][2] == 3
    assert rows[0][3] == "success"


def test_batch_chunk_exception_records_error_and_falls_back_byte_identical(db_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("whole chunk down")
    monkeypatch.setattr(arch.yf, "download", boom)
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=7, surface="pipeline")
    chunk = ["AAA", "BBB"]
    result = arch._fetch_chunk(chunk, start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert result == ({}, list(chunk), True)  # byte-identical fallback
    rows = _rows(db_path)
    assert rows[0][0] == "download_batch" and rows[0][3] == "error"


def test_batch_empty_records_empty(db_path, monkeypatch):
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: pd.DataFrame())
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=7, surface="pipeline")
    chunk = ["AAA", "BBB"]
    result = arch._fetch_chunk(chunk, start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert result == ({}, list(chunk), True)
    rows = _rows(db_path)
    assert rows[0][3] == "empty"


def test_always_on_under_sandbox(db_path, monkeypatch):
    # No environment read anywhere -> a row records regardless of sandbox/prod.
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: pd.DataFrame())
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert len(_rows(db_path)) == 1


def test_audit_failure_does_not_break_fetch(tmp_path, monkeypatch):
    df = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
    )
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: df.copy())
    # bogus db_path (missing parent dir) -> audit start fails; fetch still returns
    bad = str(tmp_path / "missing" / "x.db")
    ctxmod._set_for_test(db_path=bad, pipeline_run_id=None, surface="cli")
    out = arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert not out.empty


def test_ohlcv_archive_import_is_db_free():
    # In a FRESH subprocess, importing ohlcv_archive must NOT pull in the DB
    # module or the repo (the deliberate DB-free-at-import property).
    code = (
        "import sys, swing.data.ohlcv_archive; "
        "assert 'swing.data.db' not in sys.modules, 'db imported'; "
        "assert 'swing.data.repos.yfinance_calls' not in sys.modules, 'repo imported'; "
        "assert 'swing.data.yfinance_audit' not in sys.modules, 'service imported'"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert r.returncode == 0, r.stderr
