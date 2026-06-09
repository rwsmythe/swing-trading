from __future__ import annotations

import math
from collections.abc import Sequence

from research.harness.shadow_expectancy.io import Bar

_REASON = "invalid_ohlc"


def _finite_nonneg(*vals: float) -> bool:
    return all(math.isfinite(v) and v >= 0 for v in vals)


def validate_candidate_levels(*, pivot, initial_stop) -> str | None:
    """spec 5.0.1: pivot/initial_stop finite, pivot > 0, initial_stop >= 0,
    pivot > initial_stop. Any failure -> 'invalid_ohlc'."""
    if pivot is None or initial_stop is None:
        return _REASON
    if not (math.isfinite(pivot) and math.isfinite(initial_stop)):
        return _REASON
    if pivot <= 0 or initial_stop < 0 or pivot <= initial_stop:
        return _REASON
    return None


def validate_bars(bars: Sequence[Bar]) -> str | None:
    """spec 5.0.1: every bar OHLC finite + non-negative; low <= min(open,close);
    high >= max(open,close); high >= low; strictly chronological, no dup sessions."""
    prev_session: str | None = None
    for b in bars:
        if not _finite_nonneg(b.open, b.high, b.low, b.close):
            return _REASON
        if b.low > min(b.open, b.close):
            return _REASON
        if b.high < max(b.open, b.close):
            return _REASON
        if b.high < b.low:
            return _REASON
        if prev_session is not None and b.session <= prev_session:
            return _REASON  # non-chronological OR duplicate session
        prev_session = b.session
    return None


def validate_signal(*, pivot, initial_stop, bars: Sequence[Bar]) -> str | None:
    reason = validate_candidate_levels(pivot=pivot, initial_stop=initial_stop)
    if reason is not None:
        return reason
    return validate_bars(bars)
