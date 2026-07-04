from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

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


@dataclass(frozen=True)
class ClampEvent:
    session: str
    clamp_pct: float


def _shape_violation_pct(b: Bar) -> float | None:
    """The clamp magnitude of a bar's OHLC shape violation, as % of CLOSE (brief 2b -- the
    threshold is measured against close, faithfully, with NO other-price fallback). Returns 0.0
    when the bar is well-formed (low<=min(o,c) and high>=max(o,c)); None when close<=0 (the
    magnitude is undefined as a %-of-close, so the bar is not clampable and is left for
    validate_bars to route)."""
    if b.close <= 0:
        return None
    lo_delta = max(0.0, b.low - min(b.open, b.close))    # low sitting ABOVE the body
    hi_delta = max(0.0, max(b.open, b.close) - b.high)   # high sitting BELOW the body
    return 100.0 * max(lo_delta, hi_delta) / b.close


def clamp_ragged_bars(bars, *, max_pct):
    """19-D epsilon-tolerant reader (brief 2b). Reader-side ONLY -- the immutable log + the OHLCV
    archive are untouched. For each bar with a shape violation (low>min(o,c) OR high<max(o,c))
    whose magnitude is <= max_pct% of close, WIDEN the bar: high=max(h,o,c), low=min(l,o,c). Above
    max_pct -> left UNCHANGED (validate_bars then routes it to invalid_ohlc, exactly as today).
    Non-finite/negative bars are NOT clampable -> passthrough. Widening only ever grows the range,
    so it is idempotent and can never create high<low. Returns (clamped_bars, clamp_events)."""
    out = []
    events = []
    for b in bars:
        if not _finite_nonneg(b.open, b.high, b.low, b.close):
            out.append(b)
            continue
        pct = _shape_violation_pct(b)
        if pct is None or pct == 0.0 or pct > max_pct:
            out.append(b)
            continue
        out.append(replace(b, high=max(b.high, b.open, b.close),
                           low=min(b.low, b.open, b.close)))
        events.append(ClampEvent(session=b.session, clamp_pct=pct))
    return out, events
