"""Phase 13 T2.SB3 T-A.3.2 - VCP detector per spec section 5.2.

Volatility Contraction Pattern (Minervini-style): rule-based geometric
detector that ingests OHLCV daily bars + a CandidateWindow from the
T2.SB2 foundation primitive ``generate_candidate_windows`` and returns a
``VCPEvidence`` frozen dataclass capturing per-criterion verdicts +
the structural evidence (contractions, pivot, base anchors, volume
classification).

LOCKs (per dispatch brief Section 6 + plan G.4 LOCKs):
- L1: spec section 5.2 8 criteria + section 10.6 tolerance LOCK verbatim;
  do NOT paraphrase.
- L2: ZERO DB writes inside this module (``current_stage`` is the only
  DB call; SELECT-only).
- L5: ASCII-only output paths.
- L7: ``VCPEvidence`` + ``Contraction`` are frozen dataclasses with
  ``__post_init__`` runtime validation against explicit allowed-value
  frozensets (CLAUDE.md gotcha "Literal[...] type hints are NOT
  runtime-enforced").

Tolerance bands per spec section 10.6 LOCK (BINDING for writing-plans):
- criterion #2 (prior uptrend >= 30%): +/- 2 percentage points -> relaxed
  threshold 28%.
- criterion #3 (monotonic-decreasing depths): +/- 0.5 percentage points
  on the monotonicity inequality.
- criterion #4 (per-contraction depth bounds): NONE (strict ranges).
- criterion #5 (volume decline per pair): +/- 10% tolerance per pair.
- criterion #6 (3-12 weeks total base): NONE (strict range [21, 84]).
- criterion #7 (pivot within 1% of base_top): +/- 0.5% tolerance band.
- criterion #8 (breakout volume ratio >= 1.40): NONE (optional).
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
    volume_trend_through_swings,
)

# Detector version pin (per recon section 8). Bump on any algorithm change.
DETECTOR_VERSION: str = "vcp@v1.0.0"

# Spec section 5.2 + section 10.6 LOCK constants. All in percent units
# (e.g., 30.0 == 30%).
_PRIOR_UPTREND_BOUND_PCT: float = 30.0
_PRIOR_UPTREND_TOLERANCE_PCT: float = 2.0
_PRIOR_UPTREND_WEEKS_BOUND: int = 8
_MONOTONIC_TOLERANCE_PCT: float = 0.5
_T1_DEPTH_RANGE_PCT: tuple[float, float] = (10.0, 35.0)
_T2_DEPTH_RANGE_PCT: tuple[float, float] = (5.0, 20.0)
_T3_DEPTH_RANGE_PCT: tuple[float, float] = (3.0, 15.0)
_VOLUME_DECLINE_TOLERANCE_PCT: float = 10.0
_BASE_DURATION_DAYS_RANGE: tuple[int, int] = (21, 84)
_PIVOT_RATIO_RANGE: tuple[float, float] = (0.99, 1.01)
_PIVOT_TOLERANCE_FRAC: float = 0.005    # 0.5% band on the [0.99, 1.01] bound
_BREAKOUT_VOLUME_RATIO_BOUND: float = 1.40

# Allowed Literal values (L7 LOCK: validate in __post_init__).
_STAGE_VALUES: frozenset[str] = frozenset(
    {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
)
_VOLUME_CLASSIFICATION_VALUES: frozenset[str] = frozenset(
    {"declining", "non_declining"}
)
_CRITERION_KEYS: frozenset[str] = frozenset(
    {f"criterion_{i}" for i in range(1, 9)}
)


# ---------------------------------------------------------------------------
# Dataclasses (spec section 5.2 lines 549-577)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contraction:
    """One pullback within the VCP base sequence.

    Per spec section 5.2 lines 568-577. ``depth_pct`` is in percent units
    (e.g., 22.0 == 22% depth), matching the criterion #4 bound vocabulary
    and the section 10.1 worked example.
    """

    start_date: date
    end_date: date
    peak_price: float
    trough_price: float
    depth_pct: float
    duration_days: int
    avg_volume: float


@dataclass(frozen=True)
class VCPEvidence:
    """Structural evidence emitted by detect_vcp.

    Per spec section 5.2 lines 549-566 + section 10.1 worked example.
    Field order matches the spec sketch verbatim.

    LOCK L7: ``stage`` Literal + ``criteria_pass`` keys validated at
    ``__post_init__`` time against the frozensets at module level; this
    closes the CLAUDE.md gotcha "Literal[...] type hints are NOT
    runtime-enforced".
    """

    stage: Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]
    prior_uptrend_pct: float
    prior_uptrend_weeks: int
    base_start_date: date
    base_end_date: date
    contractions: tuple[Contraction, ...]
    pivot_price: float
    base_top_price: float
    pivot_within_top_pct: float
    volume_decline_passes: bool
    breakout_observed: bool
    breakout_volume_ratio: float | None
    criteria_pass: dict[str, bool]
    geometric_score: float

    def __post_init__(self) -> None:
        if self.stage not in _STAGE_VALUES:
            raise ValueError(
                f"VCPEvidence.stage must be one of {sorted(_STAGE_VALUES)}, "
                f"got {self.stage!r}"
            )
        if not (0.0 <= self.geometric_score <= 1.0):
            raise ValueError(
                f"VCPEvidence.geometric_score must be in [0.0, 1.0], "
                f"got {self.geometric_score}"
            )
        if set(self.criteria_pass.keys()) != _CRITERION_KEYS:
            raise ValueError(
                f"VCPEvidence.criteria_pass must have keys "
                f"{sorted(_CRITERION_KEYS)}, got "
                f"{sorted(self.criteria_pass.keys())}"
            )


# ---------------------------------------------------------------------------
# Detector
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
) -> VCPEvidence:
    """Construct an early-exit VCPEvidence with geometric_score == 0.0.

    Used when a hard gate fails (criterion #1 Stage 2 or criterion #6
    duration) or when the backward-slice cannot locate a base start.
    """
    full_flags = {f"criterion_{i}": False for i in range(1, 9)}
    full_flags.update(criteria_pass)
    return VCPEvidence(
        stage=stage,
        prior_uptrend_pct=0.0,
        prior_uptrend_weeks=0,
        base_start_date=base_start_date,
        base_end_date=base_end_date,
        contractions=tuple(),
        pivot_price=0.0,
        base_top_price=0.0,
        pivot_within_top_pct=0.0,
        volume_decline_passes=False,
        breakout_observed=False,
        breakout_volume_ratio=None,
        criteria_pass=full_flags,
        geometric_score=0.0,
    )


def _backward_slice_base_start(
    bars: pd.DataFrame, anchor_date: date
) -> date | None:
    """Locate the base START via backward-slicing from an anchor.

    For non-``zigzag_pivot`` candidate windows (``ma_crossover`` or
    ``high_low_breakout``), the ``anchor_date`` is a TRIGGER EVENT (e.g.,
    the MA50/MA150 crossover bar or the 50-bar high breakout bar) and
    NOT the base start. The detector walks BACK from the anchor to
    locate the most-recent prior swing-LOW; that swing-LOW is the
    inferred base start where the contraction sequence begins.

    Returns None if no suitable prior swing is found (the caller treats
    this as criterion #1 hard-gate failure per recon section 5).
    """
    # Slice bars up to and including the anchor.
    anchor_ts = pd.Timestamp(anchor_date)
    sub = bars.loc[bars.index <= anchor_ts]
    if len(sub) < 10:
        return None
    threshold = adaptive_initial_threshold_pct(sub)
    swings = extract_zigzag_swings(
        sub, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    # Walk backward through swings to find the most-recent DOWN-swing's
    # endpoint preceding the anchor. That's the inferred swing-LOW where
    # the base begins.
    for sw in reversed(swings):
        if sw.direction == "down":
            return sw.end_date
    return None


def _depth_pct(peak: float, trough: float) -> float:
    """Compute depth in percent units (e.g., 22.0 == 22% drawdown)."""
    if peak <= 0:
        return 0.0
    return float((peak - trough) / peak * 100.0)


def _classify_contractions(
    bars: pd.DataFrame, base_start: date, base_end: date
) -> list[Contraction]:
    """Build the contraction sequence from zigzag swings within the base.

    Each DOWN-swing within [base_start, base_end] becomes one
    Contraction. Volume is averaged across the swing's date range.
    """
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) < 4:
        return []
    threshold = adaptive_initial_threshold_pct(base_slice)
    swings = extract_zigzag_swings(
        base_slice,
        initial_threshold_pct=threshold,
        monotonic_narrow=True,    # VCP-specific narrowing per spec line 468
    )
    volume_segments = volume_trend_through_swings(base_slice, swings)
    contractions: list[Contraction] = []
    for sw, vs in zip(swings, volume_segments, strict=True):
        if sw.direction != "down":
            continue
        depth = _depth_pct(sw.start_price, sw.end_price)
        contractions.append(
            Contraction(
                start_date=sw.start_date,
                end_date=sw.end_date,
                peak_price=float(sw.start_price),
                trough_price=float(sw.end_price),
                depth_pct=depth,
                duration_days=int(sw.duration_days),
                avg_volume=float(vs.avg_volume),
            )
        )
    return contractions


def _check_monotonic_with_tolerance(
    contractions: list[Contraction],
) -> bool:
    """Per spec section 5.2 criterion #3 + tolerance LOCK section 10.6:
    each contraction's depth must be strictly less than the previous
    contraction's depth, with +/- 0.5pp tolerance (a next-depth that
    exceeds prior by <= 0.5pp still passes).
    """
    if len(contractions) < 2:
        return False
    for i in range(1, len(contractions)):
        prev = contractions[i - 1].depth_pct
        cur = contractions[i].depth_pct
        # Monotonic strict: cur < prev. Tolerance: cur < prev + 0.5pp.
        if cur >= prev + _MONOTONIC_TOLERANCE_PCT:
            return False
    return True


def _check_depth_bounds(contractions: list[Contraction]) -> bool:
    """Per spec section 5.2 criterion #4: T1 in [10%, 35%]; T2 in
    [5%, 20%]; T3 in [3%, 15%]. Tolerance NONE per section 10.6.
    Additional contractions (T4+) follow T3's bound as a defensive
    extension (spec is silent on T4+).
    """
    if not contractions:
        return False
    ranges = [_T1_DEPTH_RANGE_PCT, _T2_DEPTH_RANGE_PCT, _T3_DEPTH_RANGE_PCT]
    for i, c in enumerate(contractions):
        bound = ranges[i] if i < len(ranges) else _T3_DEPTH_RANGE_PCT
        lo, hi = bound
        if not (lo <= c.depth_pct <= hi):
            return False
    return True


def _check_volume_decline(contractions: list[Contraction]) -> bool:
    """Per spec section 5.2 criterion #5: volume MUST decline through the
    contraction sequence. Tolerance +/- 10% per pair: the next
    contraction's avg_volume may exceed the prior's by up to 10% before
    failing.
    """
    if len(contractions) < 2:
        return False
    for i in range(1, len(contractions)):
        prev = contractions[i - 1].avg_volume
        cur = contractions[i].avg_volume
        if prev <= 0:
            return False
        # Strict-decline with 10% tolerance: cur < prev * 1.10.
        if cur >= prev * (1.0 + _VOLUME_DECLINE_TOLERANCE_PCT / 100.0):
            return False
    return True


def _check_pivot_within_base_top(
    pivot_price: float, base_top_price: float
) -> tuple[bool, float]:
    """Per spec section 5.2 criterion #7 + section 10.6 LOCK: pivot must
    be within 1% of base_top (ratio in [0.99, 1.01]); tolerance 0.5%
    expands the band to [0.985, 1.015].
    """
    if base_top_price <= 0:
        return False, 0.0
    ratio = pivot_price / base_top_price
    lo = _PIVOT_RATIO_RANGE[0] - _PIVOT_TOLERANCE_FRAC
    hi = _PIVOT_RATIO_RANGE[1] + _PIVOT_TOLERANCE_FRAC
    within = lo <= ratio <= hi
    return within, float((ratio - 1.0) * 100.0)


def _compute_prior_uptrend(
    bars: pd.DataFrame, base_start: date
) -> tuple[float, int]:
    """Return (prior_uptrend_pct, prior_uptrend_weeks).

    Walks BACK from ``base_start`` to find the most-recent prior swing-low
    via zigzag on the bars preceding base_start. Computes the price gain
    from that low to base_start in percent and the duration in calendar
    weeks (rounded down).

    Returns ``(0.0, 0)`` if insufficient history.
    """
    pre = bars.loc[bars.index < pd.Timestamp(base_start)]
    if len(pre) < 10:
        return 0.0, 0
    threshold = adaptive_initial_threshold_pct(pre)
    swings = extract_zigzag_swings(
        pre, initial_threshold_pct=threshold, monotonic_narrow=False
    )
    # Find the latest UP-swing's start (the prior uptrend's swing-low).
    leg_start_idx: int | None = None
    for sw in reversed(swings):
        if sw.direction == "up":
            leg_start_idx = sw.start_date.toordinal()
            leg_start_price = sw.start_price
            break
    if leg_start_idx is None:
        # Fallback: use the earliest bar in pre as the trend start.
        leg_start_price = float(pre["Close"].iloc[0])
        leg_start_date = _ts_to_date(pre.index[0])
    else:
        leg_start_date = date.fromordinal(leg_start_idx)
    base_start_close = float(
        bars.loc[pd.Timestamp(base_start), "Close"]
    ) if pd.Timestamp(base_start) in bars.index else float(
        pre["Close"].iloc[-1]
    )
    if leg_start_price <= 0:
        return 0.0, 0
    pct = (base_start_close - leg_start_price) / leg_start_price * 100.0
    weeks = max(0, (base_start - leg_start_date).days // 7)
    return float(pct), int(weeks)


def _compute_breakout(
    bars: pd.DataFrame, base_end: date, base_top: float
) -> tuple[bool, float | None]:
    """Per spec section 5.2 criterion #8 (optional): if a bar AFTER
    base_end has close > base_top AND its volume is >= 1.40x the prior
    50-day average, report breakout_observed=True with the ratio.

    Returns (observed, ratio_or_None). Absent breakout -> (False, None).
    """
    post = bars.loc[bars.index > pd.Timestamp(base_end)]
    if len(post) == 0:
        return False, None
    for i in range(len(post)):
        bar_close = float(post["Close"].iloc[i])
        if bar_close <= base_top:
            continue
        breakout_ts = post.index[i]
        # Compute volume ratio vs the prior 50 bars (strictly before).
        prior = bars.loc[bars.index < breakout_ts, "Volume"]
        if len(prior) == 0:
            continue
        baseline = prior.iloc[-50:]
        baseline_mean = float(baseline.mean())
        if baseline_mean <= 0:
            continue
        ratio = float(post["Volume"].iloc[i]) / baseline_mean
        if ratio >= _BREAKOUT_VOLUME_RATIO_BOUND:
            return True, ratio
    return False, None


def detect_vcp(
    bars: pd.DataFrame,
    candidate_window: CandidateWindow,
    *,
    conn: sqlite3.Connection | None = None,
    ticker: str | None = None,
    asof_date: date | None = None,
) -> VCPEvidence:
    """Detect a VCP pattern on ``bars`` over ``candidate_window``.

    Per spec section 5.2 + section 10.1 worked example + section 10.6
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
          base start (per recon section 5).
    conn : sqlite3.Connection | None
        Read-only connection for ``current_stage(conn, ticker, asof)``.
        If None, criterion #1 is treated as failed (Stage 2 unknown).
    ticker : str | None
        Required when ``conn`` is provided; ignored otherwise.
    asof_date : date | None
        Required when ``conn`` is provided; ignored otherwise.

    Returns
    -------
    VCPEvidence
        Frozen dataclass with per-criterion pass flags + geometric
        score + structural evidence (contractions, pivot, base anchors,
        volume classification).
    """
    sanitize_bars(bars)
    if len(bars) < 10:
        # Not enough history to evaluate anything; return zero evidence
        # anchored on the candidate window for evidence-trail purposes.
        return _build_zero_evidence(
            stage="undefined",
            base_start_date=candidate_window.start_date,
            base_end_date=candidate_window.end_date,
            criteria_pass={f"criterion_{i}": False for i in range(1, 9)},
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
                criteria_pass={f"criterion_{i}": False for i in range(1, 9)},
            )
        base_start = sliced
    base_end = candidate_window.end_date

    # Step 2: criterion #1 — Stage 2 hard gate.
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

    # Step 3: prior uptrend (criterion #2) — section 10.6 LOCK: tolerance
    # +/- 2pp on the 30% bound; relaxed threshold 28%.
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

    # Step 4: contractions + criteria #3, #4, #5.
    contractions = _classify_contractions(bars, base_start, base_end)
    c3_pass = (
        len(contractions) >= 2
        and _check_monotonic_with_tolerance(contractions)
    )
    c4_pass = (
        len(contractions) >= 2
        and _check_depth_bounds(contractions)
    )
    c5_pass = (
        len(contractions) >= 2
        and _check_volume_decline(contractions)
    )

    # Step 5: criterion #6 — base duration hard gate; range [21, 84].
    base_days = (base_end - base_start).days
    c6_pass = (
        _BASE_DURATION_DAYS_RANGE[0]
        <= base_days
        <= _BASE_DURATION_DAYS_RANGE[1]
    )

    # Step 6: pivot vs base_top (criterion #7).
    base_slice = bars.loc[
        (bars.index >= pd.Timestamp(base_start))
        & (bars.index <= pd.Timestamp(base_end))
    ]
    if len(base_slice) == 0:
        return _build_zero_evidence(
            stage=stage,
            base_start_date=base_start,
            base_end_date=base_end,
            criteria_pass={"criterion_1": True, "criterion_6": c6_pass},
        )
    # Base top semantically = most-recent contraction's peak (per spec
    # section 10.1 worked example: contractions peak at 5.50 / 5.45 /
    # 5.35; the cited base_top of 5.34 is the LAST contraction's peak).
    # Falls back to base-slice global max when no contractions are
    # identified.
    if contractions:
        base_top_price = float(contractions[-1].peak_price)
    else:
        base_top_price = float(base_slice["High"].max())
    pivot_price = float(base_slice["Close"].iloc[-1])
    c7_pass, pivot_within_top_pct = _check_pivot_within_base_top(
        pivot_price, base_top_price
    )

    # Step 7: criterion #8 — optional breakout volume ratio.
    breakout_observed, breakout_ratio = _compute_breakout(
        bars, base_end, base_top_price
    )

    criteria_pass = {
        "criterion_1": c1_pass,
        "criterion_2": c2_pass,
        "criterion_3": c3_pass,
        "criterion_4": c4_pass,
        "criterion_5": c5_pass,
        "criterion_6": c6_pass,
        "criterion_7": c7_pass,
        "criterion_8": breakout_observed,
    }

    # Step 8: geometric_score. Hard gates: #1 + #6. Failure of either
    # zeros the score per spec section 5.2 line 547 LOCK. Otherwise
    # average over the 7 non-optional criteria (#1..#7); #8 is optional
    # and does not reduce the score when absent.
    if not c1_pass or not c6_pass:
        geometric_score = 0.0
    else:
        non_optional_keys = [f"criterion_{i}" for i in range(1, 8)]
        passed = sum(1 for k in non_optional_keys if criteria_pass[k])
        geometric_score = passed / len(non_optional_keys)

    return VCPEvidence(
        stage=stage,
        prior_uptrend_pct=float(prior_uptrend_pct),
        prior_uptrend_weeks=int(prior_uptrend_weeks),
        base_start_date=base_start,
        base_end_date=base_end,
        contractions=tuple(contractions),
        pivot_price=pivot_price,
        base_top_price=base_top_price,
        pivot_within_top_pct=float(pivot_within_top_pct),
        volume_decline_passes=c5_pass,
        breakout_observed=breakout_observed,
        breakout_volume_ratio=breakout_ratio,
        criteria_pass=criteria_pass,
        geometric_score=float(geometric_score),
    )
