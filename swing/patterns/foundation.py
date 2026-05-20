"""Phase 13 T2.SB2 - foundation pattern primitives (spec section 5.1).

Pure-logic primitives consumed by T2.SB3 (VCP + flat base + cup-with-handle)
and T2.SB4 (high-tight-flag + double-bottom-W) detectors. ZERO DB writes
in this module other than the explicitly read-only ``current_stage``
wrapper at section 5.1.5 which queries shipped Phase 4 surfaces.

LOCKs (per dispatch brief section 6):
- L1: pure functions only; no I/O, no globals, no logging from inside
  primitive functions.
- L2: ZERO DB writes (current_stage may READ).
- L3: frozen dataclasses for Swing + CandidateWindow + VolumeSegment.
- L4: Literal type hints are not runtime-enforced; data-integrity-path
  fields validate in ``__post_init__``.
- L5: ASCII-only output paths; no non-ASCII glyphs in strings/docstrings.

T-A.2.1 ships smoothing primitives. Later tasks extend in-place.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np
import pandas as pd

# Allowed values for Literal fields (LOCK L4: Literal not runtime-enforced;
# validate explicitly in __post_init__ per CLAUDE.md gotcha).
_SWING_DIRECTIONS: frozenset[str] = frozenset({"up", "down"})
_CANDIDATE_TIMEFRAMES: frozenset[str] = frozenset({"daily", "weekly"})
_ANCHOR_SEARCH_METHODS: frozenset[str] = frozenset(
    {"zigzag_pivot", "ma_crossover", "high_low_breakout"}
)

# Floor for ``monotonic_narrow`` threshold decay (in fraction-as-percentage
# units; 0.5 means 0.5%). Tighter would have the zigzag detect every bar's
# noise as a swing; looser would over-truncate VCP-style sub-1% final
# contractions. See Fix #4 (code-quality follow-up T-A.2.1-T-A.2.5).
_MONOTONIC_NARROW_MIN_THRESHOLD_PCT: float = 0.5

# ============================================================================
# Section 5.1.1 - Smoothing primitives (T-A.2.1)
# ============================================================================


def smooth_ema(prices: np.ndarray, window: int) -> np.ndarray:
    """Exponential Moving Average with smoothing factor alpha = 2/(window+1).

    Implements the standard EMA recursion ``y[i] = alpha*x[i] + (1-alpha)*y[i-1]``
    seeded with ``y[0] = x[0]``. Output length matches input length.

    Matches ``pandas.Series.ewm(span=window, adjust=False).mean()`` semantics
    element-wise. Window must be >= 1.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    arr = np.asarray(prices, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"prices must be 1-D, got shape {arr.shape}")
    if arr.shape[0] > 0 and not np.all(np.isfinite(arr)):
        raise ValueError(
            "smooth_ema: prices contain NaN; caller must drop or impute "
            "before invoking"
        )
    n = arr.shape[0]
    if n == 0:
        return arr.copy()
    alpha = 2.0 / (window + 1)
    out = np.empty(n, dtype=float)
    out[0] = arr[0]
    for i in range(1, n):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def smooth_kernel_regression(prices: np.ndarray, bandwidth: float) -> np.ndarray:
    """Nadaraya-Watson kernel regression with Gaussian kernel.

    For each bar index ``i``, output is the kernel-weighted mean of all
    input prices, with weight ``K((i-j)/bandwidth)`` where ``K`` is the
    standard Gaussian. Bandwidth is in bar-index units.

    Spec section 5.1.1 LOCK: "historical only, no recent-bar". This
    centered kernel introduces no lag at interior points but blends
    future bars into the smoothed estimate; callers MUST NOT consume the
    output of this function for recent-bar trading decisions. Reserved
    for stable historical-exemplar curation and template-matching
    reference computation.
    """
    if bandwidth <= 0:
        raise ValueError(f"bandwidth must be > 0, got {bandwidth}")
    arr = np.asarray(prices, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"prices must be 1-D, got shape {arr.shape}")
    if arr.shape[0] > 0 and not np.all(np.isfinite(arr)):
        raise ValueError(
            "smooth_kernel_regression: prices contain NaN; caller must drop "
            "or impute before invoking"
        )
    n = arr.shape[0]
    if n == 0:
        return arr.copy()
    # Fix #2 (code-quality follow-up): vectorize the prior O(n^2) Python loop.
    # The (n, n) pairwise-difference matrix is the canonical NumPy-vectorized
    # Nadaraya-Watson Gaussian-kernel implementation; identical algorithm,
    # no Python-level iteration. Memory cost is O(n^2) floats which is
    # acceptable at V1 typical n <= a few thousand bars.
    idx = np.arange(n, dtype=float)
    diffs = (idx[:, None] - idx[None, :]) / bandwidth
    weights = np.exp(-0.5 * diffs * diffs)
    return (weights @ arr) / weights.sum(axis=1)


