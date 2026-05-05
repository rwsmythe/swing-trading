"""Per-trade retrospective compute — joins trades + exits + candidates.

Pure-compute layer for the `swing trade analyze <trade_id>` CLI. Reads only;
no UPDATE/INSERT/DELETE. Composes a `TradeAnalysis` from existing repo helpers
plus a small targeted SQL join for the recommendation lookup (no analogous
helper exists in `swing.data.repos.candidates` and reusing `fetch_candidates_for_run`
per ticker would be O(N) connections per run).

Brief: `docs/trade-analyze-cli-brief.md` §4.1.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import get_trade
from swing.trades.derived_metrics import (
    initial_risk_per_share,
    r_multiple,
    realized_pnl,
)


@dataclass(frozen=True)
class _ExitShape:
    """C.12: per-module ExitLike adapter mirroring C.1/C.9/C.10/C.11.

    Reconstructed from non-entry fills so analyze_trade can drop its
    dependency on the legacy ``list_exits_for_trade`` shim before C.14
    deletes it. Fields match what the downstream ``ExitDisplay`` loop
    reads: exit_date / shares / exit_price / reason / realized_pnl /
    r_multiple.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float
    r_multiple: float

# Buckets that carry no analytical signal for this tool. `excluded` is the
# bookkeeping bucket used by `_step_evaluate` to keep last-close fresh on
# tickers rotated out of the Finviz pool (notes='open position'); `error`
# rows are evaluator failures and never produce pivot/criteria worth surfacing.
_USEFUL_BUCKETS = ("aplus", "watch", "skip")


@dataclass(frozen=True)
class CriterionResultDisplay:
    layer: str             # 'trend_template' | 'vcp' | 'risk'
    criterion_name: str
    result: str            # 'pass' | 'fail' | 'na'
    value: str | None
    rule: str | None


@dataclass(frozen=True)
class RecommendationContext:
    eval_run_id: int
    eval_run_action_session_date: str
    bucket: str
    pivot: float | None
    initial_stop: float | None
    close_at_eval: float | None
    rs_rank: int | None
    rs_return_12w_vs_spy: float | None
    pattern_tag: str | None
    notes: str | None
    criteria: tuple[CriterionResultDisplay, ...]


@dataclass(frozen=True)
class ExitDisplay:
    exit_date: str
    shares: int
    exit_price: float
    reason: str
    realized_pnl: float
    r_multiple: float


@dataclass(frozen=True)
class TradeAnalysis:
    trade_id: int
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    state: str
    status: str
    hypothesis_label: str | None
    notes: str | None
    recommendations: tuple[RecommendationContext, ...]
    exits: tuple[ExitDisplay, ...]
    days_rec_to_entry: int | None
    pct_above_pivot: float | None
    stop_dev_pct: float | None
    realized_pnl_total: float
    r_multiple_avg: float | None


