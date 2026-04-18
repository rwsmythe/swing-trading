"""Pure-function classifier ported from legacy market_weather.py.

Priority-ordered rule (first match wins):
  1. Bearish: close < 20MA AND 20MA declining (slope < -FLAT_MARGIN_PCT)
  2. Bullish: close > 20MA AND 20MA rising AND 10MA > 20MA
  3. Caution: anything else, with rationale enumerating which Bullish clause(s) missed
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FLAT_MARGIN_PCT = 0.1
SLOPE_LOOKBACK = 5
MA_SHORT = 10
MA_MID = 20
MA_LONG = 50
MIN_BARS = MA_LONG + SLOPE_LOOKBACK + 1  # 56


@dataclass(frozen=True)
class WeatherClassification:
    asof_date: str
    close: float
    sma10: float | None
    sma20: float | None
    sma50: float | None
    slope10_5bar: float
    slope20_5bar: float
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    rationale: str


def _slope_pct(series: pd.Series, lookback: int = SLOPE_LOOKBACK) -> float:
    if len(series) <= lookback:
        return 0.0
    now = series.iloc[-1]
    then = series.iloc[-lookback - 1]
    if pd.isna(now) or pd.isna(then) or then <= 0:
        return 0.0
    return float((now - then) / then * 100)


def _classify_slope(slope: float) -> str:
    if slope > FLAT_MARGIN_PCT:
        return "rising"
    if slope < -FLAT_MARGIN_PCT:
        return "declining"
    return "flat"


def classify_weather(ohlcv: pd.DataFrame) -> WeatherClassification:
    if len(ohlcv) < MIN_BARS:
        raise ValueError(
            f"insufficient bars for weather classifier: have {len(ohlcv)}, need {MIN_BARS}"
        )

    closes = ohlcv["Close"]
    sma10 = closes.rolling(MA_SHORT, min_periods=MA_SHORT).mean()
    sma20 = closes.rolling(MA_MID, min_periods=MA_MID).mean()
    sma50 = closes.rolling(MA_LONG, min_periods=MA_LONG).mean()

    last_close = float(closes.iloc[-1])
    s10 = float(sma10.iloc[-1])
    s20 = float(sma20.iloc[-1])
    s50 = float(sma50.iloc[-1])
    slope20 = _slope_pct(sma20)
    slope10 = _slope_pct(sma10)
    slope20_state = _classify_slope(slope20)

    # Priority-ordered rule
    if last_close < s20 and slope20_state == "declining":
        status = "Bearish"
        rationale = (
            f"Close ${last_close:.2f} below 20MA ${s20:.2f}; "
            f"20MA declining ({slope20:+.2f}%/5bars)."
        )
    elif last_close > s20 and slope20_state == "rising" and s10 > s20:
        status = "Bullish"
        rationale = (
            f"Close ${last_close:.2f} above 20MA ${s20:.2f}; "
            f"20MA rising ({slope20:+.2f}%/5bars); 10MA above 20MA."
        )
    else:
        status = "Caution"
        misses: list[str] = []
        if last_close <= s20:
            misses.append(f"close at/below 20MA")
        if slope20_state == "flat":
            misses.append("20MA is flat")
        elif slope20_state == "declining":
            misses.append("20MA is declining")
        if s10 <= s20:
            misses.append("10MA <= 20MA")
        rationale = (
            "Caution: " + "; ".join(misses)
            if misses
            else "Caution: ambiguous middle state."
        )

    asof = pd.Timestamp(ohlcv.index[-1]).date().isoformat()
    return WeatherClassification(
        asof_date=asof, close=last_close,
        sma10=s10, sma20=s20, sma50=s50,
        slope10_5bar=slope10, slope20_5bar=slope20,
        status=status, rationale=rationale,
    )