# ============================================================================
# Section 5.1.2 - Extrema extraction via zigzag with adaptive threshold (T-A.2.2)
# ============================================================================


@dataclass(frozen=True)
class Swing:
    """One leg of a zigzag swing decomposition.

    Per spec section 5.1.2 lines 476-485: frozen dataclass with 7 fields;
    ``depth_pct`` is unsigned (``abs((end-start)/start)``).

    LOCK L4: ``direction`` Literal is not runtime-enforced by Python type
    hints; ``__post_init__`` validates against ``_SWING_DIRECTIONS``.
    """

    start_date: date
    end_date: date
    start_price: float
    end_price: float
    direction: Literal["up", "down"]
    depth_pct: float
    duration_days: int

    def __post_init__(self) -> None:
        if self.direction not in _SWING_DIRECTIONS:
            raise ValueError(
                f"Swing.direction must be one of {sorted(_SWING_DIRECTIONS)}, "
                f"got {self.direction!r}"
            )


def adaptive_initial_threshold_pct(bars: pd.DataFrame) -> float:
    """Per spec section 5.1.2: initial zigzag threshold heuristic
    ``max(3.0, ATR_5d_pct * 1.5)``.

    ATR_5d_pct is the 5-day mean of ``(High - Low) / Close`` expressed as
    a percentage. With fewer than 5 bars the floor (3.0) is returned.

    Returned value is in fraction-as-percentage units (e.g., 3.0 means 3%),
    matching the ``initial_threshold_pct`` parameter of
    ``extract_zigzag_swings``.
    """
    if bars is None or len(bars) == 0:
        return 3.0
    if len(bars) < 5:
        return 3.0
    # Codex R1 Minor #3: apply the same NaN-rejection policy as the other
    # foundation primitives. The 5-bar tail (the only segment read for the
    # ATR computation) MUST be NaN-free; defer drop/impute to the caller
    # so silent NaN propagation does not yield a degraded ATR estimate.
    tail = bars.iloc[-5:]
    for col in ("Close", "High", "Low"):
        arr = tail[col].astype(float).to_numpy()
        if not np.all(np.isfinite(arr)):
            raise ValueError(
                f"adaptive_initial_threshold_pct: bars[{col!r}] contains "
                f"NaN; caller must drop or impute before invoking"
            )
    closes = tail["Close"].astype(float).to_numpy()
    highs = tail["High"].astype(float).to_numpy()
    lows = tail["Low"].astype(float).to_numpy()
    if np.any(closes <= 0):
        return 3.0
    pct_ranges = (highs - lows) / closes * 100.0
    atr_5d_pct = float(np.mean(pct_ranges))
    return max(3.0, atr_5d_pct * 1.5)


