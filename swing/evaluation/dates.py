"""Market-session dates: data_asof_date vs action_session_date."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

_NYSE = xcals.get_calendar("XNYS")


class PageKind(Enum):
    """Topbar-date intent for a base-layout page."""
    FORWARD_PLANNING = "forward"   # what to do at the next session
    HISTORY_ANALYSIS = "backward"  # what happened through the last completed session


def topbar_session_date(page_kind: PageKind, now_local: datetime) -> date:
    """The single source of truth for a base-layout topbar date (L6/Issue #5).

    FORWARD_PLANNING -> action_session_for_run (the next session).
    HISTORY_ANALYSIS -> last_completed_session (the last closed session).
    Eliminates the naive date.today()/datetime.now().date() third family.
    """
    if page_kind is PageKind.FORWARD_PLANNING:
        return action_session_for_run(now_local)
    return last_completed_session(now_local)


def data_asof_from_ohlcv_max(df: pd.DataFrame) -> date:
    """Most recent bar date in an OHLCV DataFrame (indexed by date)."""
    idx_max = df.index.max()
    if isinstance(idx_max, pd.Timestamp):
        return idx_max.date()
    return idx_max  # type: ignore[return-value]


def sessions_behind(reference: date, candidate: date) -> int:
    """Count NYSE trading sessions `candidate` is behind `reference`.

    Pure, stdlib `date` in/out (the canonical session-arithmetic home owns
    `_NYSE`). Returns 0 when `candidate >= reference`; otherwise walks
    `_NYSE.previous_session` backward from `reference` counting steps until the
    walk reaches `candidate` (or first passes it). NO calendar-day fallback --
    a calendar-day count false-counts across weekends/holidays. The walk is
    bounded so a far-past `candidate` returns a large int rather than looping
    forever (e.g. a candidate before the calendar's first session).
    """
    if candidate >= reference:
        return 0
    cursor = pd.Timestamp(reference)
    target = pd.Timestamp(candidate)
    count = 0
    # Bound: NYSE has ~252 sessions/yr; 100k covers ~400yr, far past any real
    # gap, so a pathological candidate terminates instead of spinning.
    for _ in range(100_000):
        cursor = _NYSE.previous_session(cursor)
        count += 1
        if cursor <= target:
            return count
    return count


def last_completed_session(now_local: datetime, *, tz: str = "Pacific/Honolulu") -> date:
    """Most recent NYSE session whose close has already happened at `now_local`.

    Used when `as_of_date` is omitted — never serve a partial in-progress daily bar.
    """
    local = now_local.replace(tzinfo=ZoneInfo(tz))
    ny = local.astimezone(ZoneInfo("America/New_York"))
    today_date = ny.date()

    if _NYSE.is_session(pd.Timestamp(today_date)):
        close_ts = _NYSE.session_close(pd.Timestamp(today_date))
        ny_ts_utc = pd.Timestamp(ny).tz_convert("UTC")
        if ny_ts_utc >= close_ts:
            return today_date
        # Before close — today's bar is incomplete; use prior session
        prev_ts = _NYSE.previous_session(pd.Timestamp(today_date))
        return prev_ts.date()

    # Non-session day — last completed session is strictly before today
    return _NYSE.date_to_session(pd.Timestamp(today_date), direction="previous").date()


def action_session_for_run(now_local: datetime, *, tz: str = "Pacific/Honolulu") -> date:
    """The next NYSE trading session at or after `now_local`.

    Converts local time to US/Eastern, then asks the NYSE calendar for the next open
    session. If `now_local` falls on a trading day before the close, returns that day.
    """
    local = now_local.replace(tzinfo=ZoneInfo(tz))
    ny = local.astimezone(ZoneInfo("America/New_York"))
    today_date = ny.date()

    if _NYSE.is_session(pd.Timestamp(today_date)):
        close_ts = _NYSE.session_close(pd.Timestamp(today_date))
        ny_ts_utc = pd.Timestamp(ny).tz_convert("UTC")
        if ny_ts_utc <= close_ts:
            return today_date
        # Past close on a session day — action session is the next session
        next_ts = _NYSE.next_session(pd.Timestamp(today_date))
        return next_ts.date()

    # Non-session (weekend/holiday) — find next session at or after today
    next_ts = _NYSE.date_to_session(pd.Timestamp(today_date), direction="next")
    return next_ts.date()
