"""Earnings-proximity variant applicator.

Per the study design, each variant filters A+ signals whose next earnings
date is "within N trading days" of the signal date.

Boundary convention (fixed here)
--------------------------------
A signal is EXCLUDED from variant ``X`` iff the trading-day gap between
``signal.date`` (exclusive) and ``next_earnings_date`` (inclusive) is
STRICTLY LESS THAN ``X``:

- ``X = 0`` (baseline): nothing is excluded.
- Signal on Mon and earnings on Fri = 4 NYSE sessions out → excluded at
  ``X = 5`` or higher, KEPT at ``X = 4`` (the boundary is strict-less-than,
  so gap ``4 < 4`` is False and the signal is kept).

Absent-data rule (from the method record)
-----------------------------------------
Signals flagged with ``absent_earnings_data=True`` are NOT excluded at
any ``X``. The method record mandates this: absent data → do NOT exclude,
flag for review downstream.

Signals with ``next_earnings_date is None`` and ``absent_earnings_data=False``
(i.e., the earnings source returned non-empty history but no future date)
are kept — there's nothing forward to exclude against.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.earnings_proximity.replay import AplusSignal


def _sessions_between_exclusive_inclusive(
    start_exclusive: date,
    end_inclusive: date,
    trading_calendar,
) -> int:
    """Count NYSE sessions in ``(start_exclusive, end_inclusive]``.

    Returns 0 if ``end_inclusive <= start_exclusive``.
    """
    if end_inclusive <= start_exclusive:
        return 0
    # `sessions_in_range` is inclusive on both ends; shift start up by 1 day.
    start_ts = pd.Timestamp(start_exclusive) + pd.Timedelta(days=1)
    end_ts = pd.Timestamp(end_inclusive)
    sessions = trading_calendar.sessions_in_range(start_ts, end_ts)
    return len(sessions)


def apply_variant(
    signals: list[AplusSignal],
    blackout_trading_days: int,
    trading_calendar,
) -> list[AplusSignal]:
    """Filter ``signals`` per the variant rule.

    ``trading_calendar`` is an ``exchange_calendars.ExchangeCalendar`` (typically
    ``xcals.get_calendar("XNYS")``).
    """
    if blackout_trading_days <= 0:
        return list(signals)

    out: list[AplusSignal] = []
    for s in signals:
        if s.absent_earnings_data:
            # Absent-data rule: never exclude, flag downstream.
            out.append(s)
            continue
        if s.next_earnings_date is None or s.next_earnings_date <= s.date:
            # No upcoming earnings within scope (None or already past / same
            # day) — nothing to exclude against. Replay's _next_earnings_after
            # enforces strictly-after, so <= should be rare but is safe.
            out.append(s)
            continue
        gap = _sessions_between_exclusive_inclusive(
            s.date, s.next_earnings_date, trading_calendar
        )
        if gap < blackout_trading_days:
            continue  # excluded
        out.append(s)
    return out
