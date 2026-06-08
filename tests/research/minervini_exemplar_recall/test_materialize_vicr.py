# tests/research/minervini_exemplar_recall/test_materialize_vicr.py
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd


def _flat_frame():
    idx = pd.bdate_range("1990-01-02", periods=5)
    idx.name = "Date"  # mirror real yfinance: the index is named 'Date'.
    return pd.DataFrame(
        {"Open": [1.0, 2, 3, 4, 5], "High": [1.0, 2, 3, 4, 5], "Low": [1.0, 2, 3, 4, 5],
         "Close": [1.0, 2, 3, 4, 5], "Volume": [10, 20, 30, 40, 50]},
        index=idx,
    )


def _multiindex_frame():
    # Recent yfinance returns MultiIndex (Price x Ticker) even for one ticker.
    frame = _flat_frame()
    frame.columns = pd.MultiIndex.from_product([list(frame.columns), ["VICR"]])
    return frame


def _install_fake_yfinance(monkeypatch, frame):
    fake = types.ModuleType("yfinance")
    fake.download = lambda *a, **k: frame
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def _materialize_with(monkeypatch, frame, csv_path):
    _install_fake_yfinance(monkeypatch, frame)
    import importlib
    mod = importlib.import_module("research.scripts.materialize_vicr_yfinance")
    importlib.reload(mod)
    mod.materialize(out_csv=csv_path)


def test_writes_tiingo_columns_no_comment_header(tmp_path, monkeypatch):
    csv_path = tmp_path / "VICR.csv"
    _materialize_with(monkeypatch, _flat_frame(), csv_path)

    text = csv_path.read_text(encoding="utf-8")
    # No '#'-comment line (Codex R1.M8): a clean header row Tiingo readers can parse.
    assert not text.lstrip().startswith("#")
    df = pd.read_csv(csv_path, parse_dates=["date"])
    for col in ("date", "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume"):
        assert col in df.columns
    # provenance is a SIBLING sidecar, not inside the CSV.
    assert (csv_path.parent / "VICR.provenance.txt").exists()


def test_handles_multiindex_columns(tmp_path, monkeypatch):
    # WRONG-PATH (no flatten): KeyError 'close' on MultiIndex columns.
    # RIGHT-PATH (flatten to level 0): adj* columns written.
    csv_path = tmp_path / "VICR.csv"
    _materialize_with(monkeypatch, _multiindex_frame(), csv_path)
    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert "adjClose" in df.columns and len(df) == 5
