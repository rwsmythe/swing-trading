"""Tests for swing.evaluation.dates."""
from __future__ import annotations

from datetime import datetime

from swing.evaluation.dates import (
    action_session_for_run,
    data_asof_from_ohlcv_max,
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