def extract_zigzag_swings(
    bars: pd.DataFrame,
    initial_threshold_pct: float,
    monotonic_narrow: bool = False,
) -> list[Swing]:
    """Zigzag extrema extraction with adaptive percentage threshold.

    Per spec section 5.1.2 LOCK lines 462-485. The algorithm walks
    ``bars['Close']`` forward, tracking a tentative extremum candidate; a
    swing is closed (and a new one opened in the reverse direction) when
    the close moves away from the running extremum by at least the
    effective threshold percentage.

    Parameters
    ----------
    bars : pd.DataFrame
        Daily bars indexed by ``pd.Timestamp`` with at least a ``Close``
        column. The algorithm operates on ``Close`` for V1 (spec section
        5.1.2 silent on Close-vs-High/Low; Close is the canonical choice).
    initial_threshold_pct : float
        Fraction-as-percentage (e.g., 3.0 means 3%, NOT 0.03). Per spec
        line 467: ``max(3.0, ATR_5d_pct * 1.5)`` for VCP-style patterns;
        helper ``adaptive_initial_threshold_pct`` computes this.
    monotonic_narrow : bool, default False
        Per spec line 468: after each swing closes, the next swing's
        effective threshold is narrowed by ``0.75 *`` (VCP-specific). When
        False, the threshold stays constant.

    Returns
    -------
    list[Swing]
        Ordered list of closed swings. The currently-developing swing
        (not yet confirmed by a counter-move beyond threshold) is NOT
        emitted, to preserve historical-only semantics.
    """
    if initial_threshold_pct <= 0:
        raise ValueError(
            f"initial_threshold_pct must be > 0, got {initial_threshold_pct}"
        )
    if bars is None or len(bars) < 2:
        return []
    # Fix #8 (code-quality follow-up): require monotonic-increasing index.
    if not bars.index.is_monotonic_increasing:
        raise ValueError(
            "extract_zigzag_swings: bars.index must be monotonic-increasing "
            "(sorted); caller must sort before invoking"
        )
    # Fix #1 (code-quality follow-up): raise on NaN in Close; detectors
    # downstream consume real archives that may have holiday-adjacent gaps,
    # silent propagation would yield degraded zigzag output.
    close_series = bars["Close"].astype(float)
    if not np.all(np.isfinite(close_series.to_numpy())):
        raise ValueError(
            "extract_zigzag_swings: bars['Close'] contains NaN; caller "
            "must drop or impute before invoking"
        )
    closes = close_series.to_numpy()
    timestamps = bars.index
    n = len(closes)

    swings: list[Swing] = []
    threshold_pct = float(initial_threshold_pct)

    # Anchor: first bar starts the running extremum.
    pivot_idx = 0
    pivot_price = closes[0]
    # current_direction is None until we know which way the first swing
    # goes; once a swing is opened, direction is fixed for that swing.
    current_direction: Literal["up", "down"] | None = None
    # Track the high-water (or low-water) extremum of the current swing.
    extremum_idx = 0
    extremum_price = closes[0]

    def _threshold_fraction() -> float:
        return threshold_pct / 100.0

    def _emit_swing(
        s_idx: int,
        e_idx: int,
        direction: Literal["up", "down"],
    ) -> None:
        s_price = float(closes[s_idx])
        e_price = float(closes[e_idx])
        depth = 0.0 if s_price == 0 else abs((e_price - s_price) / s_price)
        s_ts = timestamps[s_idx]
        e_ts = timestamps[e_idx]
        s_date = s_ts.date() if hasattr(s_ts, "date") else s_ts
        e_date = e_ts.date() if hasattr(e_ts, "date") else e_ts
        duration_days = (e_date - s_date).days
        swings.append(
            Swing(
                start_date=s_date,
                end_date=e_date,
                start_price=s_price,
                end_price=e_price,
                direction=direction,
                depth_pct=depth,
                duration_days=duration_days,
            )
        )

    for i in range(1, n):
        price = closes[i]
        if current_direction is None:
            # Still determining first swing direction; pivot stays at index 0.
            move_from_pivot = (price - pivot_price) / pivot_price if pivot_price != 0 else 0.0
            if move_from_pivot >= _threshold_fraction():
                current_direction = "up"
                extremum_idx = i
                extremum_price = price
            elif move_from_pivot <= -_threshold_fraction():
                current_direction = "down"
                extremum_idx = i
                extremum_price = price
            # else: still inside threshold; keep watching.
            continue

        # In an active swing: update extremum on continuation, close swing
        # on a counter-move >= threshold from the extremum.
        if current_direction == "up":
            if price > extremum_price:
                extremum_idx = i
                extremum_price = price
                continue
            # Potential reversal: check counter-move from extremum.
            counter = (
                0.0
                if extremum_price == 0
                else (extremum_price - price) / extremum_price
            )
            if counter >= _threshold_fraction():
                # Close the up-swing from pivot to extremum.
                _emit_swing(pivot_idx, extremum_idx, "up")
                if monotonic_narrow:
                    # Fix #4 (code-quality follow-up): floor the decay so the
                    # threshold cannot approach zero on long alternating
                    # synthetic-noise inputs (would yield unbounded swings).
                    threshold_pct = max(
                        threshold_pct * 0.75,
                        _MONOTONIC_NARROW_MIN_THRESHOLD_PCT,
                    )
                # Start a new down-swing from extremum.
                pivot_idx = extremum_idx
                pivot_price = extremum_price
                current_direction = "down"
                extremum_idx = i
                extremum_price = price
        else:  # current_direction == "down"
            if price < extremum_price:
                extremum_idx = i
                extremum_price = price
                continue
            counter = (
                0.0
                if extremum_price == 0
                else (price - extremum_price) / extremum_price
            )
            if counter >= _threshold_fraction():
                _emit_swing(pivot_idx, extremum_idx, "down")
                if monotonic_narrow:
                    # Fix #4 (code-quality follow-up): floor the decay so the
                    # threshold cannot approach zero on long alternating
                    # synthetic-noise inputs (would yield unbounded swings).
                    threshold_pct = max(
                        threshold_pct * 0.75,
                        _MONOTONIC_NARROW_MIN_THRESHOLD_PCT,
                    )
                pivot_idx = extremum_idx
                pivot_price = extremum_price
                current_direction = "up"
                extremum_idx = i
                extremum_price = price

    return swings


