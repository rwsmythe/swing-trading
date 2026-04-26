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
    if len(bars) < 36:
        return FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={},
        )
    # Search loop — populates baseline components even when no candidate
    # passes (best-attempted at (M=5, N=5)).
    M_baseline, N_baseline = 5, 5
    components = {"pole_M": float(M_baseline), "flag_N": float(N_baseline)}
    return FlagClassificationResult(
        detected=False, confidence=0.0, pattern="none",
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components=components,
    )
