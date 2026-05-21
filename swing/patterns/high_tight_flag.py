"""Phase 13 T2.SB4 T-A.4.1 - high-tight-flag detector per spec section 5.5.

Minervini / O'Neil HTF: rule-based geometric detector that ingests OHLCV
daily bars + a CandidateWindow from the T2.SB2 foundation primitive
``generate_candidate_windows`` and returns a ``HighTightFlagEvidence``
frozen dataclass capturing per-criterion verdicts + the structural
evidence (pole anchors, consolidation anchors, pivot, volume contraction).

LOCKs (per dispatch brief and plan G.6 LOCKs):
- L1: spec section 5.5 6 criteria + section 10.4 worked example +
  section 10.6 STRICT bound NONE for criterion #4 (consolidation_width)
  verbatim; do NOT paraphrase. 15.6% width REJECTS; 14.8% PASSES.
- L2: ZERO DB writes inside this module (``current_stage`` is the only
  DB call; SELECT-only).
- L5: ASCII-only output paths.
- L7: ``HighTightFlagEvidence`` is a frozen dataclass with
  ``__post_init__`` runtime validation against explicit allowed-value
  frozensets (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").
- L8: post-pole sub-window named ``consolidation_*`` NOT ``flag_*``
  (CLAUDE.md gotcha + T-A.1.8 Deficiency 3; spec section 5.5 criterion
  lock strings name the sub-window ``consolidation_*``).
- L10: bar-clipping at detector entry. Clip
  ``bars.index <= candidate_window.end_date`` BEFORE anchor identification
  (mirrors cup_with_handle precedent; preempts future-bar leak).

Tolerance bands per spec section 5.5 + section 10.6 LOCK (BINDING):
- criterion #2 (pole_pct >= 0.90 AND pole_duration in [28, 56]):
  +/- 5% on pct bound -> relaxed >= 85%; duration STRICT range.
- criterion #3 (consolidation_pullback <= 0.25 AND consolidation_duration
  in [21, 35]): +/- 2pp on pullback bound -> relaxed <= 27%; duration
  STRICT range.
- criterion #4 (consolidation_width_pct <= 15.0): **NONE - STRICT**
  per spec section 10.6 LOCK + section 10.4 errata.
- criterion #5 (consolidation_avg_volume / pole_avg_volume <= 0.65):
  +/- 10% -> relaxed <= 0.75.
- criterion #6 (pivot_price / consolidation_top_price in [0.99, 1.01]):
  +/- 0.5% -> relaxed [0.985, 1.015].

Per-mode anchor_date semantic (mirrors cup_with_handle Section 7.3 swing-
HIGH semantics): for ``ma_crossover`` / ``high_low_breakout`` modes the
detector backward-slices from the anchor_date to find the most-recent
SWING-HIGH (the pole peak). For ``zigzag_pivot`` mode the anchor_date IS
the pole peak directly. The detector then walks back from the pole peak
to identify the pole START as the most-recent swing-LOW preceding the
peak. Pole peak identification uses its OWN backward-slice helper
(not shared with cup_with_handle which targets the LEFT EDGE of a cup,
not the apex of a pole).
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
DETECTOR_VERSION: str = "high_tight_flag@v1.0.0"

# Spec section 5.5 + section 10.6 LOCK constants.
_POLE_PCT_BOUND: float = 0.90              # 90% gain
_POLE_PCT_TOLERANCE: float = 0.05          # +/- 5% -> relaxed >= 85%
_POLE_DURATION_DAYS_RANGE: tuple[int, int] = (28, 56)  # 4-8 weeks
_CONSOLIDATION_PULLBACK_BOUND: float = 0.25  # <= 25%
_CONSOLIDATION_PULLBACK_TOLERANCE: float = 0.02  # +/- 2pp -> relaxed <= 27%
_CONSOLIDATION_DURATION_DAYS_RANGE: tuple[int, int] = (21, 35)  # 3-5 weeks
_CONSOLIDATION_WIDTH_BOUND_PCT: float = 15.0  # STRICT (NONE tolerance)
_VOLUME_RATIO_BOUND: float = 0.65            # <= 65%
_VOLUME_RATIO_TOLERANCE: float = 0.10        # +/- 10% -> relaxed <= 0.75
_PIVOT_RATIO_RANGE: tuple[float, float] = (0.99, 1.01)
_PIVOT_TOLERANCE_FRAC: float = 0.005         # 0.5% band -> [0.985, 1.015]

# Pole identification lookback: search up to 70 days back from pole peak
# to locate the pole START (the prior swing-LOW). Generous upper bound;
# criterion #2 enforces the [28, 56] duration window strictly.
_POLE_LOOKBACK_DAYS: int = 70

# Allowed Literal values (L7 LOCK: validate in __post_init__).
_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)
_CRITERION_KEYS: frozenset[str] = frozenset(
    {f"criterion_{i}" for i in range(1, 7)}
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HighTightFlagEvidence:
    """Structural evidence emitted by detect_high_tight_flag.

    Per spec section 5.5 ``HighTightFlagEvidence`` shape (line 642) plus
    section 10.4 worked example fields. Field order follows the criteria
    sequence so the dataclass reads naturally against the spec table.

    LOCK L7: ``stage`` Literal + ``criteria_pass`` keys validated at
    ``__post_init__`` time against module-level frozensets; closes the
    CLAUDE.md gotcha "Literal[...] type hints are NOT runtime-enforced".

    LOCK L8: post-pole sub-window named ``consolidation_*`` NOT
    ``flag_*``. Spec section 5.5 criterion lock strings name the
    sub-window ``consolidation_*`` (see CLAUDE.md gotcha; locked at
    ``tests/patterns/test_spec_static.py``).
    """

    stage: Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]
    # Pole evidence (criterion #2).
    pole_start_date: date
    pole_start_price: float
    pole_peak_date: date
    pole_peak_price: float
    pole_pct: float
    pole_duration_days: int
    pole_avg_volume: float
    # Consolidation evidence (criteria #3, #4, #5) -- L8: consolidation_* naming.
    consolidation_start_date: date
    consolidation_end_date: date
    consolidation_top_price: float
    consolidation_bottom_price: float
    consolidation_pullback_pct: float
    consolidation_width_pct: float
    consolidation_duration_days: int
    consolidation_avg_volume: float
    # Pivot (criterion #6).
    pivot_price: float
    pivot_within_top_pct: float
    # Aggregation.
    criteria_pass: dict[str, bool]
    geometric_score: float

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_VALUES:
            raise ValueError(
                f"HighTightFlagEvidence.stage must be one of "
                f"{sorted(_STAGE_VALUES)}, got {self.stage!r}"
            )
        if not (0.0 <= self.geometric_score <= 1.0):
            raise ValueError(
                f"HighTightFlagEvidence.geometric_score must be in "
                f"[0.0, 1.0], got {self.geometric_score}"
            )
        if set(self.criteria_pass.keys()) != _CRITERION_KEYS:
            raise ValueError(
                f"HighTightFlagEvidence.criteria_pass must have keys "
                f"{sorted(_CRITERION_KEYS)}, got "
                f"{sorted(self.criteria_pass.keys())}"
            )
        if self.pole_duration_days < 0:
            raise ValueError(
                f"HighTightFlagEvidence.pole_duration_days must be >= 0, "
                f"got {self.pole_duration_days}"
            )
        if self.consolidation_duration_days < 0:
            raise ValueError(
                f"HighTightFlagEvidence.consolidation_duration_days must "
                f"be >= 0, got {self.consolidation_duration_days}"
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
    pole_peak_date: date,
    consolidation_end_date: date,
    criteria_pass: dict[str, bool],
) -> HighTightFlagEvidence:
    """Construct an early-exit HighTightFlagEvidence with geometric_score
    == 0.0. Used when a hard gate fails (criterion #1 Stage 2 or empty
    bars / missing pole) or when the backward-slice cannot locate a pole
    structure.
    """
    full_flags = {f"criterion_{i}": False for i in range(1, 7)}
    full_flags.update(criteria_pass)
    return HighTightFlagEvidence(
        stage=stage,
        pole_start_date=pole_peak_date,
        pole_start_price=0.0,
        pole_peak_date=pole_peak_date,
        pole_peak_price=0.0,
        pole_pct=0.0,
        pole_duration_days=0,
        pole_avg_volume=0.0,
        consolidation_start_date=pole_peak_date,
        consolidation_end_date=consolidation_end_date,
        consolidation_top_price=0.0,
        consolidation_bottom_price=0.0,
        consolidation_pullback_pct=0.0,
        consolidation_width_pct=0.0,
        consolidation_duration_days=0,
        consolidation_avg_volume=0.0,
        pivot_price=0.0,
        pivot_within_top_pct=0.0,
        criteria_pass=full_flags,
        geometric_score=0.0,
    )


def _backward_slice_pole_peak(
    bars: pd.DataFrame, anchor_date: date
) -> date | None:
    """Locate the POLE PEAK via backward-slicing from a trigger anchor.

    Per dispatch brief anchor_date contract: HTF uses swing-HIGH (pole
    peak). For ``ma_crossover`` / ``high_low_breakout`` candidate windows
    the anchor_date is a TRIGGER EVENT (not the pole peak). This helper
    walks BACK from the anchor to find the most-recent prior SWING-HIGH.
    That swing-HIGH is the inferred pole peak.

    Returns None if no suitable prior swing-HIGH is found.

    OWN backward-slice helper (NOT shared with cup_with_handle which
    targets the LEFT EDGE of a cup, not the apex of a pole; the algorithm
    is the same SWING-HIGH walk-back but the SEMANTIC differs).
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
    # the most-recent swing-HIGH (the pole peak).
    for sw in reversed(swings):
        if sw.direction == "up":
            return sw.end_date
    return None


