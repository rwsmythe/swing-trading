from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.control_cohort import ControlAnchor

from .constants import CONTROL_GAP_BARS, MAX_CONTROL_AGE_BARS, MIN_HISTORY_BARS
from .primary_base_screen import screen_at


def eligible_control_positions(
    bars: pd.DataFrame, *, entry_pos: int, sweep_start: int, sweep_end: int
) -> list[int]:
    """Young-window control candidates: PRE-FILTER to [MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1]
    BEFORE applying the gap + sweep-exclusion (the pre-filter, not a post-hoc clip, is what yields
    young controls for deep-history names -- spec section 6, R2.M1/R3.M1)."""
    lo = MIN_HISTORY_BARS - 1
    hi = min(MAX_CONTROL_AGE_BARS - 1, len(bars) - 1)
    return [
        p
        for p in range(lo, hi + 1)
        if abs(p - entry_pos) >= CONTROL_GAP_BARS and not (sweep_start <= p <= sweep_end)
    ]


def sample_young_controls(
    bars: pd.DataFrame,
    *,
    entry_pos: int,
    sweep_start: int,
    sweep_end: int,
    k: int,
    base_seed: int,
    exemplar_index: int,
) -> tuple[list[ControlAnchor], int]:
    """Returns (chosen anchors, eligible_control_count_before_sampling). Deterministic per seed."""
    pool = eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep_start, sweep_end=sweep_end
    )
    rng = random.Random(base_seed + exemplar_index)
    chosen = sorted(rng.sample(pool, min(k, len(pool))))
    anchors = [ControlAnchor(session=bars.index[p].date(), session_pos=p) for p in chosen]
    return anchors, len(pool)


@dataclass(frozen=True)
class ControlScreenResult:
    session: date
    single_session_fired: bool
    window_fired: bool


def screen_control_anchor(
    bars: pd.DataFrame, anchor: ControlAnchor, *, window_back: int, window_fwd: int
) -> ControlScreenResult:
    """Single-session per-anchor fire (PRIMARY estimand) + window best-of fire (reported
    separately, never conflated -- R1.M9). Controls are evaluated day-precision (a calendar
    date)."""
    single = screen_at(bars, anchor.session).fired
    start = max(0, anchor.session_pos - window_back)
    end = min(len(bars) - 1, anchor.session_pos + window_fwd)
    window = any(screen_at(bars, d.date()).fired for d in bars.index[start : end + 1])
    return ControlScreenResult(
        session=anchor.session, single_session_fired=single, window_fired=window
    )
