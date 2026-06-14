from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import swing.patterns.labeling_bars as lb
from swing.data import yfinance_audit_context as ctxmod
from swing.data.db import run_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    run_migrations(c, target_version=30, backup_dir=tmp_path)
    c.close()
    return str(p)


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def _rows(db_path: str):
    c = sqlite3.connect(db_path)
    out = c.execute(
        "SELECT call_type, ticker, status, surface FROM yfinance_calls"
    ).fetchall()
    c.close()
    return out


def test_records_download_single_under_cli_context(db_path, monkeypatch):
    captured = {}

    def spy(*a, **k):
        captured["kwargs"] = k
        return pd.DataFrame(
            {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5],
             "Volume": [10]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
        )
    monkeypatch.setattr(lb.yf, "download", spy)
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    out = lb._yf_download_window_for_labeling(
        "AAPL", start=date(2020, 7, 1), end=date(2020, 7, 10))
    assert not out.empty
    assert captured["kwargs"]["threads"] is False
    rows = _rows(db_path)
    assert rows == [("download_single", "AAPL", "success", "cli")]


def test_empty_records_empty(db_path, monkeypatch):
    monkeypatch.setattr(lb.yf, "download", lambda *a, **k: pd.DataFrame())
    ctxmod._set_for_test(db_path=db_path, pipeline_run_id=None, surface="cli")
    out = lb._yf_download_window_for_labeling(
        "AAPL", start=date(2020, 7, 1), end=date(2020, 7, 10))
    assert out.empty
    assert _rows(db_path)[0][2] == "empty"


def test_no_context_no_row_identical(db_path, monkeypatch):
    df = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [10]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
    )
    monkeypatch.setattr(lb.yf, "download", lambda *a, **k: df.copy())
    out = lb._yf_download_window_for_labeling(
        "AAPL", start=date(2020, 7, 1), end=date(2020, 7, 10))
    assert not out.empty
    assert _rows(db_path) == []
