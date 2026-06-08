# research/harness/minervini_exemplar_recall/control_cohort.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config

from . import timing
from .constants import CONTROL_GAP_BARS
from .exemplar_reader import ExemplarRow
from .timing import ExemplarTimingResult


@dataclass(frozen=True)
class ControlAnchor:
    session: date
    session_pos: int


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def sample_control_anchors(
    bars: pd.DataFrame,
    entry_anchor: date,
    *,
    k: int,
    window_back: int,
    window_fwd: int,
    screenable_floor: int,
    base_seed: int,
    exemplar_index: int,
) -> list[ControlAnchor]:
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return []
    n = len(bars)
    candidates = [
        p
        for p in range(n)
        if p >= screenable_floor - 1  # >= screenable_floor preceding bars (inclusive of p)
        and abs(p - pos) >= CONTROL_GAP_BARS
        and not (pos - window_back <= p <= pos + window_fwd)
    ]
    rng = random.Random(base_seed + exemplar_index)
    chosen = sorted(rng.sample(candidates, min(k, len(candidates))))
    return [ControlAnchor(session=bars.index[p].date(), session_pos=p) for p in chosen]


def evaluate_control(
    exemplar: ExemplarRow,
    anchor: ControlAnchor,
    *,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    window_back: int = 60,
    window_fwd: int = 5,
) -> dict[str, ExemplarTimingResult]:
    # Evaluate the control anchor with the SAME orchestration as an exemplar (both modes,
    # mode-to-mode) by treating the control date as the anchor and reusing the parent's class.
    control_ex = ExemplarRow(
        exemplar_id=f"{exemplar.exemplar_id}__control@{anchor.session.isoformat()}",
        ticker=exemplar.ticker,
        tiingo_symbol=exemplar.tiingo_symbol,
        setup_label=exemplar.setup_label,
        detector_class=exemplar.detector_class,
        entry_anchor=anchor.session,
        date_precision="day",
        buy_point_price=None,
        source=exemplar.source,
        page=exemplar.page,
        notes="negative-control",
    )
    return timing.evaluate_exemplar(
        control_ex,
        exemplar_full=exemplar_full,
        spy_full=spy_full,
        config=config,
        window_back=window_back,
        window_fwd=window_fwd,
    )
