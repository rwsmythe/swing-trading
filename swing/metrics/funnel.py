"""Spec §3.6 identification-vs-trade-funnel metric computations (plan §G T-D.5).

Per-pipeline-run aggregates measuring the divergence between candidate
identification rate (A+ + watch) and trade-take rate. Plus a 30-trading-
session rolling trend ending at backward-looking
``last_completed_session(now)`` (plan §A.15 + §G T-D.5 LOCK).

Per spec §3.6 R1 Minor #2 LOCK + plan §G T-D.5 acceptance: V1 surfaces
``watch_identifications_per_run`` + ``watch_trades_taken_per_run`` ONLY —
NO ``watch_take_rate_per_run`` field (banked as V2 candidate).

Per spec §3.6 + §A.20 + plan §G T-D.5: ``aplus_take_rate_per_run`` is
suppressed (returns None + suppressed_text) when ``aplus_identifications_per_run
== 0`` (avoids NaN / +inf / 0.0 ambiguity).

Per plan §A.0.1 (Codex R2 Major #4 + §G T-D.5): trend points compute
``aplus_trades_taken_per_run`` against CURRENT trade state — a trade with
``trade_origin='pipeline_aplus'`` AND ``pre_trade_locked_at`` matching the
run's session date is counted even if the trade has since closed.
Historical reconstruction (V2) would replay state per-run; V1 uses
current-state proxy.

Per plan §G T-D.5 + Codex R5 Minor #1 / R6 Minor #1 list-mirror: the 30-
session window is derived via
``exchange_calendars.get_calendar('XNYS').sessions_window(pd.Timestamp(end),
-30)`` (off-by-one defense — `end` is inclusive, returns 30 most-recent
sessions).
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from swing.evaluation.dates import last_completed_session

# Spec §3.6 + §4.6: trend window in TRADING sessions (NOT calendar days).
TRADING_DAYS_WINDOW: int = 30

# Spec §4.6 + plan §G T-D.5 acceptance: trend rendered once ≥10 runs.
TREND_MIN_RUNS: int = 10

# Spec §A.20 + plan §G T-D.5 + dispatch brief §0.11 BINDING: verbatim text
# for the zero-A+-identifications suppression case.
APLUS_TAKE_RATE_ZERO_APLUS_SUPPRESSED_TEXT: str = (
    "N/A — 0 A+ identifications this run"
)

# Spec §3.6: A+ trades are those with origin='pipeline_aplus'.
APLUS_TRADE_ORIGIN: str = "pipeline_aplus"

# Spec §3.6: watch trades cover both hyp-recs + manual watch origins.
WATCH_TRADE_ORIGINS: tuple[str, ...] = (
    "pipeline_watch_hyp_recs",
    "pipeline_watch_manual",
)


@dataclass(frozen=True)
class IdentificationFunnelPoint:
    """One per-pipeline-run aggregate (spec §3.6 verbatim metrics).

    Note: NO ``watch_take_rate_per_run`` field per spec §3.6 R1 Minor #2
    LOCK + plan §G T-D.5 acceptance (banked as V2 candidate).
    """

    pipeline_run_id: int
    run_date: str  # ISO YYYY-MM-DD — session anchor for the run
    aplus_identifications_per_run: int
    aplus_trades_taken_per_run: int
    aplus_take_rate_per_run: float | None  # PROPORTION [0, 1]
    aplus_take_rate_suppressed_text: str | None
    watch_identifications_per_run: int
    watch_trades_taken_per_run: int

    def __post_init__(self) -> None:
        if self.pipeline_run_id < 1:
            raise ValueError(
                f"pipeline_run_id must be >= 1; got {self.pipeline_run_id!r}"
            )
        for fname in (
            "aplus_identifications_per_run", "aplus_trades_taken_per_run",
            "watch_identifications_per_run", "watch_trades_taken_per_run",
        ):
            val = getattr(self, fname)
            if val < 0:
                raise ValueError(f"{fname} must be >= 0; got {val!r}")
        if self.aplus_take_rate_per_run is not None:
            if not math.isfinite(self.aplus_take_rate_per_run):
                raise ValueError(
                    "aplus_take_rate_per_run must be finite; got "
                    f"{self.aplus_take_rate_per_run!r}"
                )
            if self.aplus_take_rate_per_run < 0.0:
                raise ValueError(
                    "aplus_take_rate_per_run must be >= 0; got "
                    f"{self.aplus_take_rate_per_run!r}"
                )
            # Codex R1 Major #3 fix: NO upper bound on the rate. Values >1
            # are honest signals of data-quality / attribution anomalies
            # (e.g., trade.origin=pipeline_aplus on a session where the run
            # emitted zero A+ identifications). Suppressing OR clamping
            # would hide the anomaly.


@dataclass(frozen=True)
class IdentificationFunnelResult:
    """Result of :func:`compute_identification_funnel` per plan §G T-D.5."""

    asof_date: str  # ISO date — page-level last_completed_session(now)
    trend_window_sessions: int  # informational copy of `run_window` arg
    trend_runs: tuple[IdentificationFunnelPoint, ...]
    trend_suppressed: bool
    trend_suppressed_text: str | None

    def __post_init__(self) -> None:
        if not self.asof_date:
            raise ValueError(
                f"asof_date must be non-empty; got {self.asof_date!r}"
            )
        if self.trend_window_sessions < 1:
            raise ValueError(
                "trend_window_sessions must be >= 1; got "
                f"{self.trend_window_sessions!r}"
            )


def _session_dates_in_window(
    *, end_session: date, window: int,
) -> list[str]:
    """Return ascending ISO-date list of the ``window`` most-recent NYSE
    trading sessions ending at ``end_session`` (inclusive).

    Plan §G T-D.5 + dispatch brief §0.13 BINDING: off-by-one defense via
    ``cal.sessions_window(pd.Timestamp(end), -window)`` — returns ``window``
    sessions inclusive of ``end``. Discriminating test seeds 31 sessions +
    asserts the 31st (oldest) is EXCLUDED.
    """
    import exchange_calendars
    import pandas as pd

    cal = exchange_calendars.get_calendar("XNYS")
    sessions = cal.sessions_window(pd.Timestamp(end_session), -window)
    return sorted({ts.date().isoformat() for ts in sessions})


def _compute_per_run_aggregate(
    conn: sqlite3.Connection,
    *,
    pipeline_run_id: int,
    evaluation_run_id: int | None,
    run_session_date: str,
) -> tuple[int, int, int, int]:
    """Return ``(aplus_id, aplus_taken, watch_id, watch_taken)`` per spec §3.6.

    Per plan §A.0.1: trade counts use CURRENT trade state; pre_trade_locked_at
    session-date is the join key. ``evaluation_run_id`` is None when the
    pipeline_run row lacks an FK (legacy pre-Phase-2 rows); identifications
    then default to 0.
    """
    if evaluation_run_id is not None:
        a_id_row = conn.execute(
            "SELECT COUNT(*) FROM candidates "
            "WHERE evaluation_run_id = ? AND bucket = 'aplus'",
            (evaluation_run_id,),
        ).fetchone()
        w_id_row = conn.execute(
            "SELECT COUNT(*) FROM candidates "
            "WHERE evaluation_run_id = ? AND bucket = 'watch'",
            (evaluation_run_id,),
        ).fetchone()
        aplus_id = int(a_id_row[0])
        watch_id = int(w_id_row[0])
    else:
        aplus_id = 0
        watch_id = 0
    # Plan §A.0.1: count CURRENT trades whose pre_trade_locked_at session
    # equals the run's session date.
    a_taken_row = conn.execute(
        "SELECT COUNT(*) FROM trades "
        "WHERE trade_origin = ? "
        "AND pre_trade_locked_at IS NOT NULL "
        "AND substr(pre_trade_locked_at, 1, 10) = ?",
        (APLUS_TRADE_ORIGIN, run_session_date),
    ).fetchone()
    aplus_taken = int(a_taken_row[0])

    placeholders = ",".join("?" for _ in WATCH_TRADE_ORIGINS)
    w_taken_row = conn.execute(
        f"SELECT COUNT(*) FROM trades "
        f"WHERE trade_origin IN ({placeholders}) "
        f"AND pre_trade_locked_at IS NOT NULL "
        f"AND substr(pre_trade_locked_at, 1, 10) = ?",
        (*WATCH_TRADE_ORIGINS, run_session_date),
    ).fetchone()
    watch_taken = int(w_taken_row[0])
    return (aplus_id, aplus_taken, watch_id, watch_taken)


def compute_identification_funnel(
    conn: sqlite3.Connection,
    *,
    asof_date: date | None = None,
    run_window: int = TRADING_DAYS_WINDOW,
) -> IdentificationFunnelResult:
    """Plan §G Task D.5 + spec §3.6.

    ``asof_date`` defaults to backward-looking
    ``last_completed_session(datetime.now())`` per plan §A.15 BINDING.
    """
    if asof_date is None:
        asof_date = last_completed_session(datetime.now())
    session_dates = _session_dates_in_window(
        end_session=asof_date, window=run_window,
    )
    if not session_dates:
        return IdentificationFunnelResult(
            asof_date=asof_date.isoformat(),
            trend_window_sessions=run_window,
            trend_runs=(),
            trend_suppressed=True,
            trend_suppressed_text=(
                f"[funnel_trend: 0 trading sessions in window; "
                f"need: ≥{TREND_MIN_RUNS}]"
            ),
        )

    placeholders = ",".join("?" for _ in session_dates)
    # Plan §G T-D.5 line 1498 BINDING: `pipeline_runs.started_ts.date()`
    # matched against the session list — NOT data_asof_date. Caught at
    # Codex R1 Major #2. Window inclusion + trade-locked_at match both
    # anchor on the run's start-timestamp date.
    rows = conn.execute(
        f"SELECT id, started_ts, data_asof_date, evaluation_run_id "
        f"FROM pipeline_runs "
        f"WHERE state = 'complete' "
        f"AND substr(started_ts, 1, 10) IN ({placeholders}) "
        f"ORDER BY started_ts ASC, id ASC",
        session_dates,
    ).fetchall()

    points: list[IdentificationFunnelPoint] = []
    for run_id, started_ts, _data_asof, eval_id in rows:
        run_session_date = str(started_ts)[:10]
        aplus_id, aplus_taken, watch_id, watch_taken = (
            _compute_per_run_aggregate(
                conn,
                pipeline_run_id=int(run_id),
                evaluation_run_id=int(eval_id) if eval_id is not None else None,
                run_session_date=run_session_date,
            )
        )
        if aplus_id <= 0:
            take_rate: float | None = None
            suppressed: str | None = (
                APLUS_TAKE_RATE_ZERO_APLUS_SUPPRESSED_TEXT
            )
        else:
            # Codex R1 Major #3 fix: do NOT clamp the rate to [0, 1].
            # An honest >1.0 surfaces data-quality anomalies (a trade with
            # origin='pipeline_aplus' on a session where 0 A+ identifications
            # were emitted — operator override OR identification-vs-trade
            # attribution defect). Validate non-negative + finite only.
            take_rate = aplus_taken / aplus_id
            suppressed = None
        points.append(
            IdentificationFunnelPoint(
                pipeline_run_id=int(run_id),
                run_date=run_session_date,
                aplus_identifications_per_run=aplus_id,
                aplus_trades_taken_per_run=aplus_taken,
                aplus_take_rate_per_run=take_rate,
                aplus_take_rate_suppressed_text=suppressed,
                watch_identifications_per_run=watch_id,
                watch_trades_taken_per_run=watch_taken,
            )
        )

    suppressed_trend = len(points) < TREND_MIN_RUNS
    suppressed_text = (
        f"[funnel_trend: n too low "
        f"(current: {len(points)}, need: ≥{TREND_MIN_RUNS})]"
        if suppressed_trend else None
    )
    return IdentificationFunnelResult(
        asof_date=asof_date.isoformat(),
        trend_window_sessions=run_window,
        trend_runs=tuple(points),
        trend_suppressed=suppressed_trend,
        trend_suppressed_text=suppressed_text,
    )
