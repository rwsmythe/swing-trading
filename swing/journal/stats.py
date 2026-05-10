"""Journal stats — share-weighted R per trade + win rate + expectancy + streak."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from swing.data.models import CashMovement, Trade


@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(
    conn: sqlite3.Connection,
) -> list[_ExitShape]:
    """C.11: reconstruct Exit-like rows from non-entry fills.

    Mirrors the per-module ``_ExitShape`` adapter pattern from C.1/C.9/C.10
    (see ``swing/data/repos/review_log.py``). Migrates the consumer in
    ``compute_hypothesis_progress_breakdown`` off the ``list_all_exits``
    shim before C.14 deletes it.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )
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
            entry_price=trade.entry_price,
            initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        if rps == 0 or f.quantity == 0:
            rmult: float | None = None
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

Period = Literal["week", "month", "quarter", "ytd", "all"]


@dataclass(frozen=True)
class HypothesisBucket:
    """One row of the journal-review hypothesis breakdown.

    `label is None` is the "(no label)" bucket — closed trades whose
    `hypothesis_label` was never set. `win_rate is None` means the bucket has
    fewer than 3 trades and the breakdown suppresses win-rate reporting to
    avoid small-sample noise (per brief §4.5).
    """
    label: str | None
    n_trades: int
    total_pnl: float
    win_rate: float | None


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


def _trade_closed_date(trade: Trade, exits: list[_ExitShape]) -> date | None:
    # Phase 7 B.9: closed-or-reviewed sweeps both terminal lifecycle states.
    # Reviewed trades are still "closed" for aggregation purposes — the only
    # difference is whether the operator has completed the post-trade review.
    if trade.state not in ("closed", "reviewed"):
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None


def _trade_r(trade: Trade, exits: list[_ExitShape]) -> float:
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total


def _trade_pnl(trade: Trade, exits: list[_ExitShape]) -> float:
    return sum(e.realized_pnl for e in exits if e.trade_id == trade.id)


def period_filter(
    trades: Iterable[Trade], exits: Iterable[_ExitShape], *,
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
    *, trades: Iterable[Trade], exits: Iterable[_ExitShape],
    cash_movements: Iterable[CashMovement] = (),
) -> JournalStats:
    trades_list = list(trades)
    exits_list = list(exits)
    # Phase 7 B.9: closed-or-reviewed predicate sweeps both terminal states.
    closed = [t for t in trades_list if t.state in ("closed", "reviewed")]

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


# Brief §4.5: minimum trades-per-group for win-rate reporting. Below this
# threshold the breakdown suppresses win_rate to avoid small-sample noise.
_MIN_TRADES_FOR_WIN_RATE = 3


def compute_hypothesis_breakdown(
    *, trades: Iterable[Trade], exits: Iterable[_ExitShape],
) -> list[HypothesisBucket]:
    """Group closed trades by `hypothesis_label`; return one bucket per group.

    Closed-only is intentional: total_pnl and win_rate are realized-P&L
    measures and are undefined for trades still open. This matches the
    `compute_stats` frame, so the section reads as "what did each hypothesis
    *deliver*", not "what's been opened under each hypothesis".

    Win-rate definition (pinned by test): a winning trade has
    `realized_pnl > 0` (strict). Zero-P&L trades count toward `n_trades` but
    not toward wins — they sit between win and loss, the same convention as
    `compute_stats` (which uses `r > 0`).

    Ordering: the (no label) bucket appears first when non-empty (operator
    needs it surfaced regardless of count); labeled buckets follow in
    `n_trades DESC`, then `label ASC` for stable tie-breaking.
    """
    exits_list = list(exits)
    # Phase 7 B.9: closed-or-reviewed predicate sweeps both terminal states.
    closed = [t for t in trades if t.state in ("closed", "reviewed")]

    groups: dict[str | None, list[Trade]] = {}
    for t in closed:
        groups.setdefault(t.hypothesis_label, []).append(t)

    buckets: list[HypothesisBucket] = []
    for label, trades_in_group in groups.items():
        pnls = [_trade_pnl(t, exits_list) for t in trades_in_group]
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        win_rate: float | None
        win_rate = (wins / n) if n >= _MIN_TRADES_FOR_WIN_RATE else None
        buckets.append(HypothesisBucket(
            label=label, n_trades=n, total_pnl=sum(pnls), win_rate=win_rate,
        ))

    # (no label) first when present; rest ordered by count DESC, then label
    # ASC for deterministic display.
    no_label = [b for b in buckets if b.label is None]
    labeled = sorted(
        (b for b in buckets if b.label is not None),
        key=lambda b: (-b.n_trades, b.label or ""),
    )
    return no_label + labeled


# --- Hypothesis investigation progress (Phase 3e: backend brief §4.5) ---


@dataclass(frozen=True)
class HypothesisProgress:
    """One row of the per-hypothesis investigation-progress breakdown.

    Joins `hypothesis_registry` (status + target) with the closed-trade
    aggregate (current sample, mean R, win rate) and the tripwire signal.
    `mean_r_multiple` and `win_rate` are None when the bucket has zero
    samples; `win_rate` is also None when n < 3 (matches the existing
    free-text hypothesis breakdown's small-sample suppression).
    """
    hypothesis_id: int
    name: str
    status: str
    target_sample: int
    current_sample: int
    mean_r_multiple: float | None
    win_rate: float | None
    consecutive_max_loss_streak: int
    cumulative_loss: float
    consecutive_tripwire_fired: bool
    absolute_tripwire_fired: bool
    tripwire_fired: bool
    consecutive_loss_tripwire_threshold: int
    # Display-only count of OPEN trades whose hypothesis_label prefix-matches
    # this hypothesis. Does NOT count toward `current_sample` (which is
    # closed-trade evidence) or any tripwire arithmetic — open trades have
    # no realized R-multiple. Surfaces on the dashboard as "(+K in flight)"
    # decoration so the operator can see in-flight attribution. Default 0
    # for hand-constructed sites that omit the kwarg.
    in_flight_sample: int = 0


