"""Phase 13 T2.SB4 T-A.4.2 - double-bottom-W detector per spec section 5.6.

Minervini / O'Neil DBW: rule-based geometric detector that ingests OHLCV
daily bars + a CandidateWindow from the T2.SB2 foundation primitive
``generate_candidate_windows`` and returns a ``DoubleBottomWEvidence``
frozen dataclass capturing per-criterion verdicts + the structural
evidence (two troughs + center peak + undercut flag + pivot).

LOCKs (per dispatch brief and plan G.6 LOCKs):
- L1: spec section 5.6 8 criteria + section 10.5 worked example +
  section 10.6 LOCK (criterion #1 + #5 STRICT NONE tolerance;
  criterion #8 LOCK undercut bonus +0.10 capped at 1.0) verbatim;
  do NOT paraphrase. Section 10.5: geometric_score = min(base + 0.10, 1.0).
- L2: ZERO DB writes inside this module (``current_stage`` is the only
  DB call; SELECT-only).
- L5: ASCII-only output paths.
- L7: ``DoubleBottomWEvidence`` is a frozen dataclass with
  ``__post_init__`` runtime validation against explicit allowed-value
  frozensets (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").
- L10: bar-clipping at detector entry. Clip
  ``bars.index <= candidate_window.end_date`` BEFORE anchor identification
  (mirrors cup_with_handle precedent; preempts future-bar leak).

Tolerance bands per spec section 5.6 + section 10.6 LOCK (BINDING):
- criterion #2 (trough_1_drawdown_pct >= 0.15): +/- 1% on the bound ->
  relaxed >= 14%.
- criterion #3 (center_peak_retracement_pct >= 0.50): +/- 2% on the
  bound -> relaxed >= 48%.
- criterion #4 (trough_2 within +/-5% of trough_1 OR <= 5% undercut):
  +/- 0.5% on the 5% bound -> relaxed 5.5%.
- criterion #5 (both durations in [5, 35]): STRICT NONE.
- criterion #6 (pivot_price / center_peak_price in [0.99, 1.01]):
  +/- 0.5% -> relaxed [0.985, 1.015].
- criterion #7 (trough_2_avg_volume / trough_1_avg_volume in [1.0, 2.0]):
  OPTIONAL; evidence-only; does NOT increment geometric_score.
- criterion #8 LOCK: undercut bonus +0.10 added to geometric_score;
  capped at 1.0 via min(base + bonus, 1.0).

Anchor_date contract: DBW uses swing-LOW (trough_1 anchor). Different
from HTF (swing-HIGH for pole peak). The detector backward-slices the
zigzag swings to identify trough_2 (most-recent swing-LOW preceding the
candidate_window.end_date), then center_peak (preceding swing-HIGH),
then trough_1 (preceding swing-LOW). The detector implements its OWN
backward-slice helper distinct from HTF's swing-HIGH walk-back.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from swing.patterns._sanitize import sanitize_bars
from swing.patterns.foundation import (
    CandidateWindow,
    adaptive_initial_threshold_pct,
    current_stage,
    extract_zigzag_swings,
)

# Detector version pin. Bump on any algorithm change.
DETECTOR_VERSION: str = "double_bottom_w@v1.0.0"

# Spec section 5.6 + section 10.6 LOCK constants.
_TROUGH_1_DRAWDOWN_BOUND: float = 0.15            # >= 15%
_TROUGH_1_DRAWDOWN_TOLERANCE: float = 0.01        # +/- 1% -> relaxed >= 14%
_CENTER_PEAK_RETRACEMENT_BOUND: float = 0.50      # >= 50%
_CENTER_PEAK_RETRACEMENT_TOLERANCE: float = 0.02  # +/- 2% -> relaxed >= 48%
_TROUGH_2_BAND_PCT: float = 0.05                  # +/-5% of trough_1
_TROUGH_2_BAND_TOLERANCE: float = 0.005           # +/- 0.5% -> relaxed 5.5%
_DURATION_RANGE_DAYS: tuple[int, int] = (5, 35)   # STRICT NONE tolerance
_PIVOT_RATIO_RANGE: tuple[float, float] = (0.99, 1.01)
_PIVOT_TOLERANCE_FRAC: float = 0.005              # 0.5% -> [0.985, 1.015]
_VOLUME_RATIO_RANGE: tuple[float, float] = (1.0, 2.0)  # OPTIONAL criterion #7
_UNDERCUT_BONUS: float = 0.10                     # LOCK +0.10
_SCORE_CAP: float = 1.0                           # LOCK cap at 1.0

# Allowed Literal values (L7 LOCK: validate in __post_init__).
_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)
_CRITERION_KEYS: frozenset[str] = frozenset(
    {f"criterion_{i}" for i in range(1, 9)}
)
_RECENT_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DoubleBottomWEvidence:
    """Structural evidence emitted by detect_double_bottom_w.

    Per spec section 5.6 ``DoubleBottomWEvidence`` shape (line 663) +
    section 10.5 worked example. Field order follows the structural
    chronology (trough_1 -> center_peak -> trough_2 -> pivot).

    LOCK L7: ``stage`` Literal + ``criteria_pass`` keys validated at
    ``__post_init__`` time against module-level frozensets.

    ``recent_stage`` records the prior-window stage symbol for spec
    section 5.6 criterion #1 second-clause introspection. V1
    ``current_stage`` returns only ``stage_2`` / ``undefined``; the
    field is reserved for V2 widening (true 4-stage labeling).
    """

    stage: Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]
    recent_stage: Literal[
        "stage_1", "stage_2", "stage_3", "stage_4", "undefined"
    ]
    # Trough 1 (criterion #2).
    trough_1_date: date
    trough_1_price: float
    trough_1_drawdown_pct: float
    trough_1_avg_volume: float
    # Center peak (criterion #3).
    center_peak_date: date
    center_peak_price: float
    center_peak_retracement_pct: float
    # Trough 2 (criterion #4 + #8 undercut flag).
    trough_2_date: date
    trough_2_price: float
    trough_2_avg_volume: float
    undercut: bool
    # Durations (criterion #5).
    trough_1_to_center_duration_days: int
    center_to_trough_2_duration_days: int
    # Pivot (criterion #6).
    pivot_price: float
    # Aggregation.
    criteria_pass: dict[str, bool]
    geometric_score: float

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_VALUES:
            raise ValueError(
                f"DoubleBottomWEvidence.stage must be one of "
                f"{sorted(_STAGE_VALUES)}, got {self.stage!r}"
            )
        if self.recent_stage not in _RECENT_STAGE_VALUES:
            raise ValueError(
                f"DoubleBottomWEvidence.recent_stage must be one of "
                f"{sorted(_RECENT_STAGE_VALUES)}, got {self.recent_stage!r}"
            )
        if not (0.0 <= self.geometric_score <= 1.0):
            raise ValueError(
                f"DoubleBottomWEvidence.geometric_score must be in "
                f"[0.0, 1.0], got {self.geometric_score}"
            )
        if set(self.criteria_pass.keys()) != _CRITERION_KEYS:
            raise ValueError(
                f"DoubleBottomWEvidence.criteria_pass must have keys "
                f"{sorted(_CRITERION_KEYS)}, got "
                f"{sorted(self.criteria_pass.keys())}"
            )
        if self.trough_1_to_center_duration_days < 0:
            raise ValueError(
                f"DoubleBottomWEvidence.trough_1_to_center_duration_days "
                f"must be >= 0, got {self.trough_1_to_center_duration_days}"
            )
        if self.center_to_trough_2_duration_days < 0:
            raise ValueError(
                f"DoubleBottomWEvidence.center_to_trough_2_duration_days "
                f"must be >= 0, got {self.center_to_trough_2_duration_days}"
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
    anchor_date: date,
    criteria_pass: dict[str, bool] | None = None,
) -> DoubleBottomWEvidence:
    """Construct a zero-score DoubleBottomWEvidence early-exit envelope.

    Used when (a) bars are empty or pre-clip too short; (b) criterion #1
    Stage 2 hard gate fails; (c) the backward-slice cannot locate
    trough_1/center_peak/trough_2 structure within the candidate window.
    """
    full_flags: dict[str, bool] = {f"criterion_{i}": False for i in range(1, 9)}
    if criteria_pass:
        full_flags.update(criteria_pass)
    return DoubleBottomWEvidence(
        stage=stage,
        recent_stage="undefined",
        trough_1_date=anchor_date,
        trough_1_price=0.0,
        trough_1_drawdown_pct=0.0,
        trough_1_avg_volume=0.0,
        center_peak_date=anchor_date,
        center_peak_price=0.0,
        center_peak_retracement_pct=0.0,
        trough_2_date=anchor_date,
        trough_2_price=0.0,
        trough_2_avg_volume=0.0,
        undercut=False,
        trough_1_to_center_duration_days=0,
        center_to_trough_2_duration_days=0,
        pivot_price=0.0,
        criteria_pass=full_flags,
        geometric_score=0.0,
    )


def _backward_slice_dbw_structure(
    bars: pd.DataFrame, window_end_date: date
) -> tuple[date, float, date, float, date, float, date, float] | None:
    """Backward-slice to locate (prior_peak, trough_1, center_peak, trough_2).

    DBW uses swing-LOW anchor for trough_1 (distinct from HTF swing-HIGH
    for pole peak). Algorithm: extract zigzag swings over bars; walk the
    swings in REVERSE order to find the most-recent (down-up-down-up)
    sequence ending at or before window_end_date. The structural
    landmarks are:

      prior_peak (UP-swing end before trough_1)
        -> trough_1 (DOWN-swing end == prior_peak's down-swing partner)
        -> center_peak (UP-swing end, the recovery)
        -> trough_2 (DOWN-swing end, the second trough)
        -> [pivot is bars[-1] close in the window]

    In terms of zigzag swings ordered ascending in time, the sequence
    looks like (most recent at the end):

      ..., UP_to_prior_peak, DOWN_to_trough_1, UP_to_center_peak,
           DOWN_to_trough_2, [UP_to_pivot_or_in_progress]

    Returns the 4 landmarks as
    ``(prior_peak_date, prior_peak_price, trough_1_date, trough_1_price,
       center_peak_date, center_peak_price, trough_2_date, trough_2_price)``
    OR ``None`` if no DBW-shaped sequence is found.
    """
    if len(bars) < 10:
        return None
    threshold = adaptive_initial_threshold_pct(bars)
    swings = extract_zigzag_swings(
        bars, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    if len(swings) < 4:
        return None
    # Walk the swings list in reverse looking for a tail subsequence
    # matching: UP_prior_peak -> DOWN_trough_1 -> UP_center_peak -> DOWN_trough_2.
    # We scan from the end; if the very last swing is UP (in-progress
    # post-trough_2 recovery), skip it and look at the preceding 4.
    n = len(swings)
    # Try with the most-recent swing as trough_2 down-swing first; if it
    # is an UP swing (recovery in progress), skip it.
    for tail_idx in (n - 1, n - 2):
        if tail_idx < 3:
            continue
        s_trough_2 = swings[tail_idx]
        s_center_peak = swings[tail_idx - 1]
        s_trough_1 = swings[tail_idx - 2]
        s_prior_peak = swings[tail_idx - 3]
        if (
            s_trough_2.direction == "down"
            and s_center_peak.direction == "up"
            and s_trough_1.direction == "down"
            and s_prior_peak.direction == "up"
        ):
            # All four landmarks identified.
            prior_peak_date = s_prior_peak.end_date
            prior_peak_price = float(s_prior_peak.end_price)
            trough_1_date = s_trough_1.end_date
            trough_1_price = float(s_trough_1.end_price)
            center_peak_date = s_center_peak.end_date
            center_peak_price = float(s_center_peak.end_price)
            trough_2_date = s_trough_2.end_date
            trough_2_price = float(s_trough_2.end_price)
            # Validate ordering + on/before window_end_date.
            if not (
                prior_peak_date
                <= trough_1_date
                <= center_peak_date
                <= trough_2_date
                <= window_end_date
            ):
                continue
            return (
                prior_peak_date,
                prior_peak_price,
                trough_1_date,
                trough_1_price,
                center_peak_date,
                center_peak_price,
                trough_2_date,
                trough_2_price,
            )
    return None


def _check_trough_1_drawdown(drawdown_pct: float) -> bool:
    """Criterion #2: drawdown >= 0.15 (relaxed >= 0.14)."""
    relaxed = _TROUGH_1_DRAWDOWN_BOUND - _TROUGH_1_DRAWDOWN_TOLERANCE
    return drawdown_pct >= relaxed


def _check_center_peak_retracement(retracement_pct: float) -> bool:
    """Criterion #3: retracement >= 0.50 (relaxed >= 0.48)."""
    relaxed = (
        _CENTER_PEAK_RETRACEMENT_BOUND - _CENTER_PEAK_RETRACEMENT_TOLERANCE
    )
    return retracement_pct >= relaxed


def _check_trough_2_band(
    trough_1: float, trough_2: float
) -> tuple[bool, bool]:
    """Criterion #4: trough_2 within +/-5% of trough_1 (relaxed 5.5%) OR
    undercut by <= 5% (relaxed 5.5%).

    Returns ``(passes, undercut_flag)`` where ``undercut_flag`` is True
    iff trough_2 < trough_1 (and the undercut magnitude is within bound).
    """
    if trough_1 <= 0:
        return False, False
    relaxed = _TROUGH_2_BAND_PCT + _TROUGH_2_BAND_TOLERANCE
    diff_pct = abs(trough_2 - trough_1) / trough_1
    undercut = trough_2 < trough_1 and (trough_1 - trough_2) / trough_1 > 0.0
    # Symmetric ±band OR undercut by <= relaxed.
    if undercut:
        undercut_mag = (trough_1 - trough_2) / trough_1
        passes = undercut_mag <= relaxed
    else:
        passes = diff_pct <= relaxed
    return passes, undercut


def _check_durations(
    t1_to_center_days: int, center_to_t2_days: int
) -> bool:
    """Criterion #5: BOTH durations in [5, 35] STRICT (NONE tolerance)."""
    lo, hi = _DURATION_RANGE_DAYS
    return lo <= t1_to_center_days <= hi and lo <= center_to_t2_days <= hi


def _check_pivot_within_center_peak(
    pivot_price: float, center_peak_price: float
) -> bool:
    """Criterion #6: pivot/center_peak in [0.99, 1.01] (relaxed [0.985, 1.015]).
    """
    if center_peak_price <= 0:
        return False
    ratio = pivot_price / center_peak_price
    lo = _PIVOT_RATIO_RANGE[0] - _PIVOT_TOLERANCE_FRAC
    hi = _PIVOT_RATIO_RANGE[1] + _PIVOT_TOLERANCE_FRAC
    return lo <= ratio <= hi


def _check_volume_rises_into_trough_2(
    trough_1_avg_volume: float, trough_2_avg_volume: float
) -> bool:
    """Criterion #7 OPTIONAL: trough_2_avg / trough_1_avg in [1.0, 2.0].

    Evidence-only; does NOT increment geometric_score per spec section
    5.6 criterion #7 OPTIONAL semantics + section 10.5 LOCK (only
    criterion #8 undercut bonus increments score).
    """
    if trough_1_avg_volume <= 0:
        return False
    ratio = trough_2_avg_volume / trough_1_avg_volume
    lo, hi = _VOLUME_RATIO_RANGE
    return lo <= ratio <= hi


def _compute_volume_avg_around(
    bars: pd.DataFrame, anchor_date: date, *, half_window_days: int = 3
) -> float:
    """Mean Volume over a ±half_window_days slice around anchor_date.

    Used to compute trough-region volume averages without depending on
    an explicit start/end (the troughs are point landmarks). Returns
    0.0 on empty slice.
    """
    lo = pd.Timestamp(anchor_date) - pd.Timedelta(days=half_window_days)
    hi = pd.Timestamp(anchor_date) + pd.Timedelta(days=half_window_days)
    sub = bars.loc[(bars.index >= lo) & (bars.index <= hi)]
    if len(sub) == 0:
        return 0.0
    return float(sub["Volume"].astype(float).mean())


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_double_bottom_w(
    bars: pd.DataFrame,
    candidate_window: CandidateWindow,
    *,
    conn: sqlite3.Connection | None = None,
    ticker: str | None = None,
    asof_date: date | None = None,
) -> DoubleBottomWEvidence:
    """Detect a double-bottom-W pattern on ``bars`` over ``candidate_window``.

    Per spec section 5.6 + section 10.5 worked example + section 10.6
    tolerance semantics. Pure function: no DB writes; ``conn`` is
    read-only via ``current_stage`` for criterion #1 (Stage 2 hard gate).

    Parameters
    ----------
    bars : pd.DataFrame
        OHLCV daily bars indexed by ``pd.Timestamp``; must NOT contain
        NaN (validated by the shared sanitizer at
        ``swing/patterns/_sanitize.py``).
    candidate_window : CandidateWindow
        One window emitted by ``generate_candidate_windows``. DBW uses
        swing-LOW anchor semantics (trough_1); the detector backward-
        slices the zigzag swings to identify (prior_peak, trough_1,
        center_peak, trough_2) leading up to ``candidate_window.end_date``.
    conn : sqlite3.Connection | None
        Read-only connection for ``current_stage(conn, ticker, asof)``.
        If None, criterion #1 is treated as failed (Stage 2 unknown).
    ticker : str | None
        Required when ``conn`` is provided; ignored otherwise.
    asof_date : date | None
        Required when ``conn`` is provided; ignored otherwise.

    Returns
    -------
    DoubleBottomWEvidence
        Frozen dataclass with per-criterion pass flags + geometric
        score + structural evidence (trough_1, center_peak, trough_2,
        undercut flag, pivot).
    """
    sanitize_bars(bars)
    # LOCK L10: clip bars to candidate_window.end_date BEFORE anchor
    # identification (mirrors cup_with_handle + high_tight_flag precedent).
    # Without this clip the detector could identify a trough_1/trough_2
    # from a bar AFTER the operator-supplied historical window. Operator-
    # supplied windows MUST NOT consume future data.
    end_ts = pd.Timestamp(candidate_window.end_date)
    bars = bars.loc[bars.index <= end_ts]
    if len(bars) < 10:
        return _build_zero_evidence(
            stage="undefined",
            anchor_date=candidate_window.end_date,
        )

    # Step 1: criterion #1 -- Stage 2 hard gate.
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
            anchor_date=candidate_window.end_date,
            criteria_pass={"criterion_1": False},
        )

    # Step 2: backward-slice to identify the DBW structural landmarks.
    sliced = _backward_slice_dbw_structure(bars, candidate_window.end_date)
    if sliced is None:
        return _build_zero_evidence(
            stage=stage,
            anchor_date=candidate_window.end_date,
            criteria_pass={"criterion_1": True},
        )
    (
        prior_peak_date,
        prior_peak_price,
        trough_1_date,
        trough_1_price,
        center_peak_date,
        center_peak_price,
        trough_2_date,
        trough_2_price,
    ) = sliced

    # Step 3: criterion #2 -- trough_1 drawdown from prior_peak.
    if prior_peak_price <= 0:
        # Pathological zero-price baseline; reject.
        return _build_zero_evidence(
            stage=stage,
            anchor_date=candidate_window.end_date,
            criteria_pass={"criterion_1": True},
        )
    trough_1_drawdown_pct = (
        (prior_peak_price - trough_1_price) / prior_peak_price
    )
    c2_pass = _check_trough_1_drawdown(trough_1_drawdown_pct)

    # Step 4: criterion #3 -- center_peak retracement from trough_1.
    # Retracement = (center_peak - trough_1) / (prior_peak - trough_1).
    denom = prior_peak_price - trough_1_price
    if denom <= 0:
        center_peak_retracement_pct = 0.0
    else:
        center_peak_retracement_pct = (
            (center_peak_price - trough_1_price) / denom
        )
    c3_pass = _check_center_peak_retracement(center_peak_retracement_pct)

    # Step 5: criterion #4 -- trough_2 within band of trough_1 + undercut flag.
    c4_pass, undercut = _check_trough_2_band(trough_1_price, trough_2_price)

    # Step 6: criterion #5 -- both durations in [5, 35] STRICT.
    t1_to_center_days = (center_peak_date - trough_1_date).days
    center_to_t2_days = (trough_2_date - center_peak_date).days
    c5_pass = _check_durations(t1_to_center_days, center_to_t2_days)

    # Step 7: criterion #6 -- pivot at center_peak height.
    # Pivot = LAST close in the candidate window.
    pivot_price = float(bars["Close"].iloc[-1])
    c6_pass = _check_pivot_within_center_peak(pivot_price, center_peak_price)

    # Step 8: criterion #7 OPTIONAL -- volume rises into trough_2.
    trough_1_avg_volume = _compute_volume_avg_around(bars, trough_1_date)
    trough_2_avg_volume = _compute_volume_avg_around(bars, trough_2_date)
    c7_pass = _check_volume_rises_into_trough_2(
        trough_1_avg_volume, trough_2_avg_volume
    )

    # Step 9: criterion #8 -- undercut bonus flag (always set from #4 logic).
    c8_pass = undercut

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

    # Step 10: geometric_score per spec section 10.5 + section 5.6 #8 LOCK.
    # Base score = fraction of MANDATORY criteria passed (criteria #1..#6).
    # Criterion #7 is OPTIONAL evidence-only (does NOT increment score).
    # Criterion #8 (undercut) contributes via the bonus, NOT the base.
    # Bonus = +0.10 if undercut else 0.
    # Final = min(base + bonus, 1.0).
    if not c1_pass:
        geometric_score = 0.0
    else:
        mandatory_keys = (
            "criterion_1",
            "criterion_2",
            "criterion_3",
            "criterion_4",
            "criterion_5",
            "criterion_6",
        )
        passed = sum(1 for k in mandatory_keys if criteria_pass[k])
        base = passed / len(mandatory_keys)
        bonus = _UNDERCUT_BONUS if undercut else 0.0
        geometric_score = min(base + bonus, _SCORE_CAP)

    # V1 current_stage returns only stage_2/undefined; recent_stage stays
    # 'undefined' until V2 widens current_stage to true 4-stage labeling.
    return DoubleBottomWEvidence(
        stage=stage,
        recent_stage="undefined",
        trough_1_date=trough_1_date,
        trough_1_price=float(trough_1_price),
        trough_1_drawdown_pct=float(trough_1_drawdown_pct),
        trough_1_avg_volume=float(trough_1_avg_volume),
        center_peak_date=center_peak_date,
        center_peak_price=float(center_peak_price),
        center_peak_retracement_pct=float(center_peak_retracement_pct),
        trough_2_date=trough_2_date,
        trough_2_price=float(trough_2_price),
        trough_2_avg_volume=float(trough_2_avg_volume),
        undercut=bool(undercut),
        trough_1_to_center_duration_days=int(t1_to_center_days),
        center_to_trough_2_duration_days=int(center_to_t2_days),
        pivot_price=float(pivot_price),
        criteria_pass=criteria_pass,
        geometric_score=float(geometric_score),
    )
