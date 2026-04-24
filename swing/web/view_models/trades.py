"""Trade form view-models + builders for Phase 3b."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import get_trade, list_all_exits, list_exits_for_trade, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.recommendations.sizing import compute_shares
from swing.trades.entry import entry_rationale_options
from swing.trades.equity import current_equity
from swing.trades.exit import ExitReason
from swing.trades.stop_adjust import stop_adjust_rationale_options
from swing.web.price_cache import PriceCache


@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str                  # today, ISO
    entry_price: float               # from live price cache
    initial_stop: float              # from watchlist_initial_stop_target if present, else 0.0
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int
    risk_dollars: float
    risk_pct: float
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False
    rationale: str = ""       # preserved from prior submit on duplicate/drift
    notes: str = ""           # preserved from prior submit on duplicate/drift
    input_shares: int = 0     # user's submitted shares on drift-retry; 0 = no override
    # Closed-taxonomy rationale options (value, display_label) pairs — T4.
    rationale_options: tuple[tuple[str, str], ...] = ()


def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
) -> TradeEntryFormVM:
    """Build entry-form VM from: watchlist row, live price, open positions, equity.
    Spec §4.2."""
    ticker = ticker.upper()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            exits = list_all_exits(conn)
            cash_movements = list_cash(conn)
    finally:
        conn.close()

    # Live price.
    prices = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(ticker)
    entry_price = snap.price if snap else (wl_entry.last_close if wl_entry else 0.0)

    initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0
    watchlist_entry_target = wl_entry.entry_target if wl_entry else None
    watchlist_initial_stop = wl_entry.initial_stop_target if wl_entry else None

    # Sizing hint at current (entry, stop).
    equity = current_equity(
        starting_equity=cfg.account.starting_equity,
        exits=exits, cash_movements=cash_movements,
    )
    if entry_price > 0 and 0 < initial_stop < entry_price:
        sizing = compute_shares(
            entry=entry_price, stop=initial_stop, equity=equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
        suggested_shares = sizing.shares
        risk_dollars = sizing.risk_dollars
        risk_pct = sizing.risk_pct
    else:
        suggested_shares = 0
        risk_dollars = 0.0
        risk_pct = 0.0

    return TradeEntryFormVM(
        ticker=ticker,
        entry_date=date.today().isoformat(),
        entry_price=entry_price,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_entry_target,
        watchlist_initial_stop=watchlist_initial_stop,
        suggested_shares=suggested_shares,
        risk_dollars=risk_dollars,
        risk_pct=risk_pct,
        soft_warn_threshold=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        open_count=len(open_trades),
        rationale_options=entry_rationale_options(),
    )


@dataclass(frozen=True)
class TradeExitFormVM:
    trade: Trade
    exit_date: str
    exit_price: float
    remaining_shares: int
    reasons: tuple[str, ...]


def build_exit_form_vm(
    *, trade_id: int, cfg: Config, cache: PriceCache, executor,
) -> TradeExitFormVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "open":
                return None
            exits = list_exits_for_trade(conn, trade_id)
    finally:
        conn.close()
    remaining = trade.initial_shares - sum(e.shares for e in exits)

    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(trade.ticker)
    exit_price = snap.price if snap else trade.entry_price  # conservative fallback

    return TradeExitFormVM(
        trade=trade,
        exit_date=date.today().isoformat(),
        exit_price=exit_price,
        remaining_shares=remaining,
        reasons=tuple(r.value for r in ExitReason),
    )


@dataclass(frozen=True)
class TradeStopFormVM:
    trade: Trade
    current_stop: float
    suggested_stops: tuple[tuple[str, float], ...]  # empty in 3b; 3c populates
    # Closed-taxonomy rationale options (value, display_label) pairs — T5.
    rationale_options: tuple[tuple[str, str], ...] = ()


def build_stop_form_vm(*, trade_id: int, cfg: Config) -> TradeStopFormVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "open":
                return None
    finally:
        conn.close()
    return TradeStopFormVM(
        trade=trade, current_stop=trade.current_stop, suggested_stops=(),
        rationale_options=stop_adjust_rationale_options(),
    )
