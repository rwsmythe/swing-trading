"""Shared helpers for criterion files. Criteria are pure functions — no I/O, no DB."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Result:
    """Output of a single criterion evaluation.

    `metrics` carries structured numeric values that the evaluator reads directly
    for persistence. `value` is human-readable display text.
    """

    name: str
    layer: str  # 'trend_template' | 'vcp' | 'risk'
    result: str  # 'pass' | 'fail' | 'na'
    value: str  # human-readable measurement
    rule: str  # human-readable rule
    metrics: tuple[tuple[str, float | int | None], ...] = field(default_factory=tuple)

    @classmethod
    def pass_(
        cls,
        value: str,
        rule: str,
        *,
        name: str = "",
        layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(
            name=name,
            layer=layer,
            result="pass",
            value=value,
            rule=rule,
            metrics=tuple((metrics or {}).items()),
        )

    @classmethod
    def fail_(
        cls,
        value: str,
        rule: str,
        *,
        name: str = "",
        layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(
            name=name,
            layer=layer,
            result="fail",
            value=value,
            rule=rule,
            metrics=tuple((metrics or {}).items()),
        )

    @classmethod
    def na_(
        cls,
        reason: str,
        *,
        name: str = "",
        layer: str = "",
        metrics: dict[str, float | int | None] | None = None,
    ) -> Result:
        return cls(
            name=name,
            layer=layer,
            result="na",
            value=reason,
            rule="",
            metrics=tuple((metrics or {}).items()),
        )

    def with_identity(self, name: str, layer: str) -> Result:
        return Result(
            name=name,
            layer=layer,
            result=self.result,
            value=self.value,
            rule=self.rule,
            metrics=self.metrics,
        )

    def get_metric(self, key: str) -> float | int | None:
        for k, v in self.metrics:
            if k == key:
                return v
        return None


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average. NaN for first (window-1) values."""
    return series.rolling(window=window, min_periods=window).mean()


def adr_pct(df: pd.DataFrame, lookback: int = 20) -> float:
    """Average Daily Range as a percent of price, over last `lookback` bars.

    ADR% = mean((High - Low) / Close * 100).
    """
    tail = df.tail(lookback)
    ranges_pct = (tail["High"] - tail["Low"]) / tail["Close"] * 100
    return float(ranges_pct.mean())


def daily_range_pct(df: pd.DataFrame) -> pd.Series:
    """Per-bar range as percent of close."""
    return (df["High"] - df["Low"]) / df["Close"] * 100
