"""Spec §3.4 capital-friction metric computations (plan §G Task D.1).

Computes 6 spec §3.4 metrics + the dynamic PROVISIONAL/LIVE badge per
plan §A.6 + plan §A.19 + plan §A.0.1 + plan §A.15:

- ``risk_feasibility_blocked_rate`` per-run point estimate (spec §3.4 +
  §5.5 per-run special case + §A.19 set-membership guard against
  missing-or-extra criterion names).
- ``current_capital_utilization_pct`` point-in-time (PERCENT; PROVISIONAL
  fallback to ``capital_floor_constant_dollars`` when no snapshot).
- ``current_portfolio_heat_pct`` point-in-time (PERCENT; PROVISIONAL).
- ``capital_cycle_time_days`` cohort mean over closed trades.
- ``concurrent_open_positions`` point-in-time count.
- ``capital_feasibility_pressure_index`` composite (proportion form).

Multi-run trend (suppressed at <5 runs per spec §4.4):
- best-effort against CURRENT trade state per plan §A.0.1 (true historical
  reconstruction deferred to V2). Each trend point still computes
  ``concurrent_open_positions`` via the ``pre_trade_locked_at <= started_ts``
  open-at-run-time proxy (plan §A.0.1 Codex R3 Major #2 relocation).

Session-anchor (plan §A.15 BINDING):
- caller passes ``asof_date`` (backward-looking ``last_completed_session(now)``);
  helper itself is anchor-agnostic. Forward-looking
  ``action_session_for_run(now)`` MUST NOT be used here (would create the
  session-anchor read/write mismatch family per CLAUDE.md gotcha).

Per spec §5.5 per-pipeline-run special case: ``risk_feasibility_blocked_rate``
is a per-run point estimate even at run #1. Multi-run trend lines apply
Class A policy on trend-window-n; suppression at <5 runs.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from swing.evaluation.criteria import (
    adr,
    ma_stack_short,
    orderliness,
    prior_trend,
    proximity,
    pullback,
    tightness,
    trend_template,
    vcp,
)
from swing.evaluation.criteria.risk_feasibility import NAME
from swing.metrics.equity_resolver import (
    resolve_live_capital_denominator_dollars,
)
from swing.metrics.policy import read_live_policy

_LOG = logging.getLogger(__name__)

# Spec §4.4 multi-run trend threshold (suppress when fewer than 5 runs).
TREND_MIN_RUNS: int = 5

# Trend window matches Sub-bundle D's identification-funnel (plan §G T-D.5
# 30-session window). Capital-friction inherits the same window for
# operator-readability parity across the 2 trend surfaces in Sub-bundle D.
TRADING_DAYS_WINDOW: int = 30


# Plan §A.19 BINDING: enumerate the 18 expected criterion_name values from
# the shipped evaluators. The set-membership guard rejects candidates
# missing any expected name (Codex R4 Major #1 + #2 fix sequence). Imports
# the *.NAME / *.STACK_NAME / *.RISING_NAME / *.CHECK_NAMES constants
# directly to avoid string-literal drift.
EXPECTED_CRITERIA_NAMES: frozenset[str] = frozenset({
    adr.NAME,
    ma_stack_short.STACK_NAME,
    ma_stack_short.RISING_NAME,
    orderliness.NAME,
    prior_trend.NAME,
    proximity.NAME,
    pullback.NAME,
    NAME,  # risk_feasibility.NAME — imported as constant per plan §A.19.
    tightness.NAME,
    vcp.NAME,
    *trend_template.CHECK_NAMES,
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CapitalFrictionTrendPoint:
    """One historical trend-point per ``pipeline_runs`` row in the
    trend window.

    Per plan §A.0.1: historical points compute against CURRENT trade
    state (best-effort) for capital fields; ``concurrent_open_positions``
    uses the ``pre_trade_locked_at <= started_ts AND (last_fill_at IS NULL
    OR last_fill_at >= started_ts)`` proxy (Codex R3 Major #2 relocation
    to capital-friction surface).
    """

    pipeline_run_id: int
    run_date: str  # ISO date — session date the run anchored to
    risk_feasibility_blocked_rate: float | None
    risk_feasibility_blocked_rate_suppressed_text: str | None
    current_capital_utilization_pct: float | None
    current_portfolio_heat_pct: float | None
    concurrent_open_positions: int
    capital_feasibility_pressure_index: float | None
    capital_denominator_dollars: float
    capital_denominator_badge: Literal["PROVISIONAL", "LIVE"]
    capital_denominator_badge_text: str  # Plan §A.6 line 233 (Codex R1 M#1)

    def __post_init__(self) -> None:
        if self.pipeline_run_id < 1:
            raise ValueError(
                f"pipeline_run_id must be >= 1; got {self.pipeline_run_id!r}"
            )
        if self.concurrent_open_positions < 0:
            raise ValueError(
                "concurrent_open_positions must be >= 0; got "
                f"{self.concurrent_open_positions!r}"
            )
        for fname in (
            "risk_feasibility_blocked_rate",
            "current_capital_utilization_pct",
            "current_portfolio_heat_pct",
            "capital_feasibility_pressure_index",
        ):
            val = getattr(self, fname)
            if val is not None and not math.isfinite(val):
                raise ValueError(
                    f"{fname} must be None or finite (NaN/inf rejected); "
                    f"got {val!r}"
                )
        if not math.isfinite(self.capital_denominator_dollars):
            raise ValueError(
                "capital_denominator_dollars must be finite (NaN/inf "
                f"rejected); got {self.capital_denominator_dollars!r}"
            )
        if self.capital_denominator_dollars <= 0:
            raise ValueError(
                "capital_denominator_dollars must be > 0; got "
                f"{self.capital_denominator_dollars!r}"
            )
        if self.capital_denominator_badge not in ("PROVISIONAL", "LIVE"):
            raise ValueError(
                "capital_denominator_badge must be 'PROVISIONAL' or 'LIVE'; "
                f"got {self.capital_denominator_badge!r}"
            )
        if not self.capital_denominator_badge_text:
            raise ValueError(
                "capital_denominator_badge_text must be non-empty "
                "(plan §A.6 line 233 BINDING)"
            )


@dataclass(frozen=True)
class CapitalFrictionResult:
    """Result of :func:`compute_capital_friction` per plan §G T-D.1."""

    asof_date: str  # ISO YYYY-MM-DD per plan §A.15 lock

    # Point-in-time
    current_capital_utilization_pct: float | None  # PERCENT
    current_portfolio_heat_pct: float | None  # PERCENT
    concurrent_open_positions: int
    capital_cycle_time_days: float | None  # cohort mean over closed trades

    # Per-run snapshot (most recent completed pipeline_run)
    latest_run_id: int | None
    risk_feasibility_blocked_rate: float | None  # PROPORTION [0, 1]
    risk_feasibility_blocked_rate_suppressed_text: str | None
    capital_feasibility_pressure_index: float | None  # PROPORTION

    # PROVISIONAL/LIVE dynamic badge (plan §A.6)
    capital_denominator_dollars: float
    capital_denominator_badge: Literal["PROVISIONAL", "LIVE"]
    # Plan §A.6 line 233 BINDING — fallback-explanation text rendered
    # inline alongside the metric value (Codex R1 Major #1 fix). Format:
    #   PROVISIONAL → "PROVISIONAL: $7,500 floor used as live-capital
    #                  fallback (no snapshot ≤ {asof_date})"
    #   LIVE        → "LIVE: $X.XX equity from account_equity_snapshots
    #                  on-or-before {asof_date}"
    capital_denominator_badge_text: str

    # Multi-run trend (spec §4.4; plan §A.0.1)
    trend_runs: tuple[CapitalFrictionTrendPoint, ...]
    trend_suppressed: bool
    trend_suppressed_text: str | None

    def __post_init__(self) -> None:
        if not self.asof_date:
            raise ValueError(
                f"asof_date must be non-empty; got {self.asof_date!r}"
            )
        if self.concurrent_open_positions < 0:
            raise ValueError(
                "concurrent_open_positions must be >= 0; got "
                f"{self.concurrent_open_positions!r}"
            )
        for fname in (
            "current_capital_utilization_pct",
            "current_portfolio_heat_pct",
            "capital_cycle_time_days",
            "risk_feasibility_blocked_rate",
            "capital_feasibility_pressure_index",
        ):
            val = getattr(self, fname)
            if val is not None and not math.isfinite(val):
                raise ValueError(
                    f"{fname} must be None or finite (NaN/inf rejected); "
                    f"got {val!r}"
                )
        if not math.isfinite(self.capital_denominator_dollars):
            raise ValueError(
                "capital_denominator_dollars must be finite; got "
                f"{self.capital_denominator_dollars!r}"
            )
        if self.capital_denominator_dollars <= 0:
            raise ValueError(
                "capital_denominator_dollars must be > 0; got "
                f"{self.capital_denominator_dollars!r}"
            )
        if self.capital_denominator_badge not in ("PROVISIONAL", "LIVE"):
            raise ValueError(
                "capital_denominator_badge must be 'PROVISIONAL' or 'LIVE'; "
                f"got {self.capital_denominator_badge!r}"
            )
        if not self.capital_denominator_badge_text:
            raise ValueError(
                "capital_denominator_badge_text must be non-empty (plan §A.6 "
                "line 233 BINDING)"
            )
        if (
            self.risk_feasibility_blocked_rate is not None
            and not (0.0 <= self.risk_feasibility_blocked_rate <= 1.0)
        ):
            raise ValueError(
                "risk_feasibility_blocked_rate must be in [0, 1]; got "
                f"{self.risk_feasibility_blocked_rate!r}"
            )


# ---------------------------------------------------------------------------
# risk_feasibility_blocked_rate per plan §A.19
# ---------------------------------------------------------------------------

def _compute_risk_feasibility_blocked_rate(
    conn: sqlite3.Connection, *, evaluation_run_id: int,
) -> tuple[float | None, str | None]:
    """Plan §A.19 + spec §3.4: rate of risk_feasibility-blocked candidates
    among would-have-qualified candidates in the run.

    Returns ``(rate, suppressed_text)`` — ``rate`` is None when suppressed
    (zero qualifying candidates this run); ``suppressed_text`` is the
    operator-facing placeholder when None.

    Plan §A.19 BINDING:
    - Numerator restricted to ``failed risk_feasibility AND all other
      criteria pass`` (Codex R1 Major #1).
    - Denominator: ``all other criteria pass AND risk_feasibility result IN
      ('pass', 'fail')`` — ``'na'`` excludes from BOTH sides (Codex R4
      Major #3 + R2 Major #3).
    - Set-membership guard against missing-or-extra criterion names
      (Codex R4 Major #1 + #2): candidates missing any of the 18 expected
      names → EXCLUDED both sides + WARNING log. Candidates with all 18
      expected + extras → INCLUDED + INFO log.
    """
    # Step 1: load all criterion rows for the run's candidates.
    rows = conn.execute(
        "SELECT cc.candidate_id, cc.criterion_name, cc.result "
        "FROM candidate_criteria cc "
        "JOIN candidates c ON c.id = cc.candidate_id "
        "WHERE c.evaluation_run_id = ?",
        (evaluation_run_id,),
    ).fetchall()
    if not rows:
        return (None, "N/A — 0 would-have-qualified candidates this run")

    # Group by candidate.
    by_candidate: dict[int, dict[str, str]] = {}
    for cid, cname, res in rows:
        by_candidate.setdefault(cid, {})[cname] = res

    eligible_candidates: list[int] = []
    for cid, names_to_results in by_candidate.items():
        actual = frozenset(names_to_results.keys())
        missing = EXPECTED_CRITERIA_NAMES - actual
        if missing:
            _LOG.warning(
                "risk_feasibility_blocked_rate: candidate_id=%d missing "
                "expected criteria %s; excluding from rate computation",
                cid, sorted(missing),
            )
            continue
        extras = actual - EXPECTED_CRITERIA_NAMES
        if extras:
            _LOG.info(
                "risk_feasibility_blocked_rate: candidate_id=%d has "
                "unexpected criterion names %s; included anyway",
                cid, sorted(extras),
            )
        eligible_candidates.append(cid)

    # Step 2: apply spec §3.4 + §A.19 numerator/denominator predicates.
    numerator = 0
    denominator = 0
    for cid in eligible_candidates:
        results = by_candidate[cid]
        risk_result = results.get(NAME)
        if risk_result not in ("pass", "fail"):
            # 'na' on risk_feasibility → excluded both sides per R4 M#3.
            continue
        # Predicate: ALL OTHER (non-risk) criteria result == 'pass'.
        other_pass = all(
            results[n] == "pass"
            for n in EXPECTED_CRITERIA_NAMES
            if n != NAME
        )
        if not other_pass:
            # Not "would-have-qualified except risk" — excluded denom.
            continue
        denominator += 1
        if risk_result == "fail":
            numerator += 1

    if denominator == 0:
        return (None, "N/A — 0 would-have-qualified candidates this run")
    rate = numerator / denominator
    # Defensive bounds clamp (mathematically already in [0, 1] given
    # numerator <= denominator; explicit min/max for safety).
    rate = max(0.0, min(1.0, rate))
    return (rate, None)


# ---------------------------------------------------------------------------
# Live-state aggregates (current trade state)
# ---------------------------------------------------------------------------

_OPEN_STATES_SQL: str = "('entered', 'managing', 'partial_exited')"


def _count_concurrent_open_positions(conn: sqlite3.Connection) -> int:
    """Spec §3.4: count of trades in state ∈ open-states."""
    row = conn.execute(
        f"SELECT COUNT(*) FROM trades WHERE state IN {_OPEN_STATES_SQL}"
    ).fetchone()
    return int(row[0])


def _sum_open_position_exposure_dollars(
    conn: sqlite3.Connection,
) -> float:
    """Spec §3.4 numerator: sum(current_avg_cost * current_size) over open
    trades. ``current_avg_cost`` may be NULL for entered-no-fill trades;
    fall back to entry_price."""
    rows = conn.execute(
        "SELECT COALESCE(current_avg_cost, entry_price), current_size "
        f"FROM trades WHERE state IN {_OPEN_STATES_SQL}"
    ).fetchall()
    total = 0.0
    for avg_cost, size in rows:
        if avg_cost is None or size is None:
            continue
        total += float(avg_cost) * float(size)
    return total


def _sum_open_position_heat_dollars(conn: sqlite3.Connection) -> float:
    """Spec §3.4: sum of per-position heat contributions ``max(0,
    (current_avg_cost - current_stop) * current_size)`` over open trades.
    """
    rows = conn.execute(
        "SELECT COALESCE(current_avg_cost, entry_price), current_size, "
        "current_stop "
        f"FROM trades WHERE state IN {_OPEN_STATES_SQL}"
    ).fetchall()
    total = 0.0
    for avg_cost, size, stop in rows:
        if avg_cost is None or size is None or stop is None:
            continue
        delta = float(avg_cost) - float(stop)
        if delta <= 0:
            continue
        total += delta * float(size)
    return total


def _capital_cycle_time_days(conn: sqlite3.Connection) -> float | None:
    """Spec §3.4: mean(last_fill_at - pre_trade_locked_at) over closed
    cohort, in days. Returns None when no closed trades."""
    rows = conn.execute(
        "SELECT pre_trade_locked_at, last_fill_at FROM trades "
        "WHERE state IN ('closed', 'reviewed') "
        "AND pre_trade_locked_at IS NOT NULL "
        "AND last_fill_at IS NOT NULL AND pre_trade_locked_at <> '' "
        "AND last_fill_at <> ''"
    ).fetchall()
    if not rows:
        return None
    deltas: list[float] = []
    for locked_at, last_fill in rows:
        try:
            start = datetime.fromisoformat(locked_at)
            end = datetime.fromisoformat(last_fill)
        except ValueError:
            continue
        deltas.append((end - start).total_seconds() / 86400.0)
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def _count_open_at_run(
    conn: sqlite3.Connection, *, started_ts: str,
) -> int:
    """Count trades that were open at a historical run's start instant
    (Issue #3 state-based predicate; spec
    ``docs/superpowers/specs/2026-06-07-count-open-at-run-predicate-design.md``).

    A trade was open during run R iff it was entered at/before ``started_ts``
    (``pre_trade_locked_at <= started_ts``) AND not yet closed at that
    instant. "Not yet closed" keys on STATE, not on a fill-derived timestamp:

    - a NON-terminal trade (``entered``/``managing``/``partial_exited``) was
      open at any R after its entry, so it counts whenever entered <=
      ``started_ts`` — regardless of ``last_fill_at`` (which, for a still-open
      trade, is its ENTRY fill, < ``started_ts``);
    - a TERMINAL trade (``closed``/``reviewed``) was open at R iff it closed
      at/after ``started_ts``, which by G1 is ``last_fill_at >= started_ts``
      (``>=`` inclusive per OQ-2; a NULL/empty close ts degrades to count).

    The prior predicate applied the ``last_fill_at >= started_ts`` terminal
    clause to EVERY trade, wrongly excluding a still-open pre-run trade whose
    only fill is its entry (Issue #3: SKYT, capital-friction
    ``concurrent_open_positions = 0`` for Run #89 despite an open position).

    Best-effort caveats (spec §2 G1/G4): ``last_fill_at`` is the MAX fill
    datetime, a valid close proxy for well-formed terminal rows; a
    correction-path or legacy ``last_fill_at`` in a divergent shape may sort
    lexicographically out of chronological order. The predicate is pure SQL
    string comparison (no parse), so a malformed value degrades safely (the
    one row is mis-ordered, never an exception) — see test E11.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM trades "
        "WHERE pre_trade_locked_at IS NOT NULL "
        "AND pre_trade_locked_at <> '' "
        "AND pre_trade_locked_at <= ? "
        "AND (state NOT IN ('closed', 'reviewed') "
        "     OR last_fill_at IS NULL OR last_fill_at = '' "
        "     OR last_fill_at >= ?)",
        (started_ts, started_ts),
    ).fetchone()
    return int(row[0])


# ---------------------------------------------------------------------------
# Trend assembly
# ---------------------------------------------------------------------------

def _list_runs_in_trend_window(
    conn: sqlite3.Connection, *, asof_date: date,
) -> list[tuple[int, str, str, int | None]]:
    """Return ``[(pipeline_run_id, started_ts, data_asof_date,
    evaluation_run_id)]`` for completed runs within the trend window.

    Window: 30 trading sessions ending at ``asof_date`` (inclusive of
    ``asof_date``; backward-looking). Uses ``exchange_calendars`` per plan
    §G T-D.5 off-by-one defense lock.
    """
    import exchange_calendars
    import pandas as pd

    cal = exchange_calendars.get_calendar("XNYS")
    sessions = cal.sessions_window(
        pd.Timestamp(asof_date), -TRADING_DAYS_WINDOW,
    )
    if len(sessions) == 0:
        return []
    # sessions_window with negative count returns in either order depending
    # on calendar version; normalize to ascending ISO-string list.
    session_dates = sorted({ts.date().isoformat() for ts in sessions})
    placeholders = ",".join("?" for _ in session_dates)
    # Plan §G T-D.5 + §A.6 line 231 BINDING: match by
    # ``substr(started_ts, 1, 10)`` NOT ``data_asof_date``. The two differ
    # on weekend/holiday runs + the plan pins the run's start-timestamp
    # date as the session anchor for trend windowing.
    rows = conn.execute(
        f"SELECT id, started_ts, data_asof_date, evaluation_run_id "
        f"FROM pipeline_runs "
        f"WHERE state = 'complete' "
        f"AND substr(started_ts, 1, 10) IN ({placeholders}) "
        f"ORDER BY started_ts ASC, id ASC",
        session_dates,
    ).fetchall()
    return [(int(r[0]), str(r[1]), str(r[2]),
             int(r[3]) if r[3] is not None else None)
            for r in rows]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def format_capital_denominator_badge_text(
    *,
    badge: Literal["PROVISIONAL", "LIVE"],
    denominator_dollars: float,
    asof_date: date | str,
) -> str:
    """Plan §A.6 line 233 BINDING text format (Codex R1 Major #1).

    PROVISIONAL: "PROVISIONAL: $X,XXX floor used as live-capital fallback
                  (no snapshot ≤ {asof_date})"
    LIVE:        "LIVE: $X,XXX equity from account_equity_snapshots
                  on-or-before {asof_date}"
    """
    asof_str = asof_date.isoformat() if isinstance(asof_date, date) else str(asof_date)
    if badge == "PROVISIONAL":
        return (
            f"PROVISIONAL: ${denominator_dollars:,.2f} floor used as "
            f"live-capital fallback (no snapshot ≤ {asof_str})"
        )
    return (
        f"LIVE: ${denominator_dollars:,.2f} equity from "
        f"account_equity_snapshots on-or-before {asof_str}"
    )


def compute_capital_friction(
    conn: sqlite3.Connection, *, asof_date: date,
) -> CapitalFrictionResult:
    """Plan §G Task D.1 + spec §3.4.

    ``asof_date`` MUST be backward-looking (e.g., ``last_completed_session(
    datetime.now())``) per plan §A.15 BINDING + §I.13 round-trip discipline.
    """
    live_policy = read_live_policy(conn)
    denom_dollars, denom_badge = resolve_live_capital_denominator_dollars(
        conn, asof_date=asof_date, at_trade_time_policy=live_policy,
    )

    # Point-in-time aggregates against CURRENT trade state.
    open_count = _count_concurrent_open_positions(conn)
    exposure = _sum_open_position_exposure_dollars(conn)
    heat = _sum_open_position_heat_dollars(conn)
    util_pct = (exposure / denom_dollars) * 100.0 if denom_dollars > 0 else None
    heat_pct = (heat / denom_dollars) * 100.0 if denom_dollars > 0 else None
    cycle_days = _capital_cycle_time_days(conn)

    # Latest pipeline_run snapshot for per-run blocked_rate.
    # Codex R3 m#1: deterministic ordering on tied started_ts via id DESC.
    latest = conn.execute(
        "SELECT id, evaluation_run_id FROM pipeline_runs "
        "WHERE state = 'complete' AND evaluation_run_id IS NOT NULL "
        "ORDER BY started_ts DESC, id DESC LIMIT 1"
    ).fetchone()
    if latest is not None:
        latest_run_id = int(latest[0])
        latest_eval_id = int(latest[1])
        blocked_rate, blocked_suppr = _compute_risk_feasibility_blocked_rate(
            conn, evaluation_run_id=latest_eval_id,
        )
    else:
        latest_run_id = None
        blocked_rate = None
        blocked_suppr = None

    # Composite pressure index — None if either input None.
    if blocked_rate is not None and util_pct is not None:
        pressure = blocked_rate * (util_pct / 100.0)
    else:
        pressure = None

    # Multi-run trend
    runs_in_window = _list_runs_in_trend_window(conn, asof_date=asof_date)
    trend_points: list[CapitalFrictionTrendPoint] = []
    for run_id, started_ts, data_asof, eval_id in runs_in_window:
        if eval_id is not None:
            r_rate, r_suppr = _compute_risk_feasibility_blocked_rate(
                conn, evaluation_run_id=eval_id,
            )
        else:
            r_rate, r_suppr = (
                None,
                "N/A — 0 would-have-qualified candidates this run",
            )
        # Per §A.0.1 + plan §A.6 line 231: utilization + heat at historical
        # run use CURRENT trade state. Denominator resolved at the run's
        # ACTUAL start-timestamp date (NOT data_asof_date) per plan §A.6
        # §4.6 LOCK — caught at Codex R1 Major #2.
        try:
            run_asof = date.fromisoformat(started_ts[:10])
        except (ValueError, IndexError):
            # Codex R1 minor #2 fix: rather than silently fall back to
            # page asof (and risk a misleading LIVE/PROVISIONAL badge),
            # suppress the denominator-dependent fields for the row.
            trend_points.append(
                CapitalFrictionTrendPoint(
                    pipeline_run_id=run_id,
                    run_date=data_asof,
                    risk_feasibility_blocked_rate=r_rate,
                    risk_feasibility_blocked_rate_suppressed_text=r_suppr,
                    current_capital_utilization_pct=None,
                    current_portfolio_heat_pct=None,
                    concurrent_open_positions=_count_open_at_run(
                        conn, started_ts=started_ts,
                    ),
                    capital_feasibility_pressure_index=None,
                    capital_denominator_dollars=denom_dollars,
                    capital_denominator_badge=denom_badge,
                    capital_denominator_badge_text=(
                        format_capital_denominator_badge_text(
                            badge=denom_badge,
                            denominator_dollars=denom_dollars,
                            asof_date=asof_date,
                        )
                    ),
                )
            )
            continue
        run_denom, run_badge = resolve_live_capital_denominator_dollars(
            conn, asof_date=run_asof,
            at_trade_time_policy=live_policy,
        )
        run_util_pct = (
            (exposure / run_denom) * 100.0 if run_denom > 0 else None
        )
        run_heat_pct = (
            (heat / run_denom) * 100.0 if run_denom > 0 else None
        )
        run_open_count = _count_open_at_run(conn, started_ts=started_ts)
        if r_rate is not None and run_util_pct is not None:
            run_pressure = r_rate * (run_util_pct / 100.0)
        else:
            run_pressure = None
        trend_points.append(
            CapitalFrictionTrendPoint(
                pipeline_run_id=run_id,
                run_date=run_asof.isoformat(),
                risk_feasibility_blocked_rate=r_rate,
                risk_feasibility_blocked_rate_suppressed_text=r_suppr,
                current_capital_utilization_pct=run_util_pct,
                current_portfolio_heat_pct=run_heat_pct,
                concurrent_open_positions=run_open_count,
                capital_feasibility_pressure_index=run_pressure,
                capital_denominator_dollars=run_denom,
                capital_denominator_badge=run_badge,
                capital_denominator_badge_text=(
                    format_capital_denominator_badge_text(
                        badge=run_badge,
                        denominator_dollars=run_denom,
                        asof_date=run_asof,
                    )
                ),
            )
        )
    trend_suppressed = len(trend_points) < TREND_MIN_RUNS
    trend_suppressed_text = (
        f"[capital_friction_trend: n too low "
        f"(current: {len(trend_points)}, need: ≥{TREND_MIN_RUNS})]"
        if trend_suppressed else None
    )

    return CapitalFrictionResult(
        asof_date=asof_date.isoformat(),
        current_capital_utilization_pct=util_pct,
        current_portfolio_heat_pct=heat_pct,
        concurrent_open_positions=open_count,
        capital_cycle_time_days=cycle_days,
        latest_run_id=latest_run_id,
        risk_feasibility_blocked_rate=blocked_rate,
        risk_feasibility_blocked_rate_suppressed_text=blocked_suppr,
        capital_feasibility_pressure_index=pressure,
        capital_denominator_dollars=denom_dollars,
        capital_denominator_badge=denom_badge,
        capital_denominator_badge_text=format_capital_denominator_badge_text(
            badge=denom_badge,
            denominator_dollars=denom_dollars,
            asof_date=asof_date,
        ),
        trend_runs=tuple(trend_points),
        trend_suppressed=trend_suppressed,
        trend_suppressed_text=trend_suppressed_text,
    )