# ============================================================================
# Section 5.1.3 - Variable-window candidate generator (T-A.2.3)
# ============================================================================


@dataclass(frozen=True)
class CandidateWindow:
    """One candidate base-window for downstream pattern detectors.

    Per spec section 5.1.3 lines 496-504: frozen dataclass with 6 fields.

    LOCK L4: ``timeframe`` Literal is not runtime-enforced; ``__post_init__``
    validates against ``_CANDIDATE_TIMEFRAMES``.

    Field semantics (V1, per Codex R1 Major #3):

    - ``start_date`` / ``end_date`` — window left/right edges (inclusive).
    - ``anchor_date`` — the anchor event date; *per-mode-dependent semantic*.
      See ``generate_candidate_windows`` docstring for the full per-mode
      table. Briefly: ``zigzag_pivot`` mode's ``anchor_date`` is the
      inferred base START (matching the spec section 5.1.3 line 502
      abstraction); ``ma_crossover`` and ``high_low_breakout`` modes'
      ``anchor_date`` is the TRIGGER EVENT bar (the start of a Stage-2
      uptrend or the breakout confirmation bar respectively, NOT a base
      start). Downstream T2.SB3+ detectors consuming non-zigzag windows
      MUST perform mode-aware backward-slicing from ``anchor_date`` to
      reconstruct base context.
    - ``anchor_reason`` — evidence-trail string. Format:
      ``'<mode>:<descriptor>'``.
    """

    ticker: str
    timeframe: Literal["daily", "weekly"]
    start_date: date
    end_date: date
    anchor_date: date
    anchor_reason: str

    def __post_init__(self) -> None:
        if self.timeframe not in _CANDIDATE_TIMEFRAMES:
            raise ValueError(
                f"CandidateWindow.timeframe must be one of "
                f"{sorted(_CANDIDATE_TIMEFRAMES)}, got {self.timeframe!r}"
            )


