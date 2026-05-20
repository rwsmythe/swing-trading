"""Phase 13 T2.SB3 T-A.3.4 - cup-with-handle detector per spec section 5.4.

O'Neil / CANSLIM cup-with-handle: rule-based geometric detector that
ingests OHLCV daily bars + a CandidateWindow from the T2.SB2 foundation
primitive ``generate_candidate_windows`` and returns a
``CupWithHandleEvidence`` frozen dataclass capturing per-criterion
verdicts + the structural evidence (cup left/right edges, bottom, handle
anchors, pivot, rounded-vs-V verdict).

LOCKs (per dispatch brief Section 6 + plan G.4 LOCKs):
- L1: spec section 5.4 8 criteria + section 10.6 tolerance LOCK +
  section 10.7 rounded-vs-V LOCK + section D.11 ``_is_rounded_cup`` LOCK
  verbatim; do NOT paraphrase.
- L2: ZERO DB writes inside this module and inside ``_is_rounded_cup``
  (``current_stage`` is the only DB call; SELECT-only).
- L5: ASCII-only output paths.
- L7: ``CupWithHandleEvidence`` is a frozen dataclass with
  ``__post_init__`` runtime validation against explicit allowed-value
  frozensets (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").

Tolerance bands per spec section 10.6 LOCK + section 5.4 table:
- criterion #2 (cup_depth in [12%, 35%]): +/- 0.5pp on each bound ->
  relaxed [11.5%, 35.5%]; cup_left_to_bottom_days strict >= 28.
- criterion #3 (cup_right_edge >= 95% of cup_left_edge): +/- 1% tolerance.
- criterion #4 (cup_duration_days in [42, 182]): NONE (strict).
- criterion #5 (handle_depth <= 15% AND handle_duration_days >= 5):
  +/- 1pp on depth; duration strict.
- criterion #6 (handle_low > cup_midpoint): NONE (strict).
- criterion #7 (pivot/cup_right_edge in [0.99, 1.01]): +/- 0.5%.
- criterion #8 (handle_avg_volume / cup_avg_volume <= 0.85): +/- 5%
  expanded to <= 0.90 relaxed bound.

Section 10.7 rounded-vs-V LOCK semantics + section D.11 ``_is_rounded_cup``
LOCK:
- Window: cup_bottom_date +/- 10 days (21-bar window centered on cup_bottom).
- Count bars where bar.low <= cup_bottom_price * (1 + marginal_zone_pct/100).
- >= 5 bars -> HARD PASS; (True, 0.0).
- 3-4 bars -> MARGINAL ZONE; (True, 0.10).
- <= 2 bars -> HARD FAIL (V-shape); (False, +inf).
- Geometric score aggregation: criterion-mean SUBTRACTS the
  ``_is_rounded_cup`` float penalty (clamped to [0.0, 1.0]).

Per-mode anchor_date semantic (recon section 5 + 7.3): for
``ma_crossover`` / ``high_low_breakout`` modes the detector backward-slices
to find the cup LEFT EDGE which is a SWING-HIGH (DIFFERENT from VCP /
flat_base swing-LOW semantics). For ``zigzag_pivot`` mode the anchor_date
is taken as the cup left edge directly.

Empirical observation per forward-binding lesson #8 (T-A.1.7 corpus):
4 of 5 cup exemplars failed the rounded-vs-V hard gate by sub-1% margins
at corpus labeling time. The §10.7 LOCK semantics are PRESERVED at
T-A.3.4 ship; widening the marginal zone is OPERATOR-ESCALATABLE only.
The synthetic worked-example fixture (spec §10.3) yields >= 5 bars in the
marginal zone (HARD PASS) under the implemented detector, confirming the
LOCK's geometric soundness on a clean rounded-cup shape.
"""
from __future__ import annotations

import math
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

# Detector version pin (per recon section 8). Bump on any algorithm change.
DETECTOR_VERSION: str = "cup_with_handle@v1.0.0"

