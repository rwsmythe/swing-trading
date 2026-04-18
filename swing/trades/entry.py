"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.data.models import Trade, WatchlistArchiveEntry
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.data.repos.watchlist import (
    archive_watchlist_entry, get_watchlist_entry,
)


class SoftWarnException(Exception):
    """Open count >= soft_warn_open without force=True."""


class HardCapException(Exception):
    """Open count >= hard_cap_open — never bypassable."""


class DuplicateOpenPositionException(Exception):
    """Already an open trade for this ticker."""


@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str


@dataclass(frozen=True)
class EntryResult:
    trade_id: int
    warning: str | None
    watchlist_archived: bool


def record_entry(
    conn: sqlite3.Connection, req: EntryRequest, *,
    soft_warn: int, hard_cap: int, force: bool,
) -> EntryResult:
    if req.initial_stop >= req.entry_price:
        raise ValueError(
            f"stop must be < entry; got entry={req.entry_price}, stop={req.initial_stop}"
        )

    open_trades = list_open_trades(conn)
    if any(t.ticker == req.ticker for t in open_trades):
        raise DuplicateOpenPositionException(
            f"Already an open position in {req.ticker}"
        )

    open_count = len(open_trades)
    if open_count >= hard_cap:
        raise HardCapException(
            f"Hard cap reached: {open_count} >= {hard_cap}"
        )
    warning: str | None = None
    if open_count >= soft_warn:
        if not force:
            raise SoftWarnException(
                f"Open count {open_count} >= soft warn {soft_warn}; use --force"
            )
        warning = f"Soft warn exceeded: {open_count} open positions (soft={soft_warn})"

    trade = Trade(
        id=None, ticker=req.ticker, entry_date=req.entry_date,
        entry_price=req.entry_price, initial_shares=req.shares,
        initial_stop=req.initial_stop, current_stop=req.initial_stop,
        status="open",
        watchlist_entry_target=req.watchlist_entry_target,
        watchlist_initial_stop=req.watchlist_initial_stop,
        notes=req.notes,
    )

    archived = False
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=req.event_ts, rationale=req.rationale,
        )
        wl = get_watchlist_entry(conn, req.ticker)
        if wl is not None:
            archive_watchlist_entry(conn, WatchlistArchiveEntry(
                id=None, ticker=req.ticker, added_date=wl.added_date,
                removed_date=req.entry_date, reason="entered",
                qualification_count=wl.qualification_count,
                last_data_asof_date=wl.last_data_asof_date,
                notes=wl.notes,
            ))
            archived = True

    return EntryResult(trade_id=trade_id, warning=warning, watchlist_archived=archived)
