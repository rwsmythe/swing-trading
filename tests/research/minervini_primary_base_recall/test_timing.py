from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_primary_base_recall import timing


def _frame(start: date, periods: int):
    idx = pd.bdate_range(start=start, periods=periods)
    c = pd.Series([10.0 + i * 0.01 for i in range(periods)], index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )


def test_day_window_is_entry_minus_back_to_entry_plus_fwd():
    bars = _frame(date(2010, 1, 4), 300)
    entry = bars.index[200].date()
    sessions = timing.sweep_sessions(bars, entry, "day", window_back=60, window_fwd=5)
    # RIGHT-PATH: positions [140, 205] inclusive -> 66 sessions; first == entry-60bd.
    assert sessions[0] == bars.index[140].date()
    assert sessions[-1] == bars.index[205].date()
    assert len(sessions) == 66


def test_month_window_spans_full_documented_month_plus_slack():
    # A frame straddling Sept 1997; month-precision anchor parses to date(1997,9,1).
    bars = _frame(date(1997, 1, 2), 400)
    anchor = date(1997, 9, 1)
    sept = [d for d in bars.index if d.year == 1997 and d.month == 9]
    first_sept_pos = list(bars.index).index(sept[0])
    last_sept_pos = list(bars.index).index(sept[-1])
    sessions = timing.sweep_sessions(bars, anchor, "month", window_back=60, window_fwd=5)
    # RIGHT-PATH (full month): start = first_trading_day_of_month - 60bd ; end = last + 5bd.
    assert sessions[0] == bars.index[max(0, first_sept_pos - 60)].date()
    assert sessions[-1] == bars.index[last_sept_pos + 5].date()
    # WRONG-PATH (parsed-first-of-month [anchor-60, anchor+5]) would END only 5bd after the FIRST
    # trading day of September, never reaching late-September. Assert it is strictly later.
    naive_end_pos = first_sept_pos + 5  # the wrong-path tail
    assert (last_sept_pos + 5) > naive_end_pos
    assert sessions[-1] != bars.index[naive_end_pos].date()


def test_single_session_only_for_day_precision():
    bars = _frame(date(2010, 1, 4), 300)
    entry = bars.index[200].date()
    # day precision -> exactly the entry session.
    assert timing.single_session(bars, entry, "day") == [entry]
    # month precision -> EMPTY (sweep-only; R1.M3).
    assert timing.single_session(bars, date(2010, 1, 1), "month") == []


def test_no_lookahead_every_session_is_le_itself():
    # screen_at must only see bars <= the session; assert the sweep sessions are all in-frame.
    bars = _frame(date(2010, 1, 4), 120)
    entry = bars.index[100].date()
    sessions = timing.sweep_sessions(bars, entry, "day", window_back=60, window_fwd=5)
    assert all(s <= bars.index[-1].date() for s in sessions)
    assert sessions[-1] == bars.index[min(105, len(bars) - 1)].date()
