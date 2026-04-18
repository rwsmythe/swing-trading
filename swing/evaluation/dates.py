"""Market-session dates: data_asof_date vs action_session_date."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

_NYSE = xcals.get_calendar("XNYS")


def data_asof_from_ohlcv_max(df: pd.DataFrame) -> date:
    """Most recent bar date in an OHLCV DataFrame (indexed by date)."""
    idx_max = df.index.max()
    if isinstance(idx_max, pd.Timestamp):
        return idx_max.date()
    return idx_max  # type: ignore[return-value]


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
