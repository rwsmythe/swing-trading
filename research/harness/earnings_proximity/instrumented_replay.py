"""Per-criterion rejection logging on top of the standard replay loop.

The candidate-sparsity diagnostic needs to know **which criterion blocked
A+ classification** for every (ticker, date) pair the harness evaluates,
not just the rate of A+ outcomes. ``swing.evaluation.evaluator.evaluate_one``
already attaches every criterion's per-pass/fail result to the returned
:class:`Candidate` (``Candidate.criteria``); this module wraps the
standard replay loop and emits one :class:`EvaluationRecord` per evaluated
(ticker, date) pair, exposing those results plus a ``binding_constraint``
field naming the first criterion that blocked A+.

Phase isolation (CLAUDE.md)
---------------------------
Read-only consumption of ``swing.evaluation`` and ``swing.config``. No
production-code mutation. The wrapper duplicates a minimal amount of
:func:`research.harness.earnings_proximity.replay.replay` to keep the
record-emission logic adjacent to the per-criterion observation, rather
than threading a callback through the standard signature.
"""
from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from research.harness.earnings_proximity.replay import (
    _MIN_BARS_FOR_EVALUATION,
    AplusSignal,
    _next_earnings_after,
    _return_12w,
    _slice_up_to,
)
from swing.config import Config
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria._base import Result  # noqa: F401 — exported for type-hint only
from swing.evaluation.evaluator import evaluate_one

APLUS_KEY = "<aplus>"


@dataclass(frozen=True)
class EvaluationRecord:
    """One per (ticker, date) the evaluator saw, regardless of bucket.

    ``criterion_results`` is a tuple of ``(criterion_name, result)`` pairs
    in production-evaluator emission order: trend-template criteria first,
    then VCP, then risk. ``binding_constraint`` is None for A+; otherwise
    it is the first non-pass criterion (where 'fail' or 'na' both count
    as non-pass), honoring trend-template ``allowed_miss_names``.

    Aplus-only fields (``entry_target``, ``initial_stop``,
    ``next_earnings_date``, ``absent_earnings_data``) are populated for
    A+ records and ``None`` otherwise. Callers that need an
    :class:`AplusSignal` (the same shape produced by the standard replay)
    can convert via :func:`aplus_signals_from`.
    """

    ticker: str
    date: date
    bucket: str
    criterion_results: tuple[tuple[str, str], ...]
    binding_constraint: str | None
    entry_target: float | None
    initial_stop: float | None
    next_earnings_date: date | None
    absent_earnings_data: bool | None


def _binding_constraint(
    criteria: tuple,
    *,
    bucket: str,
    allowed_miss_names: frozenset[str],
) -> str | None:
    """First non-pass criterion (in evaluation order) that blocked A+.

    A+ classification is only blocked if some criterion failed AND that
    criterion is NOT in trend_template's ``allowed_miss_names``. So we
    walk the criteria once, skipping allowed misses, and return the
    first remaining non-pass. Returns ``None`` when no such criterion
    exists (i.e., bucket is genuinely A+).
    """
    if bucket == "aplus":
        return None
    for c in criteria:
        if c.result == "pass":
            continue
        if c.layer == "trend_template" and c.criterion_name in allowed_miss_names:
            continue
        return c.criterion_name
    return None


def instrumented_replay(
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
) -> Iterator[EvaluationRecord]:
    """Iterate trading days; yield one record per evaluated (ticker, date).

    Mirrors :func:`research.harness.earnings_proximity.replay.replay` but
    emits a record for every evaluator call (not just A+). Records carry
    per-criterion results so the diagnostic can aggregate which criterion
    is the binding constraint across the run.
    """
    allowed = frozenset(cfg.trend_template.allowed_miss_names)
    for day in trading_days:
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

            criterion_results = tuple(
                (c.criterion_name, c.result) for c in candidate.criteria
            )
            binding = _binding_constraint(
                candidate.criteria, bucket=candidate.bucket, allowed_miss_names=allowed
            )

            if candidate.bucket == "aplus":
                earnings_list = earnings.get(t, [])
                if earnings_list:
                    next_earn = _next_earnings_after(earnings_list, day)
                    absent = False
                else:
                    next_earn = None
                    absent = True
                yield EvaluationRecord(
                    ticker=t,
                    date=day,
                    bucket="aplus",
                    criterion_results=criterion_results,
                    binding_constraint=binding,
                    entry_target=float(candidate.pivot),
                    initial_stop=float(candidate.initial_stop),
                    next_earnings_date=next_earn,
                    absent_earnings_data=absent,
                )
            else:
                yield EvaluationRecord(
                    ticker=t,
                    date=day,
                    bucket=candidate.bucket,
                    criterion_results=criterion_results,
                    binding_constraint=binding,
                    entry_target=None,
                    initial_stop=None,
                    next_earnings_date=None,
                    absent_earnings_data=None,
                )


def aplus_signals_from(records: Iterable[EvaluationRecord]) -> list[AplusSignal]:
    """Convert A+ records to :class:`AplusSignal` shape (parity with replay())."""
    out: list[AplusSignal] = []
    for r in records:
        if r.bucket != "aplus":
            continue
        # Aplus rows always carry these fields; the type guard is for type-checkers.
        assert r.entry_target is not None
        assert r.initial_stop is not None
        assert r.absent_earnings_data is not None
        out.append(
            AplusSignal(
                ticker=r.ticker,
                date=r.date,
                entry_target=r.entry_target,
                initial_stop=r.initial_stop,
                next_earnings_date=r.next_earnings_date,
                absent_earnings_data=r.absent_earnings_data,
            )
        )
    return out


def aggregate_binding_constraints(records: Iterable[EvaluationRecord]) -> Counter[str]:
    """Sum binding_constraint occurrences across records.

    A+ records contribute under :data:`APLUS_KEY` so the totals are auditable
    (sum of all values equals number of records).
    """
    out: Counter[str] = Counter()
    for r in records:
        if r.binding_constraint is None:
            out[APLUS_KEY] += 1
        else:
            out[r.binding_constraint] += 1
    return out


def write_records_csv(records: Iterable[EvaluationRecord], path: Path) -> None:
    """Write per-(ticker, date) records to CSV with criterion columns expanded.

    Schema: ``ticker,date,bucket,binding_constraint,<criterion-1>,<criterion-2>,...``
    Each criterion column carries the per-record result string
    (``pass`` / ``fail`` / ``na``); empty if the record's evaluator produced
    no result for that criterion (defensive — does not happen in practice).

    The criterion column set is the union across all input records, sorted
    by first-appearance order (which matches production evaluation order
    for any single record, since evaluator emits criteria in fixed order).
    """
    records = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, None] = {}
    for r in records:
        for name, _ in r.criterion_results:
            if name not in seen:
                seen[name] = None
    criterion_cols = list(seen.keys())
    fieldnames = ["ticker", "date", "bucket", "binding_constraint", *criterion_cols]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fieldnames)
        for r in records:
            row_results = dict(r.criterion_results)
            row = [
                r.ticker,
                r.date.isoformat(),
                r.bucket,
                r.binding_constraint or "",
            ]
            for col in criterion_cols:
                row.append(row_results.get(col, ""))
            writer.writerow(row)
