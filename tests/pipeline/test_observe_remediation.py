# tests/pipeline/test_observe_remediation.py
from datetime import date

import pandas as pd

import swing.data.ohlcv_archive as arch
import swing.pipeline.runner as runner
from swing.data.ohlcv_archive import (
    _shape_a_path,
    _write_archive_atomic,
    write_window,
)
from tests.pipeline.conftest_temporal import _cfg

COLS = ["asof_date", "open", "high", "low", "close", "volume"]


def runner_cfg_stub(tmp_path):
    return _cfg(tmp_path, tmp_path / "swing.db")


def _seed_contaminated_schwab(tmp_path):
    # a pre-fix ext-hours-inflated (high=99) schwab_api row for the obs date.
    _write_archive_atomic(_shape_a_path(tmp_path, "AAPL", "schwab_api"),
                          pd.DataFrame([["2026-06-04", 10, 99, 9, 10.5, 100]],
                                       columns=COLS))


def _cfg_for(tmp_path):
    return runner_cfg_stub(tmp_path)  # supplies paths.prices_cache_dir = tmp_path/ohlcv


def test_success_path_overwrites_contaminated_before_lock(tmp_path, monkeypatch):
    """Schwab-success: the populate refetches clean (L1) -> keep='last'
    overwrites -> _bar_for_date returns the clean bar."""
    cfg = _cfg_for(tmp_path)
    cache = cfg.paths.prices_cache_dir
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    _seed_contaminated_schwab(cache)

    class _Cache:
        def get_or_fetch(self, *, ticker, window_days):
            # emulate the ladder's clean L1 Schwab refetch + persist.
            write_window(ticker, pd.DataFrame(
                [["2026-06-04", 10, 11, 9, 10.5, 100]], columns=COLS),
                "schwab_api", cache_dir=cache)
            return pd.DataFrame()  # return value unused by _bar_for_date's read
    bar = runner._bar_for_date(cfg, _Cache(), "AAPL", "2026-06-04")
    assert bar is not None and bar["high"] == 11   # clean, not 99
    assert bar["provider"] == "schwab_api"


def test_failure_path_then_purge_falls_to_clean_yfinance(tmp_path, monkeypatch):
    """Schwab-failure/TTL-hit: the populate does NOT overwrite; the stale
    contaminated schwab_api row wins on precedence -> _bar_for_date returns it
    (the residual gap). After the C8 purge removes *.schwab_api.parquet,
    _bar_for_date falls to the clean yfinance row."""
    cfg = _cfg_for(tmp_path)
    cache = cfg.paths.prices_cache_dir
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    _seed_contaminated_schwab(cache)
    # a clean yfinance row also exists (lower precedence).
    write_window("AAPL", pd.DataFrame([["2026-06-04", 10, 11, 9, 10.5, 100]],
                                      columns=COLS), "yfinance", cache_dir=cache)

    class _NoOpCache:
        def get_or_fetch(self, *, ticker, window_days):
            return pd.DataFrame()  # Schwab failed / TTL hit -> no overwrite
    # BEFORE purge: contaminated schwab_api wins.
    bar = runner._bar_for_date(cfg, _NoOpCache(), "AAPL", "2026-06-04")
    assert bar["high"] == 99   # documents the residual gap
    # purge (the C8 belt) -> schwab_api gone -> clean yfinance wins.
    _shape_a_path(cache, "AAPL", "schwab_api").unlink()
    bar2 = runner._bar_for_date(cfg, _NoOpCache(), "AAPL", "2026-06-04")
    assert bar2["high"] == 11 and bar2["provider"] == "yfinance"
