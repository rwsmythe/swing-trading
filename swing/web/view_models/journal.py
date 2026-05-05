"""JournalVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.fills import list_all_fills
from swing.data.repos.trades import list_closed_trades, list_open_trades
from swing.data.repos.weather import list_weather_runs
from swing.journal.flags import BehavioralFlag, compute_flags
from swing.journal.stats import JournalStats, compute_stats, period_filter

Period = Literal["week", "month", "quarter", "ytd", "all"]

_ALLOWED_PERIODS: frozenset[str] = frozenset({"week", "month", "quarter", "ytd", "all"})


@dataclass(frozen=True)
class _ExitShape:
    """Local adapter mirroring legacy Exit shape for ExitLike-consuming
    APIs (period_filter, compute_stats, compute_flags). Mirrors
    swing/web/view_models/dashboard.py's _ExitShape — both die in C.10
    when equity.py refactors to consume fills directly. Single source
    of math truth: swing.trades.derived_metrics.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(conn) -> list[_ExitShape]:
    """C.9 migration helper: produces the ExitLike collection that
    ``list_all_exits(conn)`` previously returned, but sourced from
    ``fills`` filtered to non-entry actions. Per-fill realized_pnl + r
    derive on the fly from the parent trade's entry_price/initial_stop
    via ``swing.trades.derived_metrics``.
    """
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue
        rps = initial_risk_per_share(
            entry_price=trade.entry_price, initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        rmult: float | None
        if rps == 0 or f.quantity == 0:
            rmult = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out


@dataclass(frozen=True)
class JournalVM:
    period: str
    stats: JournalStats
    flags: list[BehavioralFlag]
    trades: list[Trade]
    # Fields required by base.html.j2 (uniform banner guards)
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)


def build_journal(*, cfg: Config, period: str = "month") -> JournalVM:
    if period not in _ALLOWED_PERIODS:
        raise ValueError(
            f"unknown period {period!r}; allowed: {sorted(_ALLOWED_PERIODS)}"
        )
    today = date.today()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades = list_open_trades(conn) + list_closed_trades(conn)
            # C.9: sourced from fills (non-entry) via local adapter; C.10
            # refactors equity.py to consume Fill directly and these
            # adapters retire.
            exits = _list_all_exitshape_via_fills(conn)
            weather = list_weather_runs(conn)
    finally:
        conn.close()
    # Filter trades to the selected period.
    filtered = period_filter(trades, exits, period=period, today=today.isoformat())
    # Stats computed over the filtered trade set.
    stats = compute_stats(trades=filtered, exits=exits)
    # Flags computed over ALL trades (cross-period behavioral patterns).
    flags = compute_flags(trades=trades, exits=exits, weather_runs=weather)
    return JournalVM(
        period=period, stats=stats, flags=list(flags),
        trades=list(filtered),
        session_date=today.isoformat(),
    )
