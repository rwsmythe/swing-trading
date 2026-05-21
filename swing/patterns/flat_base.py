"""Phase 13 T2.SB3 T-A.3.3 - flat_base detector per spec section 5.3.

O'Neil/CANSLIM flat-base consolidation: rule-based geometric detector
that ingests OHLCV daily bars + a CandidateWindow from the T2.SB2
foundation primitive ``generate_candidate_windows`` and returns a
``FlatBaseEvidence`` frozen dataclass capturing per-criterion verdicts +
the structural evidence (range bounds, slope, ATR, duration, pivot).

LOCKs (per dispatch task brief and plan G.4 LOCKs):
- L1: spec section 5.3 7 criteria + section 10.6 tolerance LOCK +
  section 10.2 errata verbatim; do NOT paraphrase.
- L2: ZERO DB writes inside this module (``current_stage`` is the only
  DB call; SELECT-only).
- L5: ASCII-only output paths.
- L7: ``FlatBaseEvidence`` is a frozen dataclass with ``__post_init__``
  runtime validation against explicit allowed-value frozensets
  (CLAUDE.md gotcha "Literal[...] type hints are NOT runtime-enforced").

Tolerance bands per spec section 10.6 LOCK (BINDING):
- criterion #2 (prior uptrend pct >= 20% AND weeks >= 5):
  +/- 2 percentage points on the pct bound -> relaxed threshold 18%.
- criterion #3 (range_width in [3%, 12%]):
  +/- 0.5 percentage points on each bound -> relaxed [2.5%, 12.5%].
- criterion #4 (slope <= 0.005/week): NONE (strict).
- criterion #5 (mean ATR / mid_range <= 0.025): NONE (strict).
- criterion #6 (duration >= 35 days): NONE (strict).
- criterion #7 (pivot/range_top in [0.99, 1.01]): +/- 0.5% expanding
  the band to [0.985, 1.015].
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd

from swing.patterns._sanitize import sanitize_bars
from swing.patterns.foundation import (
    CandidateWindow,
    adaptive_initial_threshold_pct,
    current_stage,
    extract_zigzag_swings,
)

# Detector version pin. Bump on any algorithm change.
DETECTOR_VERSION: str = "flat_base@v1.0.0"

# Spec section 5.3 + section 10.6 LOCK constants.
_PRIOR_UPTREND_BOUND_PCT: float = 20.0
_PRIOR_UPTREND_TOLERANCE_PCT: float = 2.0       # relaxed threshold = 18%
_PRIOR_UPTREND_WEEKS_BOUND: int = 5
_RANGE_WIDTH_RANGE_PCT: tuple[float, float] = (3.0, 12.0)
_RANGE_WIDTH_TOLERANCE_PCT: float = 0.5          # band expands to [2.5, 12.5]
_SLOPE_BOUND_PCT_PER_WEEK: float = 0.005         # criterion #4
_ATR_BOUND_FRAC: float = 0.025                   # criterion #5
_DURATION_BOUND_DAYS: int = 35                   # criterion #6
_PIVOT_RATIO_RANGE: tuple[float, float] = (0.99, 1.01)
_PIVOT_TOLERANCE_FRAC: float = 0.005             # 0.5% band expands [0.99, 1.01]
_ATR_WINDOW_DAYS: int = 5

# Allowed Literal values (L7 LOCK: validate in __post_init__).
_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)
_CRITERION_KEYS: frozenset[str] = frozenset(
    {f"criterion_{i}" for i in range(1, 8)}
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlatBaseEvidence:
    """Structural evidence emitted by detect_flat_base.

    Per spec section 5.3 ``FlatBaseEvidence`` shape (line 597) plus
    section 10.2 worked example fields. Field order follows the criteria
    sequence (#1 .. #7) so the dataclass reads naturally against the
    spec table.

    LOCK L7: ``stage`` Literal + ``criteria_pass`` keys validated at
    ``__post_init__`` time against module-level frozensets; closes the
    CLAUDE.md gotcha "Literal[...] type hints are NOT runtime-enforced".
    """

    stage: Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]
    prior_uptrend_pct: float
    prior_uptrend_weeks: int
    base_start_date: date
    base_end_date: date
    range_top_price: float
    range_bottom_price: float
    range_width_pct: float
    regression_slope_pct_per_week: float
    mean_atr_pct: float
    base_duration_days: int
    pivot_price: float
    pivot_within_top_pct: float
    criteria_pass: dict[str, bool]
    geometric_score: float

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_VALUES:
            raise ValueError(
                f"FlatBaseEvidence.stage must be one of "
                f"{sorted(_STAGE_VALUES)}, got {self.stage!r}"
            )
        if not (0.0 <= self.geometric_score <= 1.0):
            raise ValueError(
                f"FlatBaseEvidence.geometric_score must be in [0.0, 1.0], "
                f"got {self.geometric_score}"
            )
        if set(self.criteria_pass.keys()) != _CRITERION_KEYS:
            raise ValueError(
                f"FlatBaseEvidence.criteria_pass must have keys "
                f"{sorted(_CRITERION_KEYS)}, got "
                f"{sorted(self.criteria_pass.keys())}"
            )
        if self.base_duration_days < 0:
            raise ValueError(
                f"FlatBaseEvidence.base_duration_days must be >= 0, "
                f"got {self.base_duration_days}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts_to_date(ts) -> date:
    if hasattr(ts, "date") and callable(ts.date):
        return ts.date()
    if isinstance(ts, date):
        return ts
    raise TypeError(f"expected Timestamp or date, got {type(ts).__name__}")


def _build_zero_evidence(
    *,
    stage: Literal[
        "stage_1", "stage_2", "stage_3", "stage_4", "undefined"
    ],
    base_start_date: date,
    base_end_date: date,
    criteria_pass: dict[str, bool],
) -> FlatBaseEvidence:
    """Construct an early-exit FlatBaseEvidence with geometric_score == 0.0.

    Used when a hard gate fails (criterion #1 Stage 2 or criterion #6
    duration) or when the backward-slice cannot locate a base start.
    """
    full_flags = {f"criterion_{i}": False for i in range(1, 8)}
    full_flags.update(criteria_pass)
    duration_days = max(0, (base_end_date - base_start_date).days)
    return FlatBaseEvidence(
        stage=stage,
        prior_uptrend_pct=0.0,
        prior_uptrend_weeks=0,
        base_start_date=base_start_date,
        base_end_date=base_end_date,
        range_top_price=0.0,
        range_bottom_price=0.0,
        range_width_pct=0.0,
        regression_slope_pct_per_week=0.0,
        mean_atr_pct=0.0,
        base_duration_days=duration_days,
        pivot_price=0.0,
        pivot_within_top_pct=0.0,
        criteria_pass=full_flags,
        geometric_score=0.0,
    )


def _backward_slice_base_start(
    bars: pd.DataFrame, anchor_date: date
) -> date | None:
    """Locate the base START via backward-slicing from an anchor.

    Per recon section 5 + section 7.2: for ``ma_crossover`` or
    ``high_low_breakout`` candidate windows the anchor_date is a TRIGGER
    EVENT (not the base start). The flat_base detector walks BACK from
    the anchor to find the most-recent prior swing-LOW that precedes the
    trigger by at least the 5-week criterion #6 minimum
    (``(base_end - base_start).days >= 35``). That swing-LOW is the
    inferred base start where the range begins.

    Returns None if no suitable prior swing-LOW is found (the caller
    treats this as a missing-base-start failure path).
    """
    anchor_ts = pd.Timestamp(anchor_date)
    sub = bars.loc[bars.index <= anchor_ts]
    if len(sub) < 10:
        return None
    threshold = adaptive_initial_threshold_pct(sub)
    swings = extract_zigzag_swings(
        sub, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    # Walk backward through swings; first DOWN-swing's endpoint preceding
    # the anchor is the most-recent swing-LOW. Per recon section 7.2,
    # criterion #6 is enforced separately by the caller; we return the
    # candidate base_start unconditionally and let criterion #6 reject
    # too-short bases.
    for sw in reversed(swings):
        if sw.direction == "down":
            return sw.end_date
    return None


def _compute_range_bounds(
    bars: pd.DataFrame, base_start: date, base_end: date
) -> tuple[float, float]:
    """Return ``(range_top, range_bottom)`` over the base slice.

    Uses ``High.max()`` / ``Low.min()`` over [base_start, base_end] which
    matches the spec section 5.3 LOCK shape
    ``(range_top - range_bottom) / range_bottom`` reading bars-level
    extrema.
    """
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) == 0:
        return 0.0, 0.0
    range_top = float(base_slice["High"].max())
    range_bottom = float(base_slice["Low"].min())
    return range_top, range_bottom


def _compute_regression_slope_pct_per_week(
    bars: pd.DataFrame,
    base_start: date,
    base_end: date,
    range_bottom: float,
) -> float:
    """Per spec section 5.3 criterion #4: ``np.polyfit(x_weeks, mid_range,
    1)`` -> slope in price/week; divide by ``range_bottom`` to express
    as fraction per week (matching the spec LOCK shape
    ``regression_slope_pct_per_week``).

    Returns 0.0 on degenerate base slices.
    """
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) < 2 or range_bottom <= 0:
        return 0.0
    # mid_range per bar = (High + Low) / 2.
    mid_range = (
        base_slice["High"].astype(float).to_numpy()
        + base_slice["Low"].astype(float).to_numpy()
    ) / 2.0
    # x in weeks since base_start.
    days = np.array(
        [(_ts_to_date(ts) - base_start).days for ts in base_slice.index],
        dtype=float,
    )
    weeks = days / 7.0
    slope_price_per_week = float(np.polyfit(weeks, mid_range, 1)[0])
    return slope_price_per_week / range_bottom


def _compute_mean_atr_pct(
    bars: pd.DataFrame,
    base_start: date,
    base_end: date,
    range_top: float,
    range_bottom: float,
) -> float:
    """Per spec section 5.3 criterion #5: mean_atr_pct = avg(ATR_5d) /
    mid_range. ATR_5d at bar i = mean of (High - Low) over the trailing
    5 bars. mid_range = (range_top + range_bottom) / 2.

    Returns 0.0 on degenerate inputs (insufficient bars; zero mid_range).
    """
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) < _ATR_WINDOW_DAYS:
        return 0.0
    mid = (range_top + range_bottom) / 2.0
    if mid <= 0:
        return 0.0
    hl = (
        base_slice["High"].astype(float).to_numpy()
        - base_slice["Low"].astype(float).to_numpy()
    )
    # Rolling 5-day mean; ATR_5d at bar i for i >= 4.
    atr_5d_series = pd.Series(hl).rolling(_ATR_WINDOW_DAYS).mean()
    atr_5d = atr_5d_series.dropna().to_numpy()
    if len(atr_5d) == 0:
        return 0.0
    return float(np.mean(atr_5d)) / mid


def _compute_prior_uptrend(
    bars: pd.DataFrame, base_start: date
) -> tuple[float, int]:
    """Return ``(prior_uptrend_pct, prior_uptrend_weeks)``.

    Walks BACK from ``base_start`` to find the most-recent prior
    swing-LOW. The prior-uptrend leg runs from that swing-LOW (or the
    earliest available bar if no swing exists) to the close at
    ``base_start``.

    Returns ``(0.0, 0)`` on insufficient history.
    """
    pre = bars.loc[bars.index < pd.Timestamp(base_start)]
    if len(pre) < 10:
        return 0.0, 0
    threshold = adaptive_initial_threshold_pct(pre)
    swings = extract_zigzag_swings(
        pre, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    leg_start_price: float | None = None
    leg_start_date: date | None = None
    for sw in reversed(swings):
        if sw.direction == "up":
            leg_start_price = float(sw.start_price)
            leg_start_date = sw.start_date
            break
    if leg_start_price is None or leg_start_date is None:
        # Fallback: earliest available bar.
        leg_start_price = float(pre["Close"].iloc[0])
        leg_start_date = _ts_to_date(pre.index[0])
    base_start_ts = pd.Timestamp(base_start)
    if base_start_ts in bars.index:
        base_start_close = float(bars.loc[base_start_ts, "Close"])
    else:
        base_start_close = float(pre["Close"].iloc[-1])
    if leg_start_price <= 0:
        return 0.0, 0
    pct = (base_start_close - leg_start_price) / leg_start_price * 100.0
    weeks = max(0, (base_start - leg_start_date).days // 7)
    return float(pct), int(weeks)


def _check_pivot_within_top(
    pivot_price: float, range_top: float
) -> tuple[bool, float]:
    """Per spec section 5.3 criterion #7 + section 10.6 LOCK: pivot
    within 1% of range_top (ratio in [0.99, 1.01]); tolerance 0.5%
    expands the band to [0.985, 1.015].

    Returns ``(within_band, pivot_within_top_pct)`` where
    ``pivot_within_top_pct`` is ``(ratio - 1.0) * 100``.
    """
    if range_top <= 0:
        return False, 0.0
    ratio = pivot_price / range_top
    lo = _PIVOT_RATIO_RANGE[0] - _PIVOT_TOLERANCE_FRAC
    hi = _PIVOT_RATIO_RANGE[1] + _PIVOT_TOLERANCE_FRAC
    within = lo <= ratio <= hi
    return within, float((ratio - 1.0) * 100.0)


def _check_range_width(width_pct: float) -> bool:
    """Per spec section 5.3 criterion #3 + section 10.6 tolerance:
    range_width in [3%, 12%] with +/- 0.5pp tolerance band -> relaxed
    [2.5%, 12.5%].
    """
    lo = _RANGE_WIDTH_RANGE_PCT[0] - _RANGE_WIDTH_TOLERANCE_PCT
    hi = _RANGE_WIDTH_RANGE_PCT[1] + _RANGE_WIDTH_TOLERANCE_PCT
    return lo <= width_pct <= hi


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_flat_base(
    bars: pd.DataFrame,
    candidate_window: CandidateWindow,
    *,
    conn: sqlite3.Connection | None = None,
    ticker: str | None = None,
    asof_date: date | None = None,
) -> FlatBaseEvidence:
    """Detect a flat-base pattern on ``bars`` over ``candidate_window``.

    Per spec section 5.3 + section 10.2 worked example + section 10.6
    tolerance LOCK. Pure function: no DB writes; ``conn`` is read-only
    via ``current_stage`` for criterion #1 (Stage 2 hard gate).

    Parameters
    ----------
    bars : pd.DataFrame
        OHLCV daily bars indexed by ``pd.Timestamp``; must NOT contain
        NaN (validated by the shared sanitizer at
        ``swing/patterns/_sanitize.py``).
    candidate_window : CandidateWindow
        One window emitted by ``generate_candidate_windows``. The
        ``anchor_date`` semantic is per-mode-dependent:
        - ``zigzag_pivot:*`` -> anchor_date IS the base start.
        - ``ma_crossover:*`` / ``high_low_breakout:*`` -> anchor_date is
          a TRIGGER EVENT; the detector backward-slices to find the
          base start (per recon section 5 + 7.2).
    conn : sqlite3.Connection | None
        Read-only connection for ``current_stage(conn, ticker, asof)``.
        If None, criterion #1 is treated as failed (Stage 2 unknown).
    ticker : str | None
        Required when ``conn`` is provided; ignored otherwise.
    asof_date : date | None
        Required when ``conn`` is provided; ignored otherwise.

    Returns
    -------
    FlatBaseEvidence
        Frozen dataclass with per-criterion pass flags + geometric
        score + structural evidence (range bounds, slope, ATR, duration,
        pivot).
    """
    sanitize_bars(bars)
    if len(bars) < 10:
        return _build_zero_evidence(
            stage="undefined",
            base_start_date=candidate_window.start_date,
            base_end_date=candidate_window.end_date,
            criteria_pass={f"criterion_{i}": False for i in range(1, 8)},
        )

    # Step 1: resolve the base start via per-mode anchor semantic.
    reason = candidate_window.anchor_reason or ""
    if reason.startswith("zigzag_pivot"):
        base_start = candidate_window.anchor_date
    else:
        sliced = _backward_slice_base_start(
            bars, candidate_window.anchor_date
        )
        if sliced is None:
            return _build_zero_evidence(
                stage="undefined",
                base_start_date=candidate_window.anchor_date,
                base_end_date=candidate_window.end_date,
                criteria_pass={f"criterion_{i}": False for i in range(1, 8)},
            )
        base_start = sliced
    base_end = candidate_window.end_date

    # Step 2: criterion #1 -- Stage 2 hard gate.
    if conn is None or ticker is None or asof_date is None:
        stage: Literal[
            "stage_1", "stage_2", "stage_3", "stage_4", "undefined"
        ] = "undefined"
    else:
        stage = current_stage(conn, ticker, asof_date)
    c1_pass = stage == "stage_2"
    if not c1_pass:
        return _build_zero_evidence(
            stage=stage,
            base_start_date=base_start,
            base_end_date=base_end,
            criteria_pass={"criterion_1": False},
        )

    # Step 3: criterion #2 -- prior uptrend. Section 10.6 tolerance:
    # +/- 2pp on the 20% bound -> relaxed threshold 18%.
    prior_uptrend_pct, prior_uptrend_weeks = _compute_prior_uptrend(
        bars, base_start
    )
    relaxed_uptrend_bound = (
        _PRIOR_UPTREND_BOUND_PCT - _PRIOR_UPTREND_TOLERANCE_PCT
    )
    c2_pass = (
        prior_uptrend_pct >= relaxed_uptrend_bound
        and prior_uptrend_weeks >= _PRIOR_UPTREND_WEEKS_BOUND
    )

    # Step 4: criterion #6 -- base duration hard gate (NONE tolerance).
    base_days = (base_end - base_start).days
    c6_pass = base_days >= _DURATION_BOUND_DAYS

    # Step 5: criterion #3 -- range_width.
    range_top, range_bottom = _compute_range_bounds(bars, base_start, base_end)
    range_width_pct = (
        (range_top - range_bottom) / range_bottom * 100.0
        if range_bottom > 0
        else 0.0
    )
    c3_pass = _check_range_width(range_width_pct)

    # Step 6: criterion #4 -- regression slope (fraction-of-range_bottom
    # per week). Spec LOCK shape compares against 0.005 strict.
    slope_pct_per_week = _compute_regression_slope_pct_per_week(
        bars, base_start, base_end, range_bottom
    )
    c4_pass = slope_pct_per_week <= _SLOPE_BOUND_PCT_PER_WEEK

    # Step 7: criterion #5 -- mean ATR / mid_range.
    mean_atr_pct = _compute_mean_atr_pct(
        bars, base_start, base_end, range_top, range_bottom
    )
    c5_pass = mean_atr_pct <= _ATR_BOUND_FRAC

    # Step 8: criterion #7 -- pivot near range_top. Pivot is the LAST
    # close in the base slice.
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) == 0:
        return _build_zero_evidence(
            stage=stage,
            base_start_date=base_start,
            base_end_date=base_end,
            criteria_pass={
                "criterion_1": True,
                "criterion_2": c2_pass,
                "criterion_6": c6_pass,
            },
        )
    pivot_price = float(base_slice["Close"].iloc[-1])
    c7_pass, pivot_within_top_pct = _check_pivot_within_top(
        pivot_price, range_top
    )

    criteria_pass = {
        "criterion_1": c1_pass,
        "criterion_2": c2_pass,
        "criterion_3": c3_pass,
        "criterion_4": c4_pass,
        "criterion_5": c5_pass,
        "criterion_6": c6_pass,
        "criterion_7": c7_pass,
    }

    # Step 9: geometric_score. Hard gates: #1 + #6. Failure of either
    # zeros the score per spec section 5.3 LOCK. Otherwise the score is
    # the equal-weighted pass-fraction over the 7 criteria.
    if not c1_pass or not c6_pass:
        geometric_score = 0.0
    else:
        passed = sum(1 for v in criteria_pass.values() if v)
        geometric_score = passed / len(criteria_pass)

    return FlatBaseEvidence(
        stage=stage,
        prior_uptrend_pct=float(prior_uptrend_pct),
        prior_uptrend_weeks=int(prior_uptrend_weeks),
        base_start_date=base_start,
        base_end_date=base_end,
        range_top_price=float(range_top),
        range_bottom_price=float(range_bottom),
        range_width_pct=float(range_width_pct),
        regression_slope_pct_per_week=float(slope_pct_per_week),
        mean_atr_pct=float(mean_atr_pct),
        base_duration_days=int(base_days),
        pivot_price=float(pivot_price),
        pivot_within_top_pct=float(pivot_within_top_pct),
        criteria_pass=criteria_pass,
        geometric_score=float(geometric_score),
    )
