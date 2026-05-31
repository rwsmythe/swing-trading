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
from swing.trades.review import compute_actual_realized_R_effective
from swing.web.view_models.trades import _exit_vwap, _total_risk_dollars

Period = Literal["week", "month", "quarter", "ytd", "all"]

_ALLOWED_PERIODS: frozenset[str] = frozenset({"week", "month", "quarter", "ytd", "all"})

# Phase 14 SB4 Slice 2 — pagination. The single page-size figure governs §5.3.
DEFAULT_PAGE_SIZE = 22
MAX_PAGE_SIZE = 50


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
class JournalRowVM:
    """Phase 14 SB4 Slice 2 — one enriched journal-listing row per trade.

    Math sources (phase isolation): ``_exit_vwap`` + ``_total_risk_dollars``
    reused from ``swing/web/view_models/trades.py`` (Slice 0);
    ``compute_actual_realized_R_effective`` read-only-consumed from
    ``swing/trades/review.py``. No new helper under ``swing/trades/``.
    """
    trade_id: int
    ticker: str
    entry_date: str
    state: str
    open_price: float                 # trade.entry_price
    shares: int                       # trade.initial_shares
    total_risk_dollars: float | None  # initial_shares*(entry_price-initial_stop)
    closing_price: float | None       # VWAP exit (None for open trades)
    final_r: float | None             # compute_actual_realized_R_effective (None=open)
    chart_pattern: str | None         # chart_pattern_operator|_algo|pattern_class
    aplus_bucket: str | None          # candidates.bucket via candidate_id
    hypothesis_label: str | None      # trade.hypothesis_label
    has_hyprec_link: bool             # trade_origin == 'pipeline_watch_hyp_recs'


@dataclass(frozen=True)
class JournalVM:
    period: str
    stats: JournalStats
    flags: list[BehavioralFlag]
    trades: list[Trade]
    rows: tuple[JournalRowVM, ...] = ()
    # Phase 14 SB4 Slice 2 — pagination metadata for the listing template.
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    total_rows: int = 0
    has_next: bool = False
    # Fields required by base.html.j2 (uniform banner guards)
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "JournalVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "JournalVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


def _fetch_bucket_by_cid(conn, candidate_ids: set[int]) -> dict[int, str]:
    """Batched join: candidates.bucket keyed by candidate id. Short-circuits
    the empty set (no ``IN ()`` — invalid SQL)."""
    if not candidate_ids:
        return {}
    placeholders = ",".join("?" * len(candidate_ids))
    rows = conn.execute(
        f"SELECT id, bucket FROM candidates WHERE id IN ({placeholders})",
        tuple(candidate_ids),
    ).fetchall()
    return {int(r[0]): r[1] for r in rows}


def _fetch_pclass_by_peid(conn, peids: set[int]) -> dict[int, str]:
    """Batched join: pattern_evaluations.pattern_class keyed by evaluation id.
    Short-circuits the empty set."""
    if not peids:
        return {}
    placeholders = ",".join("?" * len(peids))
    rows = conn.execute(
        "SELECT id, pattern_class FROM pattern_evaluations "
        f"WHERE id IN ({placeholders})",
        tuple(peids),
    ).fetchall()
    return {int(r[0]): r[1] for r in rows}


