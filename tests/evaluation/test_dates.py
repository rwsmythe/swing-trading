"""Tests for swing.evaluation.dates."""
from __future__ import annotations

from datetime import date, datetime

from swing.evaluation.dates import (
    action_session_for_run,
    data_asof_from_ohlcv_max,
    sessions_behind,
)


def test_action_session_weeknight():
    # Tuesday 21:49 HST == Wednesday 03:49 ET (after Tuesday's close). Action session: Wednesday.
    now_hst = datetime(2026, 4, 14, 21, 49)  # Tuesday
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-15"


def test_action_session_friday_night_returns_monday():
    # Friday 21:49 HST — next trading day is Monday.
    now_hst = datetime(2026, 4, 17, 21, 49)  # Friday
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-20"  # Monday


def test_action_session_during_market_hours():
    # Wednesday 06:30 HST == Wednesday 12:30 ET, market open. Action = Wednesday.
    now_hst = datetime(2026, 4, 15, 6, 30)
    result = action_session_for_run(now_hst, tz="Pacific/Honolulu")
    assert result.isoformat() == "2026-04-15"


def test_data_asof_from_ohlcv_max(ohlcv_factory):
    df = ohlcv_factory([10.0, 10.5, 11.0], start_date="2026-04-15")
    result = data_asof_from_ohlcv_max(df)
    # bdate_range starts 2026-04-15 (Wed), next is Thu 4/16, Fri 4/17
    assert result.isoformat() == "2026-04-17"


def test_sessions_behind_zero_when_candidate_at_or_after_reference():
    # candidate == reference -> 0; candidate after reference -> 0 (clamped).
    assert sessions_behind(date(2026, 6, 17), date(2026, 6, 17)) == 0
    assert sessions_behind(date(2026, 6, 17), date(2026, 6, 18)) == 0


def test_sessions_behind_one_immediate_predecessor():
    # Wed 06-17 immediate prior NYSE session is Tue 06-16 -> 1 behind.
    assert sessions_behind(date(2026, 6, 17), date(2026, 6, 16)) == 1


def test_sessions_behind_two_sessions_apart():
    # Thu 06-18 -> prev Wed 06-17 -> prev Tue 06-16 == 2 behind.
    assert sessions_behind(date(2026, 6, 18), date(2026, 6, 16)) == 2


def test_sessions_behind_skips_weekend():
    # Mon 06-15's immediate prior NYSE session is Fri 06-12 (Sat/Sun skipped).
    # A calendar-day (ref-cand).days impl would give 3 -> FAIL; sessions == 1.
    assert sessions_behind(date(2026, 6, 15), date(2026, 6, 12)) == 1


def test_sessions_behind_skips_holiday():
    # July 4 2026 (Sat) observed Fri 07-03 -> NYSE closed; Mon 07-06's immediate
    # prior session is Thu 07-02. 4 calendar days but ONE session behind.
    # A calendar-day impl gives 4 -> FAIL; the NYSE-walk impl gives 1.
    assert sessions_behind(date(2026, 7, 6), date(2026, 7, 2)) == 1