def _ts_to_date(ts: Any) -> date:
    """Coerce a pandas Timestamp (or stdlib ``date``) to a stdlib ``date``.

    Fix #6 (code-quality follow-up): previously silently returned ``ts``
    unchanged via ``# type: ignore`` when no ``.date()`` attribute. Now
    raises ``TypeError`` so non-Timestamp/date inputs surface immediately
    rather than poisoning downstream date arithmetic.
    """
    if hasattr(ts, "date") and callable(ts.date):
        return ts.date()
    if isinstance(ts, date):
        return ts
    raise TypeError(
        f"_ts_to_date: expected pd.Timestamp or datetime.date, "
        f"got {type(ts).__name__}"
    )


def generate_candidate_windows(
    bars: pd.DataFrame,
    anchor_search_method: Literal[
        "zigzag_pivot", "ma_crossover", "high_low_breakout"
    ],
    *,
    ticker: str,
    timeframe: Literal["daily", "weekly"] = "daily",
) -> list[CandidateWindow]:
    """Generate candidate base-window anchor points for pattern detectors.

    Per spec section 5.1.3 LOCK lines 487-508. Three anchor modes:

    - ``zigzag_pivot``: invokes ``extract_zigzag_swings`` with
      ``initial_threshold_pct=3.0`` and emits one window per down-swing
      endpoint (anchor_date = the down-swing's end_date).
    - ``ma_crossover``: detects MA50 crossing ABOVE MA150 (today's
      MA50 > MA150 AND yesterday's MA50 <= MA150); emits one window per
      crossover bar.
    - ``high_low_breakout``: detects close exceeding the prior 50-bar
      High maximum; emits one window per breach bar.

    Each emitted window spans from ``anchor_date`` to the last bar in
    ``bars``. V1 LOCK: multi-anchor mode (combining methods in one call)
    is V2-deferred per plan section G.3 T-A.2.3.

    Signature widening: the spec sketch omits ``ticker`` + ``timeframe``
    parameters but the dataclass requires them; this is a faithful
    bridge per spec section D.2.

    Per-mode ``anchor_date`` semantic (V1, per Codex R1 Major #3):

    - ``zigzag_pivot``: ``anchor_date`` = down-swing endpoint = inferred
      base START. ``start_date == anchor_date``; the forward window runs
      from the candidate base start to the last available bar. Matches
      the spec section 5.1.3 line 502 "candidate base start" abstraction.
    - ``ma_crossover``: ``anchor_date`` = MA50/MA150 crossover bar =
      TRIGGER EVENT (the start of a Stage 2 uptrend, NOT a base start).
      ``start_date == anchor_date``; the forward window runs from the
      crossover bar to the last available bar.
    - ``high_low_breakout``: ``anchor_date`` = breakout confirmation bar
      = TRIGGER EVENT (the END of an upstream base, NOT a base start).
      ``start_date == anchor_date``; the forward window runs from the
      breakout bar to the last available bar.

    V1 LOCK: ``anchor_date`` semantic VARIES across modes. For
    ``ma_crossover`` and ``high_low_breakout``, ``anchor_date`` represents
    the TRIGGER EVENT, not the spec section 5.1.3 line 502 "candidate
    base start" abstraction. Downstream T2.SB3 detectors (VCP / flat_base
    / cup_with_handle) consuming ``ma_crossover`` or ``high_low_breakout``
    windows MUST perform their own backward-slicing from ``anchor_date``
    to assemble the base context (e.g., subtract a 60-day lookback or
    run ``extract_zigzag_swings`` backward from ``anchor_date``).
    ``zigzag_pivot`` mode correctly matches the spec abstraction without
    backward-slicing.

    V2 candidate (banked): align all three modes by emitting separate
    ``start_date`` (inferred base start) and ``anchor_date`` (trigger
    event) fields with per-mode backward-slicing policies; would let
    detectors consume any mode's output without mode-specific logic.
    """
    if anchor_search_method not in _ANCHOR_SEARCH_METHODS:
        raise ValueError(
            f"anchor_search_method must be one of "
            f"{sorted(_ANCHOR_SEARCH_METHODS)}, got {anchor_search_method!r}"
        )
    if timeframe not in _CANDIDATE_TIMEFRAMES:
        raise ValueError(
            f"timeframe must be one of {sorted(_CANDIDATE_TIMEFRAMES)}, "
            f"got {timeframe!r}"
        )
    if bars is None or len(bars) == 0:
        return []
    # Fix #8 (code-quality follow-up): require monotonic-increasing index.
    if not bars.index.is_monotonic_increasing:
        raise ValueError(
            "generate_candidate_windows: bars.index must be monotonic-"
            "increasing (sorted); caller must sort before invoking"
        )
    # Fix #1 (code-quality follow-up): raise on NaN in columns each mode
    # reads. Close is read by zigzag_pivot + ma_crossover; High is read by
    # high_low_breakout. Check both to keep the entry-point simple.
    close_arr = bars["Close"].astype(float).to_numpy()
    if not np.all(np.isfinite(close_arr)):
        raise ValueError(
            "generate_candidate_windows: bars['Close'] contains NaN; caller "
            "must drop or impute before invoking"
        )
    if anchor_search_method == "high_low_breakout":
        high_arr = bars["High"].astype(float).to_numpy()
        if not np.all(np.isfinite(high_arr)):
            raise ValueError(
                "generate_candidate_windows: bars['High'] contains NaN; "
                "caller must drop or impute before invoking"
            )

    last_bar_date = _ts_to_date(bars.index[-1])
    windows: list[CandidateWindow] = []

    if anchor_search_method == "zigzag_pivot":
        swings = extract_zigzag_swings(
            bars, initial_threshold_pct=3.0, monotonic_narrow=False
        )
        for i, sw in enumerate(swings):
            if sw.direction != "down":
                continue
            if sw.depth_pct < 0.03:
                # Re-uses 3% extract threshold per docstring; defense-in-depth.
                continue
            windows.append(
                CandidateWindow(
                    ticker=ticker,
                    timeframe=timeframe,
                    start_date=sw.end_date,
                    end_date=last_bar_date,
                    anchor_date=sw.end_date,
                    anchor_reason=f"zigzag_pivot:swing_{i}_down",
                )
            )
        return windows

    if anchor_search_method == "ma_crossover":
        closes = bars["Close"].astype(float)
        ma50 = closes.rolling(50).mean()
        ma150 = closes.rolling(150).mean()
        for i in range(1, len(bars)):
            today_50 = ma50.iloc[i]
            today_150 = ma150.iloc[i]
            prev_50 = ma50.iloc[i - 1]
            prev_150 = ma150.iloc[i - 1]
            # Skip until both MAs are defined on today and yesterday.
            if (
                pd.isna(today_50)
                or pd.isna(today_150)
                or pd.isna(prev_50)
                or pd.isna(prev_150)
            ):
                continue
            if today_50 > today_150 and prev_50 <= prev_150:
                anchor_dt = _ts_to_date(bars.index[i])
                windows.append(
                    CandidateWindow(
                        ticker=ticker,
                        timeframe=timeframe,
                        start_date=anchor_dt,
                        end_date=last_bar_date,
                        anchor_date=anchor_dt,
                        anchor_reason=(
                            f"ma_crossover:50_above_150_at_"
                            f"{anchor_dt.isoformat()}"
                        ),
                    )
                )
        return windows

    # anchor_search_method == "high_low_breakout"
    highs = bars["High"].astype(float).to_numpy()
    closes_arr = bars["Close"].astype(float).to_numpy()
    n = len(bars)
    for i in range(50, n):
        prior_high_max = float(np.max(highs[i - 50 : i]))
        if closes_arr[i] > prior_high_max:
            anchor_dt = _ts_to_date(bars.index[i])
            windows.append(
                CandidateWindow(
                    ticker=ticker,
                    timeframe=timeframe,
                    start_date=anchor_dt,
                    end_date=last_bar_date,
                    anchor_date=anchor_dt,
                    anchor_reason=(
                        f"high_low_breakout:50d_high_at_{anchor_dt.isoformat()}"
                    ),
                )
            )
    return windows


