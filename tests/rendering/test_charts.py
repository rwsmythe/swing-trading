"""Chart rendering — slow-marked because it requires matplotlib + mplfinance."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.rendering.charts import render_chart, ChartingUnavailable


pytestmark = pytest.mark.slow  # heavy dep


def _ohlcv(n: int = 120):
    closes = [100.0 + i * 0.5 for i in range(n)]
    idx = pd.bdate_range(end="2026-04-15", periods=n)
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [10_000_000] * n,
    }, index=idx)


def test_render_chart_writes_png(tmp_path: Path):
    out = tmp_path / "AAPL.png"
    result = render_chart(
        ticker="AAPL", ohlcv=_ohlcv(),
        pivot=160.0, stop=150.0, output_path=out,
    )
    assert result == out
    assert out.exists() and out.stat().st_size > 1000


def test_too_few_bars_returns_none(tmp_path: Path):
    out = tmp_path / "X.png"
    result = render_chart(
        ticker="X", ohlcv=_ohlcv(n=5),
        pivot=100.0, stop=95.0, output_path=out,
    )
    assert result is None
    assert not out.exists()
