from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.ohlcv_reader import slice_to
from swing.patterns.foundation import extract_zigzag_swings

from .constants import MIN_BASE_BARS, MIN_HISTORY_BARS, ZIGZAG_THRESHOLD_PCT, depth_cap


@dataclass(frozen=True)
class PrimaryBaseVerdict:
    fired: bool
    first_rejecting_criterion: str | None  # history|no_base|duration|depth|no_emergence|not_primary
    base_start_date: date | None = None
    base_high: float | None = None
    correction_depth_pct: float | None = None
    base_duration_bars: int | None = None
    emergence_close: float | None = None


@dataclass(frozen=True)
class _BaseId:
    base_start_pos: int
    base_start_date: date
    base_high: float
    base_low: float


def _identify_base(sliced: pd.DataFrame) -> _BaseId | None:
    """The pre-base peak (highest swing-high pivot with a down-swing after it) + base low.

    Calendar->bar mapping: every Swing date is mapped back to an integer bar position in `sliced`.
    """
    swings = extract_zigzag_swings(sliced, initial_threshold_pct=ZIGZAG_THRESHOLD_PCT)
    if not swings:
        return None
    pos_by_date = {ts.date(): i for i, ts in enumerate(sliced.index)}
    closes = sliced["Close"].to_numpy()
    best: _BaseId | None = None
    for i, sw in enumerate(swings):
        # A swing-high pivot WITH a down-swing after it = an up-swing immediately followed by a
        # down-swing in the alternating closed-swing list (the trailing/developing leg is excluded
        # because the next swing must exist and be "down").
        if sw.direction != "up":
            continue
        if i + 1 >= len(swings) or swings[i + 1].direction != "down":
            continue
        peak_pos = pos_by_date[sw.end_date]
        peak_high = float(sw.end_price)
        if best is None or peak_high > best.base_high:
            base_low = float(closes[peak_pos:].min())  # lowest Close in [base_start, asof]
            best = _BaseId(
                base_start_pos=peak_pos,
                base_start_date=sw.end_date,
                base_high=peak_high,
                base_low=base_low,
            )
    return best


@dataclass(frozen=True)
class _Partial:
    fired_1_to_5: bool
    first_rejecting: str | None
    base_start_date: date | None = None
    base_high: float | None = None
    correction_depth_pct: float | None = None
    base_duration_bars: int | None = None
    emergence_close: float | None = None


def _eval_1_to_5(sliced: pd.DataFrame) -> _Partial:
    if len(sliced) < MIN_HISTORY_BARS:
        return _Partial(False, "history")
    base = _identify_base(sliced)
    if base is None:
        return _Partial(False, "no_base")
    asof_pos = len(sliced) - 1
    base_duration_bars = asof_pos - base.base_start_pos
    correction_depth_pct = (
        (base.base_high - base.base_low) / base.base_high if base.base_high else 0.0
    )
    diag = dict(
        base_start_date=base.base_start_date,
        base_high=base.base_high,
        correction_depth_pct=correction_depth_pct,
        base_duration_bars=base_duration_bars,
    )
    if base_duration_bars < MIN_BASE_BARS:
        return _Partial(False, "duration", **diag)
    if correction_depth_pct > depth_cap(base_duration_bars):
        return _Partial(False, "depth", **diag)
    closes = sliced["Close"].to_numpy()
    emergence_close = float(closes[asof_pos])
    fresh_cross = closes[asof_pos - 1] <= base.base_high < closes[asof_pos]
    first_cross = closes[base.base_start_pos:asof_pos].max() <= base.base_high
    if not (fresh_cross and first_cross):
        return _Partial(False, "no_emergence", **diag)
    return _Partial(True, None, emergence_close=emergence_close, **diag)


def screen_at(bars: pd.DataFrame, asof_date: date) -> PrimaryBaseVerdict:
    """Minervini Ch.11 primary-base screen, point-in-time at asof_date (no lookahead)."""
    sliced = slice_to(bars, asof_date)
    partial = _eval_1_to_5(sliced)
    diag = dict(
        base_start_date=partial.base_start_date,
        base_high=partial.base_high,
        correction_depth_pct=partial.correction_depth_pct,
        base_duration_bars=partial.base_duration_bars,
        emergence_close=partial.emergence_close,
    )
    if not partial.fired_1_to_5:
        return PrimaryBaseVerdict(False, partial.first_rejecting, **diag)
    # Criterion 6: primary = first base. Replay 1-5 over every prior session; if any earlier
    # session fires, asof is a LATER base -> not_primary. No lookahead (each replay reads <= s).
    asof_pos = len(sliced) - 1
    for s_pos in range(MIN_HISTORY_BARS - 1, asof_pos):
        if _eval_1_to_5(sliced.iloc[: s_pos + 1]).fired_1_to_5:
            return PrimaryBaseVerdict(False, "not_primary", **diag)
    return PrimaryBaseVerdict(True, None, **diag)
