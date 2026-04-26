"""Deterministic geometric flag-pattern classifier (V1).

Pure-function: DataFrame in, FlagClassificationResult out. No DB, no IO,
no logging side-effects. Spec: docs/superpowers/specs/2026-04-26-chart-
pattern-flag-v1-design.md §3.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class FlagClassificationResult:
    detected: bool
    confidence: float
    pattern: str | None
    pole_start_date: date | None
    pole_end_date: date | None
    flag_start_date: date | None
    flag_end_date: date | None
    pole_high: float | None
    flag_low: float | None
    pivot: float | None
    components: dict[str, float] = field(default_factory=dict)


def classify_flag(bars: pd.DataFrame) -> FlagClassificationResult:
    """Stub — implementation in subsequent tasks."""
    raise NotImplementedError