def _fetch_recommendations(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
) -> tuple[RecommendationContext, ...]:
    """All `useful_buckets` candidate rows for `ticker` whose evaluation_run
    occurred on or before `entry_date`. Returned in chronological order
    (run_ts ASC, then candidate_id ASC for deterministic tiebreak); the
    caller picks the last element for "latest".

    Selection key: `evaluation_runs.run_ts` (per brief §5 watch item:
    "MAX(run_ts) WHERE run_ts <= entry_date_timestamp"). This is the
    operationally-meaningful ordering: "what recommendations did I see
    BEFORE entering?". An alternative — `action_session_date` — would
    instead capture "what was the framework's view of this ticker for
    the entry-day session?", and would include a backfill rerun done
    AFTER the trade was entered. We use run_ts so a post-entry
    backfill can never silently re-baseline the deviation math; the
    `(c.id ASC)` tiebreaker ensures multi-run/same-second results are
    deterministic.

    Uses a bound parameter for `entry_date`; ticker is bound separately.
    Schema invariant relied on: `UNIQUE(evaluation_run_id, ticker)` on
    `candidates` (migration 0001), so within a single eval_run there
    cannot be duplicate ticker rows — the tiebreaker only matters
    across runs.
    """
    placeholders = ",".join("?" * len(_USEFUL_BUCKETS))
    sql = (
        "SELECT c.id, c.evaluation_run_id, er.action_session_date, er.run_ts, "
        "c.bucket, c.pivot, c.initial_stop, c.close, c.rs_rank, "
        "c.rs_return_12w_vs_spy, c.pattern_tag, c.notes "
        "FROM candidates c "
        "JOIN evaluation_runs er ON er.id = c.evaluation_run_id "
        "WHERE c.ticker = ? AND er.run_ts < ? "
        f"AND c.bucket IN ({placeholders}) "
        "ORDER BY er.run_ts ASC, c.id ASC"
    )
    # Exclusive next-day-midnight upper bound. The query relies on
    # lexicographic ordering of `er.run_ts` strings, which works correctly
    # for the storage convention used in production (`pipeline.runner`
    # writes `datetime.now().isoformat(timespec='seconds')` — naive local
    # time, no offset). Under that convention, a sub-second-precision row
    # (`...T23:59:59.500`) or `Z`-suffixed row that landed on `entry_date`
    # would have been silently excluded by the prior `<= entry_dateT23:59:59`
    # bound; the next-day-midnight bound includes them. Mixing naive +
    # offset-bearing timestamps in the same DB would produce ordering-
    # mismatch artifacts; that's a storage-convention invariant we rely
    # on, not a normalization guarantee. Adversarial review R2 M1 / R3 m1.
    try:
        next_day = date.fromisoformat(entry_date) + timedelta(days=1)
    except ValueError as exc:
        # Adversarial review R3 M1: surface data-integrity failure rather
        # than silently degrading to "manually-sourced". A malformed
        # entry_date implies the trades row was inserted outside the repo
        # (which validates ISO dates), and the operator needs to know.
        raise ValueError(
            f"trade.entry_date={entry_date!r} is not ISO 8601 (YYYY-MM-DD); "
            f"cannot compute recommendation lookup window"
        ) from exc
    upper_bound = f"{next_day.isoformat()}T00:00:00"
    rows = conn.execute(
        sql, (ticker, upper_bound, *_USEFUL_BUCKETS),
    ).fetchall()

    recs: list[RecommendationContext] = []
    for row in rows:
        cid = row[0]
        crit_rows = conn.execute(
            "SELECT criterion_name, layer, result, value, rule "
            "FROM candidate_criteria WHERE candidate_id = ? "
            "ORDER BY layer, criterion_name",
            (cid,),
        ).fetchall()
        criteria = tuple(
            CriterionResultDisplay(
                layer=layer, criterion_name=name, result=res,
                value=val, rule=rule,
            )
            for (name, layer, res, val, rule) in crit_rows
        )
        recs.append(RecommendationContext(
            eval_run_id=int(row[1]),
            eval_run_action_session_date=row[2],
            bucket=row[4],
            pivot=row[5], initial_stop=row[6], close_at_eval=row[7],
            rs_rank=row[8], rs_return_12w_vs_spy=row[9],
            pattern_tag=row[10], notes=row[11],
            criteria=criteria,
        ))
    return tuple(recs)


def _shares_weighted_r(exits: tuple[ExitDisplay, ...]) -> float | None:
    """Shares-weighted R-multiple: sum(shares × r) / sum(shares).
    Returns None when there are no exits — undefined.
    """
    total_shares = sum(e.shares for e in exits)
    if total_shares <= 0:
        return None
    return sum(e.shares * e.r_multiple for e in exits) / total_shares


