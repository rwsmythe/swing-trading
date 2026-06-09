from __future__ import annotations

import math
from collections.abc import Sequence

from research.harness.shadow_expectancy.io import Bar

_REASON = "invalid_ohlc"


def _finite_nonneg(*vals: float) -> bool:
    return all(math.isfinite(v) and v >= 0 for v in vals)


def validate_candidate_levels(*, pivot) -> str | None:
    """spec 5.0.1 (amended per executing-review Codex R2-M1): validate the candidate PIVOT
    only. The pivot is the SOLE candidate field the mechanical trade consumes -- entry_fill
    = max(pivot, entry_bar.open) and the canonical-detection pivot match. candidate.initial_stop
    is deliberately NOT validated and never gates eligibility: per C1 / spec 5.2 / D6 the
    mechanical trade stop is entry_bar.low, so a stale or inverted (>= pivot) candidate
    initial_stop must NOT exclude an otherwise-valid shadow trade (doing so would silently bias
    the expectancy denominators on a field the simulator ignores). pivot finite and > 0 ->
    None, else 'invalid_ohlc'."""
    if pivot is None:
        return _REASON
    if not math.isfinite(pivot):
        return _REASON
    if pivot <= 0:
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


def validate_signal(*, pivot, bars: Sequence[Bar]) -> str | None:
    reason = validate_candidate_levels(pivot=pivot)
    if reason is not None:
        return reason
    return validate_bars(bars)
