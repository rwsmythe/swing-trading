"""Smoke test — proves the test harness works."""
from __future__ import annotations

import swing


def test_package_version():
    assert swing.__version__ == "0.1.0"


def test_ohlcv_factory_shape(ohlcv_factory):
    df = ohlcv_factory([10.0, 10.5, 11.0])
    assert len(df) == 3
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
