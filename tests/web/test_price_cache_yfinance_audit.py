from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from swing.data import yfinance_audit_context as ctxmod


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def _rows(db_path):
    c = sqlite3.connect(db_path)
    out = c.execute(
        "SELECT call_type, ticker, status, rows_returned, surface FROM yfinance_calls"
    ).fetchall()
    c.close()
    return out


def _intraday_df():
    return pd.DataFrame(
        {"Close": [1.0, 1.5]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10 09:30"),
                                pd.Timestamp("2026-06-10 09:31")]),
    )


def test_intraday_success_records_download_intraday(seeded_db, monkeypatch):
    from swing.web import price_cache as pcmod
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    captured = {}
    import yfinance as yf

    def spy(*a, **k):
        captured["kwargs"] = k
        return _intraday_df()
    monkeypatch.setattr(yf, "download", spy)
    ctxmod._set_for_test(
        db_path=str(cfg.paths.db_path), pipeline_run_id=None, surface="web")
    price = cache._fetch_live_price("AAPL")
    assert price == 1.5
    assert captured["kwargs"]["period"] == "1d"
    assert captured["kwargs"]["interval"] == "1m"
    assert captured["kwargs"]["group_by"] == "column"
    assert captured["kwargs"]["threads"] is False
    rows = _rows(cfg.paths.db_path)
    assert rows == [("download_intraday", "AAPL", "success", 2, "web")]


def test_intraday_empty_records_empty_and_caller_still_raises(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    import yfinance as yf
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())
    ctxmod._set_for_test(
        db_path=str(cfg.paths.db_path), pipeline_run_id=None, surface="web")
    with pytest.raises(RuntimeError):
        cache._fetch_live_price("AAPL")
    rows = _rows(cfg.paths.db_path)
    assert rows[0][2] == "empty"  # status, NOT error (raw call boundary)


def test_intraday_allnan_records_success_and_caller_still_raises(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    import yfinance as yf
    allnan = pd.DataFrame(
        {"Close": [float("nan"), float("nan")]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10 09:30"),
                                pd.Timestamp("2026-06-10 09:31")]),
    )
    monkeypatch.setattr(yf, "download", lambda *a, **k: allnan)
    ctxmod._set_for_test(
        db_path=str(cfg.paths.db_path), pipeline_run_id=None, surface="web")
    with pytest.raises(RuntimeError):
        cache._fetch_live_price("AAPL")
    rows = _rows(cfg.paths.db_path)
    assert rows[0][2] == "success"  # raw frame had rows; NaN check is downstream


def test_intraday_no_context_no_row(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    import yfinance as yf
    monkeypatch.setattr(yf, "download", lambda *a, **k: _intraday_df())
    # NO context
    price = cache._fetch_live_price("AAPL")
    assert price == 1.5
    assert _rows(cfg.paths.db_path) == []