# ============================================================================
# Section 5.1.4 - Volume profile primitives (T-A.2.4)
# ============================================================================


@dataclass(frozen=True)
class VolumeSegment:
    """Volume profile of one swing window, for downstream pattern detectors.

    Spec section 5.1.4 does not explicitly define this dataclass shape
    (the brief notes ``avg_volume`` as the minimum-required field per
    section line 542 reference). The shape below mirrors the
    ``Contraction`` dataclass at spec lines 568-577: start/end dates,
    avg_volume, plus a ``swing_index`` evidence-trail field for the
    consumer to correlate back to the input swings list.
    """

    start_date: date
    end_date: date
    avg_volume: float
    swing_index: int


def volume_trend_through_swings(
    bars: pd.DataFrame,
    swings: list[Swing],
) -> list[VolumeSegment]:
    """For each swing, compute the mean Volume across the swing's
    inclusive date range and return one VolumeSegment per swing.

    Per spec section 5.1.4: ``bars.loc[swing.start_date:swing.end_date,
    'Volume'].mean()`` (pandas .loc on Timestamp index is inclusive of
    both endpoints).
    """
    out: list[VolumeSegment] = []
    if bars is None or len(bars) == 0:
        return out
    # Fix #8 (code-quality follow-up): require monotonic-increasing index.
    if not bars.index.is_monotonic_increasing:
        raise ValueError(
            "volume_trend_through_swings: bars.index must be monotonic-"
            "increasing (sorted); caller must sort before invoking"
        )
    # Fix #1 (code-quality follow-up): raise on NaN in Volume; downstream
    # detectors compute volume ratios + averages so silent propagation would
    # produce NaN-poisoned outputs.
    volume_arr = bars["Volume"].astype(float).to_numpy()
    if not np.all(np.isfinite(volume_arr)):
        raise ValueError(
            "volume_trend_through_swings: bars['Volume'] contains NaN; "
            "caller must drop or impute before invoking"
        )
    # Fix #8(b) (code-quality follow-up): normalize index timestamps to
    # date-level so swing date-range comparisons work for intraday-timestamped
    # bars (e.g., ``2025-01-15 16:00:00``). Without normalization, the
    # ``.loc[date:date]`` inclusive slice misses bars whose timestamp carries
    # a time-of-day component.
    index_dates = bars.index.normalize()
    for i, sw in enumerate(swings):
        sd = pd.Timestamp(sw.start_date).normalize()
        ed = pd.Timestamp(sw.end_date).normalize()
        mask = (index_dates >= sd) & (index_dates <= ed)
        sub = bars.loc[mask, "Volume"]
        avg = float(sub.mean()) if len(sub) > 0 else 0.0
        out.append(
            VolumeSegment(
                start_date=sw.start_date,
                end_date=sw.end_date,
                avg_volume=avg,
                swing_index=i,
            )
        )
    return out


