"""Journal stats — share-weighted R per trade + win rate + expectancy + streak."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Literal

from swing.data.models import CashMovement, Exit, Trade

Period = Literal["week", "month", "quarter", "ytd", "all"]


@dataclass(frozen=True)
class JournalStats:
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    largest_win_r: float
    largest_loss_r: float
    total_r: float
    total_pnl: float
    current_streak: int
    current_streak_kind: str


def _trade_closed_date(trade: Trade, exits: list[Exit]) -> date | None:
    if trade.status != "closed":
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None


def _trade_r(trade: Trade, exits: list[Exit]) -> float:
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total


def _trade_pnl(trade: Trade, exits: list[Exit]) -> float:
    return sum(e.realized_pnl for e in exits if e.trade_id == trade.id)


def period_filter(
    trades: Iterable[Trade], exits: Iterable[Exit], *,
    period: Period, today: str,
) -> list[Trade]:
    if period == "all":
        return list(trades)
    today_d = date.fromisoformat(today)
    cutoff = {
        "week": today_d - timedelta(days=7),
        "month": today_d - timedelta(days=30),
        "quarter": today_d - timedelta(days=90),
        "ytd": date(today_d.year, 1, 1),
    }[period]
    exits_list = list(exits)
    out: list[Trade] = []
    for t in trades:
        cd = _trade_closed_date(t, exits_list)
        if cd is None:
            continue
        if cd >= cutoff:
            out.append(t)
    return out


def compute_stats(
    *, trades: Iterable[Trade], exits: Iterable[Exit],
    cash_movements: Iterable[CashMovement] = (),
) -> JournalStats:
    trades_list = list(trades)
    exits_list = list(exits)
    closed = [t for t in trades_list if t.status == "closed"]

    if not closed:
        return JournalStats(
            n_trades=0, n_wins=0, n_losses=0, win_rate=0.0,
            avg_win_r=0.0, avg_loss_r=0.0, expectancy_r=0.0,
            largest_win_r=0.0, largest_loss_r=0.0,
            total_r=0.0, total_pnl=0.0,
            current_streak=0, current_streak_kind="",
        )

    decorated = sorted(
        ((t, _trade_r(t, exits_list), _trade_pnl(t, exits_list),
          _trade_closed_date(t, exits_list)) for t in closed),
        key=lambda x: x[3] or date.min,
    )
    n = len(decorated)
    rs = [r for _, r, _, _ in decorated]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = n_wins / n if n > 0 else 0.0
    avg_win = sum(wins) / n_wins if wins else 0.0
    avg_loss = sum(losses) / n_losses if losses else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    streak = 0
    kind = ""
    if rs:
        first = rs[-1]
        if first > 0:
            kind = "W"
            for r in reversed(rs):
                if r > 0:
                    streak += 1
                else:
                    break
        elif first < 0:
            kind = "L"
            for r in reversed(rs):
                if r < 0:
                    streak += 1
                else:
                    break

    return JournalStats(
        n_trades=n, n_wins=n_wins, n_losses=n_losses,
        win_rate=win_rate, avg_win_r=avg_win, avg_loss_r=avg_loss,
        expectancy_r=expectancy,
        largest_win_r=max(wins) if wins else 0.0,
        largest_loss_r=min(losses) if losses else 0.0,
        total_r=sum(rs),
        total_pnl=sum(p for _, _, p, _ in decorated),
        current_streak=streak, current_streak_kind=kind,
    )
