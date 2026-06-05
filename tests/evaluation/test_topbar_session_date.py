# tests/evaluation/test_topbar_session_date.py
from datetime import datetime

from swing.evaluation.dates import (
    PageKind,
    action_session_for_run,
    last_completed_session,
    topbar_session_date,
)


def test_forward_planning_uses_action_session():
    now = datetime(2026, 6, 4, 12, 0)  # post-close ET so the families diverge
    assert topbar_session_date(PageKind.FORWARD_PLANNING, now) == \
        action_session_for_run(now)


def test_history_analysis_uses_last_completed_session():
    now = datetime(2026, 6, 4, 12, 0)
    assert topbar_session_date(PageKind.HISTORY_ANALYSIS, now) == \
        last_completed_session(now)
