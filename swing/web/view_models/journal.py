"""JournalVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import list_all_exits, list_closed_trades, list_open_trades
from swing.data.repos.weather import list_weather_runs
from swing.journal.flags import BehavioralFlag, compute_flags
from swing.journal.stats import JournalStats, compute_stats, period_filter

Period = Literal["week", "month", "quarter", "ytd", "all"]

_ALLOWED_PERIODS: frozenset[str] = frozenset({"week", "month", "quarter", "ytd", "all"})


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
            exits = list_all_exits(conn)
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
