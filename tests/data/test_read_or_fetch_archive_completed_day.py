# tests/data/test_read_or_fetch_archive_completed_day.py
from datetime import date

import pandas as pd

import swing.data.ohlcv_archive as arch
from swing.data.ohlcv_archive import read_or_fetch_archive


def test_yfinance_fetch_never_persists_after_cutoff(tmp_path, monkeypatch):
    """Even when yfinance returns an in-progress (> cutoff) bar, the atomic
    barrier (Task C1) strips it before persist. OLD: read_or_fetch_archive
    persisted the raw fetched frame incl. the 06-05 bar. NEW: the on-disk
    archive holds no row > cutoff. NOTE: read_or_fetch_archive writes the
    LEGACY `{ticker}.parquet` path (date-indexed), NOT the Shape-A yfinance
    parquet -- the legacy file is migrated to `{ticker}.yfinance.parquet`
    later, on read, by _backward_compat_rename (which ALSO inherits the strip)."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))

    def _fake_yf(ticker, *, start, end):
        idx = pd.to_datetime(["2026-06-03", "2026-06-04", "2026-06-05"])
        return pd.DataFrame({"open": [10, 10, 10], "high": [11, 11, 12],
                             "low": [9, 9, 9], "close": [10.5, 10.5, 11],
                             "volume": [100, 100, 200]}, index=idx)
    monkeypatch.setattr(arch, "_yf_download_window", _fake_yf)

    read_or_fetch_archive("AAPL", end_date=date(2026, 6, 4),
                          cache_dir=tmp_path, archive_history_days=400)
    on_disk = pd.read_parquet(tmp_path / "AAPL.parquet")  # legacy path (_archive_paths)
    assert on_disk.index.max().date() <= date(2026, 6, 4)
