# tests/data/test_write_window_completed_day.py
from datetime import date

import pandas as pd
import pytest

import swing.data.ohlcv_archive as arch
from swing.data.ohlcv_archive import (
    _shape_a_path,
    _write_archive_atomic,
    resolve_ohlcv_window,
    write_window,
)


@pytest.fixture
def fixed_cutoff(monkeypatch):
    """Freeze the completed-session cutoff at 2026-06-04 (so 2026-06-05 is the
    'current in-progress' session) for BOTH the helper and any lazy import."""
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    return date(2026, 6, 4)


def _frame(rows):
    return pd.DataFrame(rows, columns=["asof_date", "open", "high", "low",
                                       "close", "volume"])


def test_atomic_writer_strips_after_cutoff_universal(tmp_path, fixed_cutoff):
    """The hard barrier: _write_archive_atomic itself drops > cutoff rows, so
    EVERY write path (write_window, read_or_fetch_archive, _backward_compat_
    rename) inherits it -- a > cutoff row can never land on disk."""
    path = _shape_a_path(tmp_path, "AAPL", "schwab_api")
    _write_archive_atomic(path, _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],  # > cutoff -> stripped
    ]))
    on_disk = pd.read_parquet(path)
    assert list(on_disk["asof_date"]) == ["2026-06-04"]


def test_atomic_writer_strips_date_indexed_frame(tmp_path, fixed_cutoff):
    """Shape-agnostic: a DatetimeIndex frame (the read_or_fetch_archive shape)
    is also stripped on > cutoff."""
    path = _shape_a_path(tmp_path, "AAPL", "yfinance")
    idx = pd.to_datetime(["2026-06-04", "2026-06-05"])
    _write_archive_atomic(path, pd.DataFrame(
        {"open": [10, 10], "high": [11, 12], "low": [9, 9],
         "close": [10.5, 11], "volume": [100, 200]}, index=idx))
    on_disk = pd.read_parquet(path)
    assert on_disk.index.max().date() == date(2026, 6, 4)


def test_incoming_current_day_row_is_stripped(tmp_path, fixed_cutoff):
    win = _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],
    ])
    write_window("AAPL", win, "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert list(df["asof_date"]) == ["2026-06-04"]


def test_preexisting_on_disk_current_day_row_stripped_on_empty_incoming(
        tmp_path, fixed_cutoff, monkeypatch):
    """M3: a > cutoff row already on disk is stripped even when the incoming
    window is empty. (Simulate a pre-fix raw file by writing it with the
    atomic strip DISABLED, then prove write_window cleans it.)"""
    path = _shape_a_path(tmp_path, "AAPL", "schwab_api")
    # Write a raw pre-fix file WITH a partial, bypassing the strip:
    monkeypatch.setattr(arch, "_strip_incomplete_sessions",
                        lambda df, _c: df)  # disable strip for the raw seed
    _write_archive_atomic(path, _frame([
        ["2026-06-04", 10, 11, 9, 10.5, 100],
        ["2026-06-05", 10, 12, 9, 11.0, 200],
    ]))
    monkeypatch.undo()  # re-enable the real strip
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    write_window("AAPL", _frame([]), "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert "2026-06-05" not in list(df["asof_date"])
    assert "2026-06-04" in list(df["asof_date"])


def test_transient_empty_incoming_preserves_valid_history(tmp_path, fixed_cutoff):
    """F6: an empty incoming window must NOT blank valid (<= cutoff) history."""
    seed = _frame([["2026-06-03", 10, 11, 9, 10.5, 100],
                   ["2026-06-04", 10, 11, 9, 10.5, 100]])
    write_window("AAPL", seed, "schwab_api", cache_dir=tmp_path)
    write_window("AAPL", None, "schwab_api", cache_dir=tmp_path)
    df, _ = resolve_ohlcv_window("AAPL", start="2026-06-01", end="2026-06-30",
                                 cache_dir=tmp_path)
    assert list(df["asof_date"]) == ["2026-06-03", "2026-06-04"]


def test_strip_raises_on_unrecognized_nonempty_frame(fixed_cutoff):
    """Codex R1 MAJOR #1: the barrier FAILS CLOSED -- a non-empty frame with
    neither an asof_date column nor a DatetimeIndex raises rather than silently
    persisting a possibly-> cutoff row."""
    weird = pd.DataFrame({"open": [10], "high": [11], "low": [9], "close": [10.5]})
    with pytest.raises(ValueError, match="unrecognized frame shape"):
        arch._strip_incomplete_sessions(weird, fixed_cutoff.isoformat())


def test_strip_passes_empty_unrecognized_frame(fixed_cutoff):
    """An EMPTY frame of any shape passes through (nothing to strip)."""
    empty = pd.DataFrame({"open": [], "high": [], "low": [], "close": []})
    out = arch._strip_incomplete_sessions(empty, fixed_cutoff.isoformat())
    assert len(out) == 0


def test_empty_incoming_strips_preexisting_datetimeindex_partial(
        tmp_path, fixed_cutoff, monkeypatch):
    """Codex R1 MAJOR #2: write_window with empty incoming strips a pre-existing
    on-disk partial even when `existing` is a DatetimeIndex (legacy-shape) frame
    at the Shape-A path, not only an asof_date frame."""
    path = _shape_a_path(tmp_path, "AAPL", "schwab_api")
    # Seed a DatetimeIndex partial bypassing the strip.
    monkeypatch.setattr(arch, "_strip_incomplete_sessions", lambda df, _c: df)
    idx = pd.to_datetime(["2026-06-04", "2026-06-05"])
    _write_archive_atomic(path, pd.DataFrame(
        {"open": [10, 10], "high": [11, 12], "low": [9, 9],
         "close": [10.5, 11], "volume": [100, 200]}, index=idx))
    monkeypatch.undo()
    monkeypatch.setattr(arch, "_last_completed_session_today",
                        lambda: date(2026, 6, 4))
    write_window("AAPL", None, "schwab_api", cache_dir=tmp_path)
    on_disk = pd.read_parquet(path)
    assert on_disk.index.max().date() == date(2026, 6, 4)  # 06-05 stripped


def test_timestamp_string_asof_date_keeps_cutoff_day(tmp_path, fixed_cutoff):
    """Codex R1 MINOR #1: an asof_date carrying a full Timestamp string
    (`2026-06-04 00:00:00`) must NOT be lexically stripped at cutoff 2026-06-04
    -- the value is normalized to a date before comparison."""
    df = pd.DataFrame(
        [["2026-06-04 00:00:00", 10, 11, 9, 10.5, 100],
         ["2026-06-05 00:00:00", 10, 12, 9, 11.0, 200]],
        columns=["asof_date", "open", "high", "low", "close", "volume"])
    out = arch._strip_incomplete_sessions(df, fixed_cutoff.isoformat())
    kept = [str(v)[:10] for v in out["asof_date"]]
    assert kept == ["2026-06-04"]  # cutoff day kept, 06-05 dropped
