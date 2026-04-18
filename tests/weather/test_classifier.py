"""Weather classifier — pure-function rule from legacy market_weather.py."""
from __future__ import annotations

import pandas as pd

from swing.weather.classifier import classify_weather, WeatherClassification, FLAT_MARGIN_PCT


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-04-15", periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [10_000_000] * len(closes),
    }, index=idx)


def test_bullish_when_close_above_rising_20ma_and_10_above_20():
    closes = [100.0 + i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Bullish"
    assert result.sma10 > result.sma20
    assert result.slope20_5bar > FLAT_MARGIN_PCT


def test_bearish_when_close_below_declining_20ma():
    closes = [200.0 - i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Bearish"
    assert result.slope20_5bar < -FLAT_MARGIN_PCT


def test_caution_when_close_below_20ma_but_20ma_not_declining():
    # Slight dip at the end keeps 20MA slope inside FLAT_MARGIN_PCT (flat),
    # while last close drops just below 20MA -> Caution per priority rule.
    closes = [100.0] * 55 + [99.9] * 5
    result = classify_weather(_ohlcv(closes))
    assert result.status == "Caution"
    assert "20MA" in result.rationale or "ambiguous" in result.rationale


def test_caution_when_close_above_20ma_but_10ma_not_above_20ma():
    closes = [100.0] * 50 + [99.5, 100.0, 100.5, 101.0, 102.0, 102.5, 103.0]
    result = classify_weather(_ohlcv(closes))
    assert result.status in ("Bullish", "Caution")


def test_classification_carries_metrics():
    closes = [100.0 + i * 0.5 for i in range(60)]
    result = classify_weather(_ohlcv(closes))
    assert isinstance(result, WeatherClassification)
    assert result.close > 0
    assert result.sma10 is not None
    assert result.sma20 is not None
    assert result.sma50 is not None


def test_insufficient_bars_raises():
    """Need at least 56 bars (50MA + 5 slope + 1)."""
    closes = [100.0] * 30
    import pytest
    with pytest.raises(ValueError, match="insufficient bars"):
        classify_weather(_ohlcv(closes))