def compute_hypothesis_progress_breakdown(
    conn: sqlite3.Connection, *, starting_equity: float,
) -> list[HypothesisProgress]:
    """Return one `HypothesisProgress` per registered hypothesis.

    Includes paused/closed hypotheses (status carries over) so the
    journal review surfaces all four — operator can see at a glance
    which hypotheses are running, paused, or closed. Tripwire signals
    are computed for ALL hypotheses (even closed ones); the CLI render
    layer chooses how to display "tripwire fired but hypothesis closed."
    """
    # Local imports avoid pulling repo + recommendations modules into
    # `swing.journal.stats` import time (the journal stats module is
    # used in many test fixtures that don't need DB access).
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )
    from swing.recommendations.hypothesis import (
        _label_matches_hypothesis,
        compute_tripwire_status,
    )

    hypotheses = list_hypotheses(conn)
    closed = list_closed_trades(conn)
    open_trades = list_open_trades(conn)
    exits_by_trade: dict[int, list[_ExitShape]] = {}
    for e in _list_all_exitshape_via_fills(conn):
        exits_by_trade.setdefault(e.trade_id, []).append(e)

    rows: list[HypothesisProgress] = []
    for h in hypotheses:
        matched = [
            t for t in closed
            if _label_matches_hypothesis(t.hypothesis_label, h.name)
        ]
        n = len(matched)
        in_flight = sum(
            1 for t in open_trades
            if _label_matches_hypothesis(t.hypothesis_label, h.name)
        )
        if n > 0:
            rs = []
            for t in matched:
                es = exits_by_trade.get(t.id, [])
                share_weighted = sum(
                    e.r_multiple * (e.shares / t.initial_shares) for e in es
                )
                rs.append(share_weighted)
            mean_r: float | None = sum(rs) / n
        else:
            mean_r = None

        # Win-rate definition pinned in `compute_hypothesis_breakdown`
        # docstring: realized_pnl > 0 strict; suppressed when n < 3.
        if n >= _MIN_TRADES_FOR_WIN_RATE:
            wins = sum(
                1 for t in matched
                if sum(e.realized_pnl for e in exits_by_trade.get(t.id, [])) > 0
            )
            win_rate: float | None = wins / n
        else:
            win_rate = None

        tw = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=starting_equity,
        )
        rows.append(HypothesisProgress(
            hypothesis_id=h.id,
            name=h.name,
            status=h.status,
            target_sample=h.target_sample_size,
            current_sample=n,
            mean_r_multiple=mean_r,
            win_rate=win_rate,
            consecutive_max_loss_streak=tw.consecutive_max_loss_streak,
            cumulative_loss=tw.cumulative_loss,
            consecutive_tripwire_fired=tw.consecutive_tripwire_fired,
            absolute_tripwire_fired=tw.absolute_tripwire_fired,
            tripwire_fired=tw.any_tripwire_fired,
            consecutive_loss_tripwire_threshold=h.consecutive_loss_tripwire,
            in_flight_sample=in_flight,
        ))
    return rows


def render_hypothesis_progress(rows: Iterable[HypothesisProgress]) -> str:
    """Render the journal-review "Hypothesis investigation progress"
    section. Plain-text, deterministic ordering (registry order).

    Tripwire-fired rows annotate inline with the firing reason — operator
    gets the actionable signal in the same line as the sample fraction,
    not buried in a separate section.
    """
    lines = ["", "## Hypothesis investigation progress"]
    for r in rows:
        suffix_bits: list[str] = []
        if r.tripwire_fired:
            firing: list[str] = []
            if r.consecutive_tripwire_fired:
                firing.append(
                    f"{r.consecutive_max_loss_streak} consecutive -1R "
                    f"(threshold {r.consecutive_loss_tripwire_threshold})"
                )
            if r.absolute_tripwire_fired:
                firing.append(
                    f"absolute loss ${-r.cumulative_loss:.2f}"
                )
            suffix_bits.append(
                f"TRIPWIRE FIRED — {'; '.join(firing)}; "
                "recommend escape evaluation"
            )
        status_label = r.status if not suffix_bits else f"{r.status}, {suffix_bits[0]}"
        line = (
            f"- {r.name} ({status_label}): "
            f"{r.current_sample} / {r.target_sample} samples"
        )
        extras: list[str] = []
        if r.mean_r_multiple is not None:
            extras.append(f"mean R: {r.mean_r_multiple:+.2f}")
        if r.win_rate is not None:
            extras.append(f"win rate {r.win_rate * 100:.1f}%")
        if r.cumulative_loss != 0.0 and not r.tripwire_fired:
            extras.append(f"cumulative P&L ${r.cumulative_loss:+.2f}")
        if extras:
            line += "; " + "; ".join(extras)
        lines.append(line)
    return "\n".join(lines)
