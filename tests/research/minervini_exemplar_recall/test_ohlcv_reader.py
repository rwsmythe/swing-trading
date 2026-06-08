# tests/research/minervini_exemplar_recall/test_ohlcv_reader.py
from __future__ import annotations

from datetime import date

import pytest


def _write_tiingo_csv(path, dates, base=100.0):
    # Tiingo's real header includes raw + adj columns; the reader only consumes adj* + date.
    lines = ["date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume"]
    for i, d in enumerate(dates):
        c = base + i
        lines.append(f"{d},{c},{c+1},{c-1},{c},{1000+i},{c},{c+1},{c-1},{c},{1000+i}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_full_maps_adj_columns_capitalized(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05", "2010-01-06"])
    df = read_full("ZZTOP", tiingo_dir=tmp_path)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert str(df.index.dtype).startswith("datetime64")
    assert df.index.is_monotonic_increasing
    # adjClose for the 2nd bar was 101.0
    assert df["Close"].iloc[1] == pytest.approx(101.0)


def test_slice_to_is_inclusive_backward(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_full, slice_to

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05", "2010-01-06"])
    df = read_full("ZZTOP", tiingo_dir=tmp_path)
    sliced = slice_to(df, date(2010, 1, 5))
    # <= 2010-01-05 inclusive -> 2 bars (the 01-05 bar is RETAINED).
    # WRONG-PATH (strict <): 1 bar.  RIGHT-PATH (<=): 2 bars.
    assert len(sliced) == 2
    assert sliced.index[-1].date() == date(2010, 1, 5)


def test_symbol_override(tmp_path):
    from research.harness.minervini_exemplar_recall.ohlcv_reader import tiingo_symbol

    assert tiingo_symbol("EMEX") == "ELX"
    assert tiingo_symbol("HOOK") == "BREW"
    assert tiingo_symbol("CRUS") == "CRUS"
    assert tiingo_symbol("crus") == "CRUS"  # upper-cased


def test_read_sliced_raises_archive_missing(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import TiingoArchiveMissingError
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_sliced

    with pytest.raises(TiingoArchiveMissingError, match="NOPE"):
        read_sliced("NOPE", date(2010, 1, 5), tiingo_dir=tmp_path, min_bars=1)


def test_read_sliced_raises_coverage_below_min_bars(tmp_path):
    from research.harness.minervini_exemplar_recall.exceptions import TiingoCoverageError
    from research.harness.minervini_exemplar_recall.ohlcv_reader import read_sliced

    _write_tiingo_csv(tmp_path / "ZZTOP.csv", ["2010-01-04", "2010-01-05"])
    # 2 bars <= asof, min_bars=5 -> coverage error.
    with pytest.raises(TiingoCoverageError, match="sliced=2"):
        read_sliced("ZZTOP", date(2010, 1, 6), tiingo_dir=tmp_path, min_bars=5)
