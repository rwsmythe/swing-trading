"""Behavioral flags — three pure rules from legacy trade.py."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from swing.data.models import Exit, Trade, WeatherRun


@dataclass(frozen=True)
class BehavioralFlag:
    code: str
    title: str
    detail: str
    examples: list[str]


def _trade_r_share_weighted(trade: Trade, exits: list[Exit]) -> float:
    return sum(
        e.r_multiple * (e.shares / trade.initial_shares)
        for e in exits if e.trade_id == trade.id
    )


def _hold_days(trade: Trade, exits: list[Exit]) -> int | None:
    closes = [e.exit_date for e in exits if e.trade_id == trade.id]
    if not closes:
        return None
    last = max(date.fromisoformat(d) for d in closes)
    return (last - date.fromisoformat(trade.entry_date)).days


def _caution_market_entries(
    trades: list[Trade], exits: list[Exit], weather_by_date: dict[str, str],
) -> BehavioralFlag | None:
    bad: list[str] = []
    for t in trades:
        if t.status != "closed":
            continue
        status = weather_by_date.get(t.entry_date, "")
        if status in ("Caution", "Bearish"):
            bad.append(f"{t.ticker} ({t.entry_date}: {status})")
    if len(bad) < 2:
        return None
    return BehavioralFlag(
        code="caution_market_entries",
        title="Trades entered during Caution/Bearish weather",
        detail=f"{len(bad)} trades entered when weather was Caution or Bearish \u2014 "
               "review whether these were necessary",
        examples=bad[:5],
    )


def _losers_held_too_long(trades: list[Trade], exits: list[Exit]) -> BehavioralFlag | None:
    winners_days: list[int] = []
    losers_days: list[int] = []
    for t in trades:
        if t.status != "closed":
            continue
        d = _hold_days(t, exits)
        if d is None:
            continue
        r = _trade_r_share_weighted(t, exits)
        if r > 0:
            winners_days.append(d)
        elif r < 0:
            losers_days.append(d)
    if not winners_days or not losers_days:
        return None
    avg_w = sum(winners_days) / len(winners_days)
    avg_l = sum(losers_days) / len(losers_days)
    if avg_w == 0:
        # All winners closed same-day; the loser-vs-winner ratio is undefined.
        # Surfaced 2026-04-29 by smoke-test trades entered and closed same-day
        # at profit. Future enhancement (todo: phase3e-todo.md): emit a
        # dedicated "all winners same-day" flag instead of silent skip.
        return None
    if avg_l > avg_w * 1.2:
        return BehavioralFlag(
            code="losers_held_too_long",
            title="Losers held longer than winners",
            detail=f"Avg loser hold {avg_l:.1f}d vs avg winner {avg_w:.1f}d "
                   f"({avg_l/avg_w:.1f}\u00d7 ratio)",
            examples=[],
        )
    return None


def _cutting_winners_short(trades: list[Trade], exits: list[Exit]) -> BehavioralFlag | None:
    winners = [
        t for t in trades
        if t.status == "closed" and _trade_r_share_weighted(t, exits) > 0
    ]
    if len(winners) < 3:
        return None
    below_1r = [t for t in winners if _trade_r_share_weighted(t, exits) < 1.0]
    if len(below_1r) / len(winners) >= 0.5:
        return BehavioralFlag(
            code="cutting_winners_short",
            title="Cutting winners short",
            detail=f"{len(below_1r)} of {len(winners)} winners closed below +1R "
                   "\u2014 consider letting winners run",
            examples=[t.ticker for t in below_1r[:5]],
        )
    return None


def compute_flags(
    *, trades: Iterable[Trade], exits: Iterable[Exit],
    weather_runs: Iterable[WeatherRun],
) -> list[BehavioralFlag]:
    trades_list = list(trades)
    exits_list = list(exits)
    weather_by_date = {w.asof_date: w.status for w in weather_runs}

    candidates = [
        _caution_market_entries(trades_list, exits_list, weather_by_date),
        _losers_held_too_long(trades_list, exits_list),
        _cutting_winners_short(trades_list, exits_list),
    ]
    return [f for f in candidates if f is not None]