def _identify_pole_start(
    bars: pd.DataFrame, pole_peak_date: date
) -> tuple[date, float] | None:
    """Locate (pole_start_date, pole_start_price) given the pole peak.

    Walks BACK from pole_peak_date up to ``_POLE_LOOKBACK_DAYS`` (~70
    days) to find the prior swing-LOW that gave rise to the pole. The
    pole START is the most-recent down-swing endpoint preceding the peak
    (or, equivalently, the start of the up-swing that culminates at the
    peak).

    Returns None if no suitable prior swing-LOW is found OR if the bars
    frame does not contain enough history before pole_peak_date.
    """
    peak_ts = pd.Timestamp(pole_peak_date)
    lookback_start = peak_ts - pd.Timedelta(days=_POLE_LOOKBACK_DAYS)
    sub = bars.loc[
        (bars.index >= lookback_start) & (bars.index <= peak_ts)
    ]
    if len(sub) < 10:
        return None
    threshold = adaptive_initial_threshold_pct(sub)
    swings = extract_zigzag_swings(
        sub, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    # Walk BACK through swings; find the most-recent UP-swing whose
    # end_date == pole_peak_date (or matches the peak). Its start_date
    # is the pole start. If no such swing, fall back to the earliest bar
    # in the lookback window's Low.
    for sw in reversed(swings):
        if sw.direction == "up":
            return sw.start_date, float(sw.start_price)
    # Fallback: argmin of Low within the lookback window.
    if len(sub) == 0:
        return None
    low_arr = sub["Low"].astype(float).to_numpy()
    low_idx = int(low_arr.argmin())
    return _ts_to_date(sub.index[low_idx]), float(low_arr[low_idx])


def _check_pole(
    pole_pct: float, pole_duration_days: int
) -> bool:
    """Criterion #2: pole_pct >= 0.90 (relaxed >= 0.85) AND
    pole_duration_days in [28, 56] STRICT.
    """
    relaxed_pct = _POLE_PCT_BOUND - _POLE_PCT_TOLERANCE
    pct_ok = pole_pct >= relaxed_pct
    lo, hi = _POLE_DURATION_DAYS_RANGE
    duration_ok = lo <= pole_duration_days <= hi
    return pct_ok and duration_ok


def _check_consolidation(
    pullback_pct: float, duration_days: int
) -> bool:
    """Criterion #3: pullback <= 0.25 (relaxed <= 0.27) AND
    duration in [21, 35] STRICT.
    """
    relaxed_pullback = (
        _CONSOLIDATION_PULLBACK_BOUND + _CONSOLIDATION_PULLBACK_TOLERANCE
    )
    pullback_ok = pullback_pct <= relaxed_pullback
    lo, hi = _CONSOLIDATION_DURATION_DAYS_RANGE
    duration_ok = lo <= duration_days <= hi
    return pullback_ok and duration_ok


def _check_consolidation_width(width_pct: float) -> bool:
    """Criterion #4: width_pct <= 15.0 STRICT (NONE tolerance per
    spec section 10.6 LOCK + section 10.4 errata).

    15.6% > 15.0% REJECTS; 14.8% <= 15.0% PASSES.
    """
    return width_pct <= _CONSOLIDATION_WIDTH_BOUND_PCT


def _check_volume_ratio(
    consolidation_avg_volume: float, pole_avg_volume: float
) -> tuple[bool, float]:
    """Criterion #5: consolidation_avg_volume / pole_avg_volume <= 0.65
    (relaxed <= 0.75 with +/- 10% tolerance).

    Returns (passes, ratio). Zero-volume edge case (pole_avg_volume == 0):
    returns (False, 0.0) without division.
    """
    if pole_avg_volume <= 0:
        return False, 0.0
    ratio = consolidation_avg_volume / pole_avg_volume
    relaxed = _VOLUME_RATIO_BOUND + _VOLUME_RATIO_TOLERANCE
    return ratio <= relaxed, float(ratio)


def _check_pivot_within_top(
    pivot_price: float, consolidation_top_price: float
) -> tuple[bool, float]:
    """Criterion #6: pivot / consolidation_top in [0.99, 1.01] (relaxed
    [0.985, 1.015] with +/- 0.5% tolerance).

    Returns (within_band, pivot_within_top_pct) where
    ``pivot_within_top_pct`` is ``(ratio - 1.0) * 100``.
    """
    if consolidation_top_price <= 0:
        return False, 0.0
    ratio = pivot_price / consolidation_top_price
    lo = _PIVOT_RATIO_RANGE[0] - _PIVOT_TOLERANCE_FRAC
    hi = _PIVOT_RATIO_RANGE[1] + _PIVOT_TOLERANCE_FRAC
    within = lo <= ratio <= hi
    return within, float((ratio - 1.0) * 100.0)


def _compute_consolidation_bounds(
    bars: pd.DataFrame,
    consolidation_start: date,
    consolidation_end: date,
) -> tuple[float, float]:
    """Return (top, bottom) over the consolidation slice using High.max()
    / Low.min(), matching spec section 5.5 LOCK shape
    ``consolidation_width_pct = (top - bottom) / bottom``.
    """
    sub = bars.loc[
        (bars.index >= pd.Timestamp(consolidation_start))
        & (bars.index <= pd.Timestamp(consolidation_end))
    ]
    if len(sub) == 0:
        return 0.0, 0.0
    top = float(sub["High"].max())
    bottom = float(sub["Low"].min())
    return top, bottom


def _compute_volume_avg(
    bars: pd.DataFrame, start: date, end: date
) -> float:
    """Mean Volume over [start, end] inclusive. Returns 0.0 on empty slice."""
    sub = bars.loc[
        (bars.index >= pd.Timestamp(start))
        & (bars.index <= pd.Timestamp(end))
    ]
    if len(sub) == 0:
        return 0.0
    return float(sub["Volume"].astype(float).mean())


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_high_tight_flag(
    bars: pd.DataFrame,
    candidate_window: CandidateWindow,
    *,
    conn: sqlite3.Connection | None = None,
    ticker: str | None = None,
    asof_date: date | None = None,
) -> HighTightFlagEvidence:
    """Detect a high-tight-flag pattern on ``bars`` over ``candidate_window``.

    Per spec section 5.5 + section 10.4 worked example + section 10.6
    STRICT bound NONE for criterion #4. Pure function: no DB writes;
    ``conn`` is read-only via ``current_stage`` for criterion #1
    (Stage 2 hard gate).

    Parameters
    ----------
    bars : pd.DataFrame
        OHLCV daily bars indexed by ``pd.Timestamp``; must NOT contain
        NaN (validated by the shared sanitizer at
        ``swing/patterns/_sanitize.py``).
    candidate_window : CandidateWindow
        One window emitted by ``generate_candidate_windows``. The
        ``anchor_date`` semantic is per-mode-dependent:
        - ``zigzag_pivot:*`` -> anchor_date IS the pole peak (swing-HIGH).
        - ``ma_crossover:*`` / ``high_low_breakout:*`` -> anchor_date is
          a TRIGGER EVENT; the detector backward-slices to find the pole
          peak (SWING-HIGH semantics).
    conn : sqlite3.Connection | None
        Read-only connection for ``current_stage(conn, ticker, asof)``.
        If None, criterion #1 is treated as failed (Stage 2 unknown).
    ticker : str | None
        Required when ``conn`` is provided; ignored otherwise.
    asof_date : date | None
        Required when ``conn`` is provided; ignored otherwise.

    Returns
    -------
    HighTightFlagEvidence
        Frozen dataclass with per-criterion pass flags + geometric
        score + structural evidence (pole + consolidation + pivot).
    """
    sanitize_bars(bars)
    # LOCK L10: clip bars to candidate_window.end_date BEFORE anchor
    # identification (mirrors cup_with_handle precedent at lines 631-636).
    # Without this clip the detector could identify a pole peak from a
    # bar AFTER the operator-supplied historical window. Operator-supplied
    # windows MUST NOT consume future data.
    end_ts = pd.Timestamp(candidate_window.end_date)
    bars = bars.loc[bars.index <= end_ts]
    if len(bars) < 10:
        return _build_zero_evidence(
            stage="undefined",
            pole_peak_date=candidate_window.anchor_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={f"criterion_{i}": False for i in range(1, 7)},
        )

    # Step 1: resolve the pole peak via per-mode anchor semantic.
    reason = candidate_window.anchor_reason or ""
    if reason.startswith("zigzag_pivot"):
        pole_peak_date = candidate_window.anchor_date
    else:
        sliced = _backward_slice_pole_peak(
            bars, candidate_window.anchor_date
        )
        if sliced is None:
            return _build_zero_evidence(
                stage="undefined",
                pole_peak_date=candidate_window.anchor_date,
                consolidation_end_date=candidate_window.end_date,
                criteria_pass={f"criterion_{i}": False for i in range(1, 7)},
            )
        pole_peak_date = sliced

    # Pole peak price: bar's High at pole_peak_date (or nearest forward bar).
    peak_ts = pd.Timestamp(pole_peak_date)
    if peak_ts in bars.index:
        pole_peak_price = float(bars.loc[peak_ts, "High"])
    else:
        forward = bars.loc[bars.index >= peak_ts]
        if len(forward) == 0:
            return _build_zero_evidence(
                stage="undefined",
                pole_peak_date=pole_peak_date,
                consolidation_end_date=candidate_window.end_date,
                criteria_pass={f"criterion_{i}": False for i in range(1, 7)},
            )
        pole_peak_price = float(forward["High"].iloc[0])
        pole_peak_date = _ts_to_date(forward.index[0])

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
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={"criterion_1": False},
        )

    # Step 3: identify pole start (criterion #2 evidence).
    pole_start = _identify_pole_start(bars, pole_peak_date)
    if pole_start is None:
        return _build_zero_evidence(
            stage=stage,
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={"criterion_1": True},
        )
    pole_start_date, pole_start_price = pole_start

    # Pole metrics.
    if pole_start_price <= 0:
        return _build_zero_evidence(
            stage=stage,
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={"criterion_1": True},
        )
    pole_pct = (pole_peak_price - pole_start_price) / pole_start_price
    pole_duration_days = (pole_peak_date - pole_start_date).days
    pole_avg_volume = _compute_volume_avg(
        bars, pole_start_date, pole_peak_date
    )
    c2_pass = _check_pole(pole_pct, pole_duration_days)

    # Step 4: consolidation slice = (pole_peak_date, candidate_window.end_date].
    # The pole peak bar itself is EXCLUDED from the consolidation slice
    # (the consolidation is the post-pole sub-window per L8 LOCK; the
    # pole peak's High would otherwise spuriously set consolidation_top
    # to the pole peak price + inflate consolidation_width_pct).
    peak_ts_inclusive = pd.Timestamp(pole_peak_date)
    post_peak = bars.loc[bars.index > peak_ts_inclusive]
    if len(post_peak) == 0:
        return _build_zero_evidence(
            stage=stage,
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={
                "criterion_1": True,
                "criterion_2": c2_pass,
            },
        )
    consolidation_start_date = _ts_to_date(post_peak.index[0])
    consolidation_end_date = candidate_window.end_date
    if consolidation_end_date < consolidation_start_date:
        return _build_zero_evidence(
            stage=stage,
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={
                "criterion_1": True,
                "criterion_2": c2_pass,
            },
        )
    consolidation_top_price, consolidation_bottom_price = (
        _compute_consolidation_bounds(
            bars, consolidation_start_date, consolidation_end_date
        )
    )
    # Duration measured from pole_peak_date to consolidation_end_date
    # (spec section 10.4 worked example: 25-day consolidation between
    # pole peak day-35 and last bar day-60 inclusive).
    consolidation_duration_days = (
        consolidation_end_date - pole_peak_date
    ).days
    # Pullback from pole peak to consolidation bottom.
    if pole_peak_price > 0:
        consolidation_pullback_pct = (
            (pole_peak_price - consolidation_bottom_price) / pole_peak_price
        )
    else:
        consolidation_pullback_pct = 0.0
    # Width pct: (top - bottom) / bottom (matches spec LOCK shape for
    # the "range width" criterion; analogous to flat_base section 5.3
    # range_width_pct = (range_top - range_bottom) / range_bottom).
    if consolidation_bottom_price > 0:
        consolidation_width_pct = (
            (consolidation_top_price - consolidation_bottom_price)
            / consolidation_bottom_price
            * 100.0
        )
    else:
        consolidation_width_pct = 0.0
    consolidation_avg_volume = _compute_volume_avg(
        bars, consolidation_start_date, consolidation_end_date
    )

    c3_pass = _check_consolidation(
        consolidation_pullback_pct, consolidation_duration_days
    )
    c4_pass = _check_consolidation_width(consolidation_width_pct)
    c5_pass, _ratio = _check_volume_ratio(
        consolidation_avg_volume, pole_avg_volume
    )

    # Step 5: pivot = LAST close in the consolidation slice.
    consol_slice = bars.loc[
        (bars.index >= pd.Timestamp(consolidation_start_date))
        & (bars.index <= pd.Timestamp(consolidation_end_date))
    ]
    if len(consol_slice) == 0:
        return _build_zero_evidence(
            stage=stage,
            pole_peak_date=pole_peak_date,
            consolidation_end_date=candidate_window.end_date,
            criteria_pass={
                "criterion_1": True,
                "criterion_2": c2_pass,
            },
        )
    pivot_price = float(consol_slice["Close"].iloc[-1])
    c6_pass, pivot_within_top_pct = _check_pivot_within_top(
        pivot_price, consolidation_top_price
    )

    criteria_pass = {
        "criterion_1": c1_pass,
        "criterion_2": c2_pass,
        "criterion_3": c3_pass,
        "criterion_4": c4_pass,
        "criterion_5": c5_pass,
        "criterion_6": c6_pass,
    }

    # Step 6: geometric_score.
    # Criterion #1 (Stage 2) is a hard gate; failure already short-circuits
    # above. Criterion #4 (consolidation_width) is the STRICT-bound hard
    # gate per spec section 10.6 LOCK + section 10.4 errata; failure
    # zeros the score (15.6% width REJECTS per section 10.4).
    if not c1_pass or not c4_pass:
        geometric_score = 0.0
    else:
        passed = sum(1 for v in criteria_pass.values() if v)
        geometric_score = passed / len(criteria_pass)

    return HighTightFlagEvidence(
        stage=stage,
        pole_start_date=pole_start_date,
        pole_start_price=float(pole_start_price),
        pole_peak_date=pole_peak_date,
        pole_peak_price=float(pole_peak_price),
        pole_pct=float(pole_pct),
        pole_duration_days=int(pole_duration_days),
        pole_avg_volume=float(pole_avg_volume),
        consolidation_start_date=consolidation_start_date,
        consolidation_end_date=consolidation_end_date,
        consolidation_top_price=float(consolidation_top_price),
        consolidation_bottom_price=float(consolidation_bottom_price),
        consolidation_pullback_pct=float(consolidation_pullback_pct),
        consolidation_width_pct=float(consolidation_width_pct),
        consolidation_duration_days=int(consolidation_duration_days),
        consolidation_avg_volume=float(consolidation_avg_volume),
        pivot_price=float(pivot_price),
        pivot_within_top_pct=float(pivot_within_top_pct),
        criteria_pass=criteria_pass,
        geometric_score=float(geometric_score),
    )
