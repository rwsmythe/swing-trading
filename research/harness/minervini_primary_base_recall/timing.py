from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .primary_base_screen import PrimaryBaseVerdict, screen_at

_DAY_PRECISIONS = frozenset({"day", "exact"})


@dataclass(frozen=True)
class SessionEval:
    session: date
    verdict: PrimaryBaseVerdict


@dataclass(frozen=True)
class TimingResult:
    mode: str  # "single_session" | "window_sweep"
    sessions: tuple[SessionEval, ...]
    fired: bool
    firing_sessions: tuple[date, ...]


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    return int(mask.argmax()) if mask.any() else None


def _month_bounds(bars: pd.DataFrame, anchor: date) -> tuple[int, int] | None:
    """Positions of the first and last in-frame trading day of anchor's calendar month."""
    in_month = [
        i
        for i, ts in enumerate(bars.index)
        if ts.year == anchor.year and ts.month == anchor.month
    ]
    if not in_month:
        return None
    return in_month[0], in_month[-1]


def sweep_bounds(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *,
    window_back: int, window_fwd: int,
) -> tuple[int, int] | None:
    """The positional [start, end] of the recall sweep window for this exemplar (inclusive)."""
    if date_precision == "month":
        mb = _month_bounds(bars, entry_anchor)
        if mb is None:
            return None
        first_pos, last_pos = mb
        return max(0, first_pos - window_back), min(len(bars) - 1, last_pos + window_fwd)
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return None
    return max(0, pos - window_back), min(len(bars) - 1, pos + window_fwd)


def sweep_sessions(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *,
    window_back: int, window_fwd: int,
) -> list[date]:
    bounds = sweep_bounds(
        bars, entry_anchor, date_precision, window_back=window_back, window_fwd=window_fwd
    )
    if bounds is None:
        return []
    start, end = bounds
    return [d.date() for d in bars.index[start : end + 1]]


def single_session(bars: pd.DataFrame, entry_anchor: date, date_precision: str) -> list[date]:
    # Single-session recall is reported ONLY for day/exact precision (R1.M3); month -> [].
    if date_precision not in _DAY_PRECISIONS:
        return []
    pos = _entry_pos(bars, entry_anchor)
    return [] if pos is None else [bars.index[pos].date()]


def _result(mode: str, bars: pd.DataFrame, sessions: list[date]) -> TimingResult:
    evals = tuple(SessionEval(s, screen_at(bars, s)) for s in sessions)
    firing = tuple(e.session for e in evals if e.verdict.fired)
    return TimingResult(mode=mode, sessions=evals, fired=len(firing) > 0, firing_sessions=firing)


def evaluate_exemplar(
    bars: pd.DataFrame, entry_anchor: date, date_precision: str, *,
    window_back: int, window_fwd: int,
) -> dict[str, TimingResult]:
    return {
        "single_session": _result(
            "single_session", bars, single_session(bars, entry_anchor, date_precision)
        ),
        "window_sweep": _result(
            "window_sweep",
            bars,
            sweep_sessions(
                bars, entry_anchor, date_precision, window_back=window_back, window_fwd=window_fwd
            ),
        ),
    }
