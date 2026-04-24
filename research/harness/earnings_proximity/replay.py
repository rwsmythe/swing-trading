"""Replay driver for the earnings-proximity study.

Iterates over trading days in a window and, for each day, evaluates every
ticker in the universe via :func:`swing.evaluation.evaluator.evaluate_one`.
A+ buckets yield :class:`AplusSignal` objects carrying entry/stop/next-earnings
metadata for downstream simulation and variant filtering.

Phase isolation (CLAUDE.md)
---------------------------
This module imports READ-ONLY from ``swing.evaluation.*``, ``swing.config``,
and ``swing.data.models`` (for the ``Candidate`` type returned by evaluator).
It MUST NOT import the DB-writing services under ``swing.trades.entry/.exit
/.stop_adjust`` or any repository layer under ``swing.data.repos``. The
regression guard is ``test_replay_module_imports_no_db_writing_services``.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from swing.config import (
    RS,
    VCP,
    Account,
    Config,
    ETFExclusion,
    ExportConfig,
    FocusRanking,
    NearTriggerConfig,
    Paths,
    PipelineConfig,
    PositionLimits,
    Risk,
    SizingConfig,
    StopAdvisoryConfig,
    TrendTemplate,
)
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

# Trend-template requires 200 bars for SMA-200; gate here to match.
_MIN_BARS_FOR_EVALUATION = 200

# 12 trading weeks (horizon_weeks * 5) — the production pipeline uses this
# to compute the 12-week-return numerator fed into RS. See swing/cli.py
# and swing/pipeline/runner.py for the authoritative formula.
_RETURN_12W_HORIZON_DAYS = 60


@dataclass(frozen=True)
class AplusSignal:
    """A single A+ classification emitted by the replay driver.

    ``next_earnings_date`` is the earliest scheduled earnings date STRICTLY
    AFTER ``date`` (same-day releases don't count as "next"). When the
    earnings source returned an empty list, ``absent_earnings_data`` is
    True — the method record mandates such signals are NOT auto-excluded
    by variant filters, only flagged for review.
    """

    ticker: str
    date: date
    entry_target: float
    initial_stop: float
    next_earnings_date: date | None
    absent_earnings_data: bool


def build_harness_config(
    *,
    rs_universe_path: Path | None = None,
    data_dir: Path | None = None,
) -> Config:
    """Construct a Config matching the operator's ``swing.config.toml`` values.

    The harness reuses the production evaluation parameters (TT thresholds,
    VCP cutoffs, RS rank bar) so replay classifications are faithful to the
    live pipeline. Account/paths fields are stubbed — evaluate_one does not
    read them, but Config construction requires them.
    """
    placeholder = Path(rs_universe_path or "")
    data_dir_path = Path(data_dir or "")
    paths = Paths(
        db_path=placeholder,
        data_dir=data_dir_path,
        logs_dir=data_dir_path,
        charts_dir=data_dir_path,
        backups_dir=data_dir_path,
        prices_cache_dir=data_dir_path,
        finviz_inbox_dir=data_dir_path,
        exports_dir=data_dir_path,
        rs_universe_path=placeholder,
    )
    return Config(
        paths=paths,
        account=Account(
            starting_equity=100_000.0,
            starting_date="2024-01-01",
            risk_equity_floor=0.0,
        ),
        position_limits=PositionLimits(soft_warn_open=4, hard_cap_open=6),
        risk=Risk(max_risk_pct=0.005),
        vcp=VCP(
            prior_trend_min_pct=25.0,
            adr_min_pct=4.0,
            pullback_max_pct=25.0,
            proximity_max_pct=5.0,
            tightness_days_required=2,
            tightness_range_factor=0.67,
            orderliness_max_bar_ratio=3.0,
            orderliness_max_range_cv=0.60,
        ),
        trend_template=TrendTemplate(
            min_passes=7,
            allowed_miss_names=("TT8_rs_rank",),
            rising_ma_period_days=21,
            high_52w_margin_pct=25.0,
            low_52w_min_pct=30.0,
        ),
        rs=RS(
            horizon_weeks=12,
            benchmark_ticker="SPY",
            rs_rank_min_pass=70,
            fallback_extreme_pct=20.0,
        ),
        etf_exclusion=ETFExclusion(exclude_etfs=True, manual_block=(), manual_allow=()),
        focus_ranking=FocusRanking(closeness_to_pivot=0.5, adr=0.25, prior_trend=0.25),
        near_trigger=NearTriggerConfig(),
        stop_advisory=StopAdvisoryConfig(),
        sizing=SizingConfig(),
        pipeline=PipelineConfig(),
        export=ExportConfig(),
    )


def _slice_up_to(df: pd.DataFrame, day: date) -> pd.DataFrame:
    """Return bars with index date <= ``day``. Preserves DatetimeIndex shape."""
    cutoff = pd.Timestamp(day) + pd.Timedelta(days=1)  # exclusive upper bound
    return df.loc[df.index < cutoff]


def _return_12w(closes: pd.Series, horizon_days: int = _RETURN_12W_HORIZON_DAYS) -> float | None:
    """Return the horizon-day return from the end of the series, or None.

    Mirrors ``swing/cli.py`` line 125: ``closes.iloc[-1] / closes.iloc[-bars-1] - 1``
    with ``bars = horizon_weeks * 5``. Requires > horizon bars.
    """
    if len(closes) <= horizon_days:
        return None
    start = float(closes.iloc[-horizon_days - 1])
    end = float(closes.iloc[-1])
    if start <= 0:
        return None
    return (end / start) - 1.0


def _next_earnings_after(earnings_dates: list[date], signal_date: date) -> date | None:
    """First date in ``earnings_dates`` strictly after ``signal_date``, else None."""
    for d in earnings_dates:
        if d > signal_date:
            return d
    return None


def replay(
    *,
    universe_tickers: tuple[str, ...],
    trading_days: list[date],
    ohlcv: dict[str, pd.DataFrame],
    earnings: dict[str, list[date]],
    cfg: Config,
    universe_version: str = "harness",
    universe_hash: str = "",
    benchmark_ticker: str = "SPY",
    current_equity: float = 100_000.0,
    min_bars: int = _MIN_BARS_FOR_EVALUATION,
) -> Iterator[AplusSignal]:
    """Iterate trading days; yield A+ signals.

    For each ``day`` in ``trading_days``:
      1. Slice each ticker's OHLCV to bars <= ``day``.
      2. Compute each universe-ticker's 12-week trailing return (skip if <60 bars).
      3. Compute SPY's 12-week return (fallback 0.0 if missing).
      4. For each ticker with at least ``min_bars`` of history:
         - Build CandidateContext, call evaluate_one.
         - If bucket == 'aplus': yield AplusSignal with pivot, initial_stop,
           and next-earnings lookup.
    """
    for day in trading_days:
        # Per-day universe returns (pure function of that day's slice).
        returns_12w: dict[str, float] = {}
        for t in universe_tickers:
            df = ohlcv.get(t)
            if df is None or df.empty:
                continue
            sliced = _slice_up_to(df, day)
            ret = _return_12w(sliced["Close"])
            if ret is not None:
                returns_12w[t] = ret

        spy_return = 0.0
        spy_df = ohlcv.get(benchmark_ticker)
        if spy_df is not None and not spy_df.empty:
            spy_sliced = _slice_up_to(spy_df, day)
            spy_ret = _return_12w(spy_sliced["Close"])
            if spy_ret is not None:
                spy_return = spy_ret

        batch = BatchContext(
            returns_12w_by_ticker=returns_12w,
            universe_tickers=universe_tickers,
            universe_version=universe_version,
            universe_hash=universe_hash,
            spy_return_12w=spy_return,
        )
        market = MarketContext()

        for t in universe_tickers:
            df = ohlcv.get(t)
            if df is None or df.empty:
                continue
            sliced = _slice_up_to(df, day)
            if len(sliced) < min_bars:
                continue

            ctx = CandidateContext(
                ticker=t,
                ohlcv=sliced,
                config=cfg,
                batch=batch,
                market=market,
                current_equity=current_equity,
            )
            candidate = evaluate_one(ctx)
            if candidate.bucket != "aplus":
                continue

            earnings_list = earnings.get(t, [])
            if earnings_list:
                next_earn = _next_earnings_after(earnings_list, day)
                absent = False
            else:
                next_earn = None
                absent = True

            yield AplusSignal(
                ticker=t,
                date=day,
                entry_target=float(candidate.pivot),
                initial_stop=float(candidate.initial_stop),
                next_earnings_date=next_earn,
                absent_earnings_data=absent,
            )