# Spec section 5.4 + section 10.6 + section 10.7 LOCK constants.
_CUP_DEPTH_RANGE_PCT: tuple[float, float] = (12.0, 35.0)
_CUP_DEPTH_TOLERANCE_PCT: float = 0.5            # relaxed [11.5, 35.5]
_CUP_LEFT_TO_BOTTOM_DAYS_BOUND: int = 28
_CUP_RIGHT_EDGE_BOUND_PCT: float = 95.0          # >= 95% of left edge
_CUP_RIGHT_EDGE_TOLERANCE_PCT: float = 1.0       # relaxed >= 94%
_CUP_DURATION_DAYS_RANGE: tuple[int, int] = (42, 182)
_HANDLE_DEPTH_BOUND_PCT: float = 15.0
_HANDLE_DEPTH_TOLERANCE_PCT: float = 1.0         # relaxed <= 16%
_HANDLE_DURATION_DAYS_BOUND: int = 5
_PIVOT_RATIO_RANGE: tuple[float, float] = (0.99, 1.01)
_PIVOT_TOLERANCE_FRAC: float = 0.005             # 0.5% band -> [0.985, 1.015]
_HANDLE_VOLUME_BOUND_PCT: float = 85.0           # <= 85% of cup volume
_HANDLE_VOLUME_TOLERANCE_PCT: float = 5.0        # relaxed <= 90%

# Section 10.7 rounded-vs-V LOCK constants.
_ROUNDED_WINDOW_DAYS: int = 10                   # +/- 10-day window
_ROUNDED_MARGINAL_ZONE_PCT: float = 2.0          # bars within 2% of bottom
_ROUNDED_HARD_PASS_BAR_COUNT: int = 5
_ROUNDED_MARGINAL_PENALTY: float = 0.10

# Allowed Literal values (L7 LOCK: validate in __post_init__).
_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)
_CRITERION_KEYS: frozenset[str] = frozenset(
    {f"criterion_{i}" for i in range(1, 9)}
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CupWithHandleEvidence:
    """Structural evidence emitted by detect_cup_with_handle.

    Per spec section 5.4 ``CupWithHandleEvidence`` shape (line 623) plus
    section 10.3 worked example fields. Field order follows the criteria
    sequence so the dataclass reads naturally against the spec table.

    LOCK L7: ``stage`` Literal + ``criteria_pass`` keys validated at
    ``__post_init__`` time against module-level frozensets; closes the
    CLAUDE.md gotcha "Literal[...] type hints are NOT runtime-enforced".
    """

    stage: Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]
    cup_left_edge_price: float
    cup_left_edge_date: date
    cup_right_edge_price: float
    cup_right_edge_date: date
    cup_bottom_price: float
    cup_bottom_date: date
    cup_depth_pct: float
    cup_duration_days: int
    cup_right_edge_pct_of_left_edge: float
    handle_high_price: float
    handle_low_price: float
    handle_start_date: date
    handle_end_date: date
    handle_depth_pct: float
    handle_duration_days: int
    handle_low_vs_cup_midpoint_pct: float
    handle_volume_vs_cup_volume_pct: float
    pivot_price: float
    pivot_within_cup_right_edge_pct: float
    rounded_cup_passes: bool
    rounded_cup_penalty: float
    rounded_cup_bars_in_marginal_zone: int
    criteria_pass: dict[str, bool]
    geometric_score: float

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_VALUES:
            raise ValueError(
                f"CupWithHandleEvidence.stage must be one of "
                f"{sorted(_STAGE_VALUES)}, got {self.stage!r}"
            )
        if not (0.0 <= self.geometric_score <= 1.0):
            raise ValueError(
                f"CupWithHandleEvidence.geometric_score must be in "
                f"[0.0, 1.0], got {self.geometric_score}"
            )
        if set(self.criteria_pass.keys()) != _CRITERION_KEYS:
            raise ValueError(
                f"CupWithHandleEvidence.criteria_pass must have keys "
                f"{sorted(_CRITERION_KEYS)}, got "
                f"{sorted(self.criteria_pass.keys())}"
            )
        # Penalty must be one of the LOCKed values: 0.0 / 0.10 / +inf.
        if not (
            self.rounded_cup_penalty == 0.0
            or math.isclose(self.rounded_cup_penalty, 0.10)
            or math.isinf(self.rounded_cup_penalty)
        ):
            raise ValueError(
                f"CupWithHandleEvidence.rounded_cup_penalty must be one of "
                f"{{0.0, 0.10, +inf}}, got {self.rounded_cup_penalty}"
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
    cup_left_edge_date: date,
    cup_right_edge_date: date,
    criteria_pass: dict[str, bool],
) -> CupWithHandleEvidence:
    """Construct an early-exit CupWithHandleEvidence with score 0.0.

    Used when a hard gate fails (criterion #1 Stage 2 or no cup
    structure can be identified) or when the backward-slice cannot
    locate a cup left edge.
    """
    full_flags = {f"criterion_{i}": False for i in range(1, 9)}
    full_flags.update(criteria_pass)
    return CupWithHandleEvidence(
        stage=stage,
        cup_left_edge_price=0.0,
        cup_left_edge_date=cup_left_edge_date,
        cup_right_edge_price=0.0,
        cup_right_edge_date=cup_right_edge_date,
        cup_bottom_price=0.0,
        cup_bottom_date=cup_left_edge_date,
        cup_depth_pct=0.0,
        cup_duration_days=0,
        cup_right_edge_pct_of_left_edge=0.0,
        handle_high_price=0.0,
        handle_low_price=0.0,
        handle_start_date=cup_right_edge_date,
        handle_end_date=cup_right_edge_date,
        handle_depth_pct=0.0,
        handle_duration_days=0,
        handle_low_vs_cup_midpoint_pct=0.0,
        handle_volume_vs_cup_volume_pct=0.0,
        pivot_price=0.0,
        pivot_within_cup_right_edge_pct=0.0,
        rounded_cup_passes=False,
        rounded_cup_penalty=0.0,
        rounded_cup_bars_in_marginal_zone=0,
        criteria_pass=full_flags,
        geometric_score=0.0,
    )