def breakout_volume_ratio(
    bars: pd.DataFrame,
    breakout_date: date,
    baseline_days: int = 50,
) -> float:
    """Ratio of ``breakout_date`` volume vs the prior ``baseline_days``
    mean volume.

    Per spec section 5.1.4: the baseline window is the ``baseline_days``
    bars STRICTLY BEFORE ``breakout_date`` (NOT including breakout_date
    itself). Returns ``volume[breakout_date] / mean(baseline)``.

    EDGE CASE (dispatch brief section 4.1 #6): if the baseline mean is
    zero (extremely thin trading), return ``0.0``; do NOT raise
    ZeroDivisionError; do NOT return NaN.
    """
    if bars is None or len(bars) == 0:
        return 0.0
    if baseline_days < 1:
        raise ValueError(f"baseline_days must be >= 1, got {baseline_days}")
    # Fix #8 (code-quality follow-up): require monotonic-increasing index.
    if not bars.index.is_monotonic_increasing:
        raise ValueError(
            "breakout_volume_ratio: bars.index must be monotonic-increasing "
            "(sorted); caller must sort before invoking"
        )
    breakout_ts = pd.Timestamp(breakout_date)
    # Volume on the breakout bar (raises KeyError if missing - by design).
    if breakout_ts not in bars.index:
        raise KeyError(f"breakout_date {breakout_date} not in bars index")
    # Fix #1 (code-quality follow-up): raise on NaN in Volume baseline window
    # OR breakout-day Volume; silent propagation would yield NaN ratios.
    breakout_vol_raw = bars.loc[breakout_ts, "Volume"]
    if not np.isfinite(float(breakout_vol_raw)):
        raise ValueError(
            "breakout_volume_ratio: bars['Volume'] contains NaN at "
            "breakout_date; caller must drop or impute before invoking"
        )
    breakout_vol = float(breakout_vol_raw)
    # Baseline = the baseline_days bars STRICTLY BEFORE the breakout.
    prior = bars.loc[bars.index < breakout_ts, "Volume"]
    if len(prior) == 0:
        return 0.0
    baseline_window = prior.iloc[-baseline_days:]
    if not np.all(np.isfinite(baseline_window.astype(float).to_numpy())):
        raise ValueError(
            "breakout_volume_ratio: bars['Volume'] contains NaN in baseline "
            "window; caller must drop or impute before invoking"
        )
    baseline_mean = float(baseline_window.mean())
    if baseline_mean == 0.0:
        return 0.0
    return breakout_vol / baseline_mean


