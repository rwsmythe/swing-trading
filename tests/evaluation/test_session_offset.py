"""session_offset -- the additive SIGNED NYSE session-walk helper (Arc 21-A)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from swing.evaluation.dates import session_offset, sessions_behind


def test_zero_returns_the_reference():
    assert session_offset(date(2026, 7, 20), 0) == date(2026, 7, 20)


def test_ftre_horizon_at_the_ruled_30_session_window():
    """RD gate ruling: the horizon is 30 sessions (parity with the shadow
    entry window), so FTRE's fire on 2026-07-20 expires 2026-08-31 -- NOT the
    2026-08-17 he had recorded from the untraced ~20. A calendar walk gives
    2026-08-19."""
    assert session_offset(date(2026, 7, 20), 30) == date(2026, 8, 31)
    assert session_offset(date(2026, 7, 20), 20) == date(2026, 8, 17)   # superseded


def test_skips_the_july_3_2026_holiday():
    """2026-07-01 + 30 sessions == 2026-08-13: the observed July-4 holiday and
    the intervening weekends are excluded (a 30-CALENDAR-day walk gives
    2026-07-31)."""
    assert session_offset(date(2026, 7, 1), 30) == date(2026, 8, 13)


def test_round_trips_with_sessions_behind():
    for anchor, n in ((date(2026, 7, 20), 30), (date(2026, 7, 1), 30),
                      (date(2026, 6, 25), 30), (date(2026, 7, 27), 30)):
        assert sessions_behind(session_offset(anchor, n), anchor) == n


def test_negative_n_walks_backward():
    """The derivation-session direction. 2026-07-20 is a Monday, so the prior
    session is the preceding Friday; and the July-3 holiday is skipped."""
    assert session_offset(date(2026, 7, 20), -1) == date(2026, 7, 17)
    assert session_offset(date(2026, 7, 6), -1) == date(2026, 7, 2)


def test_signed_offsets_are_inverses():
    for anchor in (date(2026, 7, 20), date(2026, 7, 1), date(2026, 7, 6)):
        assert session_offset(session_offset(anchor, -3), 3) == anchor


def test_rejects_a_bool_n():
    with pytest.raises(ValueError):
        session_offset(date(2026, 7, 20), True)


@pytest.mark.parametrize("now,expected_action", [
    (datetime(2026, 7, 20, 9, 0), date(2026, 7, 20)),    # session day, pre-close
    (datetime(2026, 7, 20, 17, 0), date(2026, 7, 21)),   # session day, post-close
    (datetime(2026, 7, 25, 12, 0), date(2026, 7, 27)),   # Saturday
    # 12:00 Pacific/Honolulu == 18:00 ET, i.e. POST-close on Thu 2026-07-02;
    # 07-03 is the observed Independence Day holiday, so the next session is
    # Monday 07-06. (The plan's illustrative 07-02 assumed a pre-close clock;
    # corrected here per its own instruction -- the INVARIANT below is what is
    # load-bearing.)
    (datetime(2026, 7, 2, 12, 0), date(2026, 7, 6)),
])
def test_prev_session_of_the_action_anchor_equals_last_completed_session(
        now, expected_action):
    """THE INVARIANT the derivation relies on (Codex R3-1): for any clock,
    `session_offset(action_session_for_run(now), -1) == last_completed_session(now)`.
    That is what lets the beacon POST rebuild the ENTIRE render-time derivation
    context from the session anchor alone, consulting `now` for nothing that can
    change a latch's state.

    NOTE the times are Pacific/Honolulu (the helpers' default tz)."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    action = action_session_for_run(now)
    assert action == expected_action
    assert session_offset(action, -1) == last_completed_session(now)