def _backward_slice_cup_left_edge(
    bars: pd.DataFrame, anchor_date: date
) -> date | None:
    """Locate the cup LEFT EDGE via backward-slicing from a trigger anchor.

    Per recon section 5 + 7.3: for ``ma_crossover`` or
    ``high_low_breakout`` candidate windows the anchor_date is a TRIGGER
    EVENT (not the cup left edge). The cup_with_handle detector walks
    BACK from the anchor to find the most-recent prior SWING-HIGH
    (DIFFERENT from VCP/flat_base swing-LOW semantics). That swing-HIGH
    is the inferred cup left edge.

    Returns None if no suitable prior swing-HIGH is found.
    """
    anchor_ts = pd.Timestamp(anchor_date)
    sub = bars.loc[bars.index <= anchor_ts]
    if len(sub) < 10:
        return None
    threshold = adaptive_initial_threshold_pct(sub)
    swings = extract_zigzag_swings(
        sub, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    # Walk backward; first UP-swing's endpoint preceding the anchor is
    # the most-recent swing-HIGH (the cup left edge).
    for sw in reversed(swings):
        if sw.direction == "up":
            return sw.end_date
    return None


def _is_rounded_cup(
    bars: pd.DataFrame,
    cup_bottom_date: date,
    cup_bottom_price: float,
    marginal_zone_pct: float = _ROUNDED_MARGINAL_ZONE_PCT,
) -> tuple[bool, float]:
    """Section 10.7 + section D.11 LOCK: rounded-vs-V predicate.

    Centered on ``cup_bottom_date +/- 10 days`` (21-bar window centered
    on cup_bottom). Count bars whose ``Low`` is within
    ``cup_bottom_price * (1 + marginal_zone_pct/100)``.

    Returns
    -------
    (True, 0.0)
        HARD PASS: >= 5 bars in marginal zone (rounded; stretched-out
        trough). Penalty contribution = 0.0.
    (True, 0.10)
        MARGINAL ZONE: 3-4 bars in marginal zone. Penalty contribution
        = 0.10 subtracted from geometric_score.
    (False, +inf)
        HARD FAIL: <= 2 bars in marginal zone (V-shape rejection).
        Penalty contribution = +inf (caller zeros the geometric_score).

    LOCK L2: PURE function; ZERO DB writes; consumes bars + scalar
    inputs only.
    """
    if cup_bottom_price <= 0:
        return False, float("inf")
    bottom_ts = pd.Timestamp(cup_bottom_date)
    lo_ts = bottom_ts - pd.Timedelta(days=_ROUNDED_WINDOW_DAYS)
    hi_ts = bottom_ts + pd.Timedelta(days=_ROUNDED_WINDOW_DAYS)
    window = bars.loc[(bars.index >= lo_ts) & (bars.index <= hi_ts)]
    if len(window) == 0:
        return False, float("inf")
    threshold_price = cup_bottom_price * (1.0 + marginal_zone_pct / 100.0)
    lows = window["Low"].astype(float).to_numpy()
    bars_within = int(np.sum(lows <= threshold_price))
    if bars_within >= _ROUNDED_HARD_PASS_BAR_COUNT:
        return True, 0.0
    if bars_within >= 3:
        return True, _ROUNDED_MARGINAL_PENALTY
    return False, float("inf")


def _check_cup_depth(depth_pct: float) -> bool:
    """Criterion #2 + section 10.6 tolerance: cup_depth in [12%, 35%]
    with +/- 0.5pp tolerance -> relaxed [11.5%, 35.5%].
    """
    lo = _CUP_DEPTH_RANGE_PCT[0] - _CUP_DEPTH_TOLERANCE_PCT
    hi = _CUP_DEPTH_RANGE_PCT[1] + _CUP_DEPTH_TOLERANCE_PCT
    return lo <= depth_pct <= hi


def _check_cup_right_edge_ratio(ratio_pct: float) -> bool:
    """Criterion #3 + section 10.6 tolerance: ratio >= 95% with +/- 1pp
    tolerance -> relaxed >= 94%.
    """
    relaxed = _CUP_RIGHT_EDGE_BOUND_PCT - _CUP_RIGHT_EDGE_TOLERANCE_PCT
    return ratio_pct >= relaxed


def _check_cup_duration(duration_days: int) -> bool:
    """Criterion #4: cup_duration_days in [42, 182]. Tolerance NONE."""
    lo, hi = _CUP_DURATION_DAYS_RANGE
    return lo <= duration_days <= hi


def _check_handle(
    depth_pct: float, duration_days: int
) -> bool:
    """Criterion #5: handle_depth <= 15% (+/- 1pp -> 16% relaxed) AND
    handle_duration_days >= 5 (NONE tolerance).
    """
    depth_ok = (
        depth_pct
        <= _HANDLE_DEPTH_BOUND_PCT + _HANDLE_DEPTH_TOLERANCE_PCT
    )
    duration_ok = duration_days >= _HANDLE_DURATION_DAYS_BOUND
    return depth_ok and duration_ok


def _check_handle_above_midpoint(
    handle_low_price: float, cup_left_edge_price: float, cup_bottom_price: float
) -> tuple[bool, float]:
    """Criterion #6: handle_low must be STRICTLY > cup_midpoint =
    (cup_left_edge_price + cup_bottom_price) / 2. Tolerance NONE.

    Returns (passes, handle_low_vs_cup_midpoint_pct) where the second
    value is ``(handle_low - midpoint) / midpoint * 100`` (positive when
    handle low is above midpoint).
    """
    midpoint = (cup_left_edge_price + cup_bottom_price) / 2.0
    if midpoint <= 0:
        return False, 0.0
    pct = (handle_low_price - midpoint) / midpoint * 100.0
    return handle_low_price > midpoint, float(pct)


def _check_pivot_within_cup_right_edge(
    pivot_price: float, cup_right_edge_price: float
) -> tuple[bool, float]:
    """Criterion #7: pivot / cup_right_edge in [0.99, 1.01]; tolerance
    0.5% expands the band to [0.985, 1.015].
    """
    if cup_right_edge_price <= 0:
        return False, 0.0
    ratio = pivot_price / cup_right_edge_price
    lo = _PIVOT_RATIO_RANGE[0] - _PIVOT_TOLERANCE_FRAC
    hi = _PIVOT_RATIO_RANGE[1] + _PIVOT_TOLERANCE_FRAC
    within = lo <= ratio <= hi
    return within, float((ratio - 1.0) * 100.0)


def _check_handle_volume(
    handle_avg_volume: float, cup_avg_volume: float
) -> tuple[bool, float]:
    """Criterion #8: handle_avg_volume / cup_avg_volume <= 85% with +/-
    5% tolerance -> relaxed <= 90%.

    Returns (passes, ratio_pct).
    """
    if cup_avg_volume <= 0:
        return False, 0.0
    ratio_pct = handle_avg_volume / cup_avg_volume * 100.0
    relaxed = _HANDLE_VOLUME_BOUND_PCT + _HANDLE_VOLUME_TOLERANCE_PCT
    return ratio_pct <= relaxed, float(ratio_pct)


def _identify_cup_anchors(
    bars: pd.DataFrame, cup_left_edge_date: date
) -> tuple[date, float, date, float] | None:
    """Locate (cup_bottom_date, cup_bottom_price, cup_right_edge_date,
    cup_right_edge_price) given the cup_left_edge_date.

    Approach: walk forward from cup_left_edge to find the cup bottom
    (argmin Low). After the bottom, scan forward to identify the cup
    RIGHT EDGE as the first SWING-HIGH (the cup recovery's peak; price
    rises from the bottom then turns DOWN into the handle pullback).
    The right edge is the LAST bar where price hits a local High that
    is followed by a DOWN-swing (handle start). If no clear swing-high
    is identifiable, fall back to the post-bottom argmax of High but
    ONLY if at least 5 bars exist after that argmax (to ensure room for
    the handle).

    Returns None if the bars frame does not contain enough history past
    cup_left_edge_date to identify a meaningful cup.
    """
    left_ts = pd.Timestamp(cup_left_edge_date)
    if left_ts not in bars.index:
        forward = bars.loc[bars.index >= left_ts]
        if len(forward) == 0:
            return None
        left_ts = forward.index[0]
    forward = bars.loc[bars.index >= left_ts]
    if len(forward) < 21:
        return None
    cap_ts = left_ts + pd.Timedelta(days=_CUP_DURATION_DAYS_RANGE[1] + 56)
    cup_region = forward.loc[forward.index <= cap_ts]
    if len(cup_region) < 21:
        cup_region = forward.iloc[: min(len(forward), 250)]

    # cup_bottom = argmin of Low across the cup region.
    bottom_idx = int(cup_region["Low"].astype(float).to_numpy().argmin())
    cup_bottom_ts = cup_region.index[bottom_idx]
    cup_bottom_price = float(cup_region["Low"].iloc[bottom_idx])

    # cup_right_edge: scan forward from cup_bottom to find a swing-HIGH
    # whose subsequent bars descend (the handle pullback). The right
    # edge is the LAST bar of the recovery, identified by the first
    # bar AFTER the post-bottom global-max-High where Close turns DOWN.
    post_bottom = cup_region.iloc[bottom_idx + 1:]
    if len(post_bottom) == 0:
        return None
    highs = post_bottom["High"].astype(float).to_numpy()
    # Run zigzag on the post-bottom segment to locate the first up-swing
    # endpoint (the cup right edge / recovery peak before handle).
    if len(post_bottom) >= 6:
        threshold = adaptive_initial_threshold_pct(post_bottom)
        swings = extract_zigzag_swings(
            post_bottom,
            initial_threshold_pct=threshold,
            monotonic_narrow=False,
        )
        # Find the first UP-swing in post_bottom. Its end_date is the
        # cup right edge (the recovery peak before the handle pullback).
        recovery_end_date: date | None = None
        for sw in swings:
            if sw.direction == "up":
                recovery_end_date = sw.end_date
                break
        if recovery_end_date is not None:
            recovery_end_ts = pd.Timestamp(recovery_end_date)
            if recovery_end_ts in post_bottom.index:
                # Use the bar's High at the recovery_end_date.
                right_price = float(
                    post_bottom.loc[recovery_end_ts, "High"]
                )
                return (
                    _ts_to_date(cup_bottom_ts),
                    cup_bottom_price,
                    recovery_end_date,
                    right_price,
                )
    # Fallback: global argmax of High in post_bottom; ensure >= 5 bars
    # exist after so the handle can be identified.
    right_idx = int(highs.argmax())
    if right_idx + 5 >= len(post_bottom):
        # Try restricting to the first 2/3 of post_bottom so the handle
        # has room.
        usable_end = max(1, int(len(post_bottom) * 2 / 3))
        right_idx = int(highs[:usable_end].argmax())
    cup_right_edge_ts = post_bottom.index[right_idx]
    cup_right_edge_price = float(post_bottom["High"].iloc[right_idx])
    return (
        _ts_to_date(cup_bottom_ts),
        cup_bottom_price,
        _ts_to_date(cup_right_edge_ts),
        cup_right_edge_price,
    )


def _identify_handle(
    bars: pd.DataFrame,
    cup_right_edge_date: date,
    cup_right_edge_price: float,
) -> tuple[date, date, float, float, int, float] | None:
    """Locate (handle_start, handle_end, handle_high, handle_low,
    handle_duration_days, handle_depth_pct).

    Approach: the handle BEGINS at cup_right_edge_date with the cup
    right-edge price as the handle_high. From cup_right_edge_date the
    handle descends to a swing-LOW (handle_low) within ~8 weeks. The
    handle ENDS when price re-approaches the handle_high (the would-be
    breakout pivot bar) or when the lookforward exhausts the bars.

    Returns None if not enough bars exist past cup_right_edge_date.
    """
    right_ts = pd.Timestamp(cup_right_edge_date)
    post = bars.loc[bars.index > right_ts]
    if len(post) < 2:
        return None
    # Cap handle lookforward at 56 days (8 weeks) generously.
    cap_ts = right_ts + pd.Timedelta(days=56)
    handle_region = post.loc[post.index <= cap_ts]
    if len(handle_region) < 2:
        handle_region = post.iloc[: min(len(post), 56)]
    # handle_low = argmin of Low in handle region.
    low_idx = int(handle_region["Low"].astype(float).to_numpy().argmin())
    handle_low_ts = handle_region.index[low_idx]
    handle_low_price = float(handle_region["Low"].iloc[low_idx])
    # handle_end = either the bar before price re-approaches the
    # handle_high (close >= 0.99 * handle_high), or the last bar of the
    # handle_region. Walk forward from handle_low.
    handle_start_ts = right_ts
    # Walk forward from handle_low; the handle ENDS when Close
    # re-approaches the handle_high (close >= 99% of handle_high) which
    # signals breakout / pivot.
    handle_end_idx = len(handle_region) - 1
    for i in range(low_idx + 1, len(handle_region)):
        close = float(handle_region["Close"].iloc[i])
        if close >= cup_right_edge_price * 0.99:
            handle_end_idx = i - 1
            break
    if handle_end_idx < low_idx:
        handle_end_idx = low_idx
    handle_end_ts = handle_region.index[handle_end_idx]
    handle_high_price = float(cup_right_edge_price)
    # Handle DURATION semantic (spec section 5.4 criterion #5):
    # operator-perspective is the PULLBACK PERIOD from cup right edge
    # to handle low (the descent), NOT the entire handle base including
    # the recovery to pivot. This matches the section 10.3 worked
    # example ("handle pulls back to $18 over 8 days") where the cited
    # "8 days" is the descent from $19.50 to $18.
    duration_days = (handle_low_ts - handle_start_ts).days
    if duration_days < 0:
        duration_days = 0
    if handle_high_price <= 0:
        return None
    depth_pct = (handle_high_price - handle_low_price) / handle_high_price * 100.0
    return (
        _ts_to_date(handle_start_ts),
        _ts_to_date(handle_end_ts),
        handle_high_price,
        handle_low_price,
        int(duration_days),
        float(depth_pct),
    )


def _avg_volume_between(
    bars: pd.DataFrame, start_date: date, end_date: date
) -> float:
    """Mean Volume across bars in [start_date, end_date] inclusive."""
    lo_ts = pd.Timestamp(start_date)
    hi_ts = pd.Timestamp(end_date)
    sub = bars.loc[(bars.index >= lo_ts) & (bars.index <= hi_ts)]
    if len(sub) == 0:
        return 0.0
    return float(sub["Volume"].astype(float).mean())


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_cup_with_handle(
    bars: pd.DataFrame,
    candidate_window: CandidateWindow,
    *,
    conn: sqlite3.Connection | None = None,
    ticker: str | None = None,
    asof_date: date | None = None,
) -> CupWithHandleEvidence:
    """Detect a cup-with-handle pattern on ``bars`` over ``candidate_window``.

    Per spec section 5.4 + section 10.3 worked example + section 10.6
    tolerance LOCK + section 10.7 rounded-vs-V LOCK + section D.11
    ``_is_rounded_cup`` LOCK. Pure function: no DB writes; ``conn`` is
    read-only via ``current_stage`` for criterion #1 (Stage 2 hard gate).

    Parameters
    ----------
    bars : pd.DataFrame
        OHLCV daily bars indexed by ``pd.Timestamp``; must NOT contain
        NaN (validated by the shared sanitizer at
        ``swing/patterns/_sanitize.py``).
    candidate_window : CandidateWindow
        One window emitted by ``generate_candidate_windows``. The
        ``anchor_date`` semantic is per-mode-dependent:
        - ``zigzag_pivot:*`` -> anchor_date IS the cup left edge.
        - ``ma_crossover:*`` / ``high_low_breakout:*`` -> anchor_date is
          a TRIGGER EVENT; the detector backward-slices to find the
          cup left edge (SWING-HIGH semantics per recon section 5 + 7.3).
    conn : sqlite3.Connection | None
        Read-only connection for ``current_stage(conn, ticker, asof)``.
        If None, criterion #1 is treated as failed (Stage 2 unknown).
    ticker : str | None
        Required when ``conn`` is provided; ignored otherwise.
    asof_date : date | None
        Required when ``conn`` is provided; ignored otherwise.

    Returns
    -------
    CupWithHandleEvidence
        Frozen dataclass with per-criterion pass flags + geometric
        score + structural evidence (cup anchors, handle anchors, pivot,
        rounded-vs-V verdict).
    """
    sanitize_bars(bars)
    if len(bars) < 20:
        return _build_zero_evidence(
            stage="undefined",
            cup_left_edge_date=candidate_window.start_date,
            cup_right_edge_date=candidate_window.end_date,
            criteria_pass={f"criterion_{i}": False for i in range(1, 9)},
        )

    # Step 1: resolve the cup left edge via per-mode anchor semantic.
    reason = candidate_window.anchor_reason or ""
    if reason.startswith("zigzag_pivot"):
        cup_left_edge_date = candidate_window.anchor_date
    else:
        sliced = _backward_slice_cup_left_edge(
            bars, candidate_window.anchor_date
        )
        if sliced is None:
            return _build_zero_evidence(
                stage="undefined",
                cup_left_edge_date=candidate_window.anchor_date,
                cup_right_edge_date=candidate_window.end_date,
                criteria_pass={f"criterion_{i}": False for i in range(1, 9)},
            )
        cup_left_edge_date = sliced

    # Cup left edge price: bar's High at cup_left_edge_date (or nearest).
    left_ts = pd.Timestamp(cup_left_edge_date)
    if left_ts in bars.index:
        cup_left_edge_price = float(bars.loc[left_ts, "High"])
    else:
        forward = bars.loc[bars.index >= left_ts]
        if len(forward) == 0:
            return _build_zero_evidence(
                stage="undefined",
                cup_left_edge_date=cup_left_edge_date,
                cup_right_edge_date=candidate_window.end_date,
                criteria_pass={f"criterion_{i}": False for i in range(1, 9)},
            )
        cup_left_edge_price = float(forward["High"].iloc[0])
        cup_left_edge_date = _ts_to_date(forward.index[0])

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
            cup_left_edge_date=cup_left_edge_date,
            cup_right_edge_date=candidate_window.end_date,
            criteria_pass={"criterion_1": False},
        )

    # Step 3: identify cup anchors (bottom + right edge).
    anchors = _identify_cup_anchors(bars, cup_left_edge_date)
    if anchors is None:
        return _build_zero_evidence(
            stage=stage,
            cup_left_edge_date=cup_left_edge_date,
            cup_right_edge_date=candidate_window.end_date,
            criteria_pass={"criterion_1": True},
        )
    (
        cup_bottom_date,
        cup_bottom_price,
        cup_right_edge_date,
        cup_right_edge_price,
    ) = anchors

    # Step 4: identify handle.
    handle = _identify_handle(
        bars, cup_right_edge_date, cup_right_edge_price
    )
    if handle is None:
        # No handle bars -> cannot evaluate criteria #5, #6, #7, #8.
        return _build_zero_evidence(
            stage=stage,
            cup_left_edge_date=cup_left_edge_date,
            cup_right_edge_date=cup_right_edge_date,
            criteria_pass={"criterion_1": True},
        )
    (
        handle_start_date,
        handle_end_date,
        handle_high_price,
        handle_low_price,
        handle_duration_days,
        handle_depth_pct,
    ) = handle

    # Step 5: criterion #2 -- cup depth + cup_left_to_bottom_days.
    if cup_left_edge_price <= 0:
        return _build_zero_evidence(
            stage=stage,
            cup_left_edge_date=cup_left_edge_date,
            cup_right_edge_date=cup_right_edge_date,
            criteria_pass={"criterion_1": True},
        )
    cup_depth_pct = (
        (cup_left_edge_price - cup_bottom_price) / cup_left_edge_price * 100.0
    )
    cup_left_to_bottom_days = (cup_bottom_date - cup_left_edge_date).days
    c2_pass = (
        _check_cup_depth(cup_depth_pct)
        and cup_left_to_bottom_days >= _CUP_LEFT_TO_BOTTOM_DAYS_BOUND
    )

    # Step 6: criterion #3 -- cup right edge ratio.
    cup_right_edge_pct = (
        cup_right_edge_price / cup_left_edge_price * 100.0
    )
    c3_pass = _check_cup_right_edge_ratio(cup_right_edge_pct)

    # Step 7: criterion #4 -- cup duration.
    cup_duration_days = (cup_right_edge_date - cup_left_edge_date).days
    c4_pass = _check_cup_duration(cup_duration_days)

    # Step 8: criterion #5 -- handle depth + duration.
    c5_pass = _check_handle(handle_depth_pct, handle_duration_days)

    # Step 9: criterion #6 -- handle low vs cup midpoint.
    c6_pass, handle_low_vs_midpoint_pct = _check_handle_above_midpoint(
        handle_low_price, cup_left_edge_price, cup_bottom_price
    )

    # Step 10: pivot price (close of the LAST bar in candidate window OR
    # the first bar AFTER handle_end where Close approaches cup_right_edge).
    pivot_ts = bars.index[-1]
    # If candidate_window.end_date is BEFORE last bar, prefer that.
    cw_end_ts = pd.Timestamp(candidate_window.end_date)
    if cw_end_ts in bars.index:
        pivot_ts = cw_end_ts
    pivot_price = float(bars.loc[pivot_ts, "Close"])

    # Step 11: criterion #7 -- pivot near cup right edge.
    c7_pass, pivot_within_pct = _check_pivot_within_cup_right_edge(
        pivot_price, cup_right_edge_price
    )

    # Step 12: criterion #8 -- handle volume vs cup volume.
    cup_avg_volume = _avg_volume_between(
        bars, cup_left_edge_date, cup_right_edge_date
    )
    handle_avg_volume = _avg_volume_between(
        bars, handle_start_date, handle_end_date
    )
    c8_pass, handle_vs_cup_volume_pct = _check_handle_volume(
        handle_avg_volume, cup_avg_volume
    )

    # Step 13: section 10.7 rounded-vs-V LOCK.
    rounded_passes, rounded_penalty = _is_rounded_cup(
        bars,
        cup_bottom_date,
        cup_bottom_price,
        marginal_zone_pct=_ROUNDED_MARGINAL_ZONE_PCT,
    )
    # Count bars in marginal zone for diagnostic field (matches the
    # _is_rounded_cup internal count semantic).
    bottom_ts = pd.Timestamp(cup_bottom_date)
    rounded_window = bars.loc[
        (bars.index >= bottom_ts - pd.Timedelta(days=_ROUNDED_WINDOW_DAYS))
        & (bars.index <= bottom_ts + pd.Timedelta(days=_ROUNDED_WINDOW_DAYS))
    ]
    if len(rounded_window) > 0 and cup_bottom_price > 0:
        threshold_price = cup_bottom_price * (
            1.0 + _ROUNDED_MARGINAL_ZONE_PCT / 100.0
        )
        rounded_bars_count = int(
            np.sum(
                rounded_window["Low"].astype(float).to_numpy()
                <= threshold_price
            )
        )
    else:
        rounded_bars_count = 0

    criteria_pass = {
        "criterion_1": c1_pass,
        "criterion_2": c2_pass,
        "criterion_3": c3_pass,
        "criterion_4": c4_pass,
        "criterion_5": c5_pass,
        "criterion_6": c6_pass,
        "criterion_7": c7_pass,
        "criterion_8": c8_pass,
    }

    # Step 14: geometric_score. Hard gates: #1 + rounded-vs-V HARD FAIL.
    # Failure of either zeros the score. Otherwise base score is the
    # equal-weighted pass-fraction over the 8 criteria, MINUS the
    # rounded_cup_penalty (clamped to [0.0, 1.0]).
    if not c1_pass or not rounded_passes:
        geometric_score = 0.0
        # Force the penalty to the canonical +inf-sentinel ONLY when
        # rounded-vs-V HARD FAIL fired; otherwise preserve 0.0 / 0.10
        # so the evidence row records the actual penalty.
    else:
        passed = sum(1 for v in criteria_pass.values() if v)
        base_score = passed / len(criteria_pass)
        # Subtract penalty (0.0 for HARD PASS; 0.10 for MARGINAL).
        score = base_score - rounded_penalty
        geometric_score = max(0.0, min(1.0, score))

    # Persist the actual penalty (not the +inf sentinel) on the evidence
    # row so the dataclass remains within the LOCKed value set.
    persisted_penalty = (
        rounded_penalty
        if not math.isinf(rounded_penalty)
        else float("inf")
    )

    return CupWithHandleEvidence(
        stage=stage,
        cup_left_edge_price=float(cup_left_edge_price),
        cup_left_edge_date=cup_left_edge_date,
        cup_right_edge_price=float(cup_right_edge_price),
        cup_right_edge_date=cup_right_edge_date,
        cup_bottom_price=float(cup_bottom_price),
        cup_bottom_date=cup_bottom_date,
        cup_depth_pct=float(cup_depth_pct),
        cup_duration_days=int(cup_duration_days),
        cup_right_edge_pct_of_left_edge=float(cup_right_edge_pct),
        handle_high_price=float(handle_high_price),
        handle_low_price=float(handle_low_price),
        handle_start_date=handle_start_date,
        handle_end_date=handle_end_date,
        handle_depth_pct=float(handle_depth_pct),
        handle_duration_days=int(handle_duration_days),
        handle_low_vs_cup_midpoint_pct=float(handle_low_vs_midpoint_pct),
        handle_volume_vs_cup_volume_pct=float(handle_vs_cup_volume_pct),
        pivot_price=float(pivot_price),
        pivot_within_cup_right_edge_pct=float(pivot_within_pct),
        rounded_cup_passes=bool(rounded_passes),
        rounded_cup_penalty=float(persisted_penalty),
        rounded_cup_bars_in_marginal_zone=int(rounded_bars_count),
        criteria_pass=criteria_pass,
        geometric_score=float(geometric_score),
    )


