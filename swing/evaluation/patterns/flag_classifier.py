"""Deterministic geometric flag-pattern classifier (V1).

Pure-function: DataFrame in, FlagClassificationResult out. No DB, no IO,
no logging side-effects. Spec: docs/superpowers/specs/2026-04-26-chart-
pattern-flag-v1-design.md §3.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from swing.config import ClassifierConfig

# Defaults match ClassifierConfig defaults; live class-tunable via the
# `cfg` argument in classify_flag(). Phase 7 FP-biased tuning dials these
# via cfg.classifier.* — module-level constants are NOT to be edited.
M_RANGE = range(5, 31)   # pole length [5, 30]
N_RANGE = range(5, 22)   # flag length [5, 21]
MIN_BARS = 36
_DEFAULT_CFG = ClassifierConfig()


@dataclass(frozen=True)
class FlagClassificationResult:
    detected: bool
    confidence: float
    pattern: str | None
    pole_start_date: date | None
    pole_end_date: date | None
    flag_start_date: date | None
    flag_end_date: date | None
    pole_high: float | None
    flag_low: float | None
    pivot: float | None
    components: dict[str, float] = field(default_factory=dict)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _ma_structure_passes(closes: np.ndarray, flag_start_idx: int) -> bool:
    """Gate 5: at flag_start, SMA10 > SMA20 > SMA50 AND each rising over
    the last 5 bars (today vs 5 bars ago, exclusive)."""
    if flag_start_idx < 50 + 5:
        return False
    def sma(window: int, at: int) -> float:
        return float(np.mean(closes[at - window + 1:at + 1]))
    today = flag_start_idx
    earlier = flag_start_idx - 5
    s10 = sma(10, today)
    s20 = sma(20, today)
    s50 = sma(50, today)
    if not (s10 > s20 > s50):
        return False
    return all(sma(w, today) > sma(w, earlier) for w in (10, 20, 50))


def _evaluate_candidate(
    bars: pd.DataFrame, pole_start: int, flag_start: int, flag_end: int,
) -> dict:
    """Return per-gate measurements for a single (pole_start, flag_start, flag_end)
    triple. Caller decides pass/fail + ranking."""
    closes = bars["Close"].to_numpy(dtype=float)
    highs = bars["High"].to_numpy(dtype=float)
    lows = bars["Low"].to_numpy(dtype=float)
    vols = bars["Volume"].to_numpy(dtype=float)

    pole_high = float(highs[pole_start:flag_start].max())
    pole_low = float(lows[pole_start:flag_start].min())
    flag_high = float(highs[flag_start:flag_end].max())
    flag_low = float(lows[flag_start:flag_end].min())

    pole_gain = (pole_high - pole_low) / max(pole_low, 1e-9)
    pullback_depth = (pole_high - flag_low) / max(pole_high, 1e-9)

    pole_ranges = (highs[pole_start:flag_start] - lows[pole_start:flag_start]) \
        / np.maximum(closes[pole_start:flag_start], 1e-9)
    flag_ranges = (highs[flag_start:flag_end] - lows[flag_start:flag_end]) \
        / np.maximum(closes[flag_start:flag_end], 1e-9)
    pole_med = float(np.median(pole_ranges)) if len(pole_ranges) else 0.0
    flag_med = float(np.median(flag_ranges)) if len(flag_ranges) else 0.0
    tightness_ratio = flag_med / max(pole_med, 1e-9)

    pole_vol_mean = (
        float(np.mean(vols[pole_start:flag_start])) if (flag_start - pole_start) else 0.0
    )
    flag_vol_mean = (
        float(np.mean(vols[flag_start:flag_end])) if (flag_end - flag_start) else 0.0
    )
    volume_ratio = flag_vol_mean / max(pole_vol_mean, 1e-9)

    N = flag_end - flag_start  # noqa: N806  # M, N are spec-canonical (§3.1: pole length M, flag length N)
    half = N // 2
    flag_low_first_half = (
        float(np.min(lows[flag_start:flag_start + half])) if half else flag_low
    )
    flag_low_second_half = (
        float(np.min(lows[flag_start + half:flag_end])) if (N - half) else flag_low
    )
    flag_floor_holds = flag_low_second_half >= flag_low_first_half

    ma_ok = _ma_structure_passes(closes, flag_start)

    return {
        "pole_M": float(flag_start - pole_start),
        "flag_N": float(N),
        "pole_gain": pole_gain,
        "pullback_depth": pullback_depth,
        "tightness_ratio": tightness_ratio,
        "volume_ratio": volume_ratio,
        "ma_structure": float(ma_ok),
        "flag_floor_holds": float(flag_floor_holds),
        "pole_high": pole_high,
        "flag_low": flag_low,
        "pivot": flag_high,
    }


def _continuous_clearances(c: dict, cfg: ClassifierConfig) -> tuple[float, float, float, float]:
    return (
        _clamp((c["pole_gain"] - cfg.flag_pole_gain_min) / 0.70, 0.0, 1.0),
        _clamp(
            (cfg.flag_pullback_depth_max - c["pullback_depth"]) / cfg.flag_pullback_depth_max,
            0.0,
            1.0,
        ),
        _clamp(
            (cfg.flag_tightness_ratio_max - c["tightness_ratio"]) / cfg.flag_tightness_ratio_max,
            0.0,
            1.0,
        ),
        _clamp(
            (cfg.flag_volume_ratio_max - c["volume_ratio"]) / cfg.flag_volume_ratio_max,
            0.0,
            1.0,
        ),
    )


def _soft_clearances(c: dict, cfg: ClassifierConfig) -> tuple[float, float, float, float]:
    """Allow negative values for failed continuous gates (best-attempted ranking)."""
    return (
        (c["pole_gain"] - cfg.flag_pole_gain_min) / 0.70,
        (cfg.flag_pullback_depth_max - c["pullback_depth"]) / cfg.flag_pullback_depth_max,
        (cfg.flag_tightness_ratio_max - c["tightness_ratio"]) / cfg.flag_tightness_ratio_max,
        (cfg.flag_volume_ratio_max - c["volume_ratio"]) / cfg.flag_volume_ratio_max,
    )


def _enrich_components(
    c: dict, anchors: tuple[int, int, int],
    bars: pd.DataFrame, cfg: ClassifierConfig,
) -> dict:
    """Augment the per-gate components dict with the 4 soft clearances and
    3 SMA-at-flag-start values per spec §3.1.1. SMA values become
    unrecoverable once raw bars aren't persisted alongside (Phase 1 → 2
    handoff item)."""
    pole_gain_cl, pullback_cl, tightness_cl, volume_cl = _soft_clearances(c, cfg)
    closes = bars["Close"].to_numpy(dtype=float)
    _, flag_start, _ = anchors

    def sma(window: int) -> float:
        if flag_start < window - 1:
            return float("nan")
        return float(np.mean(closes[flag_start - window + 1:flag_start + 1]))

    enriched = dict(c)
    enriched["pole_gain_clearance"] = pole_gain_cl
    enriched["pullback_clearance"] = pullback_cl
    enriched["tightness_clearance"] = tightness_cl
    enriched["volume_clearance"] = volume_cl
    enriched["sma10_at_flag_start"] = sma(10)
    enriched["sma20_at_flag_start"] = sma(20)
    enriched["sma50_at_flag_start"] = sma(50)
    return enriched


def _detection_passes(c: dict, cfg: ClassifierConfig) -> bool:
    return (
        c["pole_gain"] >= cfg.flag_pole_gain_min
        and c["pullback_depth"] <= cfg.flag_pullback_depth_max
        and c["tightness_ratio"] <= cfg.flag_tightness_ratio_max
        and c["volume_ratio"] <= cfg.flag_volume_ratio_max
        and c["ma_structure"] >= 1.0
        and c["flag_floor_holds"] >= 1.0
    )


def classify_flag(
    bars: pd.DataFrame,
    cfg: ClassifierConfig | None = None,
) -> FlagClassificationResult:
    cfg = cfg or _DEFAULT_CFG
    if len(bars) < MIN_BARS:
        return FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={},
        )

    n = len(bars)
    # best_pass key = (confidence, -N (lower better), -M (lower better))
    best_pass = None
    best_attempt = None  # (max_min_soft_clearance, c, anchors)

    for N in N_RANGE:  # noqa: N806  # M, N are spec-canonical (§3.1: pole length M, flag length N)
        flag_end = n
        flag_start = n - N
        if flag_start <= 0:
            continue
        for M in M_RANGE:  # noqa: N806  # M, N are spec-canonical (§3.1: pole length M, flag length N)
            pole_start = flag_start - M
            if pole_start < 0:
                continue
            c = _evaluate_candidate(bars, pole_start, flag_start, flag_end)
            anchors = (pole_start, flag_start, flag_end)
            if _detection_passes(c, cfg):
                conf = min(_continuous_clearances(c, cfg))
                # Tie-break: higher confidence first; on tie, lower N then lower M.
                key = (conf, -N, -M)
                if best_pass is None or key > best_pass[0]:
                    best_pass = (key, c, anchors)
            soft_min = min(_soft_clearances(c, cfg))
            if best_attempt is None or soft_min > best_attempt[0]:
                best_attempt = (soft_min, c, anchors)

    if best_pass is not None:
        _, c, (ps, fs, fe) = best_pass
        idx = bars.index
        return FlagClassificationResult(
            detected=True,
            confidence=min(_continuous_clearances(c, cfg)),
            pattern="flag",
            pole_start_date=idx[ps].date() if hasattr(idx[ps], "date") else None,
            pole_end_date=idx[fs - 1].date() if hasattr(idx[fs - 1], "date") else None,
            flag_start_date=idx[fs].date() if hasattr(idx[fs], "date") else None,
            flag_end_date=idx[fe - 1].date() if hasattr(idx[fe - 1], "date") else None,
            pole_high=c["pole_high"],
            flag_low=c["flag_low"],
            pivot=c["pivot"],
            components=_enrich_components(c, (ps, fs, fe), bars, cfg),
        )

    # No candidate passes. Components carry the best-attempted candidate's
    # measurements per spec §3.1 (R2 Major 1) — the (M, N) pair maximizing
    # min over the four continuous-gate soft clearances. The (5, 5) literal
    # fallback is reachable only when no candidate was evaluable at all,
    # which the data-window gate (MIN_BARS=36) effectively prevents — kept
    # as belt-and-braces for type-stability of components.
    if best_attempt is not None:
        _, c, anchors = best_attempt
        components = _enrich_components(c, anchors, bars, cfg)
    else:
        components = {"pole_M": 5.0, "flag_N": 5.0}
    return FlagClassificationResult(
        detected=False, confidence=0.0, pattern="none",
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components=components,
    )
