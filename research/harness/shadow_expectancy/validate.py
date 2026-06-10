from __future__ import annotations

import math
from collections.abc import Sequence

from research.harness.shadow_expectancy.io import Bar

_PIVOT_REASON = "no_candidate_pivot"   # spec 3.2: split from invalid_ohlc
_BAR_REASON = "invalid_ohlc"


def _finite_nonneg(*vals: float) -> bool:
    return all(math.isfinite(v) and v >= 0 for v in vals)


def validate_candidate_levels(*, pivot) -> str | None:
    """spec 3.2 (correction): the screening pivot is the SOLE candidate field the mechanical
    trade consumes (entry_fill = max(pivot, entry_bar.open)). candidate.initial_stop is
    deliberately NOT validated (the mechanical stop is entry_bar.low; R2-M1). A null / non-finite
    / <=0 pivot is an EXPECTED, common data state (no screening breakout level) -> the specific
    reason 'no_candidate_pivot', NOT 'invalid_ohlc' (which is reserved for malformed frozen
    bars). pivot finite and > 0 -> None."""
    if pivot is None:
        return _PIVOT_REASON
    if not math.isfinite(pivot):
        return _PIVOT_REASON
    if pivot <= 0:
        return _PIVOT_REASON
    return None


def validate_bars(bars: Sequence[Bar]) -> str | None:
    """spec 5.0.1: every bar OHLC finite + non-negative; low <= min(open,close);
    high >= max(open,close); high >= low; strictly chronological, no dup sessions."""
    prev_session: str | None = None
    for b in bars:
        if not _finite_nonneg(b.open, b.high, b.low, b.close):
            return _BAR_REASON
        if b.low > min(b.open, b.close):
            return _BAR_REASON
        if b.high < max(b.open, b.close):
            return _BAR_REASON
        if b.high < b.low:
            return _BAR_REASON
        if prev_session is not None and b.session <= prev_session:
            return _BAR_REASON  # non-chronological OR duplicate session
        prev_session = b.session
    return None


def validate_signal(*, pivot, bars: Sequence[Bar]) -> str | None:
    reason = validate_candidate_levels(pivot=pivot)
    if reason is not None:
        return reason
    return validate_bars(bars)