def analyze_trade(conn: sqlite3.Connection, trade_id: int) -> TradeAnalysis:
    """Compose a `TradeAnalysis` from production DB reads.

    Raises `ValueError` if `trade_id` does not exist (parity with the rest of
    the trades repo). Read-only — no INSERT/UPDATE/DELETE.

    `recommendations` is empty when no usable (`aplus`/`watch`/`skip`) candidate
    row exists for the ticker on or before `entry_date` (manually-sourced trade);
    deviation fields then return None instead of crashing on missing pivot/stop.
    """
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")

    recs = _fetch_recommendations(
        conn, ticker=trade.ticker, entry_date=trade.entry_date,
    )

    # C.12: build _ExitShape rows from non-entry fills (mirrors the per-
    # module adapter pattern from C.1/C.9/C.10/C.11). The downstream
    # ExitDisplay loop reads .exit_date/.shares/.exit_price/.reason/
    # .realized_pnl/.r_multiple — _ExitShape's fields match exactly.
    fills = list_fills_for_trade(conn, trade_id)
    exit_rows: list[_ExitShape] = []
    for f in fills:
        if f.action == "entry":
            continue
        rps = initial_risk_per_share(
            entry_price=trade.entry_price,
            initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        if rps > 0 and f.quantity > 0:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        else:
            # Defensive: ExitDisplay.r_multiple is typed `float`, and the
            # _shares_weighted_r helper multiplies by it. Under the
            # entry_price > initial_stop invariant enforced by the entry
            # service, rps > 0 always holds; this branch is a guardrail
            # only, matching the legacy shim's behaviour (it raised on
            # zero-risk trades). Use 0.0 to keep ExitDisplay constructible
            # without crashing analyze on data-anomaly trades.
            rmult = 0.0
        exit_date_str = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        exit_rows.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date_str,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    exits = tuple(
        ExitDisplay(
            exit_date=e.exit_date, shares=e.shares, exit_price=e.exit_price,
            reason=e.reason, realized_pnl=e.realized_pnl,
            r_multiple=e.r_multiple,
        )
        for e in exit_rows
    )

    days_rec_to_entry: int | None = None
    pct_above_pivot: float | None = None
    stop_dev_pct: float | None = None
    if recs:
        latest = recs[-1]
        # Days from latest pre-entry recommendation's action session to entry.
        # action_session_date is the trading session the recommendation was
        # FOR (forward-looking), so it lines up with entry_date semantically.
        try:
            days_rec_to_entry = (
                date.fromisoformat(trade.entry_date)
                - date.fromisoformat(latest.eval_run_action_session_date)
            ).days
        except ValueError:
            days_rec_to_entry = None
        if latest.pivot is not None and latest.pivot > 0:
            pct_above_pivot = (trade.entry_price - latest.pivot) / latest.pivot
        if (
            latest.initial_stop is not None and latest.initial_stop > 0
        ):
            stop_dev_pct = (
                trade.initial_stop - latest.initial_stop
            ) / latest.initial_stop

    return TradeAnalysis(
        trade_id=trade_id,
        ticker=trade.ticker,
        entry_date=trade.entry_date,
        entry_price=trade.entry_price,
        initial_shares=trade.initial_shares,
        initial_stop=trade.initial_stop,
        current_stop=trade.current_stop,
        # C.11: expose raw lifecycle state + derive legacy 'open'/'closed' for
        # CLI hold-duration branch compatibility (a.status == "open"/"closed").
        state=trade.state,
        status=(
            "open"
            if trade.state in ("entered", "managing", "partial_exited")
            else "closed"
        ),
        hypothesis_label=trade.hypothesis_label,
        notes=trade.notes,
        recommendations=recs,
        exits=exits,
        days_rec_to_entry=days_rec_to_entry,
        pct_above_pivot=pct_above_pivot,
        stop_dev_pct=stop_dev_pct,
        realized_pnl_total=sum(e.realized_pnl for e in exits),
        r_multiple_avg=_shares_weighted_r(exits),
    )