def _row_for(trade, *, fills_by_trade, exits_by_trade, bucket_by_cid,
             pclass_by_peid) -> JournalRowVM:
    """Build one ``JournalRowVM`` from a trade + its pre-grouped fills/exits
    and the batched entry-flag lookup dicts.

    ``fills_by_trade``: trade_id -> list[Fill] (non-entry only) for the
    share-weighted exit VWAP. ``exits_by_trade``: trade_id -> list[_ExitShape]
    (ExitLike) for the realized-R computation.
    """
    reducing_fills = fills_by_trade.get(trade.id, [])
    exits = exits_by_trade.get(trade.id, [])
    closing = _exit_vwap(reducing_fills)
    final_r = (
        compute_actual_realized_R_effective(trade, exits)
        if trade.state in ("closed", "reviewed") and exits else None
    )
    chart_pattern = (
        trade.chart_pattern_operator
        or trade.chart_pattern_algo
        or (pclass_by_peid.get(trade.pattern_evaluation_id)
            if trade.pattern_evaluation_id is not None else None)
    )
    return JournalRowVM(
        trade_id=trade.id, ticker=trade.ticker, entry_date=trade.entry_date,
        state=trade.state, open_price=trade.entry_price,
        shares=trade.initial_shares,
        total_risk_dollars=_total_risk_dollars(trade),
        closing_price=closing, final_r=final_r,
        chart_pattern=chart_pattern,
        aplus_bucket=(
            bucket_by_cid.get(trade.candidate_id)
            if trade.candidate_id is not None else None
        ),
        hypothesis_label=trade.hypothesis_label,
        has_hyprec_link=(trade.trade_origin == "pipeline_watch_hyp_recs"),
    )


def build_journal(
    *, cfg: Config, period: str = "month",
    page: int = 1, page_size: int = DEFAULT_PAGE_SIZE,
) -> JournalVM:
    # Slice 2 (Codex Re-R2 m#2 intent extended to the listing route): an
    # unknown period CLAMPS to the default instead of raising, so a bad
    # `period` query renders the page rather than 500/422-ing.
    if period not in _ALLOWED_PERIODS:
        period = "month"
    # Clamp pagination inputs to sane bounds.
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    page = max(1, int(page))
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
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
            unresolved = count_unresolved_material(conn)
            # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect banner counter.
            recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
            # Phase 12.5 #2 T-2.9 — banner first-pending-ambiguity link.
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
            # Slice 2 — raw non-entry fills (for the exit VWAP) keyed by trade.
            fills_by_trade: dict[int, list] = {}
            for f in list_all_fills(conn):
                if f.action == "entry":
                    continue
                fills_by_trade.setdefault(f.trade_id, []).append(f)
            # Slice 2 — period-filter here so the batched entry-flag joins run
            # inside the same connection over the FILTERED trade set only.
            filtered = period_filter(
                trades, exits, period=period, today=today.isoformat(),
            )
            candidate_ids = {
                t.candidate_id for t in filtered if t.candidate_id is not None
            }
            peids = {
                t.pattern_evaluation_id for t in filtered
                if t.pattern_evaluation_id is not None
            }
            bucket_by_cid = _fetch_bucket_by_cid(conn, candidate_ids)
            pclass_by_peid = _fetch_pclass_by_peid(conn, peids)
    finally:
        conn.close()
    # Stats computed over the filtered trade set.
    stats = compute_stats(trades=filtered, exits=exits)
    # Flags computed over ALL trades (cross-period behavioral patterns).
    flags = compute_flags(trades=trades, exits=exits, weather_runs=weather)
    # Slice 2 — per-trade enrichment rows over the FILTERED trade set,
    # sliced to the requested page window. Stats/flags stay over the full
    # filtered set (above); only the displayed rows paginate.
    exits_by_trade: dict[int, list] = {}
    for e in exits:
        exits_by_trade.setdefault(e.trade_id, []).append(e)
    total_rows = len(filtered)
    start = (page - 1) * page_size
    page_trades = filtered[start:start + page_size]
    has_next = (start + page_size) < total_rows
    rows = tuple(
        _row_for(
            t, fills_by_trade=fills_by_trade, exits_by_trade=exits_by_trade,
            bucket_by_cid=bucket_by_cid, pclass_by_peid=pclass_by_peid,
        )
        for t in page_trades
    )
    return JournalVM(
        period=period, stats=stats, flags=list(flags),
        trades=list(filtered), rows=rows,
        page=page, page_size=page_size,
        total_rows=total_rows, has_next=has_next,
        session_date=today.isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
    )
