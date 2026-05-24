"""Pattern-group deduplication for backtest cohort.

Consecutive eval_runs per ticker (gap <= MAX_GAP_BUSINESS_DAYS) collapse to a single VCP pattern.
The pivot + initial_stop are taken from the FIRST eval_run in each group (per dispatch brief
OQ-1 default).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np


# Pattern grouping window per dispatch brief OQ-3 default: ~5 trading (business)
# days. Using strict less-than: gap < MAX_GAP_BUSINESS_DAYS keeps consecutive
# eval_runs together; >= forces a new pattern.
MAX_GAP_BUSINESS_DAYS = 5


@dataclass(frozen=True)
class CandidateRow:
    ticker: str
    eval_run_id: int
    data_asof_date: date
    v1_bucket: str
    pivot: float
    initial_stop: float
    close: float


@dataclass(frozen=True)
class Pattern:
    """A deduplicated VCP pattern grouping consecutive eval_runs per ticker.

    pivot + initial_stop come from the FIRST eval_run; eval_run_ids preserves all
    constituent rows for audit + provenance.
    """
    pattern_id: str
    ticker: str
    first_eval_run_id: int
    first_data_asof_date: date
    pivot: float
    initial_stop: float
    eval_run_ids: tuple[int, ...] = field(default_factory=tuple)
    asof_dates: tuple[date, ...] = field(default_factory=tuple)

    @property
    def n_runs(self) -> int:
        return len(self.eval_run_ids)


def group_consecutive_eval_runs(
    rows: list[CandidateRow],
    *,
    max_gap_business_days: int = MAX_GAP_BUSINESS_DAYS,
) -> list[Pattern]:
    """Collapse consecutive eval_runs per ticker into patterns.

    Sorting: per-ticker by data_asof_date ascending; a new pattern starts when
    consecutive rows are separated by more than max_gap_days.

    pattern_id = f"{TICKER}-r{first_eval_run_id}".
    """
    if not rows:
        return []

    by_ticker: dict[str, list[CandidateRow]] = {}
    for r in rows:
        by_ticker.setdefault(r.ticker, []).append(r)

    patterns: list[Pattern] = []
    for ticker in sorted(by_ticker.keys()):
        ticker_rows = sorted(
            by_ticker[ticker],
            key=lambda r: (r.data_asof_date, r.eval_run_id),
        )
        cluster: list[CandidateRow] = []

        def _emit_cluster(c: list[CandidateRow]) -> None:
            first = c[0]
            patterns.append(
                Pattern(
                    pattern_id=f"{first.ticker}-r{first.eval_run_id}",
                    ticker=first.ticker,
                    first_eval_run_id=first.eval_run_id,
                    first_data_asof_date=first.data_asof_date,
                    pivot=first.pivot,
                    initial_stop=first.initial_stop,
                    eval_run_ids=tuple(r.eval_run_id for r in c),
                    asof_dates=tuple(r.data_asof_date for r in c),
                )
            )

        for row in ticker_rows:
            if not cluster:
                cluster.append(row)
                continue
            prev = cluster[-1]
            # Business-day gap: np.busday_count(start, end) returns business days
            # between start (inclusive) and end (exclusive); 0 = same day.
            bd_gap = int(
                np.busday_count(prev.data_asof_date, row.data_asof_date)
            )
            if bd_gap < max_gap_business_days:
                cluster.append(row)
            else:
                _emit_cluster(cluster)
                cluster = [row]
        if cluster:
            _emit_cluster(cluster)

    return patterns