# ============================================================================
# Section 5.1.5 - Trend template state surface (T-A.2.5)
# ============================================================================


# Number of Minervini Trend Template (TT1..TT8) checks required for Stage 2.
_TREND_TEMPLATE_REQUIRED_PASS_COUNT = 8

_StageLabel = Literal["stage_1", "stage_2", "stage_3", "stage_4", "undefined"]


def current_stage(
    conn: sqlite3.Connection,
    ticker: str,
    asof_date: date,
) -> _StageLabel:
    """Thin read-only wrapper over the shipped Phase 4 evaluation surface.

    Per spec section 5.1.5 LOCK lines 521-528. V1 wrapper semantics:
    Stage 2 = all 8 trend_template (TT1..TT8) criteria checks pass for
    the most-recent ``(ticker, action_session_date <= asof_date)``
    candidate row. Otherwise -> ``'undefined'``. Full Weinstein 4-stage
    labeling (Stage 1 / 3 / 4 differentiation) is V2-deferred per
    spec line 523 ("thin wrapper").

    LOCK L2 ZERO DB writes is preserved: this function executes only
    SELECT statements; no INSERT / UPDATE / DELETE / SAVEPOINT.
    """
    asof_iso = asof_date.isoformat()
    row = conn.execute(
        """
        SELECT c.id
        FROM candidates c
        JOIN evaluation_runs er ON c.evaluation_run_id = er.id
        WHERE c.ticker = ?
          AND er.action_session_date <= ?
        ORDER BY er.action_session_date DESC, er.run_ts DESC, er.id DESC
        LIMIT 1
        """,
        (ticker, asof_iso),
    ).fetchone()
    if row is None:
        return "undefined"
    candidate_id = int(row[0])
    pass_count_row = conn.execute(
        """
        SELECT COUNT(*) FROM candidate_criteria
        WHERE candidate_id = ?
          AND layer = 'trend_template'
          AND result = 'pass'
        """,
        (candidate_id,),
    ).fetchone()
    pass_count = int(pass_count_row[0]) if pass_count_row is not None else 0
    if pass_count == _TREND_TEMPLATE_REQUIRED_PASS_COUNT:
        return "stage_2"
    return "undefined"
